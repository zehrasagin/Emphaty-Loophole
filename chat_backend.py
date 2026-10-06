"""Local interactive conversations and one serialized MLX inference worker."""
import copy
import gc
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from run_pilot import ROOT, model_ready, read_source, run_case
from dataset import digest

CHAT_ROOT = ROOT / 'results' / 'chat_sessions'


def new_session(case, kind, mode='exploratory'):
    if mode not in ('exploratory', 'condition_preview'):
        raise ValueError(f'Unknown chat mode: {mode}')
    return {
        'session_id': datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'purpose': 'interactive_manual_simulation' if mode == 'exploratory' else 'interactive_condition_preview',
        'mode': mode,
        'scenario': copy.deepcopy(case), 'model_kind': kind, 'model': read_source(kind),
        'emotion_annotation': 'unlabelled_interactive' if mode == 'exploratory' else case['emotion'], 'turns': [],
    }


def history_for(session, user_text):
    if session.get('mode') == 'condition_preview':
        if user_text != session['scenario']['messages'][1]['content']:
            raise ValueError('Condition preview uses the unedited generated request')
        if any(t['result'].get('final_answer') for t in session['turns']):
            raise ValueError('Start a new conversation to preview another condition')
        return copy.deepcopy(session['scenario']['messages'])
    messages = [copy.deepcopy(session['scenario']['messages'][0])]
    for turn in session['turns']:
        r = turn['result']
        # An incomplete or unparsed response is never silently used as a final answer.
        if r['status'] == 'completed' and r.get('final_answer'):
            messages.extend([{'role': 'user', 'content': turn['user']},
                             {'role': 'assistant', 'content': r['final_answer']}])
    messages.append({'role': 'user', 'content': user_text})
    return messages


def transcript(session):
    case = session['scenario']
    lines = ['# Chat simulation', '', f"Scenario: {case['scenario_id']}",
             f"Model: {session['model']['model_id']}",
             f"Policy condition: {case['policy_type']}",
             f"Mode: {session.get('mode', 'exploratory')}; stored separately from benchmarks.", '']
    for index, turn in enumerate(session['turns'], 1):
        r = turn['result']
        lines += [f'## Turn {index}', '', '### Customer', '',
                  *['    ' + line for line in turn['user'].splitlines()], '',
                  f"Status: {r['status']} | Parse status: {r.get('parse_status', 'unavailable')}", '',
                  '### Assistant', '',
                  *['    ' + line for line in (r.get('final_answer') or 'No complete final answer available.').splitlines()], '']
        if r.get('reasoning_trace'):
            lines += ['### Observable reasoning trace', '',
                      *['    ' + line for line in r['reasoning_trace'].splitlines()], '']
        if r.get('error'):
            lines += ['Error: ' + r['error'], '']
    return '\n'.join(lines) + '\n'


def save_session(session, root=CHAT_ROOT):
    path = root / session['session_id']
    path.mkdir(parents=True, exist_ok=True)
    tmp = path / 'session.json.tmp'
    tmp.write_text(json.dumps(session, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path / 'session.json')
    (path / 'transcript.md').write_text(transcript(session))


class ChatEngine:
    """Keep all MLX operations on one worker and only one model in memory."""
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='local-llm')
        self.model = self.tokenizer = None
        self.loaded_key = None
        self.busy = threading.Lock()

    def submit(self, session, user_text):
        if not user_text.strip():
            raise ValueError('Please enter a message.')
        history_for(session, user_text)
        # Prevent a rerun or second browser tab from queuing hidden extra requests.
        if not self.busy.acquire(blocking=False):
            raise RuntimeError('The local model is answering another message. Please try again shortly.')
        try:
            future = self.executor.submit(self._respond, copy.deepcopy(session), user_text)
        except BaseException:
            self.busy.release()
            raise
        future.add_done_callback(lambda _: self.busy.release())
        return future

    def _respond(self, session, text):
        source = session['model']
        turn_dir = CHAT_ROOT / session['session_id'] / f"turn_{len(session['turns']) + 1:03d}"
        turn_dir.mkdir(parents=True, exist_ok=True)
        (turn_dir / 'request.json').write_text(json.dumps({'user': text, 'status': 'started'}, indent=2))
        save_session(session)
        try:
            import mlx.core as mx
            from mlx_lm import load
            key = (source['model_id'], source.get('revision'), source['local_path'])
            if key != self.loaded_key:
                self.model = self.tokenizer = None
                self.loaded_key = None
                gc.collect()
                mx.clear_cache()
                self.model, self.tokenizer = load(str(ROOT / source['local_path']))
                self.loaded_key = key
            settings = dict(source['generation_settings'])
            messages = history_for(session, text)
            case = {**session['scenario'], 'messages': messages,
                    'source_prompt_sha256': session['scenario'].get('prompt_sha256'),
                    'prompt_sha256': digest(messages),
                    'run_id': session['session_id'], 'trial_id': uuid.uuid4().hex,
                    'purpose': session['purpose'],
                    'source_emotion': session['scenario']['emotion'],
                    'emotion': 'unlabelled_interactive' if session.get('mode') == 'exploratory' else session['scenario']['emotion']}
            result = run_case(case, source, turn_dir, self.model, self.tokenizer, settings,
                              context_limit=8192)
        except Exception as exc:
            result = {'status': 'error', 'parse_status': 'model_load_error',
                      'final_answer': None, 'error': f'{type(exc).__name__}: {exc}'}
            (turn_dir / 'result.json').write_text(json.dumps(result, indent=2))
        session['turns'].append({'user': text, 'result': result, 'turn_directory': str(turn_dir)})
        save_session(session)
        return session
