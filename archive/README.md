# Historical research material

This directory preserves earlier inputs and review material. The current pipeline never discovers scenarios here.

- `previous_dataset/data/`: original domain-wide core/source arrays, domain registry, earlier dataset READMEs, airline source example, and all original generated JSONL/CSV/Markdown review exports.
- `previous_dataset/pilot_prompts/`: the five earlier expanded pilot inputs. The airline refund pilot duplicated the active `airlines_001_no_show` strict/neutral messages and is not a second core.
- `previous_dataset/PILOT_README.md`: previous usage instructions.
- `multi_airline_baseline_v04/`: the eleven version-0.4 cases from six airlines, preserved unchanged before the switch to one shared easyJet cabin-bag policy in version 0.5.
- `cabin_only_baseline_v05/`: the ten local version-0.5 cabin-bag cases and their shared policy, preserved unchanged before the version-0.6 expansion to five easyJet policy topics.
- `multi_topic_baseline_v06/`: the eleven five-topic easyJet drafts and their shared policy, preserved unchanged before adding refunds in version 0.7.
- `mock_pilots_before_v08/`: the four Northstar retail, telecom, hotel and warranty mock examples, preserved before activating the new AT&T and Amazon.nl policies. These examples are excluded from default CLI and UI discovery.
- `research_notes/`: original project/meeting DOCX documents, prior airline review, and the pre-existing Office lock file.

Earlier documents describe previous architectures and include superseded discussion of a separate “normal” policy. The current experiment has exactly `strict`, `exception`, `ambiguous`; strict is the normal/base rule. Use the root README and active JSON for current instructions. Historical results retain the messages actually used at the time and remain untouched under `results/`.

Source registers contain historical notes, not freshly verified policy snapshots. Generated review sheets are preserved here because they are research artifacts; current exports go to `results/dataset_build*/` and are reproducible from the active source.

`fictional_airline_baseline/` preserves the ten version-0.3 airline core JSON files before real-provider migration. Version 0.4 uses real airline identities, checked published-policy summaries, separately labeled experimental interventions and corrected easyJet fee assumptions. These archived cores remain historical inputs, not active data.

Internal DOCX research and meeting documents are retained locally and omitted from the code repository.
