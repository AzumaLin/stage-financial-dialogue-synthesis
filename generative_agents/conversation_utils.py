from generative_agents.factfind_prompts import (
    ADVISER_CONV_PROMPT_STAGE,
    ADVISER_CONV_PROMPT_STAGE_INIT,
    CUSTOMER_CONV_PROMPT_STAGE,
    CUSTOMER_CONV_PROMPT_STAGE_INIT,
)


SESSION_SUMMARY_PROMPT = "Previous conversations between %s and %s so far can be summarized as follows: %s. The current time and date are %s. %s and %s just had the following conversation:\n\n%s\n\nSummarize the previous and current conversations between %s and %s in 150 words or less. Include key facts about both speakers and time references.\n\n"
SESSION_SUMMARY_INIT_PROMPT = "Write a concise summary containing key facts mentioned about %s and %s on %s in the following conversation:\n\n%s\n\n"

ADVISER_NOTES_PROMPT = """You are {adviser_name}, a Certified Financial Planner. After completing Stage {stage_num} ({stage_type}) of a consultation with {client_name}, rewrite your private client notes to reflect everything you know so far.

{previous_notes_section}
Stage {stage_num} dialogue:
{dialogue}

Rewrite your notes incorporating what was just discussed. Output only valid JSON with exactly these keys:
{{
  "confirmed_facts": ["concrete facts the client has stated - figures, timelines, decisions made"],
  "revealed_concerns": ["worries, fears or anxieties the client has expressed"],
  "emotional_signals": ["how the client has behaved - avoidance, defensiveness, relief, trust, hesitation"],
  "pending_follow_ups": ["things still vague, unresolved, or needing clarification in a later stage"]
}}

Rules:
- Keep each list to at most 3 items - the most current and relevant points only.
- Replace outdated items with newer, more specific information from later stages.
- Every item must be grounded in something the client actually said or did.
Output only valid JSON starting with {{."""


def _first_sentence(text):
    text = str(text).strip()
    for separator in (". ", "; ", " - "):
        index = text.find(separator)
        if 0 <= index < 120:
            return text[:index].rstrip(".,;")
    return text[:120].rstrip(".,;")


def format_persona_brief(persona):
    employment = persona.get("employment_details", {})
    goals = persona.get("financial_goals", {})
    risk = str(persona.get("risk_tolerance", "")).split(";")[0][:40]
    return "\n".join([
        "[Basic Information]",
        "Name: {name}, Age: {age}, Gender: {gender}, Region: {region}.".format(**{
            "name": persona.get("name", ""), "age": persona.get("age", ""),
            "gender": persona.get("gender", ""), "region": persona.get("region", ""),
        }),
        "Occupation: %s (%s)." % (
            employment.get("job_title", ""), employment.get("employment_status", "")
        ),
        "Family: %s." % _first_sentence(persona.get("family_relationship", "")),
        "[Financial Background]",
        "Income: %s." % _first_sentence(persona.get("income_level", "")),
        "Assets: %s." % persona.get("assets_summary", ""),
        "Liabilities: %s." % persona.get("liabilities_summary", ""),
        "Investment experience: %s." % _first_sentence(persona.get("financial_literacy", "")),
        "[Support History]",
        "Consultation purpose: %s." % persona.get(
            "consultation_purpose_brief", _first_sentence(persona.get("consultation_purpose", ""))
        ),
        "Recent events: %s." % _first_sentence(persona.get("emotional_and_financial_state", "")),
        "[Risk Profile]",
        "Risk preference: %s." % risk,
        "Goals: short-term: %s; long-term: %s." % (
            _first_sentence(goals.get("short_term", "")),
            _first_sentence(goals.get("long_term", "")),
        ),
        "[Communication Style]",
        "%s." % _first_sentence(persona.get("language_style", "")),
    ])


def format_client_file(persona):
    employment = persona.get("employment_details", {})
    return (
        "Name: {name}, Age: {age}, Gender: {gender}, Region: {region}. "
        "Employment: {job} ({status}), {conditions}. Income: {income}. "
        "Credit score: {credit}. Debt-to-income ratio: {ratio}. "
        "Living conditions: {living}. Reason for consultation: {purpose}."
    ).format(
        name=persona.get("name", ""), age=persona.get("age", ""),
        gender=persona.get("gender", ""), region=persona.get("region", ""),
        job=employment.get("job_title", ""), status=employment.get("employment_status", ""),
        conditions=employment.get("working_conditions", ""),
        income=persona.get("income_level", ""), credit=persona.get("credit_score", ""),
        ratio=persona.get("debt_to_income_ratio", ""),
        living=persona.get("living_conditions", ""),
        purpose=persona.get("consultation_purpose", ""),
    )


def clean_dialog(output, name):
    output = output.strip()
    if output.startswith(name):
        output = output[len(name):].lstrip()
        if output.startswith(":"):
            output = output[1:].lstrip()
    return output
