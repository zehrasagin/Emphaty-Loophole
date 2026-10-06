import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dataset import (DOMAIN_LABELS, EMOTIONS, POLICIES, digest, expand_scenario,
                     load_cases, load_scenarios, reference_rows, validate_grid, validate_scenario)
from prompting import FRAMES, render_messages

ROOT = Path(__file__).resolve().parents[1]


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.cores = load_scenarios('airlines')
        self.core = self.cores[0]
        self.prompts = load_cases('airlines')

    def test_one_core_expands_to_twelve_unique_conditions(self):
        prompts = expand_scenario(self.core)
        self.assertEqual(len(prompts), 12)
        self.assertEqual(len({p['prompt_id'] for p in prompts}), 12)
        self.assertEqual({(p['policy_type'], p['emotion']) for p in prompts},
                         {(p, e) for p in POLICIES for e in EMOTIONS})
        self.assertEqual(len(self.prompts), len(self.cores) * 12)
        self.assertEqual(set(DOMAIN_LABELS), {'retail', 'airlines', 'hotels', 'telecom', 'customer_support'})
        for core in self.cores:
            group = [p for p in self.prompts if p['scenario_id'] == core['scenario_id']]
            self.assertEqual(len({p['facts_sha256'] for p in group}), 1)
            for emotion in EMOTIONS:
                self.assertEqual(len({p['messages'][1]['content'] for p in group if p['emotion'] == emotion}), 1)
            for policy in POLICIES:
                self.assertEqual(len({p['messages'][0]['content'] for p in group if p['policy_type'] == policy}), 1)

    def test_grid_rejects_missing_duplicate_and_modified_inputs(self):
        with self.assertRaises(ValueError):
            validate_grid(self.prompts[:-1], self.cores)
        with self.assertRaises(ValueError):
            validate_grid(self.prompts + [self.prompts[0]], self.cores)
        for field in ('facts', 'policy', 'id'):
            changed = copy.deepcopy(self.prompts)
            if field == 'id':
                changed[0]['prompt_id'] += '_wrong'
            else:
                changed[0]['messages'][1 if field == 'facts' else 0]['content'] += ' The flight was cancelled.'
                changed[0]['prompt_sha256'] = digest(changed[0]['messages'])
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_grid(changed, self.cores)

    def test_invalid_and_missing_policy_variants_fail(self):
        for mutation in ('missing_field', 'missing_policy', 'extra_normal', 'empty', 'unrelated'):
            core = copy.deepcopy(self.core)
            if mutation == 'missing_field':
                del core['policy_variants']
            elif mutation == 'missing_policy':
                del core['policy_variants']['exception']
            elif mutation == 'extra_normal':
                core['policy_variants']['normal'] = core['base_rule']
            elif mutation == 'empty':
                core['policy_variants']['strict'] = ''
            else:
                core['policy_variants']['exception'] = 'An unrelated policy.'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_scenario(core)

    def test_invalid_emotion_and_missing_frame_fail(self):
        with self.assertRaises(ValueError):
            render_messages(self.core, 'strict', 'fear')
        original = dict(FRAMES)
        try:
            FRAMES.pop('guilt')
            with self.assertRaises(ValueError):
                expand_scenario(self.core)
        finally:
            FRAMES.clear()
            FRAMES.update(original)

    def test_required_fields_domains_provenance_and_human_review(self):
        for field, value in [('facts', {}), ('request', ''), ('source', {}),
                             ('domain', 'banking'), ('validation_status', 'human_validated')]:
            core = copy.deepcopy(self.core)
            core[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_scenario(core)

    def test_new_json_is_discovered_without_code_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'airlines'
            folder.mkdir()
            (folder / (self.core['scenario_id'] + '.json')).write_text(json.dumps(self.core))
            self.assertEqual(len(load_cases(data_root=Path(tmp))), 12)
            new = copy.deepcopy(self.core)
            new['scenario_id'] = 'airline_011'
            (folder / 'airline_011.json').write_text(json.dumps(new))
            self.assertEqual(len(load_cases(data_root=Path(tmp))), 24)
            retail = Path(tmp) / 'retail'
            retail.mkdir()
            new['scenario_id'], new['domain'] = 'retail_002', 'retail'
            (retail / 'retail_002.json').write_text(json.dumps(new))
            self.assertEqual(len(load_cases(data_root=Path(tmp))), 36)
            new['domain'] = 'airlines'
            (retail / 'retail_002.json').write_text(json.dumps(new))
            with self.assertRaises(ValueError):
                load_cases(data_root=Path(tmp))

    def test_historical_inputs_and_existing_experimental_references_are_preserved(self):
        archived = ROOT / 'archive/previous_dataset/data/airlines/generated'
        old = {p['prompt_id']: p for p in map(json.loads, (archived / 'prompts.jsonl').read_text().splitlines())}
        self.assertTrue(all('Northstar Air' in p['messages'][0]['content'] for p in old.values()))
        baseline = json.loads((ROOT / 'archive/fictional_airline_baseline/airlines_003_early_cancellation.json').read_text())
        self.assertEqual(baseline['facts']['experimental_admin_fee_eur'], 40)
        refs = {r['prompt_id']: r for r in reference_rows(self.cores)}
        prior = {r['prompt_id']: r for r in map(json.loads, (archived / 'reference_labels.jsonl').read_text().splitlines())}
        for pid, reference in prior.items():
            self.assertEqual(refs[pid], reference)

    def test_real_airline_names_are_used_and_evaluation_labels_are_excluded(self):
        for prompt in self.prompts:
            text = json.dumps(prompt['messages'])
            for value in ('Northstar Air', 'expected_decision', 'acceptable_actions'):
                self.assertNotIn(value, text)
            self.assertIn(prompt['provider'], text)
            self.assertIn('researcher-modified', text)
            self.assertNotIn('evaluation', prompt)
            self.assertEqual(prompt['prompt_sha256'], digest(prompt['messages']))
        baseline = next(p for p in self.prompts if p['prompt_id'] == 'airlines_001_no_show__strict__neutral')
        pilot = json.loads((ROOT / 'archive/previous_dataset/pilot_prompts/airline_refund_001.json').read_text())
        self.assertNotEqual(baseline['messages'], pilot['messages'])
        self.assertEqual(pilot['source_core_scenario_id'], baseline['scenario_id'])

    def test_published_policy_has_four_emotions_and_separate_ids(self):
        for core in self.cores:
            published = expand_scenario(core, 'published')
            self.assertEqual(len(published), 4)
            self.assertEqual({p['emotion'] for p in published}, set(EMOTIONS))
            self.assertEqual({p['policy_type'] for p in published}, {core['published_policy']['policy_type']})
            self.assertEqual(len({p['facts_sha256'] for p in published}), 1)
            experimental = expand_scenario(core)
            self.assertFalse({p['prompt_id'] for p in published} & {p['prompt_id'] for p in experimental})
            for row in published:
                self.assertIn(core['published_policy']['text'], row['messages'][0]['content'])
                self.assertEqual(row['policy_basis'], 'published')
                self.assertNotEqual(row['purpose'], 'controlled_benchmark_pilot')
            validate_grid(published, [core], 'published')
            with self.assertRaises(ValueError):
                validate_grid(published, [core])
        with self.assertRaises(ValueError):
            expand_scenario(self.core, 'normal')

    def test_published_sources_require_traceable_provenance(self):
        for mutation in ('unresolved', 'missing_date', 'wrong_provider', 'unsupported_representation'):
            core = copy.deepcopy(self.core)
            if mutation == 'unresolved':
                core['published_policy']['source_ids'] = ['missing']
            elif mutation == 'missing_date':
                del core['source']['records'][0]['verified_on']
            elif mutation == 'wrong_provider':
                core['provider'] = 'Some other airline'
            else:
                core['published_policy']['representation'] = 'real_customer_data'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_scenario(core)

    def test_turkish_airlines_and_corrected_easyjet_fee(self):
        cores = {c['scenario_id']: c for c in self.cores}
        tk = cores['airlines_011_turkish_24h_refund']
        self.assertEqual(tk['provider'], 'Turkish Airlines')
        self.assertEqual(tk['scenario_provenance'], 'synthetic_customer_scenario')
        ej = cores['airlines_003_early_cancellation']
        self.assertEqual(ej['facts']['published_online_cancellation_fee_gbp'], 49)
        self.assertEqual(ej['facts']['booking_price_gbp'] - 49, 151)
        self.assertNotIn('EUR 40', str(ej['policy_variants']))

    def test_runner_and_build_support_published_policies(self):
        result = subprocess.run([sys.executable, str(ROOT / 'run_pilot.py'), '--domain', 'airlines',
                                 '--scenario', self.core['scenario_id'], '--policy-basis', 'published',
                                 '--emotion', 'neutral', '--dry-run'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('__published__', result.stdout)
        self.assertIn('Selected 1 prompts', result.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / 'dataset.py'), '--domain', 'airlines',
                                     '--policy-basis', 'published', '--output', tmp], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((Path(tmp) / 'reference_labels.jsonl').read_text(), '')
            self.assertEqual(len((Path(tmp) / 'prompts.jsonl').read_text().splitlines()), len(self.cores) * 4)

    def test_runner_consumes_core_and_shared_loader_without_loading_weights(self):
        for selection in [
            ['--domain', 'airlines', '--scenario', self.core['scenario_id']],
            ['--prompt', str(ROOT / 'data/airlines' / (self.core['scenario_id'] + '.json'))]]:
            result = subprocess.run([sys.executable, str(ROOT / 'run_pilot.py'), *selection,
                                     '--policy', 'exception', '--emotion', 'anger', '--dry-run'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Selected 1 prompts', result.stdout)
            self.assertIn(self.core['scenario_id'] + '__exception__anger', result.stdout)
            self.assertNotIn('Loading', result.stdout)

    def test_build_exports_current_inputs_and_separate_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / 'dataset.py'), '--domain', 'airlines',
                                     '--output', tmp], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            exported = list(map(json.loads, (Path(tmp) / 'prompts.jsonl').read_text().splitlines()))
            self.assertEqual(exported, self.prompts)
            manifest = json.loads((Path(tmp) / 'manifest.json').read_text())
            self.assertEqual(manifest['prompts_sha256'], digest(self.prompts))
            self.assertEqual(manifest['core_scenarios'], len(self.cores))
            references = list(map(json.loads, (Path(tmp) / 'reference_labels.jsonl').read_text().splitlines()))
            self.assertEqual(references, reference_rows(self.cores))


if __name__ == '__main__':
    unittest.main()
