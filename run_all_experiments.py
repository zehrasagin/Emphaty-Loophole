import os
import json
import time
import traceback
from pathlib import Path
from datetime import datetime
from dataset import load_scenarios, expand_scenario
from chat_backend import ChatEngine, new_session
from result_io import save_result_record

# Constants
RESULTS_DIR = Path("results/llama_3.1_8b_instruct")
TRIALS_DIR = RESULTS_DIR / "trials"
ALL_TRIALS_JSONL = RESULTS_DIR / "all_trials.jsonl"
ALL_TRIALS_JSON = RESULTS_DIR / "all_trials.json"

# Ensure results directory exists
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
TRIALS_DIR.mkdir(parents=True, exist_ok=True)

# Load scenarios
print("Loading scenarios...")
scenarios = load_scenarios()
print(f"Loaded {len(scenarios)} scenarios.")

# Initialize ChatEngine
engine = ChatEngine()

# Resume support: Load completed trials
completed_trials = set()
if ALL_TRIALS_JSONL.exists():
    with open(ALL_TRIALS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            trial = json.loads(line)
            saved_prompt_id = trial.get("prompt_id")
            if saved_prompt_id:
                completed_trials.add(saved_prompt_id)

# Run experiments
start_time = time.time()
completed, skipped, failed = 0, 0, 0

for scenario in scenarios:
    prompts = expand_scenario(scenario)
    for prompt in prompts:
        prompt_id = prompt["prompt_id"]
        trial_file = TRIALS_DIR / f"{prompt_id}.json"

        if prompt_id in completed_trials or trial_file.exists():
            print(f"SKIP - {prompt_id} already completed.")
            skipped += 1
            continue

        print(f"RUN - {prompt_id}")
        try:
            # Create the same session structure used by the Streamlit app
            session = new_session(
                prompt,
                "llama3",
                mode="condition_preview"
            )

            # In condition_preview mode, use the exact generated customer request
            user_text = prompt["messages"][1]["content"]

            # Run trial using the same backend as Streamlit
            result = engine._respond(session, user_text)
            result["prompt_id"] = prompt_id
            # Save result
            with open(trial_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            with open(ALL_TRIALS_JSONL, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")

            completed += 1
            print(f"DONE - {prompt_id}")
        except Exception as e:
            failed += 1
            print(f"ERROR - {prompt_id}: {e}")
            traceback.print_exc()
            

# Save all trials as JSON array
all_trials = []
if ALL_TRIALS_JSONL.exists():
    with open(ALL_TRIALS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            all_trials.append(json.loads(line))

with open(ALL_TRIALS_JSON, "w", encoding="utf-8") as f:
    json.dump(all_trials, f, ensure_ascii=False, indent=2)

# Print summary
end_time = time.time()
print("\nExperiment Summary:")
print(f"Completed: {completed}")
print(f"Skipped: {skipped}")
print(f"Failed: {failed}")
print(f"Total runtime: {end_time - start_time:.2f} seconds")