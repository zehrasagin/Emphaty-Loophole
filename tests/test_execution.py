"""Exercise the shared runner without loading weights or requiring a GPU."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from dataset import load_cases
from run_pilot import read_source, run_case


class ExecutionTests(unittest.TestCase):
    def test_outputs_and_interrupted_generation_are_preserved(self):
        source = read_source('reasoning')
        case = load_cases('airlines')[0]
        model = SimpleNamespace(parameters=lambda: {'model': {'embed_tokens': {'weight': SimpleNamespace(dtype='test')}}})
        tokenizer = SimpleNamespace(
            apply_chat_template=lambda messages, **kw: messages[0]['content'] + '\n<think>',
            encode=lambda text, **kw: [1, 2], chat_template='test template')
        mx = SimpleNamespace(random=SimpleNamespace(seed=lambda n: None), reset_peak_memory=lambda: None)
        samples = SimpleNamespace(make_sampler=lambda **kw: None)
        for kind, raw, finish, expected in [
                ('standard', 'No refund.\r\nThank you.', 'stop', 'plain_standard_response'),
                ('reasoning', 'Rule applies.\n</think>\nNo refund.', 'stop', 'parsed'),
                ('reasoning', 'Rule applies.', 'length', 'truncated_trace'),
                ('reasoning', 'Règle applies.\r\n', 'error', 'generation_error')]:
            def generate(*args, **kwargs):
                yield SimpleNamespace(text=raw, token=10, finish_reason=finish,
                                      generation_tokens=1, peak_memory=0.0)
                if finish == 'error':
                    raise RuntimeError('injected interruption')
            modules = {'mlx': SimpleNamespace(core=mx), 'mlx.core': mx,
                       'mlx_lm': SimpleNamespace(stream_generate=generate), 'mlx_lm.sample_utils': samples}
            with self.subTest(kind=kind, finish=finish), tempfile.TemporaryDirectory() as tmp:
                with patch.dict('sys.modules', modules), patch('run_pilot.version', return_value='test'):
                    result = run_case(case, {**source, 'model_type': kind}, Path(tmp), model, tokenizer,
                                      source['generation_settings'])
                saved = json.loads((Path(tmp) / 'result.json').read_text())
                self.assertEqual(result['raw_output'], raw)
                self.assertEqual(saved['raw_output'], raw)
                self.assertEqual((Path(tmp) / 'raw_output.txt').read_bytes(), raw.encode())
                self.assertEqual(result['parse_status'], expected)
                self.assertTrue(result['run_id'])
                self.assertTrue(result['trial_id'])
                self.assertEqual(result['model_revision'], source['revision'])
                self.assertNotIn('expected_decision', str(result['effective_messages']))
                if finish in ('error', 'length'):
                    self.assertIsNone(result['final_answer'])
                    self.assertTrue(result['trace_available'])
                if finish == 'error':
                    self.assertIn('injected interruption', result['error'])
                with self.assertRaises(FileExistsError):
                    run_case(case, source, Path(tmp), model, tokenizer, source['generation_settings'])
                self.assertEqual((Path(tmp) / 'raw_output.txt').read_bytes(), raw.encode())
                self.assertEqual(json.loads((Path(tmp) / 'result.json').read_text()), saved)


if __name__ == '__main__':
    unittest.main()
