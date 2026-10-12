"""UTC trial metadata and JSON exports; leave model output unchanged."""
import json
import platform
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


RESULT_SCHEMA_VERSION = '1.0'
ALL_TRIALS_PATH = Path(__file__).resolve().parent / 'results' / 'all_trials.json'


def read_trial_collection(path=None):
    path = path if path is not None else ALL_TRIALS_PATH
    if not path.exists():
        return {'collection_schema_version': '1.0', 'created_at': None,
                'updated_at': None, 'trial_count': 0, 'trials': []}
    collection = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(collection, dict) or collection.get('collection_schema_version') != '1.0'
            or not isinstance(collection.get('trials'), list)
            or collection.get('trial_count') != len(collection['trials'])
            or any(not isinstance(t, dict) or not t.get('trial_id') for t in collection['trials'])):
        raise ValueError(f'{path}: invalid trial collection; original file retained')
    return collection


def append_trial_record(record, path=None):
    """Append a finalized trial once, across UI sessions and runner processes."""
    # Local inference targets macOS. Keep POSIX locking out of imports so
    # model-free validation and dry runs also work on other platforms.
    import fcntl

    if not record.get('trial_id') or not record.get('finished_at'):
        raise ValueError('Only finalized records with a trial_id can enter the collection')
    path = path if path is not None else ALL_TRIALS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # The CLI and multiple Streamlit servers can finish at the same time.
    with path.with_suffix('.json.lock').open('a', encoding='utf-8') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        collection = read_trial_collection(path)
        for trial in collection['trials']:
            if trial['trial_id'] == record['trial_id']:
                if trial != record:
                    raise ValueError(f"Conflicting records for trial_id {record['trial_id']}; original retained")
                return
        now = utc_timestamp()
        collection['created_at'] = collection['created_at'] or now
        collection['updated_at'] = now
        collection['trials'].append(record)
        collection['trial_count'] = len(collection['trials'])
        temporary = path.with_suffix('.json.tmp')
        temporary.write_text(result_json(collection), encoding='utf-8')
        temporary.replace(path)


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def new_result_record(case, source, settings, run_id, *, started_at=None):
    started_at = started_at or utc_timestamp()
    return {
        **case,
        'result_schema_version': RESULT_SCHEMA_VERSION,
        'timestamp_utc': started_at,
        'started_at': started_at,
        'finished_at': None,
        'model': source,
        'model_family': source.get('model_family', 'qwen'),
        'model_type': source.get('model_type', 'standard'),
        'model_id': source['model_id'],
        'model_revision': source.get('revision'),
        'run_id': case.get('run_id', run_id),
        'trial_id': case.get('trial_id', uuid.uuid4().hex),
        'purpose': case.get('purpose', 'infrastructure_smoke_test'),
        'generation_settings': settings,
        'backend': 'mlx-lm',
        'platform': platform.platform(),
        'status': 'started',
        'raw_output': '',
        'reasoning_trace': None,
        'final_answer': None,
        'trace_available': False,
        'trace_complete': False,
        'parse_status': 'not_started',
        'finish_reason': 'not_started',
        'truncated': False,
    }


def result_filename(record):
    timestamp = record.get('timestamp_utc') or record.get('started_at')
    stamp = (datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
             .astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')) if timestamp else 'undated'
    trial_id = re.sub(r'[^a-zA-Z0-9_-]', '_', str(record.get('trial_id', 'unknown')))
    return f'result_{stamp}_{trial_id}.json'


def result_json(record):
    return json.dumps(record, ensure_ascii=False, indent=2) + '\n'


def save_result_record(record, run_dir):
    # Keep the conventional path for existing tools; write it atomically.
    payload = result_json(record)
    temporary = run_dir / 'result.json.tmp'
    temporary.write_text(payload, encoding='utf-8')
    temporary.replace(run_dir / 'result.json')
    if record.get('finished_at'):
        # One immutable final export per trial, including interrupted/error trials.
        with (run_dir / result_filename(record)).open('x', encoding='utf-8') as export:
            export.write(payload)
        append_trial_record(record)
