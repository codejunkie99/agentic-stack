"""Opt-in synthetic fixtures consumed by the production memory/context pipeline."""

FIXTURE_VERSION = 'memory-demo-v1'
CASES = [
    dict(id='deployment', title='Deployment decision', query='Which region and rollout strategy does Lantern use?',
         body='Lantern deployment uses the eu-west region. Rollouts use a canary at 5 percent before full release.'),
    dict(id='preference', title='Durable preference', query='What does the Lantern team prefer for code review?',
         body='The Lantern team prefers small pull requests with a reproducible validation command and source citations.'),
    dict(id='incident', title='Incident continuity', query='How was the Lantern duplicate payment incident resolved?',
         body='The Lantern duplicate payment incident was resolved by enforcing idempotency keys before retrying requests. The next action is to add a concurrent retry regression check.'),
]


def prepare(service, *, reset=False):
    """Only touch the dedicated marked fixture workspace; never scan personal files."""
    with service.lock:
        workspace = next((w for w in service.store.all('workspace')
                          if w.get('demoFixture') == FIXTURE_VERSION), None)
        if workspace is None:
            workspace = service.create_workspace(dict(name='Memory demo · synthetic',
                goal='Evaluate retrieval using public synthetic Lantern evidence.'))
            workspace = service.store.update('workspace', workspace['id'], demoFixture=FIXTURE_VERSION)
        wid = workspace['id']
        if reset:
            with service.store.lock, service.store.connect() as db:
                for table in ('memory_links', 'memory_proposals', 'memory_events', 'memory_claims', 'memory_evidence'):
                    db.execute(f'DELETE FROM {table} WHERE workspace_id=?', (wid,))
            # Fresh claim IDs change the production cache fingerprint. No other
            # project's cache or persisted records are touched.
        for case in CASES:
            evidence = service.memory_ledger.observe(wid, source_key=f"fixture://{FIXTURE_VERSION}/{case['id']}.md",
                body=case['body'], metadata=dict(synthetic=True, fixtureVersion=FIXTURE_VERSION))
            claim = service.memory_ledger.propose(wid, body=case['body'], kind='fact', evidence_ids=[evidence['id']])
            if claim['status'] != 'accepted':
                service.memory_ledger.review(wid, claim['id'], expected_revision=claim['revision'],
                    status='accepted', rationale='Explicitly prepared synthetic demo fixture.')
        return dict(workspaceId=wid, fixtureVersion=FIXTURE_VERSION,
            cases=[{key: case[key] for key in ('id', 'title', 'query')} for case in CASES],
            sourceCount=len(CASES), reset=reset)
