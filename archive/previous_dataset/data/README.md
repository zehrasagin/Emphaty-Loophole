# Shared benchmark data

The registered domains are **retail, airlines, hotels, telecom, and customer support**. Machine-readable IDs and display labels are defined in `domains.json`; use `customer_support` as the ID for Customer support.

Ten core scenarios per domain is a provisional equal allocation of the project's 50-scenario target. This is a planning assumption and does not imply that all 50 have been authored.

| Domain | Core benchmark drafts | Generated prompts | Original pilot examples |
| --- | ---: | ---: | ---: |
| Retail | 0 | 0 | 1 |
| Airlines | 10 | 120 | 1 |
| Hotels | 0 | 0 | 1 |
| Telecom | 0 | 0 | 1 |
| Customer support | 0 | 0 | 1 |

The original examples stay in `pilot_prompts/` for compatibility. All five now use strict experimental policies. The airline example mirrors the first benchmark scenario's strict/neutral cell. The earlier source-based Ryanair example is preserved in `airlines/source_examples/ryanair_refund_original.json` and is not included in either prompt selection.

## Structure

```text
data/
  domains.json
  airlines/
    sources.json
    core_scenarios.json
    generated/
      prompts.jsonl
      prompts.csv
      reference_labels.jsonl
      review_template.csv
      manifest.json
      catalog.md
      preview.md
      policy_variants.json
      policy_variants.md
  retail/                 # same input structure, currently empty
  hotels/
  telecom/
  customer_support/
```

`core_scenarios.json` is the editable source of truth. Each record includes a domain and core ID, fixed facts and a customer fact paragraph, a fixed request, a shared `base_rule`, a narrow `exception_rule`, source references, and human-review fields. See the airline records for complete examples. `sources.json` maps source IDs to official URLs and concise evidence notes.

Strict and normal are distinct. The current renderer implements three experimental conditions from a shared base rule; the role of normal is awaiting clarification:

1. **Strict (no exceptions):** apply the rule with no exceptions.
2. **Exception:** retain the rule and permit only the explicitly specified exception.
3. **Ambiguous:** retain the rule and permit exceptions in undefined exceptional circumstances.

Do not append an exception to a text that still says no exceptions are permitted. The renderer adds the appropriate condition clause to the shared rule. Strict policies can still grant requests that meet their ordinary eligibility criteria; strict does not mean refusing every request. `generated/policy_variants.md` displays the three policies together before any emotional framing is applied.

`dataset.py` renders the three policy conditions and four emotional frames deterministically. The exact same fact paragraph and request occur in all 12 cells. The system message stays identical across emotions within a policy condition, and the customer message stays identical across policies within an emotion condition. Real company names are retained in provenance and excluded from model-facing experimental messages.

Expected decisions and reviewer notes are exported separately from the model-facing messages. The draft references are human-review aids, not automatic compliance verdicts. No LLM judge has been added.

## Build and validate

```bash
python build_dataset.py --domain airlines
python run_pilot.py --dataset benchmark --domain airlines --dry-run
```

Generation checks domains, source resolution, IDs, complete 12-cell coverage, message invariants, and hashes. Human review is still needed to check that structured facts match the prose, the emotion is convincing, and each policy has the intended interpretation.

All files under `generated/` can be overwritten by rebuilding. Copy `review_template.csv` to a separate review location before entering annotations. Review decisions must identify the prompt hash they apply to. Completing a review sheet does not automatically mark a core record validated; update its human-review fields only after the team has reconciled annotations.

## Run selected conditions

Run the 12 cells of one core scenario:

```bash
python run_pilot.py --dataset benchmark --domain airlines --scenario airlines_001_no_show --all
```

Run all 120 airline prompts:

```bash
python run_pilot.py --dataset benchmark --domain airlines --all --model standard
```

Run one selected cell:

```bash
python run_pilot.py --dataset benchmark --domain airlines --scenario airlines_001_no_show --policy strict --emotion guilt --model reasoning
```

`--seed`, `--temperature`, `--top-p`, and `--max-tokens` are available. Every invocation stores a run manifest with selected prompt hashes and settings. Defaults remain model-specific, and the reasoning model uses a different message adapter: establish the study protocol before interpreting model differences. Automatic resumption and a repetition scheduler are not implemented.

In Chat Lab, choose the dataset, domain, core scenario, policy condition, and emotional framing. Each change starts a fresh chat. A manual follow-up conversation is exploratory even when its first message came from a controlled cell; use the command-line runner for independent benchmark responses.
