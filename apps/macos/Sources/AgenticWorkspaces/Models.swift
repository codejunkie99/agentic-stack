import Foundation

func userFacingPath(_ value: String) -> String {
    let home = FileManager.default.homeDirectoryForCurrentUser.path
    if value == home { return "~" }
    if value.hasPrefix(home + "/") { return "~" + value.dropFirst(home.count) }
    return value
}

struct Workspace: Codable, Identifiable, Hashable, Sendable {
    let id: String
    var name: String
    var goal: String
    var provider: String
    var state: String
    var boxId: String?
    var projectPath: String?
    var ttlMinutes: Int
    var inheritCredentials: Bool
    var createdAt: String
    var updatedAt: String
    var location: String { provider == "local" ? "This Mac" : "Box Cloud" }
    var stateLabel: String { state.replacingOccurrences(of: "_", with: " ").capitalized }
}

struct Source: Codable, Identifiable, Sendable {
    let id: String
    let workspaceId: String
    let name: String
    let text: String
    let digest: String
    var approved: Bool
    let createdAt: String
    var reviewedAt: String?
}

struct AgentRun: Codable, Identifiable, Sendable {
    let id: String
    let workspaceId: String
    let task: String
    var status: String
    let provider: String
    let mode: String
    let output: String
    let error: String
    let model: String
    let createdAt: String
    let timeoutSeconds: Int
    let reviewed: Bool
    let agent: String?
    let promptId: String?
    let memoryRefs: [RunMemoryReference]?
    let conversationRefs: [ConversationReference]?
    let liveOutput: String?
    let activity: [TaskActivity]?
    let startedAt: String?
    let streamUpdatedAt: String?
    let conversationId: String?
    let effort: String?
    let reportedModel: String?
    let routing: String?
    let route: ModelRoute?
    let attachments: [RunAttachment]?
    var workId: String? = nil
    var sequence: Int? = nil
    var contextPack: ContextPack? = nil
    var modelSummary: String {
        if let route, route.policy != "fixed" {
            let policy = routingName(route.policy)
            let level = route.effort.isEmpty ? "Default effort" : modelEffortName(route.effort)
            return "Auto \(policy) → \(route.model.isEmpty ? "Runner default" : route.model) · \(level) · \(route.reason)"
        }
        let requested = model.isEmpty ? "Runner default" : model
        let level = (effort?.isEmpty == false ? effort : nil).map(modelEffortName) ?? "Default effort"
        let reported = (reportedModel?.isEmpty == false ? reportedModel : nil).map { " · Reported: " + $0 } ?? ""
        return "Requested: \(requested) · \(level)\(reported)"
    }
    var startedDate: Date? {
        guard let value = startedAt else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: value) { return date }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: value)
    }
    var isActive: Bool { ["queued", "running", "cancelling", "uncertain"].contains(status) }
    var statusLabel: String { status.replacingOccurrences(of: "_", with: " ").capitalized }
}

struct ModelRoute: Codable, Sendable {
    let policy: String
    let model: String
    let effort: String
    let complexity: String
    let reason: String
    let confidence: Double?
    let signals: [String]?
    let fallback: Bool?
    let candidateCount: Int?
}

struct PersonalMemoryDocument: Decodable, Identifiable, Sendable {
    let source: String
    let content: String
    var id: String { source }
}

struct PersonalMemoryMatch: Decodable, Identifiable, Sendable {
    let source: String
    let title: String
    let content: String
    let score: Int
    var id: String { source + ":" + title }
}

struct PersonalMemoryProfile: Decodable, Sendable {
    let `static`: [PersonalMemoryDocument]
    let dynamic: PersonalMemoryDocument
    let relevant: [PersonalMemoryMatch]
}

struct RunAttachment: Codable, Identifiable, Sendable {
    let name: String
    let mimeType: String
    let kind: String
    let size: Int
    let digest: String
    let relativePath: String
    var id: String { digest }
}

struct TaskActivity: Codable, Identifiable, Sendable {
    let id: String; let title: String; let status: String; let at: String
}

struct RunMemoryReference: Codable, Identifiable, Sendable {
    let id: String; let digest: String; let title: String; let origins: [RunMemoryOrigin]
}
struct RunMemoryOrigin: Codable, Sendable { let path: String; let line: Int }

struct ConversationReferenceOrigin: Codable, Hashable, Sendable {
    let path: String
    let line: Int
}

struct ConversationReference: Codable, Identifiable, Hashable, Sendable {
    let id: String
    let kind: String
    let agent: String
    let agentName: String
    let title: String
    let origin: String
    let updatedAt: String
    let messageCount: Int
    let excerpt: String
    let digest: String?
    let origins: [ConversationReferenceOrigin]?
    let model: String?
    let role: String?
    let roleName: String?
    let workspaceName: String?
    let projectPath: String?
    let parentId: String?
    let score: Int?
    let matchReason: String?
}

struct ConversationReferenceResult: Decodable, Sendable {
    let references: [ConversationReference]
    let total: Int
    let models: [String]?
    let roles: [String]?
    let tools: [String]?
}

struct Snapshot: Codable, Sendable {
    var version: String
    var workspaces: [Workspace]
    var sources: [Source]
    var runs: [AgentRun]
    var localAvailable: Bool
    var dataPath: String
    var conversations: [AgentConversation]? = nil
    var agentProfiles: [AgentProfile]? = nil
    var workItems: [WorkItem]? = nil
    static let empty = Snapshot(version: "", workspaces: [], sources: [], runs: [], localAvailable: false, dataPath: "")
}

struct AgentConversation: Codable, Identifiable, Sendable {
    let id: String; let workspaceId: String; let agent: String; let mode: String
    let title: String; let model: String; let createdAt: String; let updatedAt: String
    let profileId: String?; let agentName: String?; let agentRole: String?; let effort: String?; let routing: String?
    var workId: String? = nil
}

struct AgentProfile: Codable, Identifiable, Sendable {
    let id: String; let name: String; let role: String; let instructions: String
    let runner: String; let model: String; let effort: String; let mode: String; let archived: Bool
}
struct AgentModelChoice: Decodable, Identifiable, Sendable {
    let id: String; let runner: String; let name: String; let efforts: [String]
    let tier: String?
    let capabilities: [String]?
    let summary: String?
}
struct AgentModelsResult: Decodable, Sendable {
    let models: [AgentModelChoice]
    let codexSource: String?
    let warning: String?
}
struct ConversationModelSelection: Sendable {
    var model: String
    var effort: String
    var routing: String

    init(model: String, effort: String, routing: String = "fixed") {
        self.model = model
        self.effort = effort
        self.routing = routing
    }
}

func routingName(_ value: String) -> String {
    switch value {
    case "auto:cost": return "Faster"
    case "auto:intelligence": return "Stronger"
    case "auto:balanced": return "Balanced"
    default: return "Fixed"
    }
}

func modelEffortName(_ value: String) -> String {
    value == "xhigh" ? "Extra high" : value.isEmpty ? "Default" : value.capitalized
}

struct BridgeError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

struct RPCEnvelope<T: Decodable>: Decodable {
    let ok: Bool
    let result: T?
    let error: String?
}
struct EmptyResult: Decodable, Sendable {}
struct TextResult: Decodable, Sendable { let text: String }
struct BundleResult: Decodable, Sendable { let payload: String; let digest: String }
struct DesktopResult: Decodable, Sendable { let desktopUrl: String?; let provisioning: Bool? }

enum WorkspaceTab: String, CaseIterable, Identifiable {
    case overview = "Dashboard", knowledge = "Knowledge", runs = "Runs", handover = "Handover", stack = "Stack"
    var id: String { rawValue }
}

struct AgentAccount: Decodable, Identifiable, Sendable {
    let id: String
    let name: String
    let path: String
    let installed: Bool
    let signedIn: Bool
    let version: String
    let status: String
}
struct AgentAccountsResult: Decodable, Sendable { let agents: [AgentAccount] }
struct PathResult: Decodable, Sendable { let path: String }
struct StackAdapter: Decodable, Identifiable, Sendable {
    let id: String
    let name: String
    let description: String
}
struct InstalledSkill: Decodable, Identifiable, Sendable { let id: String; let name: String }
struct CatalogSkill: Decodable, Identifiable, Sendable {
    let id: String
    let name: String
    let origin: String
    let description: String
    let path: String
    var installed: Bool?
}
struct CatalogResult: Decodable, Sendable { let skills: [CatalogSkill] }
struct StackItem: Decodable, Identifiable, Sendable {
    let id: String
    let label: String
    let status: String
    let summary: String
    let detail: String
}
struct StackDomain: Decodable, Identifiable, Sendable {
    let id: String
    let name: String
    let summary: String
    let status: String
    let items: [StackItem]
}
struct StackSnapshot: Decodable, Sendable {
    let path: String
    let initialized: Bool
    let installed: [String]
    let adapters: [StackAdapter]
    let domains: [StackDomain]
    let skills: [InstalledSkill]
    let files: [StackFile]
}
struct StackFile: Decodable, Identifiable, Sendable { let id: String; let name: String; let path: String }

enum DesktopSection: String, CaseIterable, Identifiable {
    case chat = "Conversations"
    case memoryBrowse = "Browse memory"
    case personal = "Personal memory"
    case insights = "Insights"
    case integrations = "Integrations", settings = "Settings"
    case overview = "Dashboard", agents = "Agents", skills = "Skills", memory = "Memory", graph = "Knowledge graph"
    case protocols = "Protocols", loops = "Loops", maintenance = "Maintenance"
    case runs = "Tasks", terminal = "Terminal", hosting = "Hosting", references = "References", handover = "Handover"
    var id: String { rawValue }
    var symbol: String {
        switch self {
        case .chat: "bubble.left.and.bubble.right"
        case .memoryBrowse: "brain"
        case .personal: "person.crop.circle.badge.checkmark"
        case .insights: "chart.bar"
        case .integrations: "puzzlepiece.extension"
        case .settings: "gearshape"
        case .overview: "square.grid.2x2"
        case .agents: "terminal"
        case .skills: "sparkles"
        case .memory: "brain"
        case .graph: "point.3.connected.trianglepath.dotted"
        case .protocols: "checkmark.shield"
        case .loops: "arrow.trianglehead.2.clockwise.rotate.90"
        case .maintenance: "wrench.and.screwdriver"
        case .runs: "play.rectangle"
        case .terminal: "apple.terminal"
        case .hosting: "server.rack"
        case .references: "doc.text"
        case .handover: "arrow.up.doc"
        }
    }
}
struct ProjectFile: Decodable, Sendable { let text: String; let digest: String; let path: String }

struct LoopContract: Decodable, Identifiable, Sendable {
    let id: String; let name: String; let description: String; let digest: String
    let autonomy: String; let executor: String; let checker: String; let limits: String
    let capabilities: [String]; let error: String
    let verification: String; let isolation: String
}
struct LoopRun: Decodable, Identifiable, Sendable {
    let id: String; let name: String; let task: String; let status: String; let phase: String
    let attempts: Int; let detail: String; let error: String; let worktree: String; let canResume: Bool
    var isActive: Bool { ["queued", "running", "cancelling"].contains(status) }
}
struct LoopSnapshot: Decodable, Sendable {
    let contracts: [LoopContract]; let runs: [LoopRun]; let profileDigest: String; let projectAccessError: String?
}
struct MemoryCandidate: Decodable, Identifiable, Sendable {
    let id: String; let claim: String; let status: String; let conditions: [String]; let digest: String; let detail: String
}
struct MemoryLesson: Decodable, Identifiable, Sendable {
    let id: String; let claim: String; let status: String; let detail: String; let digest: String
}
struct MemorySnapshot: Decodable, Sendable { let candidates: [MemoryCandidate]; let lessons: [MemoryLesson] }

struct GraphOrigin: Decodable, Hashable, Sendable {
    let sourceId: String; let provider: String; let path: String; let line: Int; let importedAt: String
}
struct GraphNote: Decodable, Identifiable, Sendable {
    let id: String; let title: String; let body: String; let origins: [GraphOrigin]; let topics: [String]
    let headline: String?; let category: String?; let filterReason: String?
    var status: String? = nil
    var review: MemoryReview? = nil
    var displayTitle: String { headline ?? title }
}
struct GraphCount: Decodable, Identifiable, Sendable { let id: String; let count: Int }
struct GraphSnapshot: Decodable, Sendable {
    let notes: [GraphNote]; let topics: [GraphCount]; let sources: [GraphCount]
    let total: Int; let matched: Int; let hasMore: Bool
    let hiddenActivity: Int?
    static let empty = GraphSnapshot(notes: [], topics: [], sources: [], total: 0, matched: 0, hasMore: false, hiddenActivity: nil)
}
struct GraphImportFile: Decodable, Identifiable, Sendable {
    let id: String; let provider: String; let path: String; let title: String; let digest: String
    let bytes: Int; let redactedLines: Int; let excerpt: String
}
struct GraphImportPreview: Decodable, Sendable {
    let id: String; let files: [GraphImportFile]; let skipped: [String]; let redactedLines: Int; let bytes: Int
}

struct ContextOptions: Sendable, Equatable {
    static func defaultForProvider(available: Bool) -> ContextOptions {
        // Provider availability is capability, not an instruction to send every query.
        // Explicit per-conversation choices remain in AppModel.
        return ContextOptions()
    }
    var mode = "local"
    var tokenBudget = 2500
    var agent = "codex"
    var model = ""
    var pinnedIds: [String] = []
    var excludeIds: [String] = []
    var params: [String: Any] {
        ["mode": mode, "tokenBudget": tokenBudget, "agent": agent, "model": model,
         "timeoutSeconds": mode == "jev-fast" ? 5 : 20, "pinnedIds": pinnedIds, "excludeIds": excludeIds]
    }
}

struct ContextPack: Codable, Identifiable, Sendable {
    let id: String; let mode: String; let status: String
    let budgetTokens: Int; let estimatedTokens: Int; let elapsedMs: Int; let cacheHit: Bool
    let warning: String; let refs: [ContextReference]; let text: String
}
struct ContextReference: Codable, Identifiable, Sendable {
    let id: String; let kind: String; let title: String; let digest: String
    let origins: [RunMemoryOrigin]; let excerpt: String; let reason: String; let status: String
}
struct WorkCheckpoint: Codable, Sendable {
    let summary: String; let nextAction: String; let runIds: [String]; let updatedAt: String?
}
struct WorkItem: Codable, Identifiable, Sendable {
    let id: String; let workspaceId: String; let title: String; let objective: String; let status: String
    let conversationIds: [String]; let latestRunId: String?; let checkpoint: WorkCheckpoint?
    let createdAt: String; let updatedAt: String
}
struct MemoryReview: Decodable, Sendable {
    let reason: String?
    let supersededBy: String?
    let updatedAt: String?
    let history: [MemoryReviewEvent]?
}
struct MemoryReviewEvent: Decodable, Sendable {
    let status: String; let reason: String; let updatedAt: String
}
