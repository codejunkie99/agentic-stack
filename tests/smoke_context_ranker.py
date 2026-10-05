"""Explicit live check: PYTHONPATH=. python3 tests/smoke_context_ranker.py

Calls the signed-in CLI once using synthetic evidence only. No project corpus or
credential changes. The second preparation must reuse the in-memory cache.
"""
import argparse
import json

from harness_manager.workspaces.context_packs import ContextPacks


class SyntheticGraph:
    rows = [
        dict(id='mercury', title='Mercury launch date',
             body='Mercury launches on September 20. Human approval is required before publishing.',
             status='accepted', origins=[dict(path='synthetic://mercury', line=1)]),
        dict(id='venus', title='Venus color', body='Venus uses a blue theme.',
             status='reference', origins=[dict(path='synthetic://venus', line=1)]),
        dict(id='jupiter', title='Jupiter tests', body='Jupiter uses pytest for testing.',
             status='reference', origins=[dict(path='synthetic://jupiter', line=1)]),
    ]

    def candidates(self, wid, prompt, limit=80):
        return self.rows[:limit]

    def note(self, wid, identifier):
        return next(r for r in self.rows if r['id'] == identifier)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=['codex', 'claude-code'], default='codex')
    parser.add_argument('--model', default='')
    arguments = parser.parse_args()
    packs = ContextPacks()
    for attempt in [1, 2]:
        pack = packs.prepare(SyntheticGraph(), 'synthetic', 'Which date is the Mercury launch?',
            dict(mode='agent', agent=arguments.agent, model=arguments.model, timeoutSeconds=20))
        assert pack['status'] == 'ready', pack['warning']
        assert [r['id'] for r in pack['refs']] == ['mercury']
        assert pack['refs'][0]['excerpt'] == SyntheticGraph.rows[0]['body']
        assert pack['estimatedTokens'] <= pack['budgetTokens']
        assert pack['cacheHit'] == (attempt == 2)
        print(json.dumps({key: pack[key] for key in ['status', 'retrievalAgent', 'retrievalModel',
            'budgetTokens', 'estimatedTokens', 'elapsedMs', 'cacheHit', 'id']}, sort_keys=True))
