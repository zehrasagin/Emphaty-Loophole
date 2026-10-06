"""JSON scenarios → validated factorial prompts. Run this file to validate/build."""
import argparse
import hashlib
import json
import re
from itertools import product
from pathlib import Path

from prompting import EMOTIONS, FRAMES, render_messages

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
POLICIES = ('strict', 'exception', 'ambiguous')
POLICY_LABELS = {'strict': 'Strict (base rule, no exceptions)',
                 'exception': 'Exception (specific eligibility)',
                 'ambiguous': 'Ambiguous (discretionary language)'}
DOMAIN_LABELS = {'retail': 'Retail', 'airlines': 'Airlines', 'hotels': 'Hotels',
                 'telecom': 'Telecom', 'customer_support': 'Customer support'}
VERSION = '0.7.0'
POLICY_BASES = ('experimental', 'published')
SHARED_POLICY_FIELDS = ('provider', 'provider_type', 'base_rule', 'policy_variants',
                        'source', 'published_policy', 'adaptation_note', 'policy_topics')


def condition_id(scenario_id, policy, emotion, policy_basis='experimental'):
    if policy_basis not in POLICY_BASES:
        raise ValueError(f'Unknown policy basis: {policy_basis}')
    basis = '__published' if policy_basis == 'published' else ''
    return f'{scenario_id}{basis}__{policy}__{emotion}'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_scenario(core, domain=None):
    if not isinstance(core, dict):
        raise ValueError('Each scenario file must contain one JSON object')
    cid = core.get('scenario_id', '<missing ID>')
    required = ('scenario_id', 'domain', 'title', 'facts', 'facts_text',
                'request', 'base_rule', 'policy_variants', 'source', 'validation_status')
    missing = [k for k in required if k not in core]
    if missing:
        raise ValueError(f'{cid}: missing fields {missing}')
    if not isinstance(cid, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', cid):
        raise ValueError(f'{cid}: use lowercase letters, digits and underscores for IDs')
    if not isinstance(core['domain'], str) or core['domain'] not in DOMAIN_LABELS or (domain and core['domain'] != domain):
        raise ValueError(f'{cid}: invalid or mismatched domain')
    if not isinstance(core['facts'], dict) or not core['facts']:
        raise ValueError(f'{cid}: facts must be a nonempty object')
    topics = core.get('policy_topics')
    if topics is not None:
        if (not isinstance(topics, list) or not topics
                or any(not isinstance(t, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', t) for t in topics)
                or len(set(topics)) != len(topics)):
            raise ValueError(f'{cid}: policy_topics must be unique nonempty topic IDs')
        if core.get('policy_topic') not in topics:
            raise ValueError(f'{cid}: policy_topic must belong to the shared policy_topics')
    elif 'policy_topic' in core and (not isinstance(core['policy_topic'], str)
            or not re.fullmatch(r'[a-z][a-z0-9_]*', core['policy_topic'])):
        raise ValueError(f'{cid}: invalid policy_topic')
    provider = core.get('provider', core.get('fictional_provider'))
    if not isinstance(provider, str) or not provider.strip():
        raise ValueError(f'{cid}: provider must be nonempty text')
    if 'provider' in core and core.get('provider_type') not in ('real', 'fictional'):
        raise ValueError(f'{cid}: provider_type must be real or fictional')
    for key in ('title', 'facts_text', 'request', 'base_rule'):
        if not isinstance(core[key], str) or not core[key].strip():
            raise ValueError(f'{cid}: {key} must be nonempty text')
    variants = core['policy_variants']
    if not isinstance(variants, dict) or set(variants) != set(POLICIES):
        raise ValueError(f'{cid}: policy_variants must contain exactly strict, exception, ambiguous')
    for policy, text in variants.items():
        if not isinstance(text, str) or not text.startswith(core['base_rule'] + ' ') or not text[len(core['base_rule']):].strip():
            raise ValueError(f'{cid}: {policy} must retain base_rule and add a condition clause')
    if len(set(variants.values())) != 3:
        raise ValueError(f'{cid}: the three policy variants must be distinct')
    source = core['source']
    if not isinstance(source, dict) or source.get('policy_provenance') != 'researcher_authored_experimental_variants':
        raise ValueError(f'{cid}: identify experimental policies as researcher-authored')
    records = source.get('records')
    if not isinstance(records, list) or not records or any(not isinstance(s, dict) for s in records):
        raise ValueError(f'{cid}: source.records must contain provenance records (synthetic is allowed)')
    ids = [s.get('source_id') for s in records]
    if any(not isinstance(sid, str) or not sid.strip() for sid in ids) or len(set(ids)) != len(ids):
        raise ValueError(f'{cid}: source records need unique nonempty source_id values')
    if core.get('provider_type') == 'real':
        if core.get('scenario_provenance') != 'synthetic_customer_scenario':
            raise ValueError(f'{cid}: identify authored customer cases as synthetic')
        if any(s.get('airline', s.get('organization')) != provider for s in records):
            raise ValueError(f'{cid}: real provider must match source organizations')
    if 'published_policy' in core:
        published = core['published_policy']
        if (not isinstance(published, dict) or not isinstance(published.get('text'), str)
                or not published['text'].strip() or published.get('policy_type') not in POLICIES
                or published.get('representation') != 'scoped_paraphrase_of_published_policy'
                or published.get('verification_status') not in ('official_source_checked_pending_human_review', 'human_verified')):
            raise ValueError(f'{cid}: incomplete published policy summary or verification metadata')
        used = published.get('source_ids')
        if not isinstance(used, list) or not used or any(s not in ids for s in used):
            raise ValueError(f'{cid}: published policy must resolve its source_ids')
        if any(not s.get('url') or not s.get('verified_on') for s in records if s['source_id'] in used):
            raise ValueError(f'{cid}: published sources need URLs and verification dates')
    if core['validation_status'] not in ('draft_pending_human_review', 'human_validated'):
        raise ValueError(f'{cid}: invalid validation status')
    if core.get('policy_validation_status', core['validation_status']) not in ('draft_pending_human_review', 'human_validated'):
        raise ValueError(f'{cid}: invalid shared policy validation status')
    if core['validation_status'] == 'human_validated':
        if core.get('policy_validation_status', 'human_validated') != 'human_validated':
            raise ValueError(f'{cid}: shared policy must also be human validated')
        review = core.get('human_review', {})
        if not isinstance(review, dict) or not review.get('reviewer') or any(review.get(k) is not True for k in
                ('facts_equivalent', 'emotion_validated', 'policy_validated', 'references_validated')):
            raise ValueError(f'{cid}: human validation requires completed review fields')
    evaluation = core.get('evaluation', {})
    if not isinstance(evaluation, dict):
        raise ValueError(f'{cid}: evaluation must be an object')
    references = evaluation.get('reference_decisions', {})
    if not isinstance(references, dict) or (references and (set(references) != set(POLICIES)
                       or any(not isinstance(r, dict) for r in references.values()))):
        raise ValueError(f'{cid}: evaluation references must cover all three policies')


def load_scenario(path):
    """Load one core, resolving its domain's optional shared _policy.json."""
    path = Path(path)
    try:
        core = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(core, dict):
            raise ValueError('Each scenario file must contain one JSON object')
        policy_path = path.parent / '_policy.json'
        if policy_path.exists():
            policy = json.loads(policy_path.read_text(encoding='utf-8'))
            if not isinstance(policy, dict):
                raise ValueError('Shared policy must contain one JSON object')
            policy_id = policy.get('policy_id')
            if not isinstance(policy_id, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', policy_id):
                raise ValueError('Shared policy needs a valid policy_id')
            if policy.get('domain') != core.get('domain') or core.get('policy_id') != policy_id:
                raise ValueError('Scenario must reference its domain\'s shared policy_id')
            overrides = [key for key in SHARED_POLICY_FIELDS if key in core]
            if overrides:
                raise ValueError(f'Scenario cannot override shared policy fields: {overrides}')
            status = policy.get('validation_status')
            if status not in ('draft_pending_human_review', 'human_validated'):
                raise ValueError('Shared policy needs a validation_status')
            if status == 'human_validated':
                review = policy.get('human_review', {})
                if (not isinstance(review, dict) or not review.get('reviewer')
                        or review.get('policy_validated') is not True or review.get('source_validated') is not True):
                    raise ValueError('Shared policy validation requires a reviewer, policy_validated and source_validated')
            core = {**{key: policy[key] for key in SHARED_POLICY_FIELDS if key in policy}, **core,
                    'policy_record_sha256': digest(policy), 'policy_validation_status': status}
        elif 'policy_id' in core:
            raise ValueError('Scenario references a shared policy but _policy.json is missing')
        validate_scenario(core, path.parent.name if path.parent.name in DOMAIN_LABELS else None)
        if path.stem != core['scenario_id']:
            raise ValueError('Filename must match scenario_id')
    except (ValueError, OSError) as exc:
        raise ValueError(f'{path}: {exc}') from exc
    return core


def load_scenarios(domain=None, data_root=DATA):
    root = Path(data_root)
    if not root.is_dir():
        raise ValueError(f'Dataset directory does not exist: {root}')
    if domain is not None and domain not in DOMAIN_LABELS:
        raise ValueError(f'Unknown domain: {domain}')
    # Fail on misplaced JSON instead of silently dropping a team's new scenario.
    for path in sorted(root.rglob('*.json')):
        if len(path.relative_to(root).parts) != 2 or path.parent.name not in DOMAIN_LABELS:
            raise ValueError(f'{path}: scenario JSON must be directly under one of the five domain folders')
    cores, seen = [], set()
    for selected in ([domain] if domain else DOMAIN_LABELS):
        for path in sorted((root / selected).glob('*.json')):
            if path.name == '_policy.json':
                continue
            core = load_scenario(path)
            if core['scenario_id'] in seen:
                raise ValueError(f'Duplicate scenario ID: {core["scenario_id"]}')
            seen.add(core['scenario_id'])
            cores.append(core)
    for selected in {c['domain'] for c in cores if c.get('policy_id')}:
        hashes = {c.get('policy_record_sha256') for c in cores if c['domain'] == selected}
        if len(hashes) != 1:
            raise ValueError(f'{selected}: shared policy changed while loading; retry with a stable dataset')
    return cores


def expand_scenario(core, policy_basis='experimental'):
    validate_scenario(core)
    if policy_basis not in POLICY_BASES:
        raise ValueError(f'Unknown policy basis: {policy_basis}')
    if policy_basis == 'published' and 'published_policy' not in core:
        raise ValueError(f"{core['scenario_id']}: no published policy available")
    policies = POLICIES if policy_basis == 'experimental' else (core['published_policy']['policy_type'],)
    if set(FRAMES) != set(EMOTIONS) or any(not isinstance(f, str) or not f.strip() for f in FRAMES.values()):
        raise ValueError('Expected exactly four nonempty emotional frames')
    facts_hash = digest({k: core[k] for k in ('facts', 'facts_text', 'request')})
    prompts = []
    for policy, emotion in product(policies, EMOTIONS):
        messages = render_messages(core, policy, emotion, policy_basis)
        prompts.append({
            'prompt_id': condition_id(core['scenario_id'], policy, emotion, policy_basis),
            'scenario_id': core['scenario_id'], 'title': core['title'], 'domain': core['domain'],
            'policy_type': policy, 'emotion': emotion, 'messages': messages,
            'dataset_version': VERSION, 'dataset_id': f'empathy_loophole_{policy_basis}',
            'policy_basis': policy_basis, 'provider': core.get('provider', core.get('fictional_provider')),
            'policy_id': core.get('policy_id'), 'policy_record_sha256': core.get('policy_record_sha256'),
            'policy_topic': core.get('policy_topic'),
            'policy_validation_status': core.get('policy_validation_status'),
            'provider_type': core.get('provider_type', 'fictional'),
            'scenario_provenance': core.get('scenario_provenance', 'synthetic_customer_scenario'),
            'policy_representation': 'researcher_modified_experimental_variant' if policy_basis == 'experimental' else core['published_policy']['representation'],
            'purpose': 'controlled_benchmark_pilot' if policy_basis == 'experimental' else 'published_policy_pilot',
            'validation_status': core['validation_status'],
            'source': core['source'], 'adaptation_note': core.get('adaptation_note'),
            'core_record_sha256': digest(core), 'facts_sha256': facts_hash,
            'prompt_sha256': digest(messages),
        })
    validate_grid(prompts, [core], policy_basis)
    return prompts


def validate_grid(prompts, cores, policy_basis='experimental'):
    if policy_basis not in POLICY_BASES:
        raise ValueError(f'Unknown policy basis: {policy_basis}')
    ids = [p['prompt_id'] for p in prompts]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate prompt IDs')
    core_ids = [c['scenario_id'] for c in cores]
    if len(core_ids) != len(set(core_ids)):
        raise ValueError('Duplicate scenario IDs')
    if set(p['scenario_id'] for p in prompts) != set(core_ids):
        raise ValueError('Core scenario coverage does not match')
    for core in cores:
        policies = POLICIES if policy_basis == 'experimental' else (core['published_policy']['policy_type'],)
        expected = set(product(policies, EMOTIONS))
        rows = [p for p in prompts if p['scenario_id'] == core['scenario_id']]
        if len(rows) != len(expected) or set((p['policy_type'], p['emotion']) for p in rows) != expected:
            raise ValueError(f"{core['scenario_id']}: incomplete or duplicate factorial grid")
        for row in rows:
            if row.get('policy_basis', 'experimental') != policy_basis or row['prompt_id'] != condition_id(core['scenario_id'], row['policy_type'], row['emotion'], policy_basis):
                raise ValueError('Prompt ID does not match its condition')
            if row['domain'] != core['domain'] or row['messages'] != render_messages(core, row['policy_type'], row['emotion'], policy_basis):
                raise ValueError(f"{row['prompt_id']}: policy, facts, request or framing changed")
            if row['prompt_sha256'] != digest(row['messages']):
                raise ValueError(f"{row['prompt_id']}: prompt hash mismatch")
            if row['facts_sha256'] != digest({k: core[k] for k in ('facts', 'facts_text', 'request')}):
                raise ValueError(f"{row['prompt_id']}: facts hash mismatch")


def load_cases(domain=None, data_root=DATA, policy_basis='experimental'):
    cores = load_scenarios(domain, data_root)
    if policy_basis == 'published':
        cores = [c for c in cores if 'published_policy' in c]
    prompts = [p for core in cores for p in expand_scenario(core, policy_basis)]
    validate_grid(prompts, cores, policy_basis)
    return prompts


def reference_rows(cores):
    # References are for evaluation only and never enter generated prompt records.
    return [{**reference, 'scenario_id': core['scenario_id'],
             'prompt_id': f"{core['scenario_id']}__{policy}__{emotion}",
             'policy_type': policy, 'emotion': emotion}
            for core in cores
            for policy, reference in core.get('evaluation', {}).get('reference_decisions', {}).items()
            for emotion in EMOTIONS]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', choices=DOMAIN_LABELS)
    parser.add_argument('--data-root', type=Path, default=DATA)
    parser.add_argument('--policy-basis', choices=POLICY_BASES, default='experimental')
    parser.add_argument('--output', type=Path, help='Build JSONL files and a manifest here; omit for validation only')
    args = parser.parse_args()
    try:
        cores = load_scenarios(args.domain, args.data_root)
        if args.policy_basis == 'published':
            cores = [c for c in cores if 'published_policy' in c]
        prompts = [p for c in cores for p in expand_scenario(c, args.policy_basis)]
        validate_grid(prompts, cores, args.policy_basis)
        if not cores:
            raise ValueError('No scenarios found')
    except ValueError as exc:
        parser.error(str(exc))
    print(f'Validated {len(cores)} core scenarios → {len(prompts)} prompts ({args.policy_basis}; {12 if args.policy_basis == "experimental" else 4} per scenario)')
    if args.output:
        if args.output.resolve().is_relative_to(args.data_root.resolve()):
            parser.error('Build output must be outside the JSON source directory')
        args.output.mkdir(parents=True, exist_ok=True)
        references = reference_rows(cores) if args.policy_basis == 'experimental' else []
        for name, rows in [('prompts.jsonl', prompts), ('reference_labels.jsonl', references)]:
            (args.output / name).write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
        manifest = {'dataset_version': VERSION, 'policy_basis': args.policy_basis, 'core_scenarios': len(cores), 'prompts': len(prompts),
                    'domain_counts': {d: sum(c['domain'] == d for c in cores) for d in DOMAIN_LABELS},
                    'cores_sha256': digest(cores), 'prompts_sha256': digest(prompts),
                    'validation_statuses': sorted({c['validation_status'] for c in cores}),
                    'notes': 'Synthetic customer scenarios. Published summaries and modified experimental policies are separate collections. Build contains no model results.'}
        (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print(f'Built dataset in {args.output}')


if __name__ == '__main__':
    main()
