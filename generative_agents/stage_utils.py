import json
import logging
import re

from global_methods import run_chatgpt
from generative_agents.factfind_prompts import STAGE_GRAPH_PROMPT
from generative_agents.persona_utils import persona_json


REQUIRED_STAGE_FIELDS = (
    "id", "stage_type", "topic", "description", "instruction", "success_signal",
)


def build_financial_context(agent):
    return persona_json(agent)


def _strip_markdown_json(text):
    text = re.sub(r"^```json\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def _is_loa(stage_type):
    value = str(stage_type).strip().lower()
    return value == "loa process" or "letter of authority" in value


def validate_stage_graph(graph, consultation_context):
    if not isinstance(graph, list) or not 5 <= len(graph) <= 8:
        raise ValueError("stage graph must contain 5 to 8 stages")
    for index, stage in enumerate(graph, start=1):
        if not isinstance(stage, dict):
            raise ValueError("stage S%d must be an object" % index)
        missing = [key for key in REQUIRED_STAGE_FIELDS if key not in stage]
        if missing:
            raise ValueError("stage S%d is missing: %s" % (index, ", ".join(missing)))
        if stage["id"] != "S%d" % index:
            raise ValueError("stage IDs must be consecutive S1...Sn")
        for key in REQUIRED_STAGE_FIELDS[1:]:
            if not isinstance(stage[key], str) or not stage[key].strip():
                raise ValueError("stage S%d field %s must be a non-empty string" % (index, key))

    types = [stage["stage_type"].strip().lower() for stage in graph]
    if types[0] != "opening":
        raise ValueError("the first stage must be Opening")
    if types[1] != "trigger discussion":
        raise ValueError("the second stage must be Trigger Discussion")
    if types[-1] != "closing":
        raise ValueError("the final stage must be Closing")

    loa_count = sum(_is_loa(stage["stage_type"]) for stage in graph)
    if consultation_context == "returning" and loa_count:
        raise ValueError("returning-client graphs must not contain LOA Process")
    if consultation_context == "new" and loa_count != 1:
        raise ValueError("new-client graphs must contain exactly one LOA Process")
    return graph


def get_stage_graph(agent, args=None):
    del args
    logging.info("Generating stage graph for %s", agent["name"])
    last_error = None
    for attempt in range(1, 4):
        context = build_financial_context(agent)
        try:
            output = run_chatgpt(
                STAGE_GRAPH_PROMPT % context,
                num_gen=1,
                num_tokens_request=3000,
                temperature=0.8,
            ).strip()
            graph = json.loads(_strip_markdown_json(output))
            return validate_stage_graph(
                graph, str(agent.get("consultation_context", "new")).strip().lower()
            )
        except Exception as exc:
            last_error = exc
            logging.warning("Stage graph attempt %d/3 failed: %s", attempt, exc)
    raise RuntimeError("Stage graph generation failed after 3 attempts: %s" % last_error)


def get_stage_string(stage):
    text = "STAGE: %s\nTOPIC: %s\nOBJECTIVE: %s" % (
        stage.get("stage_type", ""),
        stage.get("topic", ""),
        stage.get("description", ""),
    )
    instruction = stage.get("instruction", "")
    if instruction:
        text += "\nINSTRUCTION: %s" % instruction
    return text
