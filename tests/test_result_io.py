"""Check durable aggregation across independent trials and simultaneous writers."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from result_io import append_trial_record, read_trial_collection


def trial(index):
    return {'trial_id': f'trial_{index}', 'run_id': f'run_{index}',
            'scenario_id': f'scenario_{index}', 'model_id': f'model_{index % 2}',
            'timestamp_utc': '2026-10-12T12:00:00.123456+00:00',
            'finished_at': '2026-10-12T12:00:01.123456+00:00',
            'status': 'completed', 'raw_output': 'Original response.\r\n£15',
            'final_answer': 'Original response.\r\n£15'}


class CollectionTests(unittest.TestCase):
    def test_simultaneous_trials_and_duplicates_preserve_all_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'all_trials.json'
            records = [trial(i) for i in range(12)]
            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(lambda r: append_trial_record(r, path), records + records))
            saved = read_trial_collection(path)
            self.assertEqual(saved['trial_count'], len(records))
            self.assertEqual({t['trial_id']: t for t in saved['trials']},
                             {t['trial_id']: t for t in records})
            self.assertTrue(saved['created_at'])
            self.assertTrue(saved['updated_at'])
            self.assertFalse(path.with_suffix('.json.tmp').exists())
            self.assertEqual(read_trial_collection(path), saved)

    def test_conflicting_ids_and_invalid_collections_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'all_trials.json'
            record = trial(1)
            append_trial_record(record, path)
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Conflicting'):
                append_trial_record({**record, 'raw_output': 'Changed'}, path)
            self.assertEqual(path.read_bytes(), original)
            path.write_text('{broken JSON', encoding='utf-8')
            with self.assertRaises(json.JSONDecodeError):
                append_trial_record(trial(2), path)
            self.assertEqual(path.read_text(), '{broken JSON')

    def test_in_progress_trials_are_not_added(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'all_trials.json'
            with self.assertRaises(ValueError):
                append_trial_record({**trial(1), 'finished_at': None}, path)
            self.assertEqual(read_trial_collection(path)['trial_count'], 0)
            self.assertFalse(path.exists())
