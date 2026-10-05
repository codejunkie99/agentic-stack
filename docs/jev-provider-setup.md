# Jev provider setup

Open Project memory → Provider settings on the selected host. Enter a TypeSafe API key, read the disclosure, explicitly allow hosted processing, and choose Enable Jev. This does not make a test request or prove authentication; actual decisions report provider errors separately. The destination is fixed at https://api.typesafe.ai/v1/systemone with model jev-latest.

The credential and consent are stored in `jev-provider.json` under that host's Agentic Workspaces data root with mode 0600, owned by the host process user. This is an owner-readable credential file, not encrypted Keychain storage. Status responses omit credentials. MCP reads the same file without modifying it. Each decision reloads the setting, so Disconnect prevents subsequent decisions across both clients; an already in-flight request cannot be recalled. Disconnect removes only this provider credential file and retains memory/evidence/history.

Provider setup permits selected task queries, memory claims, source excerpts and metadata to be sent to TypeSafe for projects on that host. Before enablement, Jev planning reports unavailability and preserves active context; it does not silently substitute local selection. Local retrieval is an explicit separate mode. A model recommendation never accepts, archives or replaces a claim by itself.

Runtime code fails closed for missing, malformed, symlinked or group/world-accessible provider files. Tests use temporary paths and synthetic credentials only. This implementation's scripted-provider checks do not establish live authentication or model quality; no hosted smoke test is claimed.

New desktop conversation drafts default to local retrieval. Enabling a provider makes Jev available as an explicit context choice; it does not switch every new draft to hosted selection. Existing per-draft choices remain intact. The current development evaluation includes substantial Jev abstention, so provider availability alone is not treated as evidence of a quality improvement.
