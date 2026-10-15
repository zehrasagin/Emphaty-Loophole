"""Run frozen single-turn conditions sequentially on selected local models."""
import argparse
import gc
import json
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dataset import VERSION, digest, expand_scenario, load_scenarios, reference_rows
from result_io import result_json, utc_timestamp
from run_pilot import ROOT, model_ready, read_models, run_case


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(result_json(value), encoding='utf-8')
    temporary.replace(path)


def read_prompts(folder, manifest):
    cases = [json.loads(line) for line in (folder / 'prompts.jsonl').read_text(encoding='utf-8').splitlines()]
    if digest(cases) != manifest['prompts_sha256']:
        raise ValueError('Frozen prompt snapshot was modified; use the original snapshot')
    return cases


def prepare_run(folder, models, bases, cores):
    folder.mkdir(parents=True, exist_ok=False)
    cases = [p for basis in bases for core in cores for p in expand_scenario(core, basis)]
    stamp = utc_timestamp()
    manifest = {
        'experiment_id': folder.name, 'created_at': stamp, 'dataset_version': VERSION,
        'models': models, 'policy_bases': bases, 'core_count': len(cores),
        'prompts_per_model': len(cases), 'planned_trials': len(cases) * len(models),
        'prompts_sha256': digest(cases),
        'validation_status_counts': dict(Counter(c['validation_status'] for c in cores)),
        'missing_evaluation_scenarios': [c['scenario_id'] for c in cores if not c.get('evaluation')],
        'code_sha256': {name: digest((ROOT / name).read_text()) for name in
                        ['dataset.py', 'prompting.py', 'run_pilot.py', 'run_all_experiments.py',
                         'trace_parser.py', 'result_io.py', 'model_config.json']},
        'notes': 'Synthetic scenarios; draft policies and references. One independent request per condition. '
                 'Generation completion is not a compliance score. Published and experimental bases stay labelled separately.',
    }
    (folder / 'prompts.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases), encoding='utf-8')
    write_json(folder / 'cores_snapshot.json', cores)
    write_json(folder / 'experimental_references.json', reference_rows(cores) if 'experimental' in bases else [])
    write_json(folder / 'experiment_manifest.json', manifest)
    return manifest, cases


def latest_record(folder, model_name, case, source=None):
    location = folder / 'trials' / model_name / case['prompt_id']
    attempts = sorted(location.glob('attempt_*/result.json'))
    if not attempts:
        return None
    record = json.loads(attempts[-1].read_text(encoding='utf-8'))
    source = source or read_models()[model_name]
    if (record.get('prompt_sha256') != case['prompt_sha256']
            or record.get('prompt_id') != case['prompt_id']
            or record.get('run_id') != folder.name or record.get('model') != source):
        raise ValueError(f'{location}: existing record does not match the planned condition')
    return record


def update_summary(folder, manifest, cases):
    records = []
    for model_name in manifest['models']:
        for case in cases:
            record = latest_record(folder, model_name, case, manifest['models'][model_name])
            if record is not None:
                records.append(record)
    counts = Counter(r['status'] for r in records)
    final = [r for r in records if r.get('finished_at')]
    summary = {
        'experiment_id': manifest['experiment_id'], 'updated_at': utc_timestamp(),
        'planned_trials': manifest['planned_trials'], 'attempted_conditions': len(records),
        'finalized_conditions': len(final), 'remaining_conditions': manifest['planned_trials'] - len(final),
        'status_counts': dict(counts),
        'final_answers': sum(bool(r.get('final_answer')) for r in final),
        'truncated': sum(bool(r.get('truncated')) for r in final),
        'by_model': {name: dict(Counter(r['status'] for r in records if r['model_id'] == manifest['models'][name]['model_id']))
                     for name in manifest['models']},
        'by_policy_basis': {basis: dict(Counter(r['status'] for r in records if r['policy_basis'] == basis))
                            for basis in manifest['policy_bases']},
        'all_conditions_attempted': len(final) == manifest['planned_trials'],
        'all_generations_completed': len(final) == manifest['planned_trials'] and counts['completed'] == len(final),
        'note': 'Latest attempt per planned condition; all attempts remain in individual files and results/all_trials.json. '
                'Incomplete responses count as attempted, not completed. No automatic compliance scores. Filter the global collection by run_id to select this experiment.',
    }
    write_json(folder / 'summary.json', summary)
    return summary


def export_run(folder, manifest):
    # Use the existing all_trials.json schema. Include every finalized attempt,
    # including errors, so the experiment export never hides failed attempts.
    trials = []
    for path in sorted((folder / 'trials').glob('*/*/attempt_*/result.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        if record.get('finished_at'):
            trials.append(record)
    write_json(folder / 'all_trials.json', {
        'collection_schema_version': '1.0', 'created_at': manifest['created_at'],
        'updated_at': utc_timestamp(), 'trial_count': len(trials), 'trials': trials})


def execute_run(folder, manifest, cases):
    import fcntl
    with (folder / 'experiment.lock').open('a') as lock:
        # Protect against accidentally resuming the same experiment twice.
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(f'EXPERIMENT_DIR={folder}', flush=True)
        write_json(folder / 'progress.json', {'status': 'running', 'started_at': utc_timestamp()})
        try:
            for name in manifest['models']:
                # A separate process per model releases GPU memory before the next model loads.
                subprocess.run([sys.executable, str(Path(__file__).resolve()), '--resume', str(folder),
                                '--worker-model', name], check=True)
            summary = update_summary(folder, manifest, cases)
            write_json(folder / 'progress.json', {'status': 'finished', 'finished_at': utc_timestamp(),
                                                  'summary': summary})
        except BaseException as exc:
            write_json(folder / 'progress.json', {
                'status': 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'error',
                'finished_at': utc_timestamp(), 'error': str(exc)})
            update_summary(folder, manifest, cases)
            raise
        finally:
            export_run(folder, manifest)


def run_model(folder, manifest, cases, name):
    source = manifest['models'][name]
    # Import GPU libraries only after model-free validation and dry runs.
    from mlx_lm import load
    import mlx.core as mx
    pending = []
    for case in cases:
        previous = latest_record(folder, name, case, source)
        if previous and previous.get('finished_at') and previous['status'] in ('completed', 'incomplete'):
            continue
        pending.append(case)
    if not pending:
        print(f'{name}: all conditions already attempted', flush=True)
        return
    print(f'Loading {source["model_id"]}; {len(pending)} conditions remaining', flush=True)
    started = time.perf_counter()
    model, tokenizer = load(str(ROOT / source['local_path']))
    write_json(folder / f'{name}_execution.json', {
        'model_id': source['model_id'], 'loaded_at': utc_timestamp(),
        'model_load_seconds': round(time.perf_counter() - started, 2)})
    try:
        for index, case in enumerate(pending, 1):
            location = folder / 'trials' / name / case['prompt_id']
            attempts = sorted(location.glob('attempt_*'))
            attempt = max([int(p.name.split('_')[-1]) for p in attempts] or [0]) + 1
            trial = {**case, 'run_id': folder.name, 'trial_id': uuid.uuid4().hex}
            print(f'[{name} {index}/{len(pending)}] {case["prompt_id"]}', flush=True)
            record = run_case(trial, source, location / f'attempt_{attempt:03d}', model, tokenizer,
                              dict(source['generation_settings']))
            summary = update_summary(folder, manifest, cases)
            print(f'PROGRESS {summary["finalized_conditions"]}/{summary["planned_trials"]} '
                  f'{summary["status_counts"]}', flush=True)
            if record['status'] == 'error':
                raise RuntimeError(f'Generation failed; batch stopped to avoid repeating the error: {record.get("error")}')
    finally:
        del model, tokenizer
        gc.collect()
        mx.clear_cache()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    configured = read_models()
    parser.add_argument('--models', nargs='+', choices=configured)
    parser.add_argument('--policy-bases', nargs='+', choices=['experimental', 'published'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--worker-model', choices=configured, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.resume and args.output:
        parser.error('Use --output for a new run or --resume for an existing run')
    if args.resume:
        folder = args.resume.resolve()
        manifest = json.loads((folder / 'experiment_manifest.json').read_text(encoding='utf-8'))
        cases = read_prompts(folder, manifest)
        if args.models and args.models != list(manifest['models']):
            parser.error('Resume must use the original model selection')
        if args.policy_bases and args.policy_bases != manifest['policy_bases']:
            parser.error('Resume must use the original policy bases')
        for name, source in manifest['models'].items():
            if configured.get(name) != source:
                parser.error(f'{name}: model configuration changed since the experiment was frozen')
    else:
        names = args.models or ['standard', 'reasoning']
        bases = args.policy_bases or ['experimental']
        if len(names) != len(set(names)) or len(bases) != len(set(bases)):
            parser.error('Model and policy-basis selections must be unique')
        models = {name: configured[name] for name in names}
        cores = load_scenarios()
        count = sum(len(expand_scenario(c, basis)) for basis in bases for c in cores)
        print(f'{len(cores)} scenarios; {count} prompts/model; {count * len(models)} planned trials', flush=True)
        for name in names:
            print(f'{name}: ready={model_ready(name)} {models[name]["model_id"]}', flush=True)
        if args.dry_run:
            return
        missing = [name for name in names if not model_ready(name)]
        if missing:
            parser.error(f'Local weights missing: {missing}')
        folder = args.output or ROOT / 'results' / 'experiments' / (
            datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:8])
        folder = folder.resolve()
        manifest, cases = prepare_run(folder, models, bases, cores)
    if args.dry_run:
        print(json.dumps(update_summary(folder, manifest, cases), indent=2))
        return
    if args.worker_model:
        if args.worker_model not in manifest['models']:
            parser.error('Worker model is outside this experiment plan')
        run_model(folder, manifest, cases, args.worker_model)
        return
    execute_run(folder, manifest, cases)


if __name__ == '__main__':
    main()
