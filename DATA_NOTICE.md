# Data Notice

`data/stage_sanitized.jsonl` contains privacy-sanitised synthetic financial-consultation dialogues only. It is not the unprocessed output used in the experiments. Email addresses, phone numbers, postcodes, dates of birth, street addresses, National Insurance numbers, and account-like values detected during privacy sanitisation are replaced with typed placeholders. Generated client and adviser names are retained. Source conversation identifiers have been replaced with sequential public identifiers.

The export excludes source transcripts, personas, CRM records, prompts, rolling summaries, adviser notes, cumulative facts, success signals, and evaluation annotations.

The privacy processing does not alter ordinary generation-quality issues such as `[Firm Name]`, incomplete sentences, or template-like wording. These artefacts are retained because they occurred in the generated corpus used in the dissertation experiments.

The dialogues were generated from personas derived from anonymised Aveni consultations. Confirm that the intended public release is permitted by the applicable Aveni agreement and university ethics/data-management requirements before publishing this directory.
