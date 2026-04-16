"""Shared model-call helper. Factored out of conductor so memory/ can reuse."""
import os


def llm_available():
    """True iff provider + key are configured. Validation / dream cycle check
    this before making calls so they degrade gracefully offline."""
    provider = os.getenv("AGENT_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    return False


def call_model(system, user, *, temperature=0.3, max_tokens=4096, model=None):
    provider = os.getenv("AGENT_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        from anthropic import Anthropic
        c = Anthropic()
        r = c.messages.create(
            model=model or os.getenv("AGENT_MODEL", "claude-sonnet-4-5"),
            max_tokens=max_tokens, temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text
    if provider == "openai":
        from openai import OpenAI
        c = OpenAI()
        r = c.chat.completions.create(
            model=model or os.getenv("AGENT_MODEL", "gpt-4o"),
            temperature=temperature,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return r.choices[0].message.content
    raise ValueError(f"unknown provider: {provider}")
