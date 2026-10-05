"""Typed memory review operations using the stack's existing lesson tools."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

from ..transfer_bundle import scan_text_for_secrets
from ..loops.storage import _atomic_text


class MemoryControl:
    def __init__(self, stack):
        self.stack = stack

    def _execute(self, root, name, args):
        tool = (root/'.agent/tools'/name).resolve()
        if not tool.is_relative_to(root.resolve()) or not tool.is_file():
            raise ValueError('Initialize the project stack before using memory review.')
        result = subprocess.run([sys.executable, str(tool), *args], cwd=root,
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise ValueError((result.stderr or result.stdout)[-4000:] or 'The memory operation failed.')
        return result.stdout[-100000:]

    @staticmethod
    def _learning_claim(output):
        """Select one explicit reusable finding; routine completions create no memory."""
        if not isinstance(output, str):
            return None
        cues = re.compile(r'\b(root cause|because|decision|decided|fixed|solution|verified|found|avoid|must|should|requires?)\b', re.I)
        candidates = []
        for index, raw in enumerate(output.splitlines()[:500]):
            line = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+|[>#`]+\s*)', '', raw).strip()
            if not 30 <= len(line) <= 900 or line.startswith(('http://', 'https://')):
                continue
            matches = cues.findall(line)
            if not matches or scan_text_for_secrets(line):
                continue
            score = len(matches) * 5 + (3 if 55 <= len(line) <= 420 else 0) - index / 1000
            candidates.append((score, line))
        return max(candidates, default=(0, None), key=lambda item: item[0])[1]

    def learn_from_run(self, run):
        """Automatically stage a provenance-bearing lesson for owner review."""
        if not isinstance(run, dict) or run.get('status') != 'needs_review':
            return None
        wid, identifier = run.get('workspaceId'), run.get('id')
        if not isinstance(wid, str) or not isinstance(identifier, str):
            return None
        root = self.stack.root(wid)
        if not (root/'.agent/tools/learn.py').is_file():
            return None
        claim = self._learning_claim(run.get('output', ''))
        if not claim:
            return None
        state = self.snapshot(wid)
        existing = next((record for record in state['candidates'] + state['lessons']
                         if record['claim'].strip().casefold() == claim.casefold()), None)
        if existing:
            return {'id': existing['id'], 'claim': existing['claim'], 'status': existing['status']}
        task = re.sub(r'\s+', ' ', str(run.get('task', ''))).strip()[:300]
        agent = str(run.get('agentName') or run.get('agent') or 'Agent')[:80]
        rationale = f'Automatically proposed from {agent} run {identifier}. Task: {task}'
        if scan_text_for_secrets(rationale):
            return None
        self._execute(root, 'learn.py', [claim, '--rationale', rationale, '--stage-only'])
        staged = next((record for record in self.snapshot(wid)['candidates']
                       if record['status'] == 'staged' and record['claim'].strip().casefold() == claim.casefold()), None)
        if staged:
            self._annotate(root, staged['id'], 'staged', rationale)
            staged = next((record for record in self.snapshot(wid)['candidates']
                           if record['id'] == staged['id']), staged)
        return ({'id': staged['id'], 'claim': staged['claim'], 'status': staged['status']}
                if staged else None)

    def snapshot(self, wid):
        root = self.stack.root(wid)
        candidates = []
        base = root/'.agent/memory/candidates'
        for status, folder in [('staged', base), ('rejected', base/'rejected'), ('graduated', base/'graduated')]:
            for path in sorted(folder.glob('*.json'))[:300]:
                if path.stat().st_size > 200_000 or not path.resolve().is_relative_to(root):
                    continue
                try:
                    raw = path.read_text()
                    value = json.loads(raw)
                    candidates.append({'id': value['id'], 'claim': value.get('claim', ''), 'status': status,
                                       'conditions': value.get('conditions', []),
                                       'digest': hashlib.sha256(raw.encode()).hexdigest(),
                                       'detail': json.dumps(value, indent=2)})
                except (ValueError, KeyError):
                    continue
        lessons = {}
        path = root/'.agent/memory/semantic/lessons.jsonl'
        if path.is_file():
            for line in path.read_text().splitlines():
                try:
                    item = json.loads(line)
                    lessons[item['id']] = item
                except (ValueError, KeyError):
                    continue
        return {'candidates': candidates, 'lessons': [{'id': item['id'], 'claim': item.get('claim', ''),
                'status': item.get('status', 'accepted'), 'detail': json.dumps(item, indent=2),
                'digest': hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()} for item in lessons.values()]}

    def action(self, p):
        root = self.stack.root(p['workspaceId'])
        operation = p.get('operation')
        rationale = p.get('rationale', '')
        if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 4000:
            raise ValueError('Explain the reason for this memory decision (1–4,000 characters).')
        if scan_text_for_secrets(rationale):
            raise ValueError('Remove credentials from the memory decision.')
        if operation == 'teach':
            claim = p.get('claim')
            if not isinstance(claim, str) or not 20 <= len(claim.strip()) <= 4000:
                raise ValueError('Write a lesson of 20–4,000 characters.')
            if scan_text_for_secrets(claim):
                raise ValueError('Remove credentials from the lesson.')
            records = self.snapshot(p['workspaceId'])
            if any(r['claim'].strip().casefold() == claim.strip().casefold() for r in records['candidates'] + records['lessons']):
                raise ValueError('This lesson already exists. Review its existing record to preserve its history.')
            output = self._execute(root, 'learn.py', [claim, '--rationale', rationale, '--stage-only'])
            current = self.snapshot(p['workspaceId'])
            staged = next((r for r in current['candidates'] if r['status'] == 'staged' and r['claim'] == claim.strip()), None)
            if staged:
                self._annotate(root, staged['id'], 'staged', rationale)
            return {'text': output}
        identifier = p.get('id')
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', identifier):
            raise ValueError('Invalid memory record.')
        state = self.snapshot(p['workspaceId'])
        records = state['lessons'] if operation == 'retract' else state['candidates']
        record = next((r for r in records if r['id'] == identifier), None)
        if not record or record['digest'] != p.get('digest'):
            raise ValueError('This memory record changed. Refresh and review it again.')
        commands = {
            'graduate': ('graduate.py', [identifier, '--rationale', rationale, '--reviewer', 'desktop-owner'], 'staged'),
            'reject': ('reject.py', [identifier, '--reason', rationale, '--reviewer', 'desktop-owner'], 'staged'),
            'reopen': ('reopen.py', [identifier, '--reviewer', 'desktop-owner'], 'rejected'),
            'retract': ('retract_lesson.py', [identifier, '--rationale', rationale, '--reviewer', 'desktop-owner'], 'accepted'),
        }
        if operation not in commands:
            raise ValueError('Unsupported memory decision.')
        tool, args, expected = commands[operation]
        if record['status'] != expected:
            raise ValueError('This action is not available for the record’s current state.')
        output = self._execute(root, tool, args)
        if operation == 'reopen':
            self._annotate(root, identifier, 'reopened', rationale)
        return {'text': output}

    def _annotate(self, root, identifier, action, reason):
        # Older portable tools don't take a reason for staging/reopening.
        # Preserve the note on their existing decision rather than replacing history.
        path = root/'.agent/memory/candidates'/f'{identifier}.json'
        if not path.resolve().is_relative_to(root):
            raise ValueError('The candidate path leaves this project.')
        value = json.loads(path.read_text())
        decisions = value.get('decisions', [])
        if value.get('status') != 'staged' or not decisions or decisions[-1].get('action') != action:
            raise ValueError('The record changed while saving the decision reason. Refresh its history.')
        decisions[-1]['notes'] = reason
        decisions[-1]['reviewer'] = 'desktop-owner'
        _atomic_text(path, json.dumps(value, indent=2) + '\n')
