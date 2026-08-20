"""Generate one Stage consultation from a client persona."""

import argparse
import hashlib
import json
import logging
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from global_methods import model_name, provider_name, run_chatgpt, set_openai_key
from generative_agents.conversation_utils import format_client_file, format_persona_brief
from generative_agents.generate_conversations import (
    get_adviser_notes,
    get_session,
    get_session_summary,
    load_agents,
    save_agents,
)
from generative_agents.persona_utils import structured_persona
from generative_agents.stage_utils import get_stage_graph, validate_stage_graph


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

FACTS_EXTRACT_PROMPT = """Review this stage of a financial consultation.

Stage: {stage_type}
Dialogue:
{dialogue}

Extract up to five concrete facts confirmed in this stage. Include confirmed
financial figures, products, personal details, or procedural milestones.
Write one concise fact per line, starting with a dash. Use only information
explicitly confirmed in the dialogue."""


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--style-example-file",
        required=True,
        help="Authorised Aveni consultation excerpt used for Stage generation",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def make_args(out_dir, max_turns, style_example):
    class Args:
        pass

    args = Args()
    args.out_dir = out_dir
    args.max_turns_per_session = max_turns
    args.max_lines_per_turn = 0
    args.success_signal = True
    args.style_example = style_example
    args.customer_file = os.path.join(out_dir, "customer.json")
    args.adviser_file = os.path.join(out_dir, "adviser.json")
    return args


def copy_persona(persona_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for filename in ("customer.json", "adviser.json"):
        with open(os.path.join(persona_dir, filename), encoding="utf-8") as handle:
            source = json.load(handle)
        if filename == "customer.json":
            output = structured_persona(source)
            output["role"] = "customer"
            output["persona_brief"] = source.get("persona_brief") or format_persona_brief(source)
            output["client_file"] = source.get("client_file") or format_client_file(source)
        else:
            output = {
                "name": source.get("name", "Adviser"),
                "role": "adviser",
            }
        with open(os.path.join(out_dir, filename), "w", encoding="utf-8") as handle:
            json.dump(output, handle, indent=2, ensure_ascii=False)


def update_established_facts(session, stage_type, existing):
    dialogue = "\n".join("%s: %s" % (turn["speaker"], turn["clean_text"]) for turn in session)
    query = FACTS_EXTRACT_PROMPT.format(stage_type=stage_type, dialogue=dialogue)
    try:
        raw = run_chatgpt(query, num_tokens_request=300, temperature=0.2).strip()
        new_facts = [line.lstrip("- ").strip() for line in raw.splitlines() if line.strip().startswith("-")]
        return existing + new_facts[:5]
    except Exception as exc:
        logging.warning("Confirmed-fact extraction failed (%s)", exc)
        return existing


def infer_max_turns(stage_type, rng):
    stage_type = stage_type.lower()
    if "opening" in stage_type:
        return rng.randint(6, 25)
    if "trigger" in stage_type:
        return rng.randint(8, 35)
    if "loa" in stage_type:
        return rng.randint(20, 90)
    if "closing" in stage_type:
        return rng.randint(8, 25)
    if "fact-find" in stage_type or "fact find" in stage_type:
        return rng.randint(12, 80)
    return rng.randint(12, 60)


def resolve_max_turns(stage, override, rng):
    if override is not None:
        if override <= 0:
            raise ValueError("--max-turns must be positive")
        return override
    planned = stage.get("max_turns")
    if isinstance(planned, int) and planned > 0:
        return planned
    return infer_max_turns(stage["stage_type"], rng)


def main():
    cli = parse_args()
    set_openai_key()
    style_example = Path(cli.style_example_file).read_text(encoding="utf-8").strip()
    if not style_example:
        raise ValueError("The authorised style example must not be empty")
    rng = random.Random(cli.seed)
    args = make_args(cli.out_dir, cli.max_turns, style_example)

    if cli.overwrite or not (
        os.path.exists(args.customer_file) and os.path.exists(args.adviser_file)
    ):
        copy_persona(cli.persona_dir, cli.out_dir)
    else:
        logging.info("Resuming existing output in %s", cli.out_dir)

    client, adviser = load_agents(args)
    client.setdefault("role", "customer")
    adviser.setdefault("role", "adviser")
    client.setdefault("persona_brief", format_persona_brief(client))
    client.setdefault("client_file", format_client_file(client))
    adviser.setdefault("client_file", client["client_file"])
    if cli.overwrite or not client.get("graph"):
        graph = [{str(key).lower(): value for key, value in stage.items()} for stage in get_stage_graph(client)]
        validate_stage_graph(graph, client.get("consultation_context", "new"))
        client["graph"] = graph
        adviser["graph"] = graph
        client["stage_graph_method"] = "persona_conditioned"
        adviser["stage_graph_method"] = "persona_conditioned"
        save_agents([client, adviser], args)

    applied_limits = []
    for stage in client["graph"]:
        sampled_limit = resolve_max_turns(stage, cli.max_turns, rng)
        if not cli.overwrite and isinstance(stage.get("applied_max_turns"), int):
            applied_limit = stage["applied_max_turns"]
        else:
            applied_limit = sampled_limit
            stage["applied_max_turns"] = applied_limit
        applied_limits.append(applied_limit)
    adviser["graph"] = [dict(stage) for stage in client["graph"]]
    metadata = {
        "seed": cli.seed,
        "provider": provider_name(),
        "model": model_name(),
        "dialogue_temperature": 0.9,
        "planner_temperature": 0.8,
        "style_example_sha256": hashlib.sha256(style_example.encode("utf-8")).hexdigest(),
        "max_turns_override": cli.max_turns,
        "applied_max_turns": applied_limits,
    }
    client["generation_metadata"] = metadata
    adviser["generation_metadata"] = dict(metadata)
    save_agents([client, adviser], args)

    adviser_notes = None
    for stage_index, stage in enumerate(client["graph"], start=1):
        session_key = "session_%d" % stage_index
        if session_key in client and not cli.overwrite:
            adviser_notes = adviser.get("adviser_notes_stage_%d" % stage_index, adviser_notes)
            continue

        label = "Stage %d: %s" % (stage_index, stage["stage_type"])
        client["events_session_%d" % stage_index] = [stage]
        adviser["events_session_%d" % stage_index] = [stage]
        client["session_%d_date_time" % stage_index] = label
        adviser["session_%d_date_time" % stage_index] = label
        args.max_turns_per_session = stage["applied_max_turns"]

        session = get_session(
            client,
            adviser,
            args,
            curr_sess_id=stage_index,
            adviser_notes=adviser_notes,
        )
        client[session_key] = session
        adviser[session_key] = session
        stage["stopping_reason"] = args.last_stop_reason
        stage["success_achieved"] = args.last_success_achieved
        adviser["graph"][stage_index - 1].update({
            "stopping_reason": args.last_stop_reason,
            "success_achieved": args.last_success_achieved,
        })
        if "loa" in stage["stage_type"].lower():
            if args.last_success_achieved and args.last_stop_reason == "success_signal":
                client["loa_signed"] = True
                adviser["loa_signed"] = True

        facts = update_established_facts(
            session, stage["stage_type"], client.get("established_facts", [])
        )
        client["established_facts"] = facts
        adviser["established_facts"] = facts
        save_agents([client, adviser], args)

        adviser_notes = get_adviser_notes(
            session,
            adviser,
            client,
            stage_index,
            stage["stage_type"],
            previous_notes=adviser_notes,
        )
        adviser["adviser_notes_stage_%d" % stage_index] = adviser_notes

        previous_summary = client.get("session_%d_summary" % (stage_index - 1), "")
        summary = get_session_summary(session, client, adviser, label, previous_summary)
        client["session_%d_summary" % stage_index] = summary
        adviser["session_%d_summary" % stage_index] = summary
        save_agents([client, adviser], args)

    logging.info("Completed %d stages in %s", len(client["graph"]), cli.out_dir)


if __name__ == "__main__":
    main()
