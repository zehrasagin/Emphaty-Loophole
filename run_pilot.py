"""Run independent one-turn conditions using local models; retain all outputs."""
import argparse
import json
import math
import re
import time
import uuid
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from trace_parser import parse_output
from prompting import effective_messages
from result_io import new_result_record, save_result_record, utc_timestamp
from dataset import (DATA, DOMAIN_LABELS, EMOTIONS, POLICIES, POLICY_BASES,
                     condition_id, digest, expand_scenario, load_cases, load_scenario)

ROOT = Path(__file__).resolve().parent


def read_models():
    models = json.loads((ROOT / 'model_config.json').read_text())
    if not isinstance(models, dict) or not models:
        raise ValueError('model_config.json must contain model names mapped to configurations')
    for name, source in models.items():
        if not isinstance(source, dict) or any(not source.get(k) for k in ('model_id', 'local_path')):
            raise ValueError(f'{name}: model_id and local_path are required')
        if source.get('model_type') not in ('standard', 'reasoning'):
            raise ValueError(f'{name}: model_type must be standard or reasoning')
        if 'chat_template' in source and (not isinstance(source['chat_template'], str) or not source['chat_template'].strip()):
            raise ValueError(f'{name}: chat_template must be nonempty text')
        settings = source.get('generation_settings', {})
        if not isinstance(settings, dict) or set(settings) != {'temperature', 'top_p', 'max_tokens', 'seed'}:
            raise ValueError(f'{name}: supply temperature, top_p, max_tokens and seed')
        if (type(settings['max_tokens']) is not int or settings['max_tokens'] <= 0
                or type(settings['seed']) is not int
                or not isinstance(settings['temperature'], (int, float))
                or not math.isfinite(settings['temperature']) or settings['temperature'] < 0
                or not isinstance(settings['top_p'], (int, float)) or not 0 < settings['top_p'] <= 1):
            raise ValueError(f'{name}: invalid generation settings')
    return models


def read_source(name):
    return read_models()[name]


def model_ready(name):
    try:
        path = ROOT / read_source(name)['local_path']
        index = json.loads((path / 'model.safetensors.index.json').read_text())
        return bool(index['weight_map']) and all((path / shard).exists() for shard in set(index['weight_map'].values()))
    except (OSError, ValueError, KeyError):
        return False


def run_case(case, source, run_dir, model, tokenizer, settings, context_limit=None):
    run_dir.mkdir(parents=True, exist_ok=True)
    if (run_dir / 'raw_output.txt').exists() or (run_dir / 'result.json').exists():
        raise FileExistsError(f'{run_dir}: existing trial output; use a fresh directory')
    record = new_result_record(case, source, settings, run_dir.name)
    def save():
        save_result_record(record, run_dir)
    save()
    print(f"Results: {run_dir}", flush=True)
    started = time.perf_counter()
    reasoning = record['model_type'] == 'reasoning'
    prompt_opens_think = False
    try:
        import mlx.core as mx
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        record['versions'] = {n: version(n) for n in ['mlx', 'mlx-lm', 'transformers']}
        mx.random.seed(settings["seed"])
        mx.reset_peak_memory()
        messages = effective_messages(case["messages"], reasoning=reasoning)
        if not getattr(tokenizer, 'chat_template', None) and source.get('chat_template'):
            tokenizer.chat_template = source['chat_template']
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        prompt_opens_think = reasoning and rendered.rstrip().endswith("<think>")
        tokens = tokenizer.encode(rendered, add_special_tokens=False)
        record.update(prompt=rendered, prompt_token_ids=tokens, chat_template=tokenizer.chat_template,
                      effective_messages=messages, prompt_opens_think=prompt_opens_think,
                      prompt_adapter="system_into_user" if reasoning else "original_messages",
                      weight_dtype=str(model.parameters()["model"]["embed_tokens"]["weight"].dtype))
        save()
        if context_limit and len(tokens) + settings['max_tokens'] > context_limit:
            raise ValueError(f"This conversation exceeds the {context_limit}-token local context budget. Start a new conversation.")
        last = None
        print("\nModel response:\n", flush=True)
        # Flush output to disk before performing any interpretation.
        generated_token_ids = []
        with (run_dir / "raw_output.txt").open("x", encoding='utf-8', newline='') as raw:
            for response in stream_generate(model, tokenizer, tokens, max_tokens=settings["max_tokens"],
                                            sampler=make_sampler(temp=settings["temperature"], top_p=settings["top_p"])):
                generated_token_ids.append(int(response.token))
                raw.write(response.text)
                raw.flush()
                print(response.text, end="", flush=True)
                last = response
        with (run_dir / 'raw_output.txt').open(encoding='utf-8', newline='') as raw:
            text = raw.read()
        complete = last is not None and last.finish_reason == "stop"
        record.update(
            status="completed" if complete else "incomplete",
            **parse_output(text, reasoning=reasoning, prompt_opens_think=prompt_opens_think, finished=complete),
            generated_token_ids=generated_token_ids,
            finish_reason=last.finish_reason if last else "no_output",
            truncated=last is not None and last.finish_reason == 'length',
            generation_tokens=last.generation_tokens if last else 0,
            peak_memory_gb=last.peak_memory if last else None,
        )
        for field in ("reasoning_trace", "final_answer"):
            if record[field] is not None:
                (run_dir / f"{field}.txt").write_text(record[field])
        print(f"\n\nStatus: {record['status']} | Finish: {record['finish_reason']}")
    except Exception as exc:
        record.update(status="error", error=f"{type(exc).__name__}: {exc}")
        raw_path = run_dir / "raw_output.txt"
        text = ''
        if raw_path.exists():
            with raw_path.open(encoding='utf-8', newline='') as raw:
                text = raw.read()
        parsed = parse_output(text, reasoning=reasoning,
                              prompt_opens_think=prompt_opens_think, finished=False)
        record.update(parsed, trace_parse_status=parsed['parse_status'],
                      parse_status='generation_error', finish_reason='error')
        print(f"\nError: {record['error']}", flush=True)
    finally:
        record["elapsed_seconds"] = round(time.perf_counter() - started, 2)
        record['finished_at'] = utc_timestamp()
        save()
    return record


def write_summary(batch_dir, records):
    (batch_dir / "summary.json").write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    lines = ["# Pilot results", "",
             "Status indicates generation completion; it is not a policy compliance label.", "",
             "A reasoning trace is an observable explanation generated by the model, not definitive evidence of its internal decision process.", ""]
    for record in records:
        lines += [f"## {record.get('prompt_id', record['scenario_id'])}", "",
                  f"Condition: {record['policy_type']} / {record['emotion']}", "",
                  f"Policy basis: {record.get('policy_basis', 'experimental')}", "",
                  f"Model: {record['model']['model_id']}", "",
                  f"Status: {record['status']} | Finish reason: {record.get('finish_reason', '—')}", "",
                  f"Parse status: {record.get('parse_status', '—')}", "",
                  f"[Run record]({record['result_path']}) · [Raw output]({record['raw_output_path']})", ""]
        if record.get("error"):
            lines += [f"Error: {record['error']}", ""]
        # Indentation preserves the model's output as literal text in Markdown.
        if record["model_type"] == "reasoning":
            lines += ["### Observable reasoning trace", ""]
            lines += ["    " + line for line in (record.get("reasoning_trace") or "No trace is available or the trace could not be parsed.").splitlines()]
            lines += ["", "### Final answer", ""]
            lines += ["    " + line for line in (record.get("final_answer") or "A complete final answer could not be extracted; inspect the raw output.").splitlines()]
        else:
            lines += ["    " + line for line in record.get("raw_output", "").splitlines()]
        lines.append("")
    (batch_dir / "summary.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", type=Path, help="Use one core JSON or an expanded prompt JSON")
    parser.add_argument("--all", action="store_true", help="Run all prompts matching the filters")
    parser.add_argument('--data-root', type=Path, default=DATA)
    parser.add_argument('--domain', choices=DOMAIN_LABELS)
    parser.add_argument('--scenario', help='Core scenario ID')
    parser.add_argument('--policy', choices=POLICIES)
    parser.add_argument('--policy-basis', choices=POLICY_BASES, default='experimental',
                        help='Published policy summaries or matched experimental variants')
    parser.add_argument('--emotion', choices=EMOTIONS)
    parser.add_argument('--dry-run', action='store_true', help='Validate and list selection without loading a model')
    parser.add_argument('--seed', type=int)
    parser.add_argument('--temperature', type=float)
    parser.add_argument('--top-p', type=float)
    parser.add_argument("--model", choices=read_models(), default="standard")
    parser.add_argument("--max-tokens", type=int, help="Output limit (default: standard 512, reasoning 4096)")
    args = parser.parse_args()
    if args.max_tokens is not None and args.max_tokens <= 0:
        parser.error("--max-tokens must be positive")
    if args.temperature is not None and (not math.isfinite(args.temperature) or args.temperature < 0):
        parser.error('--temperature must be finite and nonnegative')
    if args.top_p is not None and not 0 < args.top_p <= 1:
        parser.error('--top-p must be greater than 0 and at most 1')
    if args.prompt:
        try:
            supplied = json.loads(args.prompt.read_text())
            if not isinstance(supplied, dict):
                raise ValueError('Expected a JSON object')
            is_core = 'messages' not in supplied and ('policy_variants' in supplied or 'policy_id' in supplied)
            cases = expand_scenario(load_scenario(args.prompt), args.policy_basis) if is_core else [supplied]
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    else:
        try:
            cases = load_cases(args.domain, args.data_root, args.policy_basis)
        except ValueError as exc:
            parser.error(str(exc))
        if not any((args.all, args.domain, args.scenario, args.policy, args.emotion)):
            cases = cases[:1]
    for field, value in [('domain', args.domain), ('scenario_id', args.scenario),
                         ('policy_type', args.policy), ('emotion', args.emotion)]:
        if value:
            cases = [c for c in cases if c.get(field) == value]
    if not cases:
        parser.error('No prompts match this selection. The selected domain may not have benchmark data yet.')
    for case in cases:
        if not all(key in case for key in ("scenario_id", "domain", "policy_type", "emotion", "messages")):
            parser.error('Missing required prompt fields')
        messages = case['messages']
        if (not isinstance(messages, list) or len(messages) != 2
                or any(not isinstance(m, dict) or not isinstance(m.get('content'), str) or not m['content'].strip() for m in messages)
                or [m.get('role') for m in messages] != ['system', 'user']):
            parser.error('Controlled prompts require one system message and one user message')
        if not isinstance(case['scenario_id'], str) or not re.fullmatch(r'[a-z][a-z0-9_]*', case['scenario_id']):
            parser.error('Invalid scenario ID')
        if not isinstance(case['domain'], str) or case['domain'] not in DOMAIN_LABELS or case['policy_type'] not in POLICIES or case['emotion'] not in EMOTIONS:
            parser.error('Invalid domain, policy or emotion')
        if case.get('policy_basis', 'experimental') != args.policy_basis:
            parser.error('Prompt policy_basis does not match --policy-basis')
        expected_id = condition_id(case['scenario_id'], case['policy_type'], case['emotion'], args.policy_basis)
        if case.get('prompt_id', expected_id) != expected_id:
            parser.error('Prompt ID does not match its condition')
        case['prompt_id'] = expected_id
        if case.get('prompt_sha256', digest(case['messages'])) != digest(case['messages']):
            parser.error('Prompt hash does not match its messages')
        case['prompt_sha256'] = digest(case['messages'])
    if len({c['prompt_id'] for c in cases}) != len(cases):
        parser.error('Duplicate prompt IDs')
    if args.dry_run:
        print(f'Selected {len(cases)} prompts')
        for case in cases:
            print(case['prompt_id'], case.get('validation_status', 'pilot'))
        return
    if len(cases) > 1 and not args.all:
        parser.error('Multiple prompts matched. Use --all or select one scenario, policy and emotion.')
    source = read_source(args.model)
    if not model_ready(args.model):
        parser.error(f"Local model files are missing or incomplete: {source['local_path']}")
    collection = 'benchmark' if args.policy_basis == 'experimental' else 'published_policy'
    batch_dir = ROOT / "results" / collection / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8])
    batch_dir.mkdir(parents=True)
    records = []
    settings = dict(source['generation_settings'])
    if args.seed is not None:
        settings['seed'] = args.seed
    if args.max_tokens is not None:
        settings['max_tokens'] = args.max_tokens
    for key, value in [('temperature', args.temperature), ('top_p', args.top_p)]:
        if value is not None:
            settings[key] = value
    selection_hash = digest(cases)
    for case in cases:
        case.update(run_id=batch_dir.name, trial_id=uuid.uuid4().hex)
    manifest = {'run_id': batch_dir.name, 'created_at': utc_timestamp(),
                'dataset': f'empathy_loophole_{args.policy_basis}',
                'policy_basis': args.policy_basis, 'model': source, 'generation_settings': settings,
                'prompt_count': len(cases), 'selection_sha256': selection_hash,
                'trials': [{'trial_id': c['trial_id'], 'prompt_id':c['prompt_id'], 'prompt_sha256':c['prompt_sha256'],
                            'validation_status':c.get('validation_status','pilot')} for c in cases]}
    (batch_dir/'run_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f"Results: {batch_dir}", flush=True)
    print("Loading local model once…", flush=True)
    started = time.perf_counter()
    try:
        from mlx_lm import load
        model, tokenizer = load(str(ROOT / source["local_path"]))
    except Exception as exc:
        (batch_dir / "load_error.json").write_text(json.dumps({
            "status": "error", "stage": "model_load", "model": source,
            "run_id": batch_dir.name, "timestamp_utc": utc_timestamp(),
            "error": f"{type(exc).__name__}: {exc}",
        }, indent=2) + "\n")
        raise
    load_seconds = round(time.perf_counter() - started, 2)
    for number, case in enumerate(cases, start=1):
        print(f"\n[{number}/{len(cases)}] {case['prompt_id']}", flush=True)
        # Each stream_generate call creates a fresh cache; no chat history is shared.
        run_dir = batch_dir / f"{number:03d}_{case['prompt_id']}" if args.all else batch_dir
        record = run_case(case, source, run_dir, model, tokenizer, settings)
        records.append({**record, "model_load_seconds": load_seconds,
                        "result_path": str((run_dir / "result.json").relative_to(batch_dir)),
                        "raw_output_path": str((run_dir / "raw_output.txt").relative_to(batch_dir))})
        write_summary(batch_dir, records)
    print(f"\nAll responses: {batch_dir / 'summary.md'}", flush=True)
    if any(record["status"] != "completed" for record in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
