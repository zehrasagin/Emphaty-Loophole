"""Preview JSON conditions or explore conversations using the shared dataset."""
import json
from pathlib import Path

import streamlit as st

from chat_backend import CHAT_ROOT, ChatEngine, model_ready, new_session, save_session, transcript
from dataset import DOMAIN_LABELS, EMOTIONS, POLICIES, POLICY_LABELS, load_cases, load_scenarios
from run_pilot import read_models

ROOT = Path(__file__).resolve().parent
LABELS = DOMAIN_LABELS
MODELS = {name: f"{source['model_id']} · {source['model_type']}" for name, source in read_models().items()}

st.set_page_config(page_title='Empathy Loophole · Chat Lab', page_icon='💬', layout='wide')


@st.cache_resource
def engine():
    return ChatEngine()


def show_turn(turn):
    with st.chat_message('user'):
        st.write(turn['user'])
    r = turn['result']
    with st.chat_message('assistant'):
        if r.get('final_answer'):
            st.write(r['final_answer'])
        else:
            st.warning('No complete final answer was produced. Retry the message or start a new conversation.')
        if r.get('error'):
            st.error(r['error'])
        if r.get('reasoning_trace'):
            with st.expander('Observable reasoning trace'):
                st.caption('A generated explanation, not definitive evidence of the internal decision process.')
                if not r.get('trace_complete'):
                    st.caption('This trace is incomplete.')
                st.text(r['reasoning_trace'])
        with st.expander('Response details'):
            st.caption(f"Status: {r['status']} · Parse: {r.get('parse_status', 'unavailable')} · Finish: {r.get('finish_reason', 'unavailable')}")
            st.text(r.get('raw_output', 'No output was generated.'))


with st.sidebar:
    st.title('Chat Lab')
    st.caption('THE EMPATHY LOOPHOLE')
    st.caption('Dataset: shared JSON scenarios')
    mode = st.selectbox('Mode', ['condition_preview', 'exploratory'],
                        format_func=lambda k: {'condition_preview': 'Condition preview (one turn)',
                                               'exploratory': 'Exploratory chat (multiple turns)'}[k])
    domain = st.selectbox('Domain', list(LABELS), index=1, format_func=LABELS.get)
    try:
        cores = load_scenarios(domain)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    airline = None
    if domain == 'airlines' and cores:
        airline = st.selectbox('Airline', list(dict.fromkeys(c['provider'] for c in cores)),
                               key='airline_selection')
        cores = [c for c in cores if c['provider'] == airline]
    bases = ['published', 'experimental'] if any('published_policy' in c for c in cores) else ['experimental']
    basis = st.selectbox('Policy basis', bases, key=f'basis_{domain}',
                         format_func=lambda k: {'published': 'Published policy summary',
                                                'experimental': 'Researcher-modified variants (3 × 4)'}[k])
    if st.session_state.get('catalog_selection') != (domain, airline, basis):
        st.session_state.catalog_selection = (domain, airline, basis)
        st.session_state.pop('selection', None)
        st.session_state.pop('pending', None)
    try:
        rows = load_cases(domain, policy_basis=basis)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    if airline is not None:
        rows = [r for r in rows if r['provider'] == airline]
    if not rows:
        st.info('No scenarios in this domain yet. Add a JSON scenario to its data folder.')
        st.stop()
    titles = {r['scenario_id']: r.get('title', r['scenario_id']) for r in rows}
    case_id = st.selectbox('Scenario', list(titles), format_func=titles.get,
                           key=f'core_{domain}_{airline}_{basis}')
    candidates = [r for r in rows if r['scenario_id']==case_id]
    policy = st.selectbox('Policy condition' if basis == 'experimental' else 'Source policy classification (draft)',
                          [p for p in POLICIES if any(r['policy_type']==p for r in candidates)],
                          format_func=POLICY_LABELS.get if basis == 'experimental' else str.title,
                          key=f'policy_{domain}_{basis}_{case_id}')
    emotion = st.selectbox('Emotional framing', [e for e in EMOTIONS if any(r['emotion']==e and r['policy_type']==policy for r in candidates)],
                           key=f'emotion_{domain}_{basis}_{case_id}')
    chosen = next(r for r in candidates if r['policy_type']==policy and r['emotion']==emotion)
    kind = st.selectbox('Assistant model', list(MODELS), format_func=MODELS.get)
    ready = model_ready(kind)
    if not ready:
        st.warning('Local model files are missing or incomplete. Select an available model.')
    reset = st.button('New conversation', use_container_width=True)

selection = (domain, airline, basis, case_id, policy, emotion, kind, mode, chosen.get('prompt_sha256'))
if reset or st.session_state.get('selection') != selection:
    st.session_state.selection = selection
    st.session_state.conversation = new_session(chosen, kind, mode)
    st.session_state.pop('pending', None)

# Finish any request already submitted before a Streamlit rerun.
if 'pending' in st.session_state:
    with st.spinner('The assistant is responding. The first message also loads the model…'):
        try:
            st.session_state.conversation = st.session_state.pending.result()
        except Exception as exc:
            st.error(str(exc))
        finally:
            del st.session_state.pending

session = st.session_state.conversation
case = session['scenario']
st.title('Customer-service simulation')
st.caption('Preview a single generated request, or choose Exploratory chat to write messages and follow up.')
st.markdown(f"**{LABELS.get(case['domain'], case['domain'])}** · {case['policy_type'].title()} policy · {MODELS[kind]}")
st.caption(f"{case['provider']} · {basis.title()} policy · Synthetic customer scenario · {case['validation_status']}")

with st.expander('Scenario and policy', expanded=not session['turns']):
    st.markdown('**Policy given to the assistant**')
    st.write(case['messages'][0]['content'])
    st.markdown('**Starting customer request**')
    st.write(case['messages'][1]['content'])
    for source in case.get('source', {}).get('records', []):
        provider = source.get('organization', source.get('airline', 'Source'))
        if source.get('url'):
            st.markdown(f"[Policy source: {provider} — {source.get('title', 'Policy')}]({source['url']}) · Checked {source.get('verified_on', source.get('accessed_on', 'unrecorded'))}")
        else:
            st.caption(source.get('description', source.get('title', 'Synthetic researcher-authored scenario')))
    if basis == 'published':
        st.caption('Scoped paraphrase of published policy. Human verification and classification review remain pending.')
    else:
        st.caption('Researcher-modified interventions. These variants are not the named provider’s official policies.')
    st.caption('Keep the scenario facts fixed when testing emotional framing. Free-form chat is exploratory and is saved separately from the controlled pilot runs.')

with st.sidebar:
    st.divider()
    st.caption('Changing domain, airline, policy basis, scenario, policy, emotion, model or mode starts a fresh conversation. All UI sessions are saved separately from runner results.')
    if session['turns']:
        st.download_button('Download conversation · JSON', json.dumps(session, indent=2, ensure_ascii=False),
                           file_name=f"{session['session_id']}.json", mime='application/json')
        st.download_button('Download transcript · Markdown', transcript(session),
                           file_name=f"{session['session_id']}.md", mime='text/markdown')
        st.caption(f"Saved to results/chat_sessions/{session['session_id']}/")

for turn in session['turns']:
    show_turn(turn)

starter = False
retry = False
if not session['turns']:
    st.info('Send the generated starting request. Exploratory chat also allows custom messages.')
    starter = st.button('Send starting request', type='primary', disabled=not ready)
elif not session['turns'][-1]['result'].get('final_answer'):
    retry = st.button('Retry last message', disabled=not ready)
    st.caption('Incomplete turns are retained in the log but excluded from the next model prompt.')

message = None
if mode == 'exploratory':
    message = st.chat_input('Write as the customer…', max_chars=12000, disabled=not ready,
                           submit_mode='disable', key=f"message_{session['session_id']}")
elif session['turns'] and session['turns'][-1]['result'].get('final_answer'):
    st.info('Condition preview is complete. Start a new conversation or choose Exploratory chat to follow up.')
if starter:
    message = case['messages'][1]['content']
elif retry:
    message = session['turns'][-1]['user']
if message and message.strip():
    try:
        st.session_state.pending = engine().submit(session, message)
        st.rerun()
    except (ValueError, RuntimeError) as exc:
        st.error(str(exc))
