"""Thin conductor loop. Reads files, calls the model, logs. No reasoning here.

Strategy lives in four seats (harness/seats.py): memory assembles context,
planning frames the approach, capability lists the tools, action judges a
step. Override any seat via harness/seats.json; the conductor does not care.
"""
import os, sys
from hooks.post_execution import log_execution
from llm import call_model
from seats import seat

RESERVED = 40000
MAX_CTX = int(os.getenv("AGENT_MAX_CONTEXT", "128000"))


SYSTEM_PREAMBLE = (
    "You are an agent with externalized memory, skills, and protocols.\n"
    "Your memory, skills, and constraints are in the context below.\n"
    "Read them before acting. Follow constraints strictly.\n"
    "Log every action. Update memory/working/WORKSPACE.md as you go.\n\n"
)


def run(user_input: str) -> str:
    context, used = seat("memory")(user_input, budget=MAX_CTX - RESERVED)
    frame = seat("planning")(user_input)
    tools = seat("capability")(user_input)
    system = (SYSTEM_PREAMBLE + "Planning frame: " + frame + "\n"
              + "Tools available this turn: " + (", ".join(tools) or "none") + "\n\n" + context)
    try:
        result = call_model(system, user_input)
        log_execution("conductor", user_input[:100], result[:500], True)
        return result
    except Exception as e:
        log_execution("conductor", user_input[:100], str(e), False)
        raise


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or sys.stdin.read()
    print(run(prompt))
