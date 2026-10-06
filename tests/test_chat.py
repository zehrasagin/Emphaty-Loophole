import copy
import json
import tempfile
import unittest
from pathlib import Path

from chat_backend import history_for, new_session, save_session
from dataset import load_cases
from prompting import effective_messages
from trace_parser import parse_output

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
