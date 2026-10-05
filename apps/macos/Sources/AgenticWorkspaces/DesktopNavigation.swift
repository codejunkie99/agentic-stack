import AppKit
import SwiftUI

extension DesktopSection {
    var workspace: DesktopSection {
        switch self {
        case .chat, .overview, .insights, .runs, .terminal, .loops: .graph
        case .memoryBrowse, .personal, .references, .handover: .memory
        case .agents: .integrations
        case .hosting, .protocols, .maintenance: .settings
        default: self
        }
    }
    var workspaceTitle: String {
        switch workspace {
        case .graph: "Work"
        case .memory: "Memory"
        case .integrations: "Connections"
        default: workspace.rawValue
        }
    }
    var pageTitle: String {
        switch self {
        case .graph: "Graph"
        case .chat: "Conversation"
        case .overview: "Recent work"
        case .insights: "Overview"
        case .runs: "Tasks"
        case .memoryBrowse: "Browse"
        case .personal: "Personal"
        case .memory: "Project memory"
        case .handover: "Exports"
        case .integrations: "Connections"
        case .agents: "Project adapters"
        case .settings: "General"
        case .protocols: "Rules"
        default: rawValue
        }
    }
    var siblings: [DesktopSection] {
        switch workspace {
        case .graph: [.graph, .chat, .overview, .insights, .runs, .terminal, .loops]
        case .memory: [.memory, .memoryBrowse, .personal, .references, .handover]
        case .integrations: [.integrations, .agents]
        case .settings: [.settings, .protocols, .maintenance, .hosting]
        default: []
        }
    }
    var searchTitle: String { workspaceTitle + " · " + pageTitle }
    var searchDetail: String {
        switch self {
        case .graph: "Explore the 3D knowledge graph and start or continue work"
        case .overview: "Conversations, tasks, checkpoints and results in one work history"
        case .insights: "Project dashboard, activity, memory counts and agent readiness"
        case .runs: "Inspect run activity, results and pending reviews"
        case .memoryBrowse: "Search imported memories and inspect their original sources"
        case .personal: "Review the stable preferences and current context agents carry into work"
        case .memory: "Review evidence, Jev suggestions, corrections and decision history"
        case .references: "Review documents explicitly included in future tasks"
        case .handover: "Export reviewed references as a handover or portable bundle"
        case .agents: "Install project adapters for your coding tools"
        case .integrations: "Detect tools, connect accounts and import existing knowledge"
        case .hosting: "Connect a server or export a hosting package"
        case .protocols: "Edit project permissions, delegation rules and tool schemas"
        case .maintenance: "Project diagnostics, health checks and upgrades"
        default: "Open " + pageTitle.lowercased()
        }
    }
}

/// Wide editors must not enlarge the document window when a sheet is opened.
@MainActor enum DesktopSizing {
    private static var documentWindow: NSWindow? {
        var window = NSApp.mainWindow ?? NSApp.keyWindow
        while let parent = window?.sheetParent { window = parent }
        return window ?? NSApp.windows.first { $0.isVisible && $0.sheetParent == nil && $0.styleMask.contains(.titled) }
    }
    static func sheetWidth(_ preferred: CGFloat) -> CGFloat {
        min(preferred, max(520, (documentWindow?.contentLayoutRect.width ?? 1180) - 40))
    }
    static func sheetHeight(_ preferred: CGFloat) -> CGFloat {
        min(preferred, max(440, (documentWindow?.contentLayoutRect.height ?? 780) - 30))
    }
}

extension StackAdapter {
    var displayName: String {
        ["codex": "Codex", "claude-code": "Claude Code", "copilot-cli": "GitHub Copilot", "autohand-code": "Autohand Code", "gemini": "Gemini CLI", "opencode": "OpenCode", "openclaw": "OpenClaw", "standalone-python": "Python", "pi": "Pi"][id] ?? name.capitalized
    }
}
