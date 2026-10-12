---
name: evolver
description: "Diagnose recurring failures, scaffold harness candidates, screen them with paired gates, and install only winners."
version: 2026-10-11
triggers: ["evolve", "improve the harness", "why does this keep failing", "self-improve", "diagnose failures", "gene bank", "screen candidate"]
tools: [bash, evolve]
preconditions: ["memory/episodic/AGENT_LEARNINGS.jsonl exists"]
constraints: ["never install an unscreened candidate", "one cell (where, pathology) per candidate", "same task sample for every candidate in a round", "keep the activation marker honest"]
category: meta
quality: {"utility": 7, "robustness": 7, "safety": 9}
---

# Evolver — change the harness only when a paired screen says it is better

Recursive self-improvement without self-deception: a candidate edits the
policy around the model (prompt, knowledge, runtime seat, config), carries
a diagnosis, and is installed only after beating its parent on the same
tasks with a 1.96 paired-t margin. Tool: `tools/evolve.py`.

## Loop
1. `evolve.py diagnose` — failures from episodic memory grouped into
   (skill, pathology) with symptom, trace events, edit location, expected
   change. Pick the top one.
2. `evolve.py scaffold <dx_id> --where prompt --marker <TOKEN>` — a
   candidate directory with the file(s) to edit. Edit
   `evolve/candidates/<cid>/files/...`. Put the marker where the new
   behaviour fires (a sentence in the prompt, a log line in a seat) so the
   activation gate can prove the change ran.
3. `evolve.py screen <cid> --n 4` — validity gate, activation gate, paired
   gain. Read `rounds/<id>.json`. No pass, no install; write a better
   candidate or a better eval card.
4. `evolve.py round <cid> ... --keep 2` — survivors get full-training
   utility and enter the gene bank cell if they beat the incumbent (ties
   keep the incumbent). Stagnation and max-rounds stop the loop.
5. `evolve.py install <cid>` — applies files to the live `.agent/` with a
   backup under `evolve/backups/`. `--force` exists for humans and is logged.

## Evals are the bottleneck
Add task cards to `evolve/evals/` whenever a diagnosis has no task that
reproduces it: `{id, domain, prompt, check}` with `contains`, `regex`, or a
`command` check. Two cards minimum; more cards, less noise.

## Seats
`harness/seats.py` splits the loop into memory / planning / capability /
action. A `runtime` candidate ships `harness/seats.json` pointing a seat at
a new module; the conductor needs no change.

## Example
Pathology "rejected-tests-failing-before-push" in git-proxy → candidate
edits `skills/git-proxy/SKILL.md` to run the test command before `git push`
and prints `[evolved:pretest]`. Screen on 4 push-flavoured cards: gain 0.75,
t=3.0 → pass → round → install.

## Failure that taught this skill
A candidate "passed" with zero variance because the eval cards were all
trivially solved by both harnesses after the first run (cached state in
the overlay). Lesson: overlays are copied without `runtime/`, and eval
cards must not depend on files a prior task wrote.

## Self-rewrite hook
Every 5 rounds: if stagnation keeps hitting, the diagnoses are too coarse
or the evals too weak — propose edits to this file's loop or thresholds in
DECISIONS.md before touching λ.
