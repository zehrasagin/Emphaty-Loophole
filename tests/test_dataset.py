import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dataset import (DOMAIN_LABELS, EMOTIONS, POLICIES, digest, expand_scenario,
                     load_cases, load_scenarios, load_shared_policy, reference_rows, validate_grid, validate_scenario)
from prompting import EMOTION_LABELS, FRAMES, render_messages

ROOT = Path(__file__).resolve().parents[1]


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.cores = load_scenarios('airlines')
        self.core = self.cores[0]
        self.prompts = load_cases('airlines')

    def test_one_core_expands_to_all_unique_policy_emotion_conditions(self):
        prompts = expand_scenario(self.core)
        expected_count = len(POLICIES) * len(EMOTIONS)
        self.assertEqual(len(prompts), expected_count)
        self.assertEqual(len({p['prompt_id'] for p in prompts}), expected_count)
        self.assertEqual({(p['policy_type'], p['emotion']) for p in prompts},
                         {(p, e) for p in POLICIES for e in EMOTIONS})
        self.assertEqual(len(self.prompts), len(self.cores) * expected_count)
        self.assertEqual(set(DOMAIN_LABELS), {'retail', 'airlines', 'hotels', 'telecom', 'customer_support'})
        for core in self.cores:
            group = [p for p in self.prompts if p['scenario_id'] == core['scenario_id']]
            self.assertEqual(len({p['facts_sha256'] for p in group}), 1)
            for emotion in EMOTIONS:
                self.assertEqual(len({p['messages'][1]['content'] for p in group if p['emotion'] == emotion}), 1)
            for policy in POLICIES:
                self.assertEqual(len({p['messages'][0]['content'] for p in group if p['policy_type'] == policy}), 1)

    def test_emotional_frames_are_named_and_standardized_across_domains(self):
        self.assertEqual(set(EMOTION_LABELS), set(EMOTIONS))
        self.assertEqual(set(FRAMES), set(EMOTIONS))
        for emotion in EMOTIONS:
            rendered_frames = set()
            for domain in ('airlines', 'customer_support', 'hotels', 'retail', 'telecom'):
                if domain == 'retail':
                    retail_dir = ROOT / 'data' / domain
                    scenario_path = next(p for p in retail_dir.glob('*.json')
                                         if p.name not in ('_policy.json', 'policy_retail.json'))
                    _, shared_policy = load_shared_policy(retail_dir)
                    core = {**shared_policy, **json.loads(scenario_path.read_text())}
                else:
                    core = load_scenarios(domain)[0]
                policy = POLICIES[0]
                user_message = render_messages(core, policy, emotion)[1]['content']
                rendered_frames.add(user_message.rsplit('\n\n', 1)[-1])
            self.assertEqual(rendered_frames, {FRAMES[emotion]})

    def test_current_catalog_uses_new_policies_without_legacy_mock_scenarios(self):
        cores = load_scenarios()
        self.assertEqual({c['domain'] for c in cores}, {'airlines', 'customer_support', 'telecom', 'retail', 'hotels'})
        self.assertEqual({c.get('provider', c.get('fictional_provider')) for c in cores},
                         {'easyJet', 'Uber Eats', 'AT&T', 'Amazon.nl', 'easyHotel'})
        self.assertFalse(any('Northstar' in str(p['messages']) for p in load_cases()))
        self.assertEqual(len(load_scenarios('hotels')), 10)
        self.assertNotIn('support_warranty_001', {c['scenario_id'] for c in cores})
        self.assertEqual(len(load_cases()), len(cores) * len(POLICIES) * len(EMOTIONS))
        for domain, provider in (('retail', 'Amazon.nl'), ('telecom', 'AT&T'),
                                 ('customer_support', 'Uber Eats')):
            core = load_scenarios(domain)[0]
            path, policy = load_shared_policy(ROOT / 'data' / domain)
            self.assertEqual(path.name, '_policy.json' if domain == 'customer_support' else f'policy_{domain}.json')
            self.assertEqual(core['provider'], provider)
            self.assertEqual(core['policy_id'], policy['policy_id'])
            self.assertEqual(core['policy_record_sha256'], digest(policy))
            self.assertEqual(core['policy_variants'], policy['policy_variants'])
            self.assertEqual(len(load_cases(domain, policy_basis='published')),
                             len(load_scenarios(domain)) * len(EMOTIONS))
            self.assertEqual(len(reference_rows([core])), len(POLICIES) * len(EMOTIONS))

    def test_named_policy_discovery_rejects_malformed_documents(self):
        policy = json.loads((ROOT / 'data/telecom/policy_telecom.json').read_text())
        for mutation in ('domain', 'policy_id', 'policy_variants', 'scenario_id', 'invalid_json'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / 'telecom'
                folder.mkdir()
                draft = copy.deepcopy(policy)
                draft[mutation] = 'invalid value'
                (folder / 'policy_telecom.json').write_text('{' if mutation == 'invalid_json' else json.dumps(draft))
                with self.assertRaises(ValueError):
                    load_scenarios('telecom', tmp)

    def test_named_policies_reject_overrides_wrong_references_and_duplicate_bundles(self):
        raw = json.loads((ROOT / 'data/telecom/telecom_data_001.json').read_text())
        policy = json.loads((ROOT / 'data/telecom/policy_telecom.json').read_text())
        for mutation in ('provider', 'policy_variants', 'missing_reference', 'wrong_reference', 'duplicate_bundle'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / 'telecom'
                folder.mkdir()
                core = copy.deepcopy(raw)
                if mutation in ('provider', 'policy_variants'):
                    core[mutation] = policy[mutation]
                elif mutation == 'missing_reference':
                    del core['policy_id']
                elif mutation == 'wrong_reference':
                    core['policy_id'] = 'another_policy'
                elif mutation == 'duplicate_bundle':
                    (folder / '_policy.json').write_text(json.dumps(policy))
                (folder / 'policy_telecom.json').write_text(json.dumps(policy))
                (folder / 'telecom_data_001.json').write_text(json.dumps(core))
                with self.assertRaises(ValueError):
                    load_cases('telecom', tmp)

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
            render_messages(self.core, 'strict', 'unlisted')
        original = dict(FRAMES)
        try:
            FRAMES.pop('sadness')
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
            raw = json.loads((ROOT / 'data/airlines' / (self.core['scenario_id'] + '.json')).read_text())
            (folder / '_policy.json').write_bytes((ROOT / 'data/airlines/_policy.json').read_bytes())
            (folder / (raw['scenario_id'] + '.json')).write_text(json.dumps(raw))
            self.assertEqual(len(load_cases(data_root=Path(tmp))), len(POLICIES) * len(EMOTIONS))
            new = copy.deepcopy(raw)
            new['scenario_id'] = 'airline_011'
            (folder / 'airline_011.json').write_text(json.dumps(new))
            self.assertEqual(len(load_cases(data_root=Path(tmp))), 2 * len(POLICIES) * len(EMOTIONS))
            retail = Path(tmp) / 'retail'
            retail.mkdir()
            new = json.loads((ROOT / 'archive/mock_pilots_before_v08/retail/retail_return_001.json').read_text())
            new['scenario_id'] = 'retail_002'
            (retail / 'retail_002.json').write_text(json.dumps(new))
            self.assertEqual(len(load_cases(data_root=Path(tmp))), 3 * len(POLICIES) * len(EMOTIONS))
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
        archived_cores = load_scenarios('airlines', ROOT / 'archive/multi_airline_baseline_v04')
        refs = {r['prompt_id']: r for r in reference_rows(archived_cores)}
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
        archived_cores = load_scenarios('airlines', ROOT / 'archive/multi_airline_baseline_v04')
        baseline = expand_scenario(archived_cores[0])[0]
        pilot = json.loads((ROOT / 'archive/previous_dataset/pilot_prompts/airline_refund_001.json').read_text())
        self.assertNotEqual(baseline['messages'], pilot['messages'])
        self.assertEqual(pilot['source_core_scenario_id'], baseline['scenario_id'])

    def test_published_policy_has_all_emotions_and_separate_ids(self):
        for core in self.cores:
            published = expand_scenario(core, 'published')
            self.assertEqual(len(published), len(EMOTIONS))
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

    def test_previous_turkish_airlines_and_corrected_easyjet_fee_are_archived(self):
        cores = {c['scenario_id']: c for c in load_scenarios('airlines', ROOT / 'archive/multi_airline_baseline_v04')}
        tk = cores['airlines_011_turkish_24h_refund']
        self.assertEqual(tk['provider'], 'Turkish Airlines')
        self.assertEqual(tk['scenario_provenance'], 'synthetic_customer_scenario')
        ej = cores['airlines_003_early_cancellation']
        self.assertEqual(ej['facts']['published_online_cancellation_fee_gbp'], 49)
        self.assertEqual(ej['facts']['booking_price_gbp'] - 49, 151)
        self.assertNotIn('EUR 40', str(ej['policy_variants']))

    def test_airline_cases_share_one_company_and_identical_policy_wording(self):
        self.assertEqual({c['provider'] for c in self.cores}, {'easyJet'})
        self.assertEqual(len({c['policy_id'] for c in self.cores}), 1)
        self.assertEqual(len({c['base_rule'] for c in self.cores}), 1)
        self.assertEqual(len({c['policy_record_sha256'] for c in self.cores}), 1)
        self.assertEqual(len({digest(c['facts']) for c in self.cores}), len(self.cores))
        for policy in POLICIES:
            self.assertEqual(len({p['messages'][0]['content'] for p in self.prompts if p['policy_type'] == policy}), 1)
        self.assertTrue(any(c['evaluation']['exception_applies'] for c in self.cores))
        self.assertTrue(any(not c['evaluation']['exception_applies'] for c in self.cores))
        self.assertTrue(any(c['evaluation']['base_allows_request'] for c in self.cores))
        for prompt in self.prompts:
            self.assertEqual(prompt['policy_id'], self.core['policy_id'])
            self.assertEqual(prompt['policy_record_sha256'], self.core['policy_record_sha256'])

    def test_shared_policy_rejects_overrides_missing_reference_and_invalid_variants(self):
        original = json.loads((ROOT / 'data/airlines' / (self.core['scenario_id'] + '.json')).read_text())
        policy = json.loads((ROOT / 'data/airlines/_policy.json').read_text())
        for mutation in ('provider', 'policy_variants', 'policy_topics', 'wrong_reference', 'missing_reference', 'missing_policy_file', 'missing_variant'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / 'airlines'
                folder.mkdir()
                raw, shared = copy.deepcopy(original), copy.deepcopy(policy)
                if mutation == 'provider':
                    raw['provider'] = 'A different company'
                elif mutation == 'policy_variants':
                    raw['policy_variants'] = self.core['policy_variants']
                elif mutation == 'policy_topics':
                    raw['policy_topics'] = ['different_topic']
                elif mutation == 'wrong_reference':
                    raw['policy_id'] = 'another_policy'
                elif mutation == 'missing_reference':
                    del raw['policy_id']
                elif mutation == 'missing_variant':
                    del shared['policy_variants']['exception']
                if mutation != 'missing_policy_file':
                    (folder / '_policy.json').write_text(json.dumps(shared))
                (folder / (raw['scenario_id'] + '.json')).write_text(json.dumps(raw))
                with self.assertRaises(ValueError):
                    load_scenarios(data_root=Path(tmp))

    def test_shared_policy_review_cannot_be_bypassed_by_a_scenario(self):
        core = copy.deepcopy(self.core)
        core['validation_status'] = 'human_validated'
        core['human_review'] = {'reviewer': 'test reviewer', 'facts_equivalent': True,
                                'emotion_validated': True, 'policy_validated': True, 'references_validated': True}
        with self.assertRaisesRegex(ValueError, 'shared policy must also be human validated'):
            validate_scenario(core)

    def test_topics_are_shared_metadata_without_changing_policy_wording(self):
        self.assertEqual({c['policy_topic'] for c in self.cores}, set(self.core['policy_topics']))
        for row in self.prompts:
            core = next(c for c in self.cores if c['scenario_id'] == row['scenario_id'])
            self.assertEqual(row['policy_topic'], core['policy_topic'])
        for topic in (None, '', 'unknown_topic', 12):
            core = copy.deepcopy(self.core)
            core['policy_topic'] = topic
            with self.subTest(topic=topic), self.assertRaisesRegex(ValueError, 'policy_topic'):
                validate_scenario(core)
        for topics in ([], ['cabin_baggage', 'cabin_baggage'], [''], [12]):
            core = copy.deepcopy(self.core)
            core['policy_topics'] = topics
            with self.subTest(topics=topics), self.assertRaisesRegex(ValueError, 'policy_topics'):
                validate_scenario(core)

    def test_refund_cases_keep_fees_timing_and_facts_controlled(self):
        refunds = [c for c in self.cores if c.get('policy_topic') == 'refunds']
        self.assertTrue(refunds)
        self.assertEqual({c['evaluation']['exception_applies'] for c in refunds}, {True, False})
        for core in refunds:
            facts = core['facts']
            self.assertEqual(facts['booking_price_gbp'] - facts['online_cancellation_fee_gbp'],
                             facts['refund_amount_requested_gbp'])
            self.assertGreaterEqual(facts['hours_until_first_departure'], 2)
            self.assertEqual(core['evaluation']['exception_applies'], facts['hours_since_purchase'] <= 24)
            rows = expand_scenario(core)
            self.assertEqual(len(rows), len(POLICIES) * len(EMOTIONS))
            self.assertEqual(len({r['facts_sha256'] for r in rows}), 1)
            for reference in core['evaluation']['reference_decisions'].values():
                self.assertIn('waive_cancellation_fee', reference['forbidden_actions'])

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
            self.assertEqual(len((Path(tmp) / 'prompts.jsonl').read_text().splitlines()),
                             len(self.cores) * len(EMOTIONS))

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
        with tempfile.TemporaryDirectory() as tmp:
            row = next(p for p in self.prompts if p['policy_type'] == 'exception' and p['emotion'] == 'anger')
            path = Path(tmp) / 'expanded.json'
            path.write_text(json.dumps(row))
            result = subprocess.run([sys.executable, str(ROOT / 'run_pilot.py'), '--prompt', str(path), '--dry-run'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(row['prompt_id'], result.stdout)

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
