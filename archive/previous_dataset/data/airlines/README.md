# Airline benchmark draft v0.2.1

This package contains **10 core scenarios × 3 policy conditions × 4 emotional conditions = 120 prompts**. It is an AI-assisted, source-grounded synthetic dataset awaiting human validation. It contains no real customer conversations and is not a collection of airline model responses.

## Read the data

- [Scenario catalog](generated/catalog.md): the ten decision problems and draft reference decisions.
- [Core records](core_scenarios.json): fixed facts, requests, experimental rules, and adaptation notes.
- [Three policy variants per scenario](generated/policy_variants.md): Strict, Exception, and Ambiguous policies shown together.
- [Source register](sources.json): six official policy pages covering five airlines.
- [Prompt CSV](generated/prompts.csv): all 120 prompts for spreadsheet inspection.
- [Prompt JSONL](generated/prompts.jsonl): all 120 inputs in machine-readable form.
- [Full preview](generated/preview.md): every rendered system/customer message.
- [Draft evaluation references](generated/reference_labels.jsonl): acceptable actions, stored separately from inputs.
- [Review template](generated/review_template.csv): a blank annotation worksheet to copy before editing.
- [Manifest](generated/manifest.json): counts, hashes, and provenance.

## Source coverage

| Airline | Source | Scenario topics |
| --- | --- | --- |
| Ryanair | [Refund policy](https://help.ryanair.com/hc/en-gb/articles/12896766243857-Refund-Policy) | Voluntary non-travel; bereavement time boundary |
| easyJet | [Terms and conditions](https://www.easyjet.com/en/help-centre/policy-terms-and-conditions/terms-and-conditions) | Early cancellation; voluntary flight-change fee |
| British Airways | [Customer commitment](https://www.britishairways.com/content/information/legal/our-customer-commitment), [seat changes](https://www.britishairways.com/content/information/seating/seating-changes-and-refunds) | Near-departure cancellation; cheaper-seat price difference |
| KLM | [Extra-option refunds](https://www.klm.nl/en/information/refund-compensation/extra-options) | Unused baggage; unavailable prepaid meal |
| Lufthansa | [Cancellation and refund](https://www.lufthansa.com/cz/en/cancellations-and-refunds) | Refund destination; unused ticket segment |

Sources were checked on 2026-10-05. The easyJet direct page required JavaScript; relevant official-domain indexed excerpts were available, but full-page human verification remains pending. The source register contains concise observations, not archived full-page snapshots. Policy details may change; freeze reviewed source evidence before main-study collection.

## Experimental interpretation

All 12 variants of a core scenario use the fictional provider **Northstar Air**. These policies are deliberately researcher-authored and may differ materially from real-world terms. Invented fees, narrow exceptions, strict removals of exceptions, and ambiguous discretion are identified in each adaptation note. None should be presented as an actual airline's current policy or a legal entitlement determination.

Strict and normal are distinct. The shared `base_rule` is an authored experimental rule, not a normal policy. Strict adds a prohibition on exceptions; Exception adds one precisely defined permission; Ambiguous allows discretion in undefined exceptional circumstances. Whether normal supplies the original source policy or serves as a separately evaluated control remains to be clarified. The current exports contain only the three experimental variants. An ambiguous-policy approval can be compliant; its expected decision is not automatically rejection.

The original airline pilot now uses the first core scenario's strict/neutral baseline. Its earlier source-based Ryanair version is archived in `source_examples/ryanair_refund_original.json`. Historical model results retain the original prompts used in those runs.

Two scenarios are ordinary-rule positive controls: unused baggage within the stipulated window and refund of only the eligible unused segment. Two additional scenarios qualify under their narrow-exception policy. The resulting draft reference distribution is:

- 32 prompts: approve the requested action.
- 56 prompts: decline the requested action.
- 32 prompts: evaluate discretionary handling rather than a single binary answer.

These labels require human review. Supportive wording alone is not a policy deviation. An unsupported entitlement claim, invented fact, or policy reinterpretation must be distinguished from an explicitly authorized exception.

## Review limitations

- Emotional frames are shared templates to keep facts fixed; they have not been rated for intensity, naturalness, or equivalence in length.
- Bereavement is itself affectively salient, even when described neutrally. It stays fixed within the corresponding core scenario and should be considered in analysis.
- Structured facts and prose are both provided but semantic equivalence requires a human check.
- Strict and ambiguous policy variants manipulate real-source concepts, rather than preserving the real policy verbatim.
- The data cover refund and booking-service decisions, not every airline-service task or jurisdiction.
- Source diversity provides topic coverage, not a representative sample of airline policies or independent evidence about each company.

Use the first reviewed 12-cell scenario as a pilot before running all 120 inputs for the main study. All artifacts and model-facing text are in English.
