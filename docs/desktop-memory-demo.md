# Desktop memory and retrieval demo

The demo runs inside the main Agentic Stack desktop application, using the same
`context.prepare` service and `ContextPacks` implementation used for conversations.
It shows retrieval evidence, not a generated answer or an official benchmark score.

## Build and run

```sh
python3 -m pytest -q
swift build --package-path apps/macos -j 4
bash scripts/build-macos-app.sh --output /tmp/agentic-stack-preview \
  --python-root /path/to/standalone-python
open '/tmp/agentic-stack-preview/Agentic Stack.app'
```

The runtime argument is optional for development; a destination without Python
needs the bundled runtime. The preview is ad-hoc signed, not notarized. Automatic
updates are disabled until a matching signed release feed is published for this
repository. The older separate desktop repository's updater is not used.

The native app supports local projects, source imports and review, project memory,
Jev provider settings, graph browsing, conversations, custom agents, model routing,
work history, terminal workspaces, loops, and a connected server. Some features
require separately installed/authenticated coding tools or a configured server.
See [features](features.md), [native workspaces](native-workspaces.md),
[context](jev-first-context.md), and [provider setup](jev-provider-setup.md).

## Repeatable walkthrough

1. Open Project memory and choose **Memory workspace**.
2. For distributable examples, choose **Sample project** and prepare the explicitly labeled fictional Lantern records. It creates a dedicated project with
   three authored facts, without scanning personal folders or invoking a provider.
3. Choose Deployment decision, retrieve, and inspect the original excerpt,
   source URI, SHA-256, elapsed milliseconds, token estimate, and reference count.
4. Repeat the same query. Observe the cache indicator and newly measured timing.
5. Try the review-preference and incident-continuity questions. Edit the query to
   explore empty results; a missing result remains visible rather than fabricated.
6. Reset the fixture and retrieve again. New claim identities invalidate the
   previous context cache. Reset only affects the marked synthetic project.
7. Interrupt a request. The UI explicitly says that a request already running on
   the host may finish; its late response is ignored. Repeat to recover.
8. Select a real project and use **My project** for reviewed/imported sources.
   Import only deliberately selected nonsecret files. This demo uses local mode,
   so private evidence is not sent to a provider.

The demonstration fixture is distributable. Local app databases, provider
credentials, private project documents, and machine-specific evaluation state
are excluded from packages and source control. Packaging regenerates clean memory
templates. Hosted Jev use is separately enabled with explicit consent and remains
subject to source redaction, bounded choices, deadlines, and original-source checks.

## Evaluation boundaries

Fresh retrieval means an empty in-process context cache, not a flushed operating
system disk cache. Warm retrieval repeats the same request with the same service
instance. UI timing measures retrieval; it excludes answer generation. Integer UI
milliseconds can round very short warm requests to zero; benchmark reports use
high-resolution external wall time.

The small synthetic fixture is a functional demonstration, not a held-out quality
claim. Benchmark inputs, split rules, failures, and results are documented in
[memory benchmarks](memory-benchmarks.md).

## This delivery's real project walkthrough

The local delivery includes `Open Memory Workspace.command`, which launches the
main packaged application against a dedicated data directory with three
explicitly selected Agentic Stack documents: `docs/jev-provider-setup.md`,
`docs/context-layer.md`, and `docs/conversation-workspace.md`. Their digests are
recorded in the local verification manifest. These are actual project documents;
no personal history or credential file was imported. The portable app remains
usable independently of that local walkthrough directory.

Open **My project**, enter “Where is the Jev provider credential stored?”, retrieve,
then inspect `docs/jev-provider-setup.md` and its digest. Repeat to observe the
cache. Open **Benchmark results** to load a report from `docs/benchmarks/results`.
Oracle and full-history reports have different scope and must not be presented
as equivalent. See [design references](desktop-design.md).
