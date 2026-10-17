import json
import re
from pathlib import Path


# Combined experiment output to split by model_id
INPUT_FILE = Path(
    "results/experiments/clean_local_models_v09_20261014T233610Z/all_trials.json"
)

# Çıktı klasörü
OUTPUT_ROOT = Path("results")


def safe_name(model_id):
    """
    Convert e.g.
    Qwen/Qwen2.5-7B-Instruct
    ->
    qwen_qwen2.5_7b_instruct
    """
    name = model_id.strip().lower()
    name = re.sub(r"[^a-z0-9._-]+", "_", name)
    return name.strip("_")


# ------------------------------------------------------------
# Load combined JSON
# ------------------------------------------------------------

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)


# If the file is directly a JSON array
if isinstance(data, list):
    trials = data

# Handle common wrapper formats if needed
elif isinstance(data, dict):
    if "trials" in data:
        trials = data["trials"]
    elif "results" in data:
        trials = data["results"]
    else:
        raise ValueError(
            "Could not find trials. Expected a JSON array "
            "or a dict containing 'trials' or 'results'."
        )

else:
    raise ValueError("Unsupported JSON structure.")


# ------------------------------------------------------------
# Group trials by model
# ------------------------------------------------------------

models = {}

for trial in trials:

    model_id = trial.get("model_id")

    # Some result schemas may store it inside model metadata
    if not model_id and isinstance(trial.get("model"), dict):
        model_id = trial["model"].get("model_id")

    if not model_id:
        raise ValueError(
            f"Trial has no model_id:\n{json.dumps(trial, indent=2)[:500]}"
        )

    models.setdefault(model_id, []).append(trial)


# ------------------------------------------------------------
# Save in the same structure as our batch runner
# ------------------------------------------------------------

for model_id, model_trials in models.items():

    folder_name = safe_name(model_id)

    model_dir = OUTPUT_ROOT / folder_name
    trials_dir = model_dir / "trials"

    model_dir.mkdir(parents=True, exist_ok=True)
    trials_dir.mkdir(parents=True, exist_ok=True)

    # Individual trial JSON files
    for i, trial in enumerate(model_trials, start=1):

        prompt_id = (
            trial.get("prompt_id")
            or trial.get("trial_id")
            or f"trial_{i:04d}"
        )

        trial_file = trials_dir / f"{prompt_id}.json"

        with open(trial_file, "w", encoding="utf-8") as f:
            json.dump(
                trial,
                f,
                ensure_ascii=False,
                indent=2
            )

    # all_trials.json
    with open(model_dir / "all_trials.json", "w", encoding="utf-8") as f:
        json.dump(
            model_trials,
            f,
            ensure_ascii=False,
            indent=2
        )

    # all_trials.jsonl
    with open(model_dir / "all_trials.jsonl", "w", encoding="utf-8") as f:
        for trial in model_trials:
            f.write(
                json.dumps(trial, ensure_ascii=False) + "\n"
            )

    print(
        f"{model_id}: {len(model_trials)} trials "
        f"-> {model_dir}"
    )


print("\nDone.")