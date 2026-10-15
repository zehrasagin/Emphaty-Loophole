# Qwen and DeepSeek: completed experimental-policy run

This snapshot contains **1,296 completed single-turn responses**: 648 from
Qwen2.5-7B-Instruct and 648 from DeepSeek-R1-Distill-Qwen-7B.
The grid covers all 54 active synthetic scenarios across five domains,
three experimental policies, and four emotional frames (dataset v0.9.0).

- `all_trials.json`: original finalized records in the existing collection schema.
- `experiment_manifest.json`: selected models, settings, input and code hashes.
- `prompts.jsonl`: the exact frozen model-facing conditions, without reference labels.
- `cores_snapshot.json`: resolved policy/scenario snapshots for provenance.
- `experimental_references.json`: separate draft evaluation references.
- `summary.json`: generation status and coverage counts.

Earliest generation start: `2026-10-14T23:36:22.012900+00:00`.
Latest generated answer finished: `2026-10-15T06:11:48.469666+00:00`.
Summary update times can be later because the completed run was subsequently checked.
The run was resumed after an editor-process interruption; completed conditions were
skipped and the interrupted condition was retried without replacing prior raw files.
This published aggregate contains the 1,296 finalized responses. Local partial raw
attempts, machine logs and lock files are excluded from this snapshot.

Generation completion does **not** establish correctness or policy compliance.
Policies and reference decisions remain draft/pending human review; the manifest
identifies missing evaluation annotations. No automatic compliance scoring was run.
Model-specific generation settings differ and are retained in each trial record.
Model weights remain local.
