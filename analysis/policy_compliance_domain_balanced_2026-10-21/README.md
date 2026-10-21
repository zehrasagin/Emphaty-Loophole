# Equal-domain reaggregation — 2026-10-21

This package reuses the existing frozen annotations. It does not generate responses, invoke a judge, change labels, resolve references or modify the earlier paper draft.

## Overall PCR comparison

| Model | Original pooled PCR | Equal-domain PCR | 95% stratified scenario CI |
| --- | --- | --- | --- |
| Llama 3.1 8B | 65.47% | 67.57% | [62.07, 72.73]% |
| Qwen2.5 7B | 70.67% | 72.66% | [68.02, 77.15]% |
| DeepSeek-R1 Distill 7B | 62.22% | 64.83% | [59.64, 69.58]% |

## Metric changes

| Model | Metric | Condition | Original pooled | Domain-balanced |
| --- | --- | --- | --- | --- |
| Llama 3.1 8B | ECI | anger | +10.20 pp | +12.00 pp |
| Llama 3.1 8B | ECI | guilt | +0.68 pp | +1.43 pp |
| Llama 3.1 8B | ECI | fear | +7.59 pp | +8.80 pp |
| Llama 3.1 8B | LSR | all_frames | -0.108 | -0.071 |
| Llama 3.1 8B | LSR | emotional_frames | -0.150 | -0.114 |
| Qwen2.5 7B | ECI | anger | +11.81 pp | +11.13 pp |
| Qwen2.5 7B | ECI | guilt | +7.48 pp | +5.61 pp |
| Qwen2.5 7B | ECI | fear | +20.00 pp | +19.45 pp |
| Qwen2.5 7B | LSR | all_frames | -0.113 | -0.072 |
| Qwen2.5 7B | LSR | emotional_frames | -0.099 | -0.048 |
| DeepSeek-R1 Distill 7B | ECI | anger | -8.22 pp | -7.82 pp |
| DeepSeek-R1 Distill 7B | ECI | guilt | -8.22 pp | -6.67 pp |
| DeepSeek-R1 Distill 7B | ECI | fear | +9.03 pp | +10.39 pp |
| DeepSeek-R1 Distill 7B | LSR | all_frames | -0.047 | -0.053 |
| DeepSeek-R1 Distill 7B | LSR | emotional_frames | -0.051 | -0.069 |
| DeepSeek-R1 Distill 7B | RAI | all_frames | 9.05% | 11.20% |
| DeepSeek-R1 Distill 7B | RTI | all_frames | 2.62% | 2.76% |

## Definitions

- Five domains have a fixed 20% weight each. Within the supported population of a metric, an observation in domain d has weight w=1/(5*n_d). Scenario counts and raw outcome counts are not changed.
- PCR/CSCR, FIVR and RTI use weighted event mass divided by weighted trial mass; this equals the unweighted mean of domain-specific rates. Policy/emotion groups are standardized separately.
- ECI uses matched scenario-policy neutral/emotion pairs, averages domain-level paired differences and reports percentage points. Each contrast retains its own matched support.
- LSR first standardizes strict and ambiguous PCR on the same scenario-emotion pairs, then computes(strict-ambiguous)/strict. It is not the mean of domain LSRs; zero strict baseline is undefined and negative values are retained.
- BDD weights all reference-eligible known trials first, then conditions on violations: sum_d(category_violations_d/n_d)/sum_d(all_violations_d/n_d). The same denominator is used for every category, including the residual. A zero-violation domain contributes zero event mass, not a fabricated 0% conditional share.
- RAI uses the same conditional-ratio approach on reference-eligible known complete trace/final pairs. RTI and FIVR remain reference-independent. Only DeepSeek has traces; final-only FIVR is the cross-model measure.
- Unknown compliance labels and 180 reference-quarantined records retain their original handling. Raw counts/coverage are exported separately from weighted masses. Unknown bounds retain each domain’s full reference-eligible denominator.
- A missing domain makes an estimate undefined; no automatic redistribution to fewer domains. Bootstrap draws with missing support or a zero ratio denominator are counted explicitly, not recoded to zero.

## Confidence intervals

Five thousand bootstrap draws (seed 20261021) resample full scenario clusters within each domain, preserving its original number of scenarios. Exactly the same multiplicities are reused across models, policies, emotions and metrics. Numerator/denominator terms and within-domain weights are recomputed in every draw. Intervals describe scenario resampling, not new model generations or uncertainty in the existing AI-assisted labels.

## Files

- [Summary JSON](summary.json): all balanced metrics, per-domain supports/weights, raw counts, weighted masses and intervals.
- [Metric comparison](tables/metric_comparison.csv): old pooled versus new balanced estimates.
- [Weights and support](tables/domain_weights_and_support.csv): metric-specific domain normalization.
- [Policy × emotion](tables/policy_emotion_compliance.csv), [reasoning by emotion](tables/reasoning_by_emotion.csv), [coverage](tables/coverage.csv).
- [Figures](figures/): seven sets in PNG/PDF/SVG, each with its calculation caption.
- [Validation and input hashes](validation.json). Original labels remain in ../policy_compliance_2026-10-18/annotations.jsonl.

## Reproduce

From the repository root, using the existing environment with numpy and matplotlib:

```sh
.venv/bin/python analysis/policy_compliance_domain_balanced_2026-10-21/domain_balanced.py
.venv/bin/python -m unittest discover -s analysis/policy_compliance_domain_balanced_2026-10-21 -p test_domain_balanced.py -v
```

This command writes only to this new output directory. It verifies baseline/source hashes before and after generation. No Git push is performed.
