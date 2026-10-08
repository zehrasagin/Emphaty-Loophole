"""Exercise Streamlit widgets and conversation flow without loading model weights."""
import copy
import importlib.util
import json
import unittest
from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from chat_backend import history_for
from dataset import DOMAIN_LABELS, load_scenarios

HAS_STREAMLIT = importlib.util.find_spec('streamlit') is not None
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_STREAMLIT, 'Install UI dependencies to run Streamlit tests')
class UITests(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        st.cache_resource.clear()
        self.app = AppTest.from_file(str(ROOT / 'chat_app.py'))

    def tearDown(self):
        import streamlit as st
        st.cache_resource.clear()

    def select(self, label, value):
        next(s for s in self.app.selectbox if s.label == label).select(value).run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.error)

    def click(self, label):
        next(b for b in self.app.button if b.label == label).click().run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.error)

    def test_domains_conditions_and_session_reset(self):
        self.app.run()
        active_domains = {c['domain'] for c in load_scenarios()}
        domain_widget = next(s for s in self.app.selectbox if s.label == 'Domain')
        self.assertEqual(set(domain_widget.options), {DOMAIN_LABELS[d] for d in active_domains})
        for domain in DOMAIN_LABELS:
            if domain not in active_domains:
                continue
            with self.subTest(domain=domain):
                self.select('Domain', domain)
                scenarios = next(s for s in self.app.selectbox if s.label == 'Scenario')
                self.assertEqual(len(scenarios.options), len(load_scenarios(domain)))
                before = self.app.session_state.conversation['session_id']
                self.select('Policy condition', 'exception')
                self.select('Emotional framing', 'distress')
                session = self.app.session_state.conversation
                self.assertNotEqual(before, session['session_id'])
                self.assertEqual(session['turns'], [])
                self.assertEqual(session['scenario']['policy_type'], 'exception')
                self.assertEqual(session['scenario']['emotion'], 'distress')
                self.assertIn('overwhelmed', session['scenario']['messages'][1]['content'])
                if domain in ('retail', 'telecom'):
                    self.assertEqual(session['scenario']['provider'], 'Amazon.nl' if domain == 'retail' else 'AT&T')
                    self.assertFalse(any('inactive policy draft' in w.value for w in self.app.warning))
                    self.select('Policy basis', 'published')
                    self.assertEqual(self.app.session_state.conversation['scenario']['policy_basis'], 'published')
                    self.assertEqual(len(next(s for s in self.app.selectbox if s.label == 'Emotional framing').options), 4)

    def test_preview_retry_exploration_and_downloads(self):
        contexts = []

        def respond(session, text):
            contexts.append(history_for(session, text))
            session = copy.deepcopy(session)
            complete = len(contexts) > 1
            session['turns'].append({'user': text, 'result': {
                'status': 'completed' if complete else 'incomplete',
                'parse_status': 'plain_standard_response' if complete else 'truncated_final',
                'final_answer': 'A completed response.' if complete else None,
                'raw_output': 'A completed response.' if complete else 'Partial',
            }})
            future = Future()
            future.set_result(session)
            return future

        with patch('chat_backend.ChatEngine', return_value=SimpleNamespace(submit=respond)), \
                patch('chat_backend.model_ready', return_value=True):
            self.app.run()
            self.click('Send starting request')
            self.assertIsNone(self.app.session_state.conversation['turns'][0]['result']['final_answer'])
            self.click('Retry last message')
            session = self.app.session_state.conversation
            self.assertEqual(len(session['turns']), 2)
            self.assertEqual(contexts[0], contexts[1])
            self.assertEqual(len(contexts[1]), 2)
            self.assertTrue(any('Condition preview is complete' in i.value for i in self.app.info))
            self.assertEqual(len(self.app.get('download_button')), 2)
            self.select('Mode', 'exploratory')
            self.assertEqual(self.app.session_state.conversation['turns'], [])
            self.click('Send starting request')
            self.app.chat_input[0].set_value('Please explain the decision.').run()
            self.assertFalse(self.app.exception)
            self.assertFalse(self.app.error)
            self.assertEqual(len(self.app.session_state.conversation['turns']), 2)
            self.assertEqual([m['role'] for m in contexts[-1]], ['system', 'user', 'assistant', 'user'])
            self.click('New conversation')
            self.assertEqual(self.app.session_state.conversation['turns'], [])

    def test_shared_policy_topics_show_declared_catalog_and_empty_coverage(self):
        self.app.run()
        for domain, covered in (('telecom', 'data_allowance'), ('retail', 'voluntary_returns')):
            with self.subTest(domain=domain):
                self.select('Domain', domain)
                policy = json.loads((ROOT / 'data' / domain / f'policy_{domain}.json').read_text())
                topic_widget = next(s for s in self.app.selectbox if s.label == 'Policy topic')
                self.assertEqual(len(topic_widget.options), len(policy['policy_topics']) + 1)
                for topic in policy['policy_topics']:
                    self.assertTrue(any(option.startswith(topic.replace('_', ' ').title()) for option in topic_widget.options))
                previous = self.app.session_state.conversation['session_id']
                for topic in policy['policy_topics']:
                    self.select('Policy topic', topic)
                    if topic == covered:
                        self.assertEqual(self.app.session_state.conversation['scenario']['policy_topic'], topic)
                    else:
                        self.assertTrue(any(f"No scenarios for {topic.replace('_', ' ').title()} yet" in i.value for i in self.app.info))
                        self.assertFalse(any(s.label == 'Scenario' for s in self.app.selectbox))
                        self.assertFalse(any(b.label == 'Send starting request' for b in self.app.button))
                        self.assertNotIn('conversation', self.app.session_state)
                self.select('Policy basis', 'published')
                self.assertTrue(any('No scenarios for' in i.value for i in self.app.info))
                self.select('Policy topic', covered)
                session = self.app.session_state.conversation
                self.assertNotEqual(previous, session['session_id'])
                self.assertEqual(session['scenario']['policy_basis'], 'published')
                self.select('Policy topic', None)
                self.assertEqual(self.app.session_state.conversation['scenario']['policy_topic'], covered)
        self.select('Domain', 'airlines')
        self.select('Policy topic', 'refunds')
        self.assertEqual(self.app.session_state.conversation['scenario']['policy_topic'], 'refunds')
        self.select('Domain', 'customer_support')
        topics = next(s for s in self.app.selectbox if s.label == 'Policy topic').options
        self.assertFalse(any('no scenarios yet' in topic for topic in topics))


if __name__ == '__main__':
    unittest.main()
