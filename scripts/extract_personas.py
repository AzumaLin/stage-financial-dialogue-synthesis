"""Extract structured client personas from local anonymised transcripts."""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from global_methods import run_chatgpt, set_openai_key
from scripts.persona_prompt import DEFAULT_ADVISER, PERSONA_EXTRACT_PROMPT


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

REQUIRED_FIELDS = {
    "name", "gender", "age", "region", "role", "employment_details",
    "family_relationship", "living_conditions", "income_level",
    "assets_summary", "liabilities_summary", "consultation_purpose_brief",
    "consultation_purpose", "financial_goals", "risk_tolerance",
    "financial_literacy", "current_financial_stress_level",
    "emotional_and_financial_state", "language_style", "health",
    "consultation_context", "persona_brief", "client_file",
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON or JSONL containing anonymised transcripts")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--text-field", default="anonymised_text")
    parser.add_argument("--id-field", default="conversation_id")
    parser.add_argument("--max-characters", type=int, default=80000)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_records(path):
    path = Path(path)
    if path.suffix.lower() == ".jsonl":
        with path.open(encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("conversations"), list):
        return data["conversations"]
    raise ValueError("Input must be a JSON list, a JSON object with conversations, or JSONL")


def parse_model_json(raw):
    raw = re.sub(r"^```json\s*|^```\s*", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw)


def validate_persona(persona):
    if not isinstance(persona, dict):
        raise ValueError("Persona output must be a JSON object")
    missing = sorted(REQUIRED_FIELDS - set(persona))
    if missing:
        raise ValueError("Persona output is missing required fields: %s" % ", ".join(missing))
    if persona["age"] is not None and not isinstance(persona["age"], int):
        raise ValueError("Persona age must be an integer or null")
    if persona["consultation_context"] not in {"new", "returning"}:
        raise ValueError("consultation_context must be new or returning")


def safe_conversation_id(value, fallback):
    conversation_id = str(value if value is not None else fallback).strip()
    if not conversation_id or conversation_id in {".", ".."}:
        raise ValueError("Invalid conversation ID")
    if Path(conversation_id).name != conversation_id or "/" in conversation_id or "\\" in conversation_id:
        raise ValueError("Conversation ID must not contain path components: %s" % conversation_id)
    return conversation_id


def main():
    args = parse_args()
    set_openai_key()
    records = load_records(args.input)
    output_root = Path(args.out_dir)

    failures = []
    for index, record in enumerate(records, start=1):
        conversation_id = safe_conversation_id(record.get(args.id_field), index)
        output_dir = output_root / conversation_id
        client_path = output_dir / "customer.json"
        if client_path.exists() and not args.overwrite:
            continue
        transcript = str(record.get(args.text_field, ""))[:args.max_characters]
        if not transcript.strip():
            failures.append(conversation_id)
            continue
        try:
            raw = run_chatgpt(
                PERSONA_EXTRACT_PROMPT.format(transcript=transcript),
                num_tokens_request=2000,
                temperature=0.3,
            )
            persona = parse_model_json(raw)
            validate_persona(persona)
            output_dir.mkdir(parents=True, exist_ok=True)
            with client_path.open("w", encoding="utf-8") as handle:
                json.dump(persona, handle, indent=2, ensure_ascii=False)
            with (output_dir / "adviser.json").open("w", encoding="utf-8") as handle:
                json.dump(DEFAULT_ADVISER, handle, indent=2, ensure_ascii=False)
            logging.info("[%d/%d] %s", index, len(records), conversation_id)
        except Exception as exc:
            logging.error("Failed %s: %s", conversation_id, exc)
            failures.append(conversation_id)

    if failures:
        raise RuntimeError("Persona extraction failed for: %s" % ", ".join(failures))


if __name__ == "__main__":
    main()
