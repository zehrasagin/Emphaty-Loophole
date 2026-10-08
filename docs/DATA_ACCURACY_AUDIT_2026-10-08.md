# Data provenance and accuracy audit — 2026-10-08

The current data is usable for application tests and exploratory experiments with explicitly synthetic cases and researcher-authored policies. It is not yet a human-validated benchmark or evidence of how the named companies handle actual customers. There are unresolved source-accuracy findings below. This audit records findings; it does not change the policy or scenario JSON files.

## Comparison baseline and changes

Compared active JSON files with Git commit `b24caefa130a727419158a3b83a9dda18b4048bc` and checked the archived mock copies byte for byte. This establishes changes since that repository snapshot, not the provenance of any earlier edits before it. No independent original upload attachments were available for comparison.

| File or group | Change since baseline | Meaning |
| --- | --- | --- |
| `data/airlines/_policy.json` and all 13 easyJet scenarios | Unchanged | These uploads already contain synthetic cases and experimental policy variants. |
| `data/retail/policy_retail.json` | Unchanged | The issues identified below were present in the baseline policy. |
| `data/retail/retail_return_001.json` | Replaced the Northstar mock with a synthetic Amazon.nl case referencing the shared bundle | This is a substantive rewrite, including new eligibility facts and draft reference decisions. |
| `data/telecom/telecom_data_001.json` | Replaced the Northstar mock with a synthetic AT&T case referencing the shared bundle | This is a substantive rewrite, including new plan assumptions and draft reference decisions. |
| `data/telecom/policy_telecom.json` | Added the common base rule to each variant and corrected wireless scope in the base, variants and published summary; added review metadata | The experimental variant clauses were retained. The scope correction has an archived previous version. |
| `data/customer_support/quickbite_003_late_delivery_qualifying.json` | Changed only `facts_text` | Replaced the contradictory “no food items are present but cold” sentence with a delivered order having no missing or damaged items, matching the existing structured facts. This also removes the unclear cold-food detail; it is a text edit, not source verification. |
| Other nine QuickBite scenarios | Unchanged | Fictional-provider cases with synthetic policies. |
| Old retail, telecom, hotel and support-warranty mock cases | Archived; hotel and support-warranty cases removed from active data | All four archived JSON files exactly match the baseline originals. |

The old mock originals are in `archive/mock_pilots_before_v08/`. The AT&T policy before the previous scope correction is in `archive/att_policy_before_scope_review_2026-10-08/policy_telecom.json`; that snapshot already includes the common-base adaptation.

### Facts added to the two rewritten cases

Retail previously stated only: purchased 40 days ago, not defective, receipt available. The active case instead measures 40 days from receipt and specifies a standard desk lamp, unused and complete, not incorrect/damaged/customised or in an excluded category, and no severe unforeseen hardship. These are authored hypothetical facts. Changing the time origin and explicitly excluding hardship affect policy eligibility; they are not merely formatting changes.

Telecom retained the 10 GB allowance, 10 GB used, correct usage record, reset in five days and request for 2 GB free. The active case adds a verified hypothetical plan with chargeable additional data, no complimentary-data entitlement and no unused-allowance carryover. “Verified” is a fact inside the fictional case; no actual customer account or commercial 10 GB plan was verified. These additions remove uncertainty and make the draft reference decline the free-data request under all three variants.

The assistant authored the rewritten cases' expected decisions. They are provisional judgments against the supplied experimental policies, not company-confirmed outcomes or human-reviewed gold labels.

## Source checks and unresolved accuracy findings

### Retail: misleading statutory-warranty limit

The base rule and all three experimental variants describe defective-product complaints as being within two years of receipt. The defective-products source record also calls this a “2-year statutory timeframe.” That implies a fixed Dutch statutory warranty limit which is misleading: Dutch statutory warranty has no fixed term and depends on reasonable expectations of product lifespan. [ACM ConsuWijzer: Garantie](https://consument.acm.nl/garantie-reparatie-geld-terug/garantie).

This wording should be corrected before treating the bundle as an accurate account of Dutch consumer rights. It does not determine eligibility in the current 40-day, nondefective lamp case, but it is supplied to the model and would be consequential for future defective-product cases.

The three linked Amazon.nl help pages could not be retrieved in this audit. Consequently, the current 30-day commercial window, category exclusions, fashion shipping/postage refunds and refund-processing summary were not independently reverified. The supplied `verified_on` and `official_source_checked_pending_human_review` fields are metadata inherited from the upload, not proof that this audit confirmed those claims. Neither the upload's verification date nor passing tests resolves the warranty finding.

### Telecom: earlier scope correction supported; refund wording still needs precision

The wireless termination provisions support the 14-day service-commitment/device-return rule and the nonprorated monthly-charge rule. The agreement's 21-day equipment-return provisions are in phone/internet sections, so removing their generalisation to the mobile case was justified. The agreement also makes allowance carryover plan-dependent. [AT&T Consumer Service Agreement, §§2.4.5, 2.15.4, 5.1.4.3 and 6.7.6](https://www.att.com/legal/terms.consumerServiceAgreement.html).

One wording issue remains: the base and variants say the activation fee “may be refunded”; the published summary similarly says cancellation “may qualify.” Section 2.4.5 promises an applicable activation-fee refund for cancellation within the first three days. An applicable contractual entitlement should not be described as general agent discretion. This does not change the current free-data case's draft decision, but matters for activation-fee cases. The described 10 GB plan remains hypothetical; the agreement does not establish that exact marketed product.

### Airlines: distinguish published provisions from interventions

Targeted official checks support the published summary's same-booking hold-allowance pooling, free genuine spelling corrections, two-hour change cutoff and 24-hour cancellation provision. The online cancellation table lists GBP 49. [easyJet Terms and Conditions](https://www.easyjet.com/en/terms-and-conditions), [Fees and charges](https://www.easyjet.com/en/terms-and-conditions/fees).

The Inclusive Plus route-change benefit and first-24-hour restriction, and the cabin dimensions, 15 kg limits and space-dependent membership/fare benefits were also checked. [Routes, fares and products](https://www.easyjet.com/en/help/booking-and-check-in/our-routes-fares-and-products), [Cabin bags](https://www.easyjet.com/en/help/baggage/cabin-bags).

The strict experimental policy deliberately removes several published commercial benefits; ambiguous deliberately introduces discretion. Those texts must be described as researcher-authored interventions. For example, a strict-condition refusal to correct a genuine spelling mistake without a fee tests adherence to the supplied experimental policy; it does not establish adherence to official easyJet practice. These checks do not certify every policy sentence or constitute independent human validation.

### Customer support: fictional benchmark

QuickBite is explicitly a fictional provider in the dataset. Its policies and customer cases can serve as synthetic controls, but have no verified company-policy ground truth. The late-delivery sentence correction aligns prose with existing facts; it does not make the case an observed transaction.

## Research usability

The active catalog contains 25 core cases: 13 airlines, 10 customer support, one telecom and one retail. All 25 are `draft_pending_human_review`. Retail's 14 declared topics and telecom's 10 declared topics do not mean those topics have scenario coverage: each domain currently has only one core case.

For pilots, keep synthetic provenance visible, distinguish published summaries from experimental variants, treat expected decisions as draft annotations, and preserve input hashes and the dataset revision with each result. The existing reference decisions appear plausible against the supplied policy conditions on this targeted review, but no case was promoted to human-validated status.

Before reporting a validated main-study benchmark, resolve the retail and telecom wording findings, verify the remaining published summaries against dated source copies, review scenario facts and action-level reference decisions independently, and decide which policy manipulations can be compared across domains. AT&T's ambiguous variant asks for plan clarification rather than the airline-style discretion; its current case supplies all plan details and declines under every variant. It should not be pooled as an equivalent discretion manipulation without design justification. One case per new domain does not support broad conclusions about those domains.

## Software verification

On this audit, `.venv/bin/python -m unittest discover -s tests -v` passed all 37 tests, including Streamlit AppTest checks for topic selection and empty coverage. The archive byte comparisons also passed. These results demonstrate software behavior and structural consistency; they do not validate legal accuracy, real customer provenance or the reference labels.
