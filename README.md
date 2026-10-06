# The Empathy Loophole

**How Emotional Pressure Affects Policy Compliance in Standard and Reasoning LLMs.**

This repository lets our research team author customer-service scenarios, generate controlled prompts, run local language models, and inspect their outputs. There is also a Streamlit chatbot for trying scenarios interactively.

If you are joining the project, start with the setup below, read one scenario JSON, and follow the code map. **Adding a scenario normally means adding one JSON file, without changing Python.**

```text
data/<domain>/<scenario>.json
    → dataset.py: load, validate, expand conditions
    → prompting.py: construct model-facing messages
    → run_pilot.py: execute a local model
    → raw_output.txt: preserve generated text
    → trace_parser.py: extract observable trace and final answer
    → result.json: save the complete trial record

chat_app.py → chat_backend.py → the same dataset, prompting and execution code
                              → separate interactive session logs
```

## 1. Start here

Open a terminal in the project folder. Commands in this README assume that is your current directory.

### Inspect and validate without downloading models

With Python 3.10 or newer, these commands use only the standard library:

```bash
python3 dataset.py
python3 -m unittest discover -s tests -v
python3 run_pilot.py --domain airlines --scenario airlines_011_turkish_24h_refund --policy-basis published --emotion neutral --dry-run
```

The first command checks the JSON dataset. The tests check expansion, validation, parsing, execution bookkeeping and chat isolation using small examples and simulated generation. The dry run lists the selected condition; it does not load weights or generate an answer.

Current data contains **15 core scenarios: 11 airline cases and one in each of the other four domains**. Validation currently reports **180 experimental prompts**, or **44 published-policy prompts** when selecting airlines with the published basis. These counts grow automatically as teammates add files. All current scenarios are research drafts awaiting human review.

### Set up the model runner and chatbot

Local generation currently uses **MLX on an Apple Silicon Mac**. Teammates on other platforms can author scenarios, validate the dataset and run dry runs; a different execution backend would require code changes.

If this computer already has the project's `.venv`, activate it:

```bash
source .venv/bin/activate
```

On a new compatible Mac, create your own environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The configured model weights must also be available locally at the paths in [model_config.json](model_config.json). Installing dependencies does not install weights. Agree model snapshots with the team and record their revisions; the runner does not download missing models automatically.

When sharing the project, include source files, `data/`, `tests/`, configuration and documentation. `.venv/` is specific to a computer; `models/` and `results/` are excluded by `.gitignore` and must be shared separately if needed. Preserve `archive/` as research history rather than editing it as active data.

## 2. Where everything lives

```text
.
├── data/                           # active source: one JSON per core scenario
│   ├── airlines/                   # currently eleven cases across six airlines
│   ├── retail/retail_return_001.json
│   ├── hotels/hotel_cancellation_001.json
│   ├── telecom/telecom_data_001.json
│   └── customer_support/support_warranty_001.json
├── dataset.py                      # loading, validation, expansion/build CLI
├── prompting.py                    # shared emotion frames and prompt construction
├── run_pilot.py                    # controlled runs and shared execution function
├── trace_parser.py                 # observable trace/final-answer extraction
├── chat_backend.py                 # chat history, model worker and session logs
├── chat_app.py                     # Streamlit interface
├── model_config.json               # model IDs, local paths, revisions and settings
├── requirements.txt                # pinned model/UI dependencies
├── tests/
│   ├── test_dataset.py              # condition grid, sources and prompt controls
│   ├── test_execution.py            # parser and result/raw-output handling
│   └── test_chat.py                 # fresh sessions and exploratory history
├── README.md                       # this onboarding guide
├── .gitignore                      # excludes environments, weights and outputs
├── archive/                        # earlier data, exports, documents and baseline
├── models/                         # local weights; not bundled with source
└── results/                        # generated datasets, runs, chat logs and history
```

### Read the code in this order

| Start with | Key functions | What to understand |
| --- | --- | --- |
| [One airline JSON](data/airlines/airlines_011_turkish_24h_refund.json) | No Python required | Shared facts/request, policies, provider and sources |
| [dataset.py](dataset.py) | `load_scenarios`, `validate_scenario`, `expand_scenario`, `load_cases` | Discover JSON, reject invalid inputs, expand cores into conditions |
| [prompting.py](prompting.py) | `FRAMES`, `render_messages`, `effective_messages` | Construct messages and adapt them to reasoning-model templates |
| [run_pilot.py](run_pilot.py) | `main`, `read_models`, `run_case` | Select conditions, load a model once, save raw text and results |
| [trace_parser.py](trace_parser.py) | `parse_output` | Separate observable trace and final answer, preserving raw output |
| [chat_backend.py](chat_backend.py), then [chat_app.py](chat_app.py) | `new_session`, `history_for`, `ChatEngine`; UI selectors | Reuse the pipeline while keeping interactive sessions separate |

**`run_pilot.py` is the entry point for controlled experiments.** `dataset.py` builds or validates data; it does not run models. `chat_app.py` is the interactive entry point.

For example, `load_cases('airlines')` loads each airline JSON, calls `expand_scenario`, and returns condition dictionaries containing `messages` and metadata. The runner selects those dictionaries and passes each to `run_case`. The chatbot selects from the same dictionaries and uses `run_case` through its worker.

## 3. Research design and policy choices

The planned benchmark is **50 core scenarios × 3 policies × 4 emotions = 600 prompts per model**, across `retail`, `airlines`, `hotels`, `telecom` and `customer_support`. The code does not require ten scenarios per domain.

| Experimental condition | Construction |
| --- | --- |
| `strict` | The normal/base rule with no discretionary exceptions |
| `exception` | The same rule plus a narrow, explicit exception, checkable from the shared facts |
| `ambiguous` | The same rule plus vague discretion, such as consideration of exceptional circumstances |

There is no fourth `normal` condition. Each variant retains the same `base_rule` verbatim and adds its condition clause. The four emotions are `neutral`, `anger`, `distress` and `guilt`.

### Published policies versus experimental variants

Airline cases use real airline names and official sources, but their customer facts are **synthetic research cases**, not collected passenger records. The other four current domain pilots still use fictional providers and synthetic policies.

| Policy basis | Policy text used | Prompts per core | Purpose |
| --- | --- | --- | --- |
| `experimental` | Researcher-modified strict/exception/ambiguous variants | 12: three policies × four emotions | Matched factorial experiment |
| `published` | One scoped paraphrase of the published source policy | 4: one policy × four emotions | Separate source-grounded pilot |

`published` is a source-selection option, not a fourth policy condition. The CLI defaults to `experimental`; the chatbot starts with `published` where summaries exist. Use `--policy-basis` explicitly when recording runs.

**Why does the chatbot sometimes show only “Exception” as the source policy?** A published summary has one draft classification in `published_policy.policy_type`. If its provisions include an explicit exception, its current classification may be `exception`. That label does not mean the customer qualifies, and it does not create three official versions of the source. Real policies may mix firm rules, exceptions and discretion, so classifications need team review. Choose **Researcher-modified variants (3 × 4)** to access all three experimental conditions.

Experimental messages identify the policy as a researcher-modified intervention. Removing an official exception or adding discretion must not be described as an airline's actual policy. Published and experimental results are saved separately and should not be pooled as one balanced experiment.

## 4. How one JSON becomes twelve prompts

For `airlines_011_turkish_24h_refund.json`, experimental expansion crosses:

```text
strict    × neutral, anger, distress, guilt
exception × neutral, anger, distress, guilt
ambiguous × neutral, anger, distress, guilt
```

Each row gets a stable ID:

```text
scenario_id: airlines_011_turkish_24h_refund
prompt_id:   airlines_011_turkish_24h_refund__strict__neutral
```

The system message contains the provider, selected policy and task instructions. The user message is:

```text
facts_text + shared request + FRAMES[selected emotion]
```

The structured `facts` support review and metadata; **`facts_text` is the fact description the model actually reads**. Keep them consistent. Sources and evaluation references are retained for research use; expected decisions are never included in model messages.

Inspect the expansion without a model:

```python
from dataset import load_scenarios, expand_scenario

core = next(c for c in load_scenarios('airlines')
            if c['scenario_id'] == 'airlines_011_turkish_24h_refund')
cases = expand_scenario(core)  # default: experimental
assert len(cases) == 12
print(cases[0]['prompt_id'])
print(cases[0]['messages'])
```

Published IDs include a marker, for example `airlines_011_turkish_24h_refund__published__exception__neutral`.

**Emotion must change framing, not eligibility.** Edit the four global strings in `prompting.py` to change emotional wording. Do not introduce illness, bereavement, defects, disruption or financial eligibility through an emotion frame unless those facts are shared by every condition. Do not put domain-specific facts in global frames.

## 5. Scenario fields and adding your own case

Use the complete [Turkish Airlines case](data/airlines/airlines_011_turkish_24h_refund.json) as the real-source example, or [retail_return_001.json](data/retail/retail_return_001.json) as the simpler synthetic example. Keep one core per `data/<domain>/<scenario_id>.json`; the filename must match the ID.

| Field | What the scenario author supplies |
| --- | --- |
| `scenario_id`, `domain`, `title` | Unique lowercase ID with digits/underscores, one of the five domains, readable title |
| `provider`, `provider_type` | Provider name and `real` or `fictional` |
| `scenario_provenance` | `synthetic_customer_scenario` for authored customer cases |
| `facts`, `facts_text` | Nonempty structured facts and matching model-facing prose |
| `request` | One requested action, shared across all conditions |
| `base_rule` | Common rule, retained as the exact prefix of every experimental variant |
| `policy_variants` | Exactly `strict`, `exception`, `ambiguous`; three distinct full texts |
| `source` | `policy_provenance: researcher_authored_experimental_variants` and nonempty `records` with unique `source_id` values |
| `published_policy` | Optional source summary; needed to include the core in published-mode runs |
| `validation_status` | Start with `draft_pending_human_review` |
| `human_review` | Reviewer and facts/emotion/policy/reference review checks |
| `adaptation_note`, `review_notes` | Explain interventions, source scope and unresolved issues |
| `evaluation` | Optional experimental reference decisions; excluded from prompts |

`schema_version` is informative. Older non-airline pilots use `fictional_provider`; the loader accepts it for compatibility. For new records, prefer `provider` with `provider_type`. A real provider must match the organizations in its sources and explicitly identify the customer case as synthetic.

For `published_policy`, copy the example's structure: `text`, `policy_type`, `source_ids`, `representation: scoped_paraphrase_of_published_policy`, and `verification_status: official_source_checked_pending_human_review`. Referenced sources need URLs and `verified_on` dates. `source.policy_provenance` describes the experimental variants, even when a separate published summary is present.

### Teammate workflow

1. Choose a unique ID in your assigned domain and copy an appropriate JSON into that domain folder. Rename both the file and `scenario_id`.
2. Replace the title, provider, facts, `facts_text`, request, common rule and all three variants. Check exception eligibility against the fixed facts.
3. Replace provenance records and source IDs. For a real policy, inspect the official source, record its date/scope, and author a faithful published summary separately from experimental interventions.
4. Reset copied human-review fields to `null` and status to draft. Remove or re-author copied evaluation references; do not inherit another case's expected decisions.
5. Run validation, tests and a dry run for the new ID. Obtain another teammate's review of facts, policy comparability and emotional framing before main-study collection.

For example, adding `data/hotels/hotel_002.json` with `scenario_id: hotel_002` makes it discoverable by runner and chatbot. No registration step or Python edit is needed. This applies to scenarios in the existing five domains; a sixth research domain would require a design and code change.

Keep generated JSON, exports and source snapshots outside `data/`. The validator rejects misplaced JSON, mismatched filenames, missing fields, duplicate IDs, invalid domains and incomplete condition grids. It checks rendering and hashes, but cannot establish semantic agreement between facts/prose or the quality of emotional manipulations.

Only use `human_validated` once a reviewer is recorded and `facts_equivalent`, `emotion_validated`, `policy_validated`, `references_validated` are all `true`. Automated checks do not confer human validation.

## 6. Validate and build the dataset

After activating the environment, use `python` for the commands below:

```bash
python dataset.py
python dataset.py --domain airlines
python dataset.py --domain airlines --policy-basis published
python -m unittest discover -s tests -v
```

To export expanded data:

```bash
python dataset.py --policy-basis experimental --output results/dataset_build_v04
python dataset.py --domain airlines --policy-basis published --output results/published_build_v04
```

Builds write `prompts.jsonl` (one prompt record per line), `reference_labels.jsonl` (evaluation only), and `manifest.json` (counts, version and hashes). Published builds currently write an empty reference file because experimental labels cannot be reused for source-policy evaluation.

The runner and chatbot read source JSON directly, so exporting is optional. Builds overwrite files at the selected destination; preserve annotations separately and use a new destination when keeping a dataset snapshot.

## 7. Run a controlled pilot

Use **`run_pilot.py`**. Start with a dry run, then remove `--dry-run` when weights and settings are ready.

### One published-policy airline condition

```bash
python run_pilot.py --domain airlines --scenario airlines_011_turkish_24h_refund --policy-basis published --emotion neutral --model standard --dry-run
python run_pilot.py --domain airlines --scenario airlines_011_turkish_24h_refund --policy-basis published --emotion neutral --model standard
```

### One experimental condition, a full core, or a domain

```bash
python run_pilot.py --domain airlines --scenario airlines_001_no_show --policy-basis experimental --policy strict --emotion neutral --model standard
python run_pilot.py --domain airlines --scenario airlines_001_no_show --policy-basis experimental --all --model standard
python run_pilot.py --domain airlines --policy-basis experimental --all --model standard
python run_pilot.py --domain airlines --policy-basis published --all --model standard
```

These select one experimental prompt, twelve prompts for one core, all experimental airline prompts, and all published airline prompts respectively. Replace `airlines` with another domain to run its experimental cases. Omit `--domain` with `--all` for the complete experimental dataset. Published runs include only cores with a `published_policy` summary; currently these are airline cases.

Each controlled condition uses one system message and one user message, a fresh generation cache, and no prior conversation. Multi-condition runs require `--all`. Without selection filters, the runner selects the first discovered condition; explicit selection is preferable for research runs.

`--prompt path/to/file.json` accepts a core JSON or a single expanded prompt JSON object; its basis must match `--policy-basis`. It does not take an entire JSONL build. The old `--dataset` option is no longer used. See all flags with `python run_pilot.py --help`.

### Model configuration

Both runner and chatbot discover entries in [model_config.json](model_config.json). The entry key is the `--model` value:

| Key | Model | Temperature | Top-p | Output limit | Seed |
| --- | --- | --- | --- | --- | --- |
| `standard` | Qwen 2.5 7B Instruct | 0.0 | 1.0 | 512 | 42 |
| `reasoning` | DeepSeek-R1-Distill-Qwen-7B | 0.6 | 0.95 | 4096 | 42 |

Use `--model reasoning` for DeepSeek. Overrides are `--seed`, `--temperature`, `--top-p`, `--max-tokens`; effective settings are recorded. For the reasoning model, system instructions are merged into the first user message before applying its template. Original and effective messages are retained.

To add a compatible local model, copy a configuration entry and update its key, `model_id`, `revision`, `local_path`, `model_type`, `model_family` and generation settings. The current presence check expects `model.safetensors.index.json` and its referenced shards. New formats/templates may require backend work. Planned Llama models are not configured or downloaded. Revision IDs are recorded declarations, not cryptographic verification of local weights.

## 8. Run the chatbot

```bash
python -m streamlit run chat_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

Open **http://127.0.0.1:8501** and keep the terminal running. Select mode, domain, **airline**, policy basis, **scenario**, policy/classification, emotion and model. Airline and scenario are separate selectors; scenarios are filtered to the selected airline. Other domains do not show the airline selector.

| UI mode | Behavior | Where results go |
| --- | --- | --- |
| Condition preview | Sends the generated starting request once, without editing | `results/chat_sessions/` |
| Exploratory chat | Allows custom messages and multiple turns | `results/chat_sessions/` |

Changing a selection or clicking **New conversation** starts a fresh session. All UI sessions, including one-turn previews, remain separate from controlled benchmark runs. Exploratory turns record `emotion: unlabelled_interactive` and retain the source condition's emotion as metadata.

Only completed final assistant answers enter follow-up history; raw outputs and traces remain in logs. The worker serializes generation and holds one local model; the first response also loads weights. Chat has an 8192-token budget including output allowance; exceeding it fails rather than silently cutting history. Session JSON and Markdown downloads appear after a turn. Saved sessions are not restored automatically after browser refresh.

If the UI reports a dataset error, run `python dataset.py --domain airlines` (or the selected domain) and fix the named JSON. After source-code changes, restart Streamlit from the project environment if an old process is still running.

## 9. Read results and reasoning traces

| Location | Contents |
| --- | --- |
| `results/benchmark/<run_id>/` | Controlled experimental-policy runs |
| `results/published_policy/<run_id>/` | Separate published-policy pilots |
| `results/chat_sessions/<session_id>/` | Interactive turns, session JSON and transcript |
| Your dataset build destination | Expanded prompts, separate references and manifest |

Runner output looks like this; batch runs put trial files in numbered subfolders:

```text
<run_id>/
├── run_manifest.json          # conditions, model and settings
├── summary.json               # machine-readable trial summaries
├── summary.md                 # readable output overview
├── result.json                # complete trial record
├── raw_output.txt             # generated text, flushed during generation
├── final_answer.txt           # when a complete answer is available
└── reasoning_trace.txt        # when an observable trace is available
```

Begin with `summary.md` to inspect responses, then use `result.json` for analysis. A model-load failure produces `load_error.json`. Trial records retain run/trial IDs, `scenario_id`, `prompt_id`, domain, policy, emotion, policy basis, sources, original/effective messages, rendered prompt/token IDs, model ID/type/revision, settings, raw output, trace/final answer, timing, errors and finish/parse/truncation status.

`status: completed` means generation finished; it is not a compliance label. A reasoning-model answer may be complete with `parse_status: missing_trace`. An incomplete generation has no complete `final_answer`; inspect its raw output and finish reason. Failed generation retains partial raw text and recoverable trace information. Existing trial directories cannot be reused to overwrite raw output.

The parser handles ordinary `<think>...</think>` blocks, template-supplied opening tags, missing/malformed tags, missing traces, empty output and truncation. **Raw model output is preserved. Observable generated reasoning traces are model-emitted text, not reliable records of true internal reasoning.** Trace availability, generation completion and policy compliance are separate questions.

Historical results remain in place. Dataset version 0.4 changed airline branding, policy wording and selected fee assumptions; interpret earlier runs using their saved inputs. There is currently no automatic compliance evaluator, repetition scheduler or run-resume mechanism.

## 10. Sources, team review and next work

Official airline pages were checked on **6 October 2026**. JSON records keep dates, URLs, observations and scope limitations. Summaries remain pending human verification and are not exhaustive policy snapshots.

| Airline | Source | Current scenario numbers |
| --- | --- | --- |
| Ryanair | [Refund policy](https://help.ryanair.com/hc/en-gb/articles/12896766243857-Refund-Policy) | 001, 002 |
| easyJet | [Terms](https://www.easyjet.com/en/help-centre/policy-terms-and-conditions/terms-and-conditions), [fees](https://www.easyjet.com/en/help-centre/policy-terms-and-conditions/fees-charges) | 003, 004 |
| British Airways | [Customer commitment](https://www.britishairways.com/content/information/legal/our-customer-commitment), [seating](https://www.britishairways.com/content/information/seating/seating-changes-and-refunds) | 005, 006 |
| KLM | [Extra-option refunds](https://www.klm.nl/en/information/refund-compensation/extra-options) | 007, 008 |
| Lufthansa | [Cancellation and refund](https://www.lufthansa.com/cz/en/cancellations-and-refunds) | 009, 010 |
| Turkish Airlines | [24-hour refund provision](https://www.turkishairlines.com/en-us/ticket-refund-at-no-charge-in-the-first-24-hours/) | 011 |

easyJet cases use the checked GBP fee assumptions; booking values are synthetic. Turkish Airlines' terms and FAQs differ in the seven-day time anchor; the current case satisfies both and records that limitation. Review source scope and linked conditions before main-study collection.

For the paper, describe these as **synthetic customer-service scenarios grounded in real airline policy sources**, with a separate researcher-modified factorial collection. No real customer conversations or observed airline decisions have been collected.

### Where to make a change

| Your task | Edit |
| --- | --- |
| Add a scenario, airline, facts or scoped policy summary | A JSON under `data/<domain>/` |
| Change shared emotional wording or model-facing instructions | `prompting.py` — affects many prompts and requires review |
| Change validation or export metadata | `dataset.py` |
| Add a supported local model or change decoding defaults | `model_config.json` |
| Change generation or result recording | `run_pilot.py` |
| Change trace extraction | `trace_parser.py` and focused parser tests |
| Change exploratory history or logging | `chat_backend.py` |
| Change selectors or presentation | `chat_app.py` |

For the five-person team, domain owners can work on separate JSON files while another teammate reviews them. Coordinate changes to global framing, instructions, validation and decoding because they affect everyone's conditions. Validate/test after combining changes, and record the dataset snapshot and settings used for each experiment.

The team still needs to agree scenario allocation, source snapshots/scope, classifications of mixed policies, eligible versus ineligible exception cases, emotion strength, reference decisions, ambiguity scoring, decoding/repetitions, branding effects and treatment of failed/truncated generations. Earlier airline experimental references are drafts; Turkish and other-domain pilots still need references, and published-policy references need separate authorship.

Earlier inputs and documents are preserved in [archive/](archive/README.md), including the ten pre-migration fictional airline cores. Active code reads `data/`, not the archive. Use this README for current commands; historical documentation describes superseded layouts.
