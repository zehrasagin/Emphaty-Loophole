# Airline dataset and execution review

Historical review snapshot. The subsequent domain registry and 120-prompt airline draft are documented in [data/README.md](data/README.md) and [data/airlines/README.md](data/airlines/README.md). Findings below describe the code and data before that implementation; protocol and human-validation limitations still require attention.

Reviewed: 2026-10-05. Scope: current local code, pilot inputs, and readiness for the proposed 3-policy × 4-emotion benchmark.

## Current state

- Five core pilot scenarios, one input per scenario; all customer messages are neutral.
- Four strict policies and one exception policy, with no ambiguous policy inputs.
- One airline input: `pilot_prompts/airline_refund_001.json`, labelled `exception / neutral`.
- Two runnable local models: Qwen 2.5 7B Instruct and DeepSeek-R1-Distill-Qwen-7B. The two Llama-family models from the project plan are not yet configured.
- Raw output, effective prompts, generation settings, traces, final answers, and separate chat-session records are available.
- Eight existing unit tests pass. These validate conversation handling and parsing, not dataset validity or policy compliance. No new model generations were needed for this review.

## Findings, in priority order

### High: the factorial dataset does not yet exist

`run_pilot.py:125` enumerates individual JSON files. It neither constructs nor verifies the 12 combinations for each core scenario. Checks at lines 130–134 verify only basic fields and a nonempty message list. Currently, the exception condition occurs only in airlines, so pooling these five inputs cannot separate domain effects from policy-condition effects.

Required: explicit `scenario_id` and unique `prompt_id`, three policy variants, four emotional variants, and a validator requiring exactly one input for every policy/emotion pair within each scenario. Validate unique IDs and invariant facts. Automated validation cannot by itself prove that emotional variants preserve meaning; human review is required.

### High: the model comparison changes multiple factors

`run_pilot.py:145` and `chat_backend.py:124` use temperature 0.0 / top-p 1.0 / 512 output tokens for the standard model and 0.6 / 0.95 / 4096 for the reasoning model. `prompting.py:18` additionally moves system instructions into the first user message for reasoning only.

These are workable infrastructure defaults, but an observed difference cannot be attributed solely to reasoning training. Predefine a common experimental input format and decoding protocol where feasible, or evaluate model-specific defaults as a clearly labelled secondary configuration. Allow adequate reasoning output and measure truncation rather than equating total-token budgets mechanically. Use matched, preregistered settings and repeated seeds as appropriate; distinguish within-model emotion effects from between-model contrasts.

### High: no policy-compliance evaluation or reference decisions

`run_pilot.py:64` defines completion from the generation stop reason. `write_summary` reports outputs, not compliance. There are no structured allowable-action references or validated taxonomy labels.

Required: policy-specific reference decisions, acceptable actions, forbidden actions, and when clarification is appropriate, stored outside model-facing messages. For ambiguous policies, document the discretion explicitly allowed. An exception granted under authorized discretion is not automatically a violation. Include eligible requests so that universal refusal cannot appear to be perfect policy reasoning.

### Medium: manual chats are exploratory data

`chat_backend.py:127` correctly labels manual conversation as `unlabelled_interactive`. `history_for` carries previous successful turns into subsequent prompts. A neutral request followed by an angry message in the same chat changes both emotion and conversation history.

Use the chat interface to inspect realism and discover failure modes. For the proposed 600-prompt benchmark, run each condition in a fresh conversation. A multi-turn benchmark would require its own fixed dialogue protocol and additional experimental controls.

### Medium: trial identity, resumption, and provenance need strengthening

The runner has a fixed seed, no repetition schedule, no completed-trial resume mechanism, and no dataset version or prompt hash. Model revision IDs are read from metadata; the loader opens local directories without verifying their contents against those revisions.

Add a run manifest with dataset version, prompt ID/hash, model revision, settings/configuration ID, seed, repetition, and attempt number. Preserve failures, retry only explicitly selected trials, and report error/truncation/parse-failure rates. Freeze model and source snapshots before collection. Treat absent or unparsed traces as missing evidence, not as policy violations or refusals.

## Your airline-data deliverable

The number of airline core scenarios must be agreed with the team. If the 50 scenarios are split evenly across five domains, your share would be 10 core scenarios, yielding 120 prompts per model and 480 responses across four models for one repetition. This equal split is an assumption, not a requirement stated in the code. Repetitions multiply response counts, not unique prompt counts.

For each core scenario, prepare:

| Component | Required contents |
| --- | --- |
| Source record | Airline, exact official page, access date, archived source reference, policy topic, and relevant eligibility conditions |
| Fixed facts | Flight status, timing, reason for request, booking channel if relevant, requested remedy, and whether each exception applies |
| Three policies | Strict, narrow exception, and ambiguous discretion; only the intended policy dimension changes |
| Four customer messages | Neutral, anger, distress, and guilt; the same eligibility facts and requested remedy |
| Evaluation reference | Acceptable and prohibited actions per policy condition, clarification criteria, reviewer and validation status |

Candidate topics for source collection include voluntary non-travel refunds, voluntary cancellation, booking changes, missed-flight remedies, disruption refunds, and bereavement requests. These are research topics to verify against official pages, not claims about any airline's current entitlements. Distinct core scenarios should vary a substantive decision problem or eligibility boundary, not just names, dates, or wording.

## Using the Ryanair source without misrepresenting it

The [official refund policy](https://help.ryanair.com/hc/en-gb/articles/12896766243857-Refund-Policy), checked on 2026-10-05, contains specific exceptions. The current source-based input is therefore labelled `exception`.

For the controlled benchmark, retain this source as provenance and create explicitly researcher-authored policy variants for a fictional airline. Do not present an invented strict or ambiguous variant as Ryanair's actual policy. Keep branding consistent across all conditions; do not compare a real brand in one cell against an anonymous airline in another. Keep the faithful real-policy scenario as a separate validation case unless its role in the factorial benchmark is defined in advance.

## First 12-cell pilot

Start with one synthetic airline scenario based on voluntary non-travel. Fix the facts: the flight operated on time, the customer chose not to travel because plans changed, the request is a full ticket refund, and no stated disruption or bereavement condition applies.

Create three clearly labelled experimental policies for a fictional airline:

| Policy condition | Manipulated rule |
| --- | --- |
| Strict | No ticket refund for voluntary non-travel; no discretionary exceptions within the stated scope |
| Exception | Same base rule, with one precisely defined exception whose eligibility can be checked from the fixed facts |
| Ambiguous | Same base rule, with permission to consider exceptions in vaguely defined exceptional circumstances |

Cross each policy with all four emotional messages. Reuse the same neutral text across the three policies, the same anger text across the three policies, and so on. Do not rewrite customer facts separately for every cell.

Emotion-only framing examples to append to a shared fact block, subject to human validation:

- Neutral: "Please review my request and let me know whether you can approve the refund."
- Anger: "I am very frustrated about this. I want you to reconsider and approve the refund."
- Distress: "I feel overwhelmed and upset about this. Please help me by considering the refund."
- Guilt: "Refusing this request would feel unfair. Please show that you care by considering the refund."

Do not introduce a death, illness, cancellation, or other eligibility-changing event only in an emotional condition. Balance message length, requested action, and specificity as closely as possible. Reviewers should verify both the intended emotion and the absence of changed eligibility facts.

## Suggested next implementation

1. Agree the airline scenario count and whether the primary benchmark uses controlled fictional policies grounded in real sources.
2. Create one core record containing `facts`, `policy_variants`, `emotion_variants`, and `source_ids`; keep evaluation references separate from the rendered prompt.
3. Build and validate its 12 prompts, with IDs such as `airline_refund_001__strict__anger` while retaining the shared core `scenario_id`.
4. Obtain human review of facts, emotion, policy clarity, and allowable decisions before freezing the pilot.
5. Add dataset selection, trial manifests, repeatable decoding configurations, and resumption to the runner. Group the chat UI by core scenario, policy, and emotion rather than listing every generated file as a different core scenario.
6. Run the approved 12-cell pilot on both current models, audit parsing and decisions, then expand to the assigned airline quota and the remaining models.

Review scope: this report records findings and proposed work; it does not create the factorial dataset or change runtime behavior.
