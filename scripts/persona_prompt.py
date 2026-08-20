PERSONA_EXTRACT_PROMPT = """You are extracting a client persona from a real UK financial consultation call transcript.

The transcript is anonymised: real names, locations, companies, and numbers have been replaced with generic placeholders.

Read the transcript and extract what you can infer about the client. Be specific where the transcript gives clear information; use "Not mentioned" where it does not.

Output a valid JSON object with EXACTLY these keys:

{{
  "name": "the first name the adviser uses to address the client in the transcript; if two clients are present, use the primary speaker's anonymised name; do not invent a name",
  "gender": "male or female, inferred from pronouns or context, or unknown",
  "age": "age as an integer when directly stated or reliably calculable from the transcript, otherwise null",
  "region": "England, Scotland, Wales, or more specific if mentioned",
  "role": "customer",
  "employment_details": {{
    "job_title": "as mentioned",
    "employment_status": "employed, self-employed, retired, part-time, or Not mentioned",
    "working_conditions": "brief description"
  }},
  "family_relationship": "married, single, in a relationship, and children if mentioned",
  "living_conditions": "owns or rents, and mortgage situation if mentioned",
  "income_level": "approximate figure or description if mentioned",
  "assets_summary": "savings, ISAs, pensions, and property mentioned",
  "liabilities_summary": "mortgage, loans, and credit cards mentioned",
  "consultation_purpose_brief": "one sentence explaining why the client called",
  "consultation_purpose": "two or three sentences describing what the client wants",
  "financial_goals": {{
    "short_term": "next one or two years",
    "medium_term": "three to ten years",
    "long_term": "more than ten years or retirement"
  }},
  "risk_tolerance": "conservative, moderate, or adventurous based on the conversation",
  "financial_literacy": "Low, Low-Medium, Medium, or High based on how the client discusses finances",
  "current_financial_stress_level": "Low, Medium, or High with a brief reason",
  "emotional_and_financial_state": "how the client comes across, such as relaxed, anxious, organised, or confused",
  "language_style": "how the client communicates, such as chatty, formal, vague, or precise",
  "health": "Good, Poor, or Not mentioned",
  "consultation_context": "new or returning, inferred from direct evidence about whether the client has previously worked with the adviser or firm",
  "persona_brief": "a 150-200 word summary using these headings: Basic Information, Financial Background, Consultation Context, Risk Profile, and Communication Style",
  "client_file": "Name, age, region, occupation, and reason for calling in one sentence"
}}

TRANSCRIPT:
{transcript}

Output ONLY valid JSON starting with {{. No explanation and no Markdown."""

DEFAULT_ADVISER = {"name": "Adviser", "role": "adviser"}
