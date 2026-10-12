"""Four strategy seats: the swappable policy around the model.

    memory      what a turn gets to see        memory_seat(user_input, budget) -> (context, used)
    planning    how it approaches the work     planning_seat(user_input) -> str
    capability  which tools an iteration gets  capability_seat(user_input) -> [tool names]
    action      judge a step before it runs    action_seat(tool, operation, args) -> (allowed, reason)

Defaults live in this file and reuse the existing harness (context_budget,
pre_tool_call, protocols/). `harness/seats.json` overrides any seat with a
`"module:function"` spec — a module name importable from `harness/`, or an
absolute `.py` path — so an evolver candidate (cell `runtime`) can swap one
seat without touching the conductor:

    {"planning": "seats_custom:planning_seat",
     "disabled_tools": ["shell"]}

The conductor stays dumb: it asks each seat, assembles, calls the model.
"""
import importlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SEATS = ("memory", "planning", "capability", "action")
sys.path.insert(0, HERE)

DEFAULT_PLANNING = (
    "Approach: restate the goal in one line; list what is known from memory; "
    "plan the smallest sequence of steps; act; verify each step against evidence "
    "before claiming completion; log the outcome."
)


def _config(root=None):
    path = os.path.join(root or HERE, "seats.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def memory_seat(user_input, budget=80000):
    from context_budget import build_context
    return build_context(user_input, budget=budget)


def planning_seat(user_input):
    path = os.path.join(HERE, "PLANNING.md")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return DEFAULT_PLANNING


def capability_seat(user_input, root=None):
    cfg = _config(root)
    schemas = os.path.join(AGENT_ROOT, "protocols", "tool_schemas")
    tools = []
    if os.path.isdir(schemas):
        tools = sorted(f[:-len(".schema.json")] for f in os.listdir(schemas) if f.endswith(".schema.json"))
    disabled = set(cfg.get("disabled_tools") or [])
    return [t for t in tools if t not in disabled]


def action_seat(tool, operation, args):
    from hooks.pre_tool_call import check_tool_call
    return check_tool_call(tool, operation, args or {})


_DEFAULTS = {"memory": memory_seat, "planning": planning_seat,
             "capability": capability_seat, "action": action_seat}


def _resolve(spec):
    mod_name, _, fn_name = spec.partition(":")
    if not fn_name:
        raise ValueError(f"seat spec must be module:function, got {spec!r}")
    if mod_name.endswith(".py") or os.path.isabs(mod_name):
        s = importlib.util.spec_from_file_location("seat_override", mod_name)
        mod = importlib.util.module_from_spec(s)
        s.loader.exec_module(mod)
    else:
        mod = importlib.import_module(mod_name)
    return getattr(mod, fn_name)


def seat(name, root=None):
    """Return the callable bound to `name`, honoring seats.json overrides."""
    if name not in SEATS:
        raise KeyError(name)
    spec = _config(root).get(name)
    if spec:
        return _resolve(spec)
    return _DEFAULTS[name]


def describe(root=None):
    cfg = _config(root)
    return {s: cfg.get(s, "default") for s in SEATS}


if __name__ == "__main__":
    print(json.dumps(describe(), indent=2))
