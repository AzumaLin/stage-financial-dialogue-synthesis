"""Persona filtering for the released Stage generation method."""

import json


EXCLUDED_PERSONA_KEYS = {
    "adviser_notes",
    "client_file",
    "conversation_id",
    "conversation_identifier",
    "conv_id",
    "customer_file",
    "established_facts",
    "generation_metadata",
    "graph",
    "loa_signed",
    "persona_brief",
    "persona_summary",
    "prompt",
    "role",
    "source_conversation",
    "source_conversation_id",
    "source_id",
    "stage_graph_method",
}


def structured_persona(persona):
    """Return source persona fields without summaries or runtime metadata."""
    return {
        key: value for key, value in persona.items()
        if key not in EXCLUDED_PERSONA_KEYS
        and not key.startswith(("session_", "events_", "adviser_", "runtime_"))
    }


def persona_json(persona):
    return json.dumps(structured_persona(persona), indent=2, ensure_ascii=False)
