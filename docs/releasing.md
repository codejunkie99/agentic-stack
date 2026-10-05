# Building the unified desktop preview

The primary repository is `codejunkie99/agentic-stack`; its primary branch is
`master`. The desktop implementation is built from this same tree. Historical
preview release notes came from the separate desktop repository and are retained
as history, not evidence that the current build has passed those checks.

```sh
python3 -m pytest -q
bash scripts/build-macos-app.sh --output /tmp/agentic-stack-release \
  --python-root /path/to/standalone-python
codesign --verify --deep --strict '/tmp/agentic-stack-release/Agentic Stack.app'
hdiutil verify '/tmp/agentic-stack-release/Agentic-Stack-macOS-arm64.dmg'
shasum -a 256 /tmp/agentic-stack-release/*.zip /tmp/agentic-stack-release/*.dmg
```

The Python runtime must be relocatable and include its license. Without it the
bundle needs Python installed on the destination Mac. The build script sanitizes
its payload, regenerates memory templates and excludes credentials, runtime
databases and personal memory. Verify archive entries and run the exact produced
bundle against an isolated data directory before delivery.

This preview uses ad-hoc signing. Developer ID signing and notarization are not
claimed. Automatic updates are disabled: the historical `appcast.xml` is not
configured as this build's update source. Publishing a new signed feed requires
verified matching release assets, version numbers and update signatures.

To install an explicitly selected local bundle, preserving any previous version:

```sh
bash scripts/install-macos.sh '/tmp/agentic-stack-release/Agentic Stack.app'
```

The helper does not download a historical release or activate a different feed.
A source merge does not imply that GitHub Release assets have been uploaded.
See [desktop walkthrough](desktop-memory-demo.md) and
[benchmark protocol](memory-benchmarks.md) for verification limits.
