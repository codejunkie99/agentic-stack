"""Shared model-call helper. Factored out of conductor so memory/ can reuse."""
import os


# MiniMax regional endpoints. Each region exposes OpenAI- and Anthropic-compatible
# base URLs so the portable harness can call MiniMax directly instead of relying
# on undocumented external SDK environment behavior.
MINIMAX_REGIONS = {
    "global_en": {
        "openai_base_url": "https://api.minimax.io/v1",
        "anthropic_base_url": "https://api.minimax.io/anthropic",
    },
    "cn_zh": {
        "openai_base_url": "https://api.minimaxi.com/v1",
        "anthropic_base_url": "https://api.minimaxi.com/anthropic",
    },
}

# Current MiniMax text models. ``MiniMax-M3`` is the default; ``MiniMax-M2.7`` is
# also supported via AGENT_MODEL. Context windows are in tokens.
MINIMAX_MODELS = {
    "MiniMax-M3": {"context_window": 1000000},
    "MiniMax-M2.7": {"context_window": 204800},
}
MINIMAX_DEFAULT_MODEL = "MiniMax-M3"


def _minimax_region():
    """Resolve the configured MiniMax region and return its base URLs."""
    region = os.getenv("AGENT_MINIMAX_REGION", "global_en").lower()
    if region not in MINIMAX_REGIONS:
        raise ValueError(f"unknown MiniMax region: {region}")
    return region


def llm_available():
    """True iff provider + key are configured. Validation / dream cycle check
    this before making calls so they degrade gracefully offline."""
    provider = os.getenv("AGENT_PROVIDER", "anthropic").lower()
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "minimax":
        return bool(os.getenv("MINIMAX_API_KEY"))
    return False


def _call_minimax(system, user, *, temperature, max_tokens, model):
    region = _minimax_region()
    base_urls = MINIMAX_REGIONS[region]
    model = model or os.getenv("AGENT_MODEL", MINIMAX_DEFAULT_MODEL)
    if model not in MINIMAX_MODELS:
        raise ValueError(
            f"unknown MiniMax model: {model}. "
            f"Supported: {', '.join(MINIMAX_MODELS)}"
        )
    api_key = os.getenv("MINIMAX_API_KEY", "")
    wire = os.getenv("AGENT_MINIMAX_WIRE", "openai").lower()
    if wire == "anthropic":
        from anthropic import Anthropic
        c = Anthropic(api_key=api_key, base_url=base_urls["anthropic_base_url"])
        r = c.messages.create(
            model=model,
            max_tokens=max_tokens, temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return r.content[0].text
    if wire == "openai":
        from openai import OpenAI
        c = OpenAI(api_key=api_key, base_url=base_urls["openai_base_url"])
        r = c.chat.completions.create(
            model=model,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return r.choices[0].message.content
    raise ValueError(f"unknown MiniMax wire: {wire}")


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
    if provider == "minimax":
        return _call_minimax(
            system, user,
            temperature=temperature, max_tokens=max_tokens, model=model,
        )
    raise ValueError(f"unknown provider: {provider}")
