import json
import logging
import os
import re

from global_methods import run_chatgpt
from generative_agents.conversation_utils import (
    ADVISER_CONV_PROMPT_STAGE,
    ADVISER_CONV_PROMPT_STAGE_INIT,
    ADVISER_NOTES_PROMPT,
    CUSTOMER_CONV_PROMPT_STAGE,
    CUSTOMER_CONV_PROMPT_STAGE_INIT,
    SESSION_SUMMARY_INIT_PROMPT,
    SESSION_SUMMARY_PROMPT,
    clean_dialog,
)
from generative_agents.stage_utils import get_stage_string
from generative_agents.persona_utils import persona_json


def save_agents(agents, args):
    client, adviser = agents
    with open(args.customer_file, "w", encoding="utf-8") as handle:
        json.dump(client, handle, indent=2, ensure_ascii=False)
    with open(args.adviser_file, "w", encoding="utf-8") as handle:
        json.dump(adviser, handle, indent=2, ensure_ascii=False)


def load_agents(args):
    with open(args.customer_file, encoding="utf-8") as handle:
        client = json.load(handle)
    with open(args.adviser_file, encoding="utf-8") as handle:
        adviser = json.load(handle)
    return client, adviser


def get_adviser_notes(session, adviser, client, stage_num, stage_type, previous_notes=None):
    dialogue = "\n".join("%s: %s" % (turn["speaker"], turn["clean_text"]) for turn in session)
    if previous_notes:
        lines = [
            "%s: %s" % (key, "; ".join(items))
            for key, items in previous_notes.items()
            if items
        ]
        previous_section = "Your notes so far:\n" + "\n".join(lines) + "\n\n"
    else:
        previous_section = ""
    query = ADVISER_NOTES_PROMPT.format(
        adviser_name=adviser["name"],
        stage_num=stage_num,
        stage_type=stage_type,
        client_name=client["name"],
        previous_notes_section=previous_section,
        dialogue=dialogue,
    )
    try:
        output = run_chatgpt(query, num_tokens_request=1000).strip()
        output = re.sub(r"^```json\s*|^```\s*", "", output, flags=re.MULTILINE).strip()
        notes = json.loads(output)
    except Exception as exc:
        logging.warning("Adviser notes generation failed (%s); retaining previous notes", exc)
        return previous_notes or {}
    keys = ("confirmed_facts", "revealed_concerns", "emotional_signals", "pending_follow_ups")
    return {key: notes.get(key, [])[:3] for key in keys}


def format_adviser_notes(notes):
    if not notes:
        return "No notes yet."
    labels = {
        "confirmed_facts": "Confirmed facts",
        "revealed_concerns": "Concerns expressed",
        "emotional_signals": "Emotional signals",
        "pending_follow_ups": "Pending follow-ups",
    }
    sections = []
    for key, label in labels.items():
        items = notes.get(key, [])
        if items:
            sections.append("%s:\n%s" % (label, "\n".join("- " + item for item in items)))
    return "\n\n".join(sections) or "No notes yet."


def get_session_summary(session, client, adviser, current_stage, previous_summary=""):
    dialogue = "\n".join("%s: %s" % (turn["speaker"], turn["clean_text"]) for turn in session)
    if previous_summary:
        query = SESSION_SUMMARY_PROMPT % (
            client["name"], adviser["name"], previous_summary, current_stage,
            client["name"], adviser["name"], dialogue, client["name"], adviser["name"],
        )
    else:
        query = SESSION_SUMMARY_INIT_PROMPT % (
            client["name"], adviser["name"], current_stage, dialogue,
        )
    return run_chatgpt(query, num_tokens_request=1000).strip()


def get_agent_query(
    speaker,
    other,
    current_stage_id,
    turn_index,
    stage_max_turns,
    adviser_notes=None,
    instruct_stop=False,
    style_example="",
):
    stop = (
        "When this stage has reached a natural conclusion, write [END] at the very end of your turn."
        if instruct_stop else ""
    )
    if turn_index < int(stage_max_turns * 0.35):
        depth = "You are in the early part of this stage. Do not wrap up yet; explore relevant details."
    elif turn_index < int(stage_max_turns * 0.70):
        depth = "You are in the middle of this stage. Continue the discussion and avoid summarising too early."
    else:
        depth = "You are approaching the end of this stage. Conclude naturally when its objectives are met."

    stage = speaker["events_session_%s" % current_stage_id][0]
    stage_string = get_stage_string(stage)
    summary = speaker.get("session_%s_summary" % (current_stage_id - 1), "")

    if speaker.get("role", "customer") == "adviser":
        is_returning = other.get("consultation_context", "new") == "returning"
        if is_returning:
            call_goal = (
                "Understand why the client returned, review their current circumstances, "
                "and complete the relevant financial fact-find. Do not introduce or request "
                "a Letter of Authority unless the client explicitly raises it. You may explain "
                "processes, describe what happens next, share general guidance, and reassure "
                "the client along the way."
            )
        else:
            call_goal = (
                "Understand why the client called, obtain a signed Letter of Authority where "
                "needed, and complete a financial fact-find covering their income, savings, "
                "protection, and liabilities. You may explain processes, describe what happens "
                "next, share general guidance, and reassure the client along the way."
            )
        transition = (
            "Acknowledge what was just covered before steering naturally into the new topic. "
            "Do not announce the stage name."
            if current_stage_id > 1 and turn_index == 0 else ""
        )
        if is_returning:
            client_context = "CLIENT ON FILE: %s" % other.get("client_file", "")
        else:
            client_context = "This is a new client. Discover their information through conversation."
        persistent = []
        if other.get("loa_signed"):
            persistent.append("The Letter of Authority was already signed earlier in this call; do not request it again.")
        persistent.extend(other.get("established_facts", []))
        if persistent:
            client_context += "\n\nKEY FACTS CONFIRMED SO FAR:\n" + "\n".join("- " + fact for fact in persistent)

        if current_stage_id == 1:
            return ADVISER_CONV_PROMPT_STAGE_INIT.format(
                adviser_name=speaker["name"], client_context=client_context,
                stage_string=stage_string, depth_instruction=depth, stop_instruction=stop,
                call_goal=call_goal, style_example=style_example,
            )
        return ADVISER_CONV_PROMPT_STAGE.format(
            adviser_name=speaker["name"], client_context=client_context,
            adviser_notes=format_adviser_notes(adviser_notes), stage_string=stage_string,
            summary=summary, depth_instruction=depth, stop_instruction=stop,
            transition_instruction=transition,
            call_goal=call_goal, style_example=style_example,
        )

    full_persona = persona_json(speaker)
    if current_stage_id == 1:
        return CUSTOMER_CONV_PROMPT_STAGE_INIT.format(
            customer_name=speaker["name"], adviser_name=other["name"],
            full_persona=full_persona, stage_string=stage_string,
            depth_instruction=depth, stop_instruction=stop,
            style_example=style_example,
        )
    return CUSTOMER_CONV_PROMPT_STAGE.format(
        customer_name=speaker["name"], adviser_name=other["name"],
        full_persona=full_persona, stage_string=stage_string, summary=summary,
        depth_instruction=depth, stop_instruction=stop,
        style_example=style_example,
    )


SUCCESS_SIGNAL_CHECK_PROMPT = """You are evaluating a financial consultation dialogue.

SUCCESS SIGNAL: {success_signal}

LAST TURNS:
{last_turns}

Has the success signal been achieved? Reply with YES or NO only."""


def check_success_signal(success_signal, session):
    if not success_signal or len(session) < 4:
        return False
    last_turns = "\n".join(
        "%s: %s" % (turn["speaker"], turn["clean_text"]) for turn in session[-12:]
    )
    query = SUCCESS_SIGNAL_CHECK_PROMPT.format(
        success_signal=success_signal, last_turns=last_turns
    )
    try:
        result = run_chatgpt(query, num_tokens_request=5, temperature=0.0).strip().upper()
        return result.startswith("YES")
    except Exception as exc:
        logging.warning("Success-signal check failed (%s)", exc)
        return False


def get_session(client, adviser, args, curr_sess_id=1, adviser_notes=None, **unused):
    del unused
    current_speaker = 1
    previous = ""
    if curr_sess_id > 1:
        for turn in client.get("session_%s" % (curr_sess_id - 1), [])[-2:]:
            previous += "%s: %s\n" % (turn["speaker"], turn["clean_text"])
    dialogue_prompt = previous + adviser["name"] + ": "

    session = []
    turn_count = 0
    maximum = args.max_turns_per_session
    end_signalled = False
    stop_reason = "max_turn"
    success_achieved = False
    success_signal = client.get("events_session_%s" % curr_sess_id, [{}])[0].get("success_signal", "")
    speaker_pattern = re.compile(r"^[A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*\s*:")

    while turn_count < maximum:
        speaker = client if current_speaker == 0 else adviser
        other = adviser if current_speaker == 0 else client
        speaker_name = speaker["name"]
        minimum_before_end = max(14, int(maximum * 0.6))
        should_stop = turn_count >= minimum_before_end
        query = get_agent_query(
            speaker, other, curr_sess_id, turn_count, maximum,
            adviser_notes=adviser_notes, instruct_stop=should_stop,
            style_example=getattr(args, "style_example", ""),
        )
        output = run_chatgpt(
            query + dialogue_prompt,
            num_tokens_request=160,
            temperature=0.9,
        ) or ""

        lines = []
        for line in output.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if speaker_pattern.match(line) and not line.startswith(speaker_name):
                break
            lines.append(line)

        for line in lines[:1]:
            if turn_count >= maximum:
                break
            line = clean_dialog(line, speaker_name)
            has_end = "[END]" in line and turn_count >= minimum_before_end
            clean_text = line.replace("[END]", "").strip()
            if not clean_text:
                continue
            session.append({
                "text": line,
                "raw_text": line,
                "clean_text": clean_text,
                "speaker": speaker_name,
                "dia_id": "D%s:%s" % (curr_sess_id, turn_count + 1),
            })
            dialogue_prompt += clean_text + "\n"
            turn_count += 1
            if has_end:
                end_signalled = True
                stop_reason = "end"
                break

        if end_signalled:
            break
        dialogue_prompt += "\n%s: " % (client["name"] if current_speaker == 1 else adviser["name"])
        current_speaker = int(not current_speaker)

        if len(session) >= 4:
            recent = [turn["clean_text"] for turn in session[-4:] if turn["speaker"] == speaker_name]
            if len(recent) >= 2:
                latest, previous_turn = recent[-1], recent[-2]
                if len(latest.split()) >= 15 and len(previous_turn.split()) >= 15:
                    overlap = len(set(latest.lower().split()) & set(previous_turn.lower().split()))
                    if overlap / max(len(set(latest.lower().split())), 1) > 0.8:
                        logging.info("Repetition detected; stopping stage at turn %d", turn_count)
                        stop_reason = "repetition"
                        break

        success_check_start = min(maximum, max(16, int(maximum * 0.7)))
        checker_due = turn_count >= success_check_start and (
            current_speaker == 0 or (maximum < 16 and turn_count >= maximum)
        )
        if success_signal and checker_due:
            if check_success_signal(success_signal, session):
                logging.info("Success signal met at turn %d", turn_count)
                success_achieved = True
                stop_reason = "success_signal"
                break

    args.last_stop_reason = stop_reason
    args.last_success_achieved = success_achieved
    return session
