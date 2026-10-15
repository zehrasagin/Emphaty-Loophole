"""Batch snapshots, per-model resume and failure bookkeeping without a GPU."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dataset import load_scenarios
from result_io import new_result_record, utc_timestamp
from run_all_experiments import export_run, latest_record, prepare_run, read_prompts, run_model, update_summary, write_json
from run_pilot import read_models


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name) / 'batch'
        sources = read_models()
        self.models = {k: sources[k] for k in ('standard', 'reasoning')}
        self.manifest, self.cases = prepare_run(self.folder, self.models, ['experimental'], load_scenarios('airlines')[:1])

    def tearDown(self):
        self.temp.cleanup()

    def test_frozen_inputs_and_no_reference_labels_in_prompts(self):
        self.assertEqual(self.manifest['planned_trials'], 24)
        self.assertEqual(read_prompts(self.folder, self.manifest), self.cases)
        self.assertTrue(json.loads((self.folder / 'experimental_references.json').read_text()))
        self.assertNotIn('expected_decision', str([c['messages'] for c in self.cases]))
        path = self.folder / 'prompts.jsonl'
        path.write_text(path.read_text().replace('Please process', 'Please change'))
        with self.assertRaisesRegex(ValueError, 'modified'):
            read_prompts(self.folder, self.manifest)

    def test_resume_does_not_confuse_models_incomplete_and_failed_trials(self):
        cases = self.cases[:2]
        manifest = {**self.manifest, 'planned_trials': 4, 'prompts_per_model': 2}
        mx = SimpleNamespace(clear_cache=lambda: None)
        modules = {'mlx': SimpleNamespace(core=mx), 'mlx.core': mx,
                   'mlx_lm': SimpleNamespace(load=lambda *a: (object(), object()))}
        calls = []
        statuses = iter(['incomplete', 'error', 'completed', 'completed', 'completed'])

        def generate(case, source, folder, model, tokenizer, settings):
            calls.append({**copy.deepcopy(case), 'attempt_directory': folder.name})
            record = new_result_record(case, source, settings, self.folder.name)
            status = next(statuses)
            record.update(status=status, finished_at=utc_timestamp(), final_answer='answer' if status == 'completed' else None,
                          truncated=status == 'incomplete', error='injected' if status == 'error' else None)
            folder.mkdir(parents=True)
            write_json(folder / 'result.json', record)
            return record

        with patch.dict('sys.modules', modules), patch('run_all_experiments.run_case', side_effect=generate):
            with self.assertRaisesRegex(RuntimeError, 'Generation failed'):
                run_model(self.folder, manifest, cases, 'standard')
            summary = update_summary(self.folder, manifest, cases)
            self.assertEqual(summary['status_counts'], {'incomplete': 1, 'error': 1})
            self.assertFalse(summary['all_generations_completed'])
            run_model(self.folder, manifest, cases, 'standard')
            self.assertEqual(calls[-1]['attempt_directory'], 'attempt_002')
            self.assertEqual(calls[-1]['prompt_id'], cases[1]['prompt_id'])
            self.assertEqual(len(calls), 3)
            run_model(self.folder, manifest, cases, 'reasoning')
            self.assertEqual(len(calls), 5)
            self.assertNotEqual(calls[0]['trial_id'], calls[3]['trial_id'])
            summary = update_summary(self.folder, manifest, cases)
            self.assertEqual(summary['status_counts'], {'incomplete': 1, 'completed': 3})
            self.assertTrue(summary['all_conditions_attempted'])
            self.assertFalse(summary['all_generations_completed'])
            run_model(self.folder, manifest, cases, 'reasoning')
            self.assertEqual(len(calls), 5)
            record = latest_record(self.folder, 'standard', cases[1])
            self.assertNotIn('attempt', record)
            self.assertNotIn('experiment_id', record)
            self.assertNotIn('model_key', record)
            self.assertEqual(len(list((self.folder / 'trials' / 'standard' / cases[1]['prompt_id']).glob('attempt_*/result.json'))), 2)
            export_run(self.folder, manifest)
            exported = json.loads((self.folder / 'all_trials.json').read_text())
            self.assertEqual(set(exported), {'collection_schema_version', 'created_at', 'updated_at', 'trial_count', 'trials'})
            self.assertEqual(exported['trial_count'], 5)
            self.assertEqual(sum(t['status'] == 'error' for t in exported['trials']), 1)
