# Stage-Structured Financial Dialogue Synthesis

This repository contains the Stage synthetic dialogue dataset and the code used to generate Stage-structured long-form UK financial-consultation dialogues.

## Contents

- `data/stage_sanitized.jsonl`: privacy-sanitised Stage corpus.
- `scripts/extract_personas.py`: extracts structured client personas from authorised transcripts.
- `scripts/generate_stage.py`: generates one Stage dialogue from one persona directory.
- `scripts/batch_generate.py`: generates Stage dialogues for a directory of personas.
- `scripts/export_stage.py`: converts generation outputs to the released JSONL structure.
- `generative_agents/`: Stage planning, dialogue generation, memory, prompts, and stopping logic.
- `schemas/`: persona and released-dialogue schemas.

Evaluation code, baseline generation methods, ablation methods, CRM code, Aveni preprocessing code, source personas, and source-ID mappings are not included in this release.

## Released Dataset

`data/stage_sanitized.jsonl` contains:

- 199 dialogues;
- 1,356 consultation stages;
- 34,108 turns.

Each JSONL row contains a sequential public dialogue ID, generated participant names, and a list of turns. Each turn contains its global turn ID, stage index, stage label, speaker, and text. Source conversation IDs are not included.

The released file is privacy-sanitised and is not the unprocessed generation output. See `DATA_NOTICE.md` before publication or redistribution.

## Installation

Python 3.10 or later is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The dissertation generation runs used Gemini 2.5 Flash:

```bash
export MODEL_PROVIDER=gemini
export GOOGLE_API_KEY=...
export GEMINI_MODEL=gemini-2.5-flash
```

The provider wrapper also supports OpenAI through `MODEL_PROVIDER=openai`, but this was not the model setting used for the reported Stage corpus.

## Restricted Inputs

Aveni transcripts, extracted personas, source-ID mappings, and the real consultation style excerpt are not included. Reproducing the pipeline requires authorised local copies of these inputs.

Do not commit API keys or restricted inputs to this repository.

## Persona Extraction

Persona extraction accepts JSONL, a JSON list, or a JSON object containing a `conversations` list:

```bash
python scripts/extract_personas.py \
  --input authorised_transcripts.jsonl \
  --out-dir outputs/personas
```

By default, each input record must contain `conversation_id` and `anonymised_text`. The output is one directory per conversation containing `customer.json` and `adviser.json`. The expected persona fields are described in `schemas/persona.schema.json`.

## Stage Generation

An authorised real consultation excerpt must be supplied as a local style-example file. It is used at runtime but is not stored in generated turn records.

Generate one dialogue:

```bash
python scripts/generate_stage.py \
  --persona-dir outputs/personas/example_id \
  --out-dir outputs/stage/example_id \
  --style-example-file authorised/style_example.txt \
  --seed 13
```

Generate all persona directories:

```bash
python scripts/batch_generate.py \
  --persona-root outputs/personas \
  --out-root outputs/stage \
  --style-example-file authorised/style_example.txt \
  --seed 13
```

`--max-turns` overrides the maximum for every stage and therefore differs from the dissertation default. Without this override, a positive limit from the stage plan is used; otherwise the limit is sampled from the stage-type ranges described below.

## Generation Settings

- Stage planning: Gemini 2.5 Flash, temperature 0.8, maximum 3,000 output tokens.
- Dialogue turns: Gemini 2.5 Flash, temperature 0.9, maximum 160 output tokens per call.
- Success checker: temperature 0.0.
- Established-fact extraction: temperature 0.2.
- Stage limits: Opening 6-25, Trigger Discussion 8-35, LOA Process 20-90, Fact-find 12-80, and Closing 8-25 turns.

Each model call contributes at most one spoken turn. A stage ends when its success signal is met, an accepted `[END]` marker is produced, repetitive long turns are detected, or the stage reaches its maximum turn limit.

The adviser receives the current stage guidance, rolling summary, adviser notes, cumulative established facts, and local dialogue context. The client receives the full structured persona, current stage guidance, rolling summary, and local dialogue context. The adviser does not receive the full persona.

New generation outputs record the provider, model, temperatures, seed, style-example SHA-256 hash, applied stage limits, and stopping reasons. They do not store the style example or complete runtime prompts in turn records. The historical seed used for the released corpus was not recorded and has not been reconstructed.

## Public JSONL Export

Generation outputs can be converted to the released structure with:

```bash
python scripts/export_stage.py \
  --input-dir outputs/stage \
  --out outputs/stage.jsonl
```

This export command does not perform privacy redaction. Review and sanitise any newly exported file before publication.

## Attribution and Licence

The generation scaffolding is adapted from LoCoMo. See `NOTICE.md`. This repository grants no rights to excluded Aveni material. Confirm Aveni publication permission and applicable university ethics and data-management requirements before publishing the dataset.
