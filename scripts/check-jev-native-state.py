#!/usr/bin/env python3
"""Run focused checks against the production Swift Jev state, without app/backend startup."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'apps/macos/Sources/AgenticWorkspaces/JevMemoryView.swift').read_text()
state = source[source.index('struct JevContextDecision:'):source.index('struct JevMemoryPage:')]
fixtures = source[source.index('extension JevMemoryWorkspace {'):]
search_source = (root / 'apps/macos/Sources/AgenticWorkspaces/SpotlightSearchView.swift').read_text()
search_types = search_source[search_source.index('struct SpotlightJevMatch:'):search_source.index('private struct SpotlightResult:')]
models = (root / 'apps/macos/Sources/AgenticWorkspaces/Models.swift').read_text()
origins = models[models.index('struct RunMemoryOrigin:'):models.index('struct RunMemoryOrigin:') + models[models.index('struct RunMemoryOrigin:'):].index('\n')]
context_options = models[models.index('struct ContextOptions:'):models.index('struct ContextPack:')]
provider_source = (root / 'apps/macos/Sources/AgenticWorkspaces/JevProviderSettingsView.swift').read_text()
provider_status = provider_source[provider_source.index('struct JevProviderStatus:'):provider_source.index('struct JevProviderSettingsView:')]
checks = r'''
@main struct StateCheck {
    @MainActor static func main() async throws {
        let state = JevMemoryWorkspace()
        state.loadFixture("results")
        assert(state.planIsCurrent && state.plan?.decisions?.count == 5)
        assert(state.plan?.selectedIds?.contains("claim:memory-1") == true)
        let selected = state.selectedID
        state.task += " revised"
        assert(!state.planIsCurrent && state.selectedID == selected)
        state.requestSignature = state.signature
        state.busy = true
        let generation = state.generation
        state.request = Task { try? await Task.sleep(for: .milliseconds(20)) }
        state.cancel()
        assert(state.generation > generation && !state.busy && state.request == nil)
        state.loadFixture("forget")
        assert(state.targetIDs == ["claim:memory-1"])
        assert(state.plan?.decisions?.first?.memoryAction == "forget")
        let signature = state.signature
        state.targetIDs = []
        assert(state.signature != signature && !state.planIsCurrent)
        for status in ["unavailable", "abstained"] {
            state.loadFixture(status)
            assert(state.plan?.status == status && state.plan?.decisions?.isEmpty == true)
            assert(state.plan?.applyAvailable == false)
        }
        let payload = #"{"status":"unavailable","decisions":[],"coverage":{"candidateCount":0,"evaluatedCount":0,"omittedCount":0,"exhaustive":false},"toolDecisions":[],"providerCalls":0}"#
        let decoded = try JSONDecoder().decode(JevContextPlan.self, from: Data(payload.utf8))
        assert(decoded.status == "unavailable" && decoded.coverage?.evaluatedCount == 0)
        let noConsent = try JSONDecoder().decode(JevProviderStatus.self, from: Data(#"{"configured":true,"enabled":true,"model":"jev"}"#.utf8))
        assert(!noConsent.isAvailable)
        let denied = try JSONDecoder().decode(JevProviderStatus.self, from: Data(#"{"configured":true,"enabled":true,"consent":false,"available":true}"#.utf8))
        assert(!denied.isAvailable)
        assert(JevProviderStatus.fixture("settings-connected")?.isAvailable == true)
        assert(JevProviderStatus.fixture("provider-missing")?.isAvailable == false)
        assert(JevProviderStatus.fixture("provider-disabled")?.isAvailable == false)
        assert(JevProviderStatus.fixture("provider-checking") == nil)
        for mode in ["fast", "standard", "jev-fast", "jev"] {
            assert(!JevProviderModes.allows(mode, available: false))
            assert(JevProviderModes.allows(mode, available: true))
            assert(!JevProviderModes.shows(mode, selected: "local", available: false))
            assert(JevProviderModes.shows(mode, selected: mode, available: false))
        }
        for mode in ["local", "off", "agent"] {
            assert(JevProviderModes.allows(mode, available: false))
            assert(JevProviderModes.shows(mode, selected: "local", available: false))
        }
        assert(ContextOptions.defaultForProvider(available: false).mode == "local")
        assert(ContextOptions.defaultForProvider(available: true).mode == "jev-fast")
        var options = ContextOptions()
        assert(options.mode == "jev-fast" && options.params["timeoutSeconds"] as? Int == 5)
        options.mode = "jev"
        assert(options.params["timeoutSeconds"] as? Int == 20)
        let searchPayload = #"{"matches":[{"id":"claim:fixture","title":"Exact source","body":"Source evidence.","kind":"memory","source":"Synthetic project","score":3,"confidence":0.95,"digest":"fixture","origins":[{"path":"fixture.md","line":1}]}],"status":"completed","warning":"","coverage":{"candidateCount":8,"evaluatedCount":8,"omittedCount":0,"exhaustive":false},"providerCalls":1,"elapsedMs":38,"cacheHit":false}"#
        let search = try JSONDecoder().decode(SpotlightJevResponse.self, from: Data(searchPayload.utf8))
        assert(search.matches.first?.body == "Source evidence." && search.elapsedMs == 38)
        assert(search.coverage?.exhaustive == false && search.matches.first?.origins?.first?.line == 1)
        let unavailableSearch = #"{"matches":[],"status":"unavailable","providerCalls":0,"elapsedMs":0,"cacheHit":false}"#
        let unavailable = try JSONDecoder().decode(SpotlightJevResponse.self, from: Data(unavailableSearch.utf8))
        assert(unavailable.matches.isEmpty && unavailable.providerCalls == 0 && unavailable.status == "unavailable")
        print("Jev native memory and search state checks passed")
    }
}
'''
with tempfile.TemporaryDirectory(prefix='jev-native-state-') as directory:
    swift = Path(directory) / 'check.swift'
    swift.write_text('import Foundation\nimport Observation\n' + state + search_types + provider_status + origins + "\n" + context_options + fixtures + checks)
    binary = Path(directory) / 'check'
    subprocess.run(['swiftc', '-parse-as-library', str(swift), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
