import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from chat_backend import ChatEngine, history_for, new_session, save_session
from dataset import load_cases
from prompting import effective_messages
from trace_parser import parse_output
from result_io import result_filename

ROOT = Path(__file__).resolve().parents[1]


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.case = load_cases('retail')[0]

    def test_followup_preserves_policy_and_final_answer_only(self):
        session = new_session(self.case, 'reasoning')
        session['turns'] = [{'user': 'Refund please', 'result': {
            'status': 'completed', 'final_answer': 'Outside the return window.',
            'reasoning_trace': 'A private-to-this-output trace', 'raw_output': '<think>trace</think>answer'}}]
        messages = history_for(session, 'Please reconsider.')
        self.assertEqual(messages[0], self.case['messages'][0])
        self.assertEqual([x['role'] for x in messages], ['system', 'user', 'assistant', 'user'])
        self.assertEqual(messages[2]['content'], 'Outside the return window.')
        self.assertNotIn('trace', str(messages))

    def test_r1_adaptation_keeps_followups_without_mutating_original(self):
        messages = [self.case['messages'][0], self.case['messages'][1],
                    {'role': 'assistant', 'content': 'No refund.'}, {'role': 'user', 'content': 'Why?'}]
        original = copy.deepcopy(messages)
        adapted = effective_messages(messages, reasoning=True)
        self.assertEqual(messages, original)
        self.assertIn(messages[0]['content'], adapted[0]['content'])
        self.assertIn(messages[1]['content'], adapted[0]['content'])
        self.assertEqual(adapted[1:], messages[2:])

    def test_failed_turn_is_audited_but_excluded_from_context(self):
        session = new_session(self.case, 'standard')
        session['turns'] = [{'user': 'Failed request', 'result': {
            'status': 'incomplete', 'final_answer': None, 'raw_output': 'partial'}}]
        messages = history_for(session, 'Retry request')
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[-1]['content'], 'Retry request')
        with tempfile.TemporaryDirectory() as tmp:
            save_session(session, Path(tmp))
            saved = json.loads((Path(tmp) / session['session_id'] / 'session.json').read_text())
            self.assertEqual(saved['turns'][0]['user'], 'Failed request')

    def test_new_sessions_are_isolated(self):
        a, b = new_session(self.case, 'standard'), new_session(self.case, 'standard')
        a['scenario']['messages'][0]['content'] = 'Changed'
        a['turns'].append({'user': 'Test'})
        self.assertNotEqual(a['session_id'], b['session_id'])
        self.assertEqual(b['turns'], [])
        self.assertEqual(b['scenario'], self.case)

    def test_condition_preview_is_one_turn_and_keeps_generated_input(self):
        session = new_session(self.case, 'standard', mode='condition_preview')
        text = self.case['messages'][1]['content']
        self.assertEqual(history_for(session, text), self.case['messages'])
        with self.assertRaises(ValueError):
            history_for(session, 'Change the facts')
        session['turns'].append({'user': text, 'result': {'final_answer': 'No refund.', 'status': 'completed'}})
        with self.assertRaises(ValueError):
            history_for(session, text)
        self.assertNotEqual(session['purpose'], 'controlled_benchmark_pilot')

    def test_model_load_failure_and_retry_keep_timestamped_trial_records(self):
        session = new_session(self.case, 'standard', mode='condition_preview')
        text = self.case['messages'][1]['content']
        mx = SimpleNamespace(clear_cache=lambda: None)

        def fail_load(*args):
            raise RuntimeError('injected load failure')

        modules = {'mlx': SimpleNamespace(core=mx), 'mlx.core': mx,
                   'mlx_lm': SimpleNamespace(load=fail_load)}
        engine = ChatEngine()
        try:
            with tempfile.TemporaryDirectory() as tmp, \
                    patch('chat_backend.CHAT_ROOT', Path(tmp)), \
                    patch('result_io.ALL_TRIALS_PATH', Path(tmp) / 'all_trials.json'), \
                    patch.dict('sys.modules', modules):
                session = engine._respond(session, text)
                session = engine._respond(session, text)
                first, second = (t['result'] for t in session['turns'])
                self.assertNotEqual(first['trial_id'], second['trial_id'])
                for index, turn in enumerate(session['turns'], 1):
                    record = turn['result']
                    directory = Path(turn['turn_directory'])
                    self.assertEqual(record['status'], 'error')
                    self.assertEqual(record['parse_status'], 'model_load_error')
                    self.assertEqual(record['model_id'], session['model']['model_id'])
                    self.assertEqual(record['scenario_id'], self.case['scenario_id'])
                    self.assertEqual(record['turn_index'], index)
                    self.assertEqual(record['messages'], self.case['messages'])
                    self.assertEqual(record['timestamp_utc'], record['requested_at'])
                    self.assertGreaterEqual(datetime.fromisoformat(record['finished_at']),
                                            datetime.fromisoformat(record['started_at']))
                    request = json.loads((directory / 'request.json').read_text())
                    self.assertEqual(request['trial_id'], record['trial_id'])
                    self.assertEqual(request['requested_at'], record['requested_at'])
                    self.assertEqual(json.loads((directory / 'result.json').read_text()), record)
                    self.assertEqual(json.loads((directory / result_filename(record)).read_text()), record)
                saved = json.loads((Path(tmp) / session['session_id'] / 'session.json').read_text())
                self.assertEqual(saved, session)
                collection = json.loads((Path(tmp) / 'all_trials.json').read_text())
                self.assertEqual(collection['trial_count'], 2)
                self.assertEqual(collection['trials'], [first, second])
        finally:
            engine.executor.shutdown(wait=True)


class TraceTests(unittest.TestCase):
    def test_template_supplied_opener(self):
        r = parse_output('Consider the rule.\n</think>\nNo refund.', reasoning=True, prompt_opens_think=True)
        self.assertEqual(r['reasoning_trace'], 'Consider the rule.')
        self.assertEqual(r['final_answer'], 'No refund.')
        self.assertEqual(r['parse_status'], 'parsed')

    def test_truncated_trace_is_not_a_final_answer(self):
        r = parse_output('<think>Consider the rule.', reasoning=True, finished=False)
        self.assertEqual(r['parse_status'], 'truncated_trace')
        self.assertIsNone(r['final_answer'])
        self.assertFalse(r['trace_complete'])

    def test_malformed_and_missing_tags_are_flagged(self):
        for raw, expected in [('trace</think>No refund.', 'missing_open_tag'),
                              ('<think>x</think>y</think>', 'malformed_trace_tags')]:
            with self.subTest(raw=raw):
                r = parse_output(raw, reasoning=True)
                self.assertEqual(r['parse_status'], expected)
                self.assertEqual(r['raw_output'], raw)
                if expected == 'malformed_trace_tags':
                    self.assertIsNone(r['final_answer'])

    def test_missing_trace_retains_final_answer(self):
        for reasoning in (True, False):
            r = parse_output('No refund.', reasoning=reasoning)
            self.assertEqual(r['final_answer'], 'No refund.')
            self.assertFalse(r['trace_available'])
            self.assertEqual(r['parse_status'], 'missing_trace' if reasoning else 'plain_standard_response')

    def test_explicit_opener_missing_close_empty_and_malformed(self):
        for raw, status in [('<think>Rule</think>No refund.', 'parsed'),
                            ('<think>Rule', 'missing_close_tag'), ('', 'empty_output'),
                            ('  ', 'empty_output'), ('<think><think>x</think>y', 'malformed_trace_tags'),
                            ('<think>Rule</think>', 'missing_final')]:
            with self.subTest(raw=raw):
                r = parse_output(raw, reasoning=True)
                self.assertEqual(r['parse_status'], status)
                self.assertEqual(r['raw_output'], raw)

    def test_empty_trace_and_truncated_final(self):
        r = parse_output('<think></think>No refund.', reasoning=True)
        self.assertEqual(r['parse_status'], 'empty_trace')
        self.assertFalse(r['trace_available'])
        r = parse_output('<think>Policy</think>Partial answer', reasoning=True, finished=False)
        self.assertEqual(r['parse_status'], 'truncated_final')
        self.assertIsNone(r['final_answer'])


if __name__ == '__main__':
    unittest.main()
