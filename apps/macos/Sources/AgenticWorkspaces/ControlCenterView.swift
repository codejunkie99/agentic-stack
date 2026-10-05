import SwiftUI

struct StackAction: Identifiable {
    let id: String
    let title: String
    let detail: String
    let symbol: String
    var section: DesktopSection?
    var terminal: String?

    static let commands: [StackAction] = [
        .init(id: "create-agent", title: "Create custom agent", detail: "Save instructions and choose a runner, model, effort and file access", symbol: "person.crop.square.badge.plus"),
        .init(id: "setup", title: "Set up this project", detail: "Guided onboarding, preferences, agents and optional features", symbol: "wand.and.stars"),
        .init(id: "dashboard", title: "CLI health dashboard", detail: "Legacy terminal health and harness verification", symbol: "gauge", terminal: "stack-dashboard"),
        .init(id: "manage", title: "Manage adapters", detail: "Add, remove and repair harness integrations", symbol: "puzzlepiece.extension", terminal: "stack-manage"),
        .init(id: "transfer", title: "Transfer a stack", detail: "Preview portable exports and imports across coding tools", symbol: "arrow.left.arrow.right", terminal: "stack-transfer"),
        .init(id: "brain-connect", title: "Connect Brain", detail: "Run Brain’s project onboarding", symbol: "brain", terminal: "stack-brain-onboard"),
        .init(id: "brain-explore", title: "Explore Brain", detail: "Search the external Brain memory in its terminal UI", symbol: "brain.head.profile", terminal: "stack-brain-tui"),
        .init(id: "brain-log", title: "Brain history", detail: "Recent notes from the current host’s Brain store", symbol: "clock", terminal: "stack-brain-log"),
        .init(id: "brain-health", title: "Brain diagnostics", detail: "Check Brain’s store and configuration", symbol: "stethoscope", terminal: "stack-brain-doctor"),
        .init(id: "brain-mcp", title: "Brain MCP connection", detail: "Show the host’s stdio MCP command", symbol: "network", terminal: "stack-brain-mcp"),
        .init(id: "loop-check", title: "Validate loop contracts", detail: "Check limits, permissions and verifier configuration", symbol: "checkmark.shield", terminal: "stack-loop-validate"),
        .init(id: "loop-status", title: "Loop status", detail: "Inspect the repository’s loop state", symbol: "arrow.trianglehead.2.clockwise.rotate.90", terminal: "stack-loop-status"),
        .init(id: "doctor", title: "Project health", detail: "Run the stack’s doctor audit", symbol: "stethoscope", terminal: "stack-doctor"),
        .init(id: "upgrade", title: "Preview an upgrade", detail: "Inspect infrastructure changes before applying them", symbol: "arrow.up.circle", terminal: "stack-upgrade"),
        .init(id: "manifest", title: "Rebuild skill manifest", detail: "Refresh discovery for project skills", symbol: "sparkles", terminal: "stack-manifest"),
        .init(id: "cli-setup", title: "Original setup wizard", detail: "The repository’s complete interactive setup flow", symbol: "terminal", terminal: "stack-onboard")
    ]
    static var all: [StackAction] {
        DesktopSection.allCases.map {
            .init(id: "section-" + $0.id, title: $0.searchTitle, detail: $0.searchDetail, symbol: $0.symbol, section: $0)
        } + commands
    }

    @MainActor func perform(_ model: AppModel) {
        if id == "create-agent" { model.editAgent() }
        else if id == "setup" { model.showingOnboarding = true }
        else if let section { model.section = section }
        else if let terminal {
            model.section = .terminal
            Task { await model.terminalWorkspace.launch(terminal, model: model) }
        }
    }
}

struct CommandPaletteView: View {
    @Bindable var model: AppModel
    var body: some View { SpotlightSearchView(model: model) }
}
