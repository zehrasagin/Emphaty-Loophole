# Complete exploratory policy-compliance audit

All 1,944 final answers and 648 available emitted traces were reviewed against their frozen experiment policies and customer facts. Original data/results formats are unchanged. Labels are AI-assisted and await independent human validation.

- [English paper draft and tables](PAPER_RESULTS.md)
- [Evidence examples](EXAMPLES.md) and [machine-readable examples](examples.json)
- [Interactive record browser](review.html): exact supplied policy, customer prompt, original final/trace, evidence and labels; opens locally without a server
- [All evidence-bearing annotations](annotations.jsonl), [summary JSON](summary.json), [tables](tables/), [PNG/PDF/SVG figures](figures/)
- [Annotation protocol](protocol.md), [source hashes/reference issue register](source_manifest.json), [preservation checks](qa_source_preservation.json)
- [Blank independent human review worksheet](tables/human_review_worksheet.csv)

Reproduce from repository root, with the existing `.venv` (numpy/matplotlib):

```sh
.venv/bin/python analysis/policy_compliance_2026-10-18/report.py
.venv/bin/python -m unittest discover -s analysis/policy_compliance_2026-10-18 -p test_analysis.py -v
```

The report reads saved semantic reviews; it does not regenerate model outputs. Do not rerun reviewer-authored replay scripts when making isolated adjudication edits unless the script contains those edits too. Failed local-judge calibration drafts are kept for provenance but excluded from metrics. See the paper draft for exclusions, unknowns, denominator differences and limitations.
