"""Small model-provider wrapper used by the released generation code."""

import json
import os
import re
import time


_gemini_client = None
_openai_client = None


def _provider():
    explicit = os.environ.get("MODEL_PROVIDER", "").strip().lower()
    if explicit:
        if explicit not in {"gemini", "openai"}:
            raise ValueError("MODEL_PROVIDER must be 'gemini' or 'openai'")
        return explicit
    if os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    raise EnvironmentError("Set GOOGLE_API_KEY or OPENAI_API_KEY")


def provider_name():
    return _provider()


def model_name(model="chatgpt"):
    provider = _provider()
    if provider == "gemini":
        return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    if model in {"chatgpt", "davinci"}:
        return os.environ.get("OPENAI_GENERATION_MODEL", "gpt-4o-mini")
    return model


def set_openai_key():
    """Initialise the provider; the legacy name is kept for compatibility."""
    global _gemini_client, _openai_client
    provider = _provider()
    if provider == "gemini" and _gemini_client is None:
        from google import genai

        _gemini_client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    elif provider == "openai" and _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def run_chatgpt(
    query,
    num_gen=1,
    num_tokens_request=1000,
    model="chatgpt",
    use_16k=False,
    temperature=1.0,
    wait_time=1,
):
    """Generate one response using Gemini or OpenAI.

    The original LoCoMo-compatible function name and signature are retained.
    The thesis generation runs used Gemini 2.5 Flash through this interface.
    """
    del num_gen, use_16k
    set_openai_key()
    provider = _provider()

    for attempt in range(6):
        try:
            if provider == "gemini":
                from google.genai import types

                selected_model = model_name(model)
                config = {
                    "max_output_tokens": num_tokens_request,
                    "temperature": temperature,
                }
                if "flash" in selected_model.lower():
                    config["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
                response = _gemini_client.models.generate_content(
                    model=selected_model,
                    contents=query,
                    config=types.GenerateContentConfig(**config),
                )
                return response.text or ""

            selected_model = model_name(model)
            response = _openai_client.chat.completions.create(
                model=selected_model,
                messages=[{"role": "user", "content": query}],
                temperature=temperature,
                max_tokens=num_tokens_request,
            )
            return response.choices[0].message.content or ""
        except Exception:
            if attempt == 5:
                raise
            time.sleep(wait_time * (2 ** attempt))


def run_chatgpt_with_examples(
    query,
    examples,
    input,
    num_gen=1,
    num_tokens_request=1000,
    use_16k=False,
    wait_time=1,
    temperature=1.0,
):
    del num_gen, use_16k
    blocks = [query]
    for example_input, example_output in examples:
        blocks.append("INPUT:\n%s\nOUTPUT:\n%s" % (example_input, example_output))
    blocks.append("INPUT:\n%s\nOUTPUT:" % input)
    return run_chatgpt(
        "\n\n".join(blocks),
        num_tokens_request=num_tokens_request,
        temperature=temperature,
        wait_time=wait_time,
    )


def run_json_trials(
    query,
    num_gen=1,
    num_tokens_request=1000,
    model="chatgpt",
    use_16k=False,
    temperature=1.0,
    wait_time=1,
    examples=None,
    input=None,
):
    for attempt in range(10):
        if examples is not None and input is not None:
            output = run_chatgpt_with_examples(
                query,
                examples,
                input,
                num_tokens_request=num_tokens_request,
                temperature=temperature,
                wait_time=wait_time,
            )
        else:
            output = run_chatgpt(
                query,
                num_gen=num_gen,
                num_tokens_request=num_tokens_request,
                model=model,
                use_16k=use_16k,
                temperature=temperature,
                wait_time=wait_time,
            )
        try:
            return json.loads(output.strip())
        except json.JSONDecodeError:
            match = re.search(r"(\{.*\}|\[.*\])", output, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        if attempt < 9:
            time.sleep(wait_time)
    raise ValueError("Model did not return valid JSON after 10 attempts")
