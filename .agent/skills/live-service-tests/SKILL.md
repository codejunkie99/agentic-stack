---
name: live-service-tests
description: >
  Write tests that run against a real external service, and keep them safe to
  run. Covers env-var gating, the read tier and the write tier, self-cleaning
  writes, and run-unique identifiers. Use when a connector, adapter, gateway,
  or API client has only fake-backed tests, or when the user says "test against
  the real API", "run it live", "does this work against production", or "we
  need real data".
---

# Live service tests

## Rule

A fake proves the rules. A fake does not prove the wire.

A test against a fake object proves that your logic is correct. It cannot
prove the authentication handshake, the payload shape, the error format, or
the runtime defaults of your HTTP client. Those are assumptions until a real
call runs.

Every adapter needs one live test tier. Every live test tier must be safe to
run and safe to skip.

## The port boundary changes behaviour

When you port an adapter from one language or runtime to another, the source
runtime's defaults are part of the contract. The new runtime has different
defaults, and the difference is silent.

A real example. A Python client used `http.client`, which does not follow
redirects. The .NET port used `HttpClient`, which follows redirects by
default. A rejected credential produced a redirect to a sign-in page. The
Python client saw the redirect status and reported an authentication error.
The .NET port followed the redirect, received HTTP 200 and an HTML page, and
threw a JSON parse exception through a `Result` type that promised no
exceptions.

The retry rules were ported correctly. The redirect default was not ported,
because nobody wrote it down. Only a live call found it.

Check these defaults at every port boundary:

- Redirect following.
- Timeout values and timeout behaviour.
- Retry and connection reuse.
- Content-type handling and character encoding.
- Certificate and proxy handling.
- What counts as a success status.

## Structure

Use two gates and three tiers.

```text
No environment variable set        -> every live test skips. This is the default.
LIVE_CONFIG set                    -> read-only tests run.
LIVE_CONFIG + LIVE_WRITE=1 set     -> writing tests also run.
```

The skip message must name the missing variable. A silently skipped test is a
test that does not exist.

Do not use a passing test as a skip. A test that returns early and reports
success hides the gap.

## The read tier

Run these with only the read gate. They are safe against any environment.

1. A read succeeds and returns typed data. Assert on the content, not only on
   success. An empty list passes a bare success assertion.
2. A rejected credential maps to your authentication error. Use a deliberately
   invalid credential. Assert the error code, and assert the credential does
   not appear in the message.
3. A missing resource maps to your not-found error.
4. Cross-check against the reference implementation, when one exists. Point
   both at the same live data. They must report the same result.

Item 4 is the strongest test you can write for a port. It compares two
implementations against reality, not against a fixture.

## The write tier

Run these only with the write gate, and only against a target you can damage.

Rules:

1. **Make identifiers unique for each run.** Derive them from the clock.
   Repeated runs must not collide, and must not need a manual clean-up first.
2. **Clean up in a `finally` block.** Delete what the run created, whether the
   test passed or failed.
3. **Keep the clean-up in the test code, not in the product.** If the product
   has no delete path by design, do not add one to tidy up after a test. Call
   the API directly from the test helper.
4. **Prefer a recoverable delete.** Use the recycle bin, not a permanent
   destroy.
5. **Assert idempotency.** Run the operation twice. The second run must plan no
   work. This proves the identifiers you write are the identifiers you read
   back, which no fake can prove.
6. **Assert the refusal path.** Make the state stale on purpose, then assert
   that nothing was written before the refusal.

With rules 1 and 2, a shared target becomes acceptable. Without them, only a
throwaway target is safe.

## Before you ask for a target

Check the permission before you ask a person to create a sandbox. Query the
permission API and report the result. Do not attempt a create to find out.

Report the difference between these two causes, because the remedy differs:

- The account lacks the permission.
- The credential's scope excludes the operation.

To separate them, query a permission the account certainly holds. If that
query also returns false, the API is scope-limited and the result is not
conclusive.

## Continuous integration

Live tests must skip in the pipeline. Do not set the gate variables there.
Assert that the suite passes with no variables set, in the same configuration
the pipeline uses.

## Related

- `skills/verify-by-breaking/SKILL.md` — prove each refusal test really refuses.
- `skills/resilience/SKILL.md` — retry and timeout policy.
- `skills/session-audit/SKILL.md` — finds adapters that still have no live tier.
