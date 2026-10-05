import AppKit
import Foundation
import Observation
import UniformTypeIdentifiers

private func isRequestCancellation(_ error: Error) -> Bool {
    if error is CancellationError { return true }
    let value = error as NSError
    return value.domain == NSURLErrorDomain && value.code == NSURLErrorCancelled
}

struct ConversationAttachmentRequest: Identifiable {
    let id = UUID()
    let draftKey: String
    let draftText: String
    let host: String
    let workspaceID: String
    let query: String
    let agent: String
    let context: String
    let mentionOffset: Int?
}

struct ConversationFileAttachment: Identifiable, Hashable, Sendable {
    let id = UUID()
    let sourcePath: String
    let name: String
    let mimeType: String
    let kind: String
    let data: Data

    var size: Int { data.count }
    var payload: [String: Any] {
        ["name": name, "mimeType": mimeType, "data": data.base64EncodedString()]
    }
}

@MainActor @Observable
final class AppModel {
    init() {
        if !ProcessInfo.processInfo.arguments.contains("--jev-ui-fixture") && !ProcessInfo.processInfo.arguments.contains("--jev-search-fixture") { ProjectAccess.shared.restore() }
    }

    var snapshot = Snapshot.empty
    var accounts: [AgentAccount] = []
    var selectedID: String? {
        didSet {
            if oldValue != selectedID {
                invalidateHandover()
                selectedConversationID = nil; selectedWorkID = nil; focusedRunID = nil; focusedMemory = nil; focusedContextReference = nil
                graphFullPage = false; section = .graph
            }
            if let selectedID { UserDefaults.standard.set(selectedID, forKey: selectionKey) }
        }
    }
    var tab = WorkspaceTab.overview
    var section = DesktopSection.graph
    var selectedAgent = "codex"
    var selectedProfileID: String?
    var editingProfile: AgentProfile?
    var showingAgentEditor = false
    var availableModels: [AgentModelChoice] = []
    var modelsError: String?
    var modelCatalogSource = ""
    var modelCatalogWarning = ""
    var selectedConversationID: String?
    var conversationDrafts: [String: String] = [:]
    var conversationModelSelections: [String: ConversationModelSelection] = [:]
    var conversationReferenceSelections: [String: [ConversationReference]] = [:]
    var conversationFileSelections: [String: [ConversationFileAttachment]] = [:]
    var conversationAttachmentRequest: ConversationAttachmentRequest? {
        didSet {
            if oldValue?.id != conversationAttachmentRequest?.id {
                if conversationAttachmentRequest != nil { knowledgeFilterRequest = nil }
                searchFocusGeneration += 1
            }
        }
    }
    var dismissedConversationAttachments: [String: String] = [:]
    var selectedWorkID: String?
    var focusedMemory: GraphNote?
    var focusedContextReference: ContextReference?
    var requestedGraphNoteID: String?
    var graphFullPage = false
    var jevMemoryWorkspaces: [String: JevMemoryWorkspace] = [:]
    var jevProviderSetupRequested = false
    var showingJevProviderSettings = false
    var jevProviderStatus: JevProviderStatus?
    var jevProviderStatusKey = ""
    var jevProviderStatusError = ""
    var jevProviderStatusLoading = false
    private var jevProviderStatusGeneration = 0
    var contextInspectorVisible = true
    var preparingContext = false
    var contextOptionsByDraft: [String: ContextOptions] = [:]
    var contextPreview: ContextPack?
    var contextPreviewKey = ""
    var contextPreviewPrompt = ""
    var contextPreviewOptions: ContextOptions?
    var contextPreviewWorkVersion = ""
    var focusedRunID: String?
    var terminalWorkspace = TerminalWorkspace()
    var isRemote = UserDefaults.standard.bool(forKey: "serverEnabled") {
        didSet { if oldValue != isRemote { invalidateHandover() } }
    }
    var serverURL = UserDefaults.standard.string(forKey: "serverURL") ?? "" {
        didSet { if oldValue != serverURL { invalidateHandover() } }
    }
    var showingRemoteProject = false
    var showingOnboarding = false
    var showingCommandPalette = false {
        didSet {
            if oldValue != showingCommandPalette {
                if showingCommandPalette { knowledgeFilterRequest = nil; dismissConversationAttachment() }
                searchFocusGeneration += 1
            }
        }
    }
    var knowledgeFilterRequest: KnowledgeFilterRequest? {
        didSet {
            if oldValue?.id != knowledgeFilterRequest?.id {
                if knowledgeFilterRequest != nil { showingCommandPalette = false; dismissConversationAttachment() }
                searchFocusGeneration += 1
            }
        }
    }
    private(set) var searchFocusGeneration = 0
    var isSearchPresented: Bool { conversationAttachmentRequest != nil || showingCommandPalette || knowledgeFilterRequest != nil }
    var spotlightCategory = "All"
    var spotlightTopic = ""
    var spotlightQuery = ""
    var error: String?
    var connectionError: String?
    var accountError: String?
    var loading = true
    var busy = false
    var showingNewWorkspace = false
    var showingSource = false
    var showingRun = false
    var search = ""
    var handover = ""
    private var handoverGeneration = 0
    private var handoverPreviewGeneration = 0
    var runTemplate = ""
    var dashboardDrafts: [String: String] = [:]
    private var refreshing = false
    private var refreshingAccounts = false
    private var switchingHost = false
    private var hostGeneration = 0 {
        didSet { if oldValue != hostGeneration { invalidateHandover() } }
    }
    private var prewarmedConversationHosts: Set<String> = []
    private let bridge = Bridge()
    private var selectionKey: String { "selectedProject." + (isRemote ? serverURL : "local") }
    var selected: Workspace? { snapshot.workspaces.first { $0.id == selectedID } }
    var terminalHost: String { isRemote ? serverURL : "local" }
    var hostReady: Bool { !switchingHost }
    var jevProviderHostKey: String { "\(hostGeneration):\(terminalHost):\(switchingHost)" }
    var currentJevProviderStatus: JevProviderStatus? { jevProviderStatusKey == jevProviderHostKey && hostReady ? jevProviderStatus : nil }
    var jevProviderAvailable: Bool { currentJevProviderStatus?.isAvailable == true }
    var jevProviderStatusMessage: String {
        if !hostReady { return "Connect a host to configure Jev" }
        if let status = currentJevProviderStatus { return status.description }
        if jevProviderStatusKey == jevProviderHostKey && !jevProviderStatusError.isEmpty { return jevProviderStatusError }
        return "Checking Jev availability…"
    }
    var jevProviderFixture: String? {
        let args = ProcessInfo.processInfo.arguments
        for flag in ["--jev-search-fixture", "--jev-ui-fixture"] {
            if let index = args.firstIndex(of: flag) { return args.indices.contains(index + 1) ? args[index + 1] : "results" }
        }
        return nil
    }
    func acceptJevProviderStatus(_ status: JevProviderStatus, key: String) {
        guard key == jevProviderHostKey, hostReady else { return }
        jevProviderStatusGeneration += 1
        jevProviderStatus = status; jevProviderStatusKey = key; jevProviderStatusError = ""; jevProviderStatusLoading = false
    }
    func refreshJevProviderStatus() async {
        let key = jevProviderHostKey
        guard hostReady else { return }
        if let fixture = jevProviderFixture {
            jevProviderStatus = JevProviderStatus.fixture(fixture); jevProviderStatusKey = key; jevProviderStatusError = ""; jevProviderStatusLoading = fixture.hasSuffix("checking")
            return
        }
        jevProviderStatusGeneration += 1
        let generation = jevProviderStatusGeneration, host = terminalHost
        jevProviderStatusLoading = true
        defer { if generation == jevProviderStatusGeneration { jevProviderStatusLoading = false } }
        do {
            let status = try await terminalCall("memory.provider.status", [:], host: host, as: JevProviderStatus.self)
            guard !Task.isCancelled, key == jevProviderHostKey, generation == jevProviderStatusGeneration else { return }
            jevProviderStatus = status; jevProviderStatusKey = key; jevProviderStatusError = ""
        } catch {
            guard !Task.isCancelled, key == jevProviderHostKey, generation == jevProviderStatusGeneration else { return }
            jevProviderStatus = nil; jevProviderStatusKey = key; jevProviderStatusError = "Jev status unavailable · Local search remains available"
        }
    }
    var handoverPreviewKey: String { "\(hostGeneration):\(terminalHost):\(selectedID ?? ""):\(switchingHost)" }
    var sources: [Source] { snapshot.sources.filter { $0.workspaceId == selectedID } }
    var runs: [AgentRun] { snapshot.runs.filter { $0.workspaceId == selectedID } }
    var conversations: [AgentConversation] {
        (snapshot.conversations ?? []).filter { $0.workspaceId == selectedID }.sorted { $0.updatedAt > $1.updatedAt }
    }
    var conversation: AgentConversation? { conversations.first { $0.id == selectedConversationID } }
    var conversationRuns: [AgentRun] {
        guard let id = conversation?.id else { return [] }
        return runs.filter { $0.conversationId == id }.sorted {
            if let left = $0.sequence, let right = $1.sequence, left != right { return left < right }
            return $0.createdAt == $1.createdAt ? $0.id < $1.id : $0.createdAt < $1.createdAt
        }
    }
    var profiles: [AgentProfile] { (snapshot.agentProfiles ?? []).filter { !$0.archived }.sorted { $0.name.localizedStandardCompare($1.name) == .orderedAscending } }
    var selectedProfile: AgentProfile? { (snapshot.agentProfiles ?? []).first { $0.id == selectedProfileID } }
    var conversationAgentName: String { conversation?.agentName ?? selectedProfile?.name ?? (selectedAgent == "codex" ? "Codex" : "Claude Code") }
    var conversationDraftKey: String { terminalHost + ":" + (selectedID ?? "") + ":" + (conversation?.id ?? "new:" + (selectedProfileID ?? selectedAgent) + (selectedWorkID.map { ":work:" + $0 } ?? "")) }
    var selectedConversationReferences: [ConversationReference] { conversationReferenceSelections[conversationDraftKey] ?? [] }
    var selectedConversationFiles: [ConversationFileAttachment] { conversationFileSelections[conversationDraftKey] ?? [] }

    var workItems: [WorkItem] {
        (snapshot.workItems ?? []).filter { $0.workspaceId == selectedID }.sorted { $0.updatedAt > $1.updatedAt }
    }
    var currentWork: WorkItem? {
        let id = conversation?.workId ?? selectedWorkID
        return workItems.first { $0.id == id }
    }
    var contextOptions: ContextOptions {
        get { contextOptionsByDraft[conversationDraftKey] ?? ContextOptions.defaultForProvider(available: jevProviderAvailable) }
        set { contextOptionsByDraft[conversationDraftKey] = newValue; contextPreview = nil }
    }
    var validContextPreview: ContextPack? {
        contextPreviewWorkVersion == (currentWork?.updatedAt ?? "") && contextPreviewOptions == contextOptions && contextPreviewKey == conversationDraftKey && contextPreviewPrompt == (conversationDrafts[conversationDraftKey] ?? "") ? contextPreview : nil
    }
    var displayedContextPack: ContextPack? {
        if let preview = validContextPreview { return preview }
        if conversation != nil { return conversationRuns.last?.contextPack }
        guard let work = currentWork else { return nil }
        return runs.first { $0.id == work.latestRunId }?.contextPack
    }
    var contextReferenceIDs: Set<String> { Set(displayedContextPack?.refs.filter { $0.kind == "memory" }.map(\.id) ?? []) }

    func prepareContext() async {
        guard !preparingContext, let wid = selectedID else { return }
        let key = conversationDraftKey, prompt = conversationDrafts[key] ?? ""
        let options = contextOptions, workVersion = currentWork?.updatedAt ?? ""
        guard !prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        preparingContext = true
        defer { preparingContext = false }
        do {
            var params: [String: Any] = ["workspaceId": wid, "prompt": prompt, "contextOptions": options.params]
            if let id = currentWork?.id { params["workId"] = id }
            let pack = try await call("context.prepare", params, as: ContextPack.self)
            guard key == conversationDraftKey, options == contextOptions, workVersion == (currentWork?.updatedAt ?? "") else { return }
            contextPreview = pack; contextPreviewKey = key; contextPreviewPrompt = prompt; contextPreviewOptions = options; contextPreviewWorkVersion = workVersion
            focusedMemory = nil; focusedContextReference = nil; contextInspectorVisible = true
        } catch { self.error = error.localizedDescription }
    }

    func pinContext(_ id: String) {
        var options = contextOptions
        options.excludeIds.removeAll { $0 == id }
        if options.pinnedIds.contains(id) { options.pinnedIds.removeAll { $0 == id } }
        else { options.pinnedIds.append(id) }
        contextOptions = options
    }

    func excludeContext(_ id: String) {
        var options = contextOptions
        options.pinnedIds.removeAll { $0 == id }
        if options.excludeIds.contains(id) { options.excludeIds.removeAll { $0 == id } }
        else { options.excludeIds.append(id) }
        contextOptions = options
    }

    func openWork(_ item: WorkItem) {
        selectedWorkID = item.id
        if let conversation = conversations.first(where: { $0.workId == item.id || item.conversationIds.contains($0.id) }) {
            openConversation(conversation)
        } else {
            selectedConversationID = nil; selectedProfileID = nil; focusedMemory = nil
            if let runID = item.latestRunId {
                focusedRunID = runID; section = .runs
                selectedAgent = runs.first { $0.id == runID }?.agent ?? "codex"
            } else { section = .graph }
        }
    }

    func openStandaloneRun(_ id: String) {
        selectedConversationID = nil; selectedProfileID = nil; focusedMemory = nil
        focusedRunID = id; selectedWorkID = runs.first { $0.id == id }?.workId; section = .runs
    }

    func continueWork(_ item: WorkItem, agent: String) async {
        guard !busy else { return }
        busy = true; error = nil
        let host = terminalHost, workspaceID = selectedID
        defer { busy = false }
        do {
            let source = conversations.first { $0.workId == item.id || item.conversationIds.contains($0.id) }
            let sameRunner = source?.agent == agent
            let params: [String: Any] = ["id": item.id, "agent": agent, "mode": source?.mode ?? "read-only",
                "model": sameRunner ? source?.model ?? "" : "", "effort": sameRunner ? source?.effort ?? "" : ""]
            let options = source.map { contextOptionsByDraft[host + ":" + item.workspaceId + ":" + $0.id] ?? ContextOptions.defaultForProvider(available: jevProviderAvailable) } ?? ContextOptions.defaultForProvider(available: jevProviderAvailable)
            let result = try await call("work.continue", params, as: AgentConversation.self)
            await refresh()
            guard host == terminalHost, workspaceID == selectedID else { return }
            openConversation(result)
            contextOptions = options
            conversationDrafts[conversationDraftKey] = item.checkpoint?.nextAction.isEmpty == false
                ? item.checkpoint?.nextAction : "Continue this work toward its objective. Verify the current state before making changes."
        } catch { self.error = error.localizedDescription }
    }

    func inspectMemory(_ id: String, showGraph: Bool = false) async {
        guard let wid = selectedID else { return }
        let host = terminalHost
        do {
            let note = try await call("knowledge.note", ["workspaceId": wid, "noteId": id], as: GraphNote.self)
            guard host == terminalHost, wid == selectedID else { return }
            focusedMemory = note; focusedContextReference = nil; contextInspectorVisible = true
            if showGraph { requestedGraphNoteID = id; section = .graph }
        } catch { self.error = error.localizedDescription }
    }

    func newConversation(agent: String? = nil) {
        if let agent { selectedAgent = agent; selectedProfileID = nil }
        selectedConversationID = nil; selectedWorkID = nil; focusedRunID = nil; focusedMemory = nil; focusedContextReference = nil; graphFullPage = false; section = .graph
    }

    func selectAgent(_ agent: String) {
        if let recent = conversations.first(where: { $0.agent == agent && $0.profileId == nil }) { openConversation(recent) }
        else { newConversation(agent: agent) }
    }

    func openConversation(_ conversation: AgentConversation) {
        selectedAgent = conversation.agent; selectedProfileID = conversation.profileId; selectedConversationID = conversation.id; selectedWorkID = conversation.workId; focusedMemory = nil; focusedContextReference = nil; graphFullPage = false; section = .chat
    }

    func sendMessage(_ text: String, mode: String, modelID: String, effort: String, useMemory: Bool) async {
        guard !busy, let wid = selectedID else { return }
        busy = true; error = nil
        let host = terminalHost, key = conversationDraftKey
        let attached = selectedConversationReferences
        let attachedFiles = selectedConversationFiles
        let selection = conversationModelSelection
        let options = contextOptions
        defer { busy = false }
        let task = text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !attachedFiles.isEmpty
            ? "Please inspect the attached files." : text
        var params: [String: Any] = ["workspaceId": wid, "task": task, "agent": selectedAgent, "mode": mode,
                                     "model": modelID, "effort": effort, "routing": selection.routing,
                                     "attachments": attachedFiles.map(\.payload), "timeoutSeconds": 600, "useKnowledgeGraph": useMemory,
                                     "conversationReferenceIds": attached.map(\.id), "contextOptions": options.params]
        if let id = conversation?.id { params["conversationId"] = id }
        else {
            params["modelSelection"] = ["model": selection.model, "effort": selection.effort, "routing": selection.routing]
            if let id = selectedWorkID { params["workId"] = id }
            if let id = selectedProfileID { params["profileId"] = id }
        }
        do {
            let run = try await call("conversation.send", params, as: AgentRun.self)
            await refresh()
            if let id = run.conversationId {
                let destination = host + ":" + wid + ":" + id
                if destination != key {
                    contextOptionsByDraft[destination] = contextOptionsByDraft[key] ?? options
                    contextOptionsByDraft[key] = nil
                }
            }
            if conversationReferenceSelections[key]?.map(\.id) == attached.map(\.id) {
                conversationReferenceSelections[key] = nil
            }
            if conversationFileSelections[key]?.map(\.id) == attachedFiles.map(\.id) {
                conversationFileSelections[key] = nil
            }
            if conversationDrafts[key] == text { conversationDrafts[key] = nil }
            else if let remaining = conversationDrafts[key], let id = run.conversationId {
                let destination = host + ":" + wid + ":" + id
                if destination != key {
                    conversationDrafts[destination] = remaining
                    conversationDrafts[key] = nil
                }
            }
            if key == conversationDraftKey && wid == selectedID && host == terminalHost {
                selectedConversationID = run.conversationId; selectedWorkID = run.workId; focusedRunID = run.id; section = .chat
                contextPreview = nil
            }
        } catch { self.error = error.localizedDescription }
    }

    func openConversationAttachment(query: String = "", agent: String = "", context: String = "", mentionOffset: Int? = nil) {
        guard let wid = selectedID, !busy, selectedConversationReferences.count < 5 else { return }
        let key = conversationDraftKey
        showingCommandPalette = false
        conversationAttachmentRequest = .init(draftKey: key, draftText: conversationDrafts[key] ?? "",
            host: terminalHost, workspaceID: wid, query: query, agent: agent, context: context, mentionOffset: mentionOffset)
    }

    func dismissConversationAttachment() {
        if let request = conversationAttachmentRequest {
            let text = conversationDrafts[request.draftKey] ?? ""
            dismissedConversationAttachments[request.draftKey] = text.lastIndex(of: "@").map { String(text[...$0]) }
        }
        conversationAttachmentRequest = nil
    }

    func selectConversationAttachment(_ reference: ConversationReference, requestID: UUID) {
        guard let request = conversationAttachmentRequest, request.id == requestID else { return }
        guard request.draftKey == conversationDraftKey, request.workspaceID == selectedID, request.host == terminalHost else {
            dismissConversationAttachment(); return
        }
        guard selectedConversationReferences.count < 5,
              !selectedConversationReferences.contains(where: { $0.id == reference.id }) else { return }
        attachConversationReference(reference)
        if conversationDrafts[request.draftKey] == request.draftText, let offset = request.mentionOffset,
           let at = request.draftText.index(request.draftText.startIndex, offsetBy: offset, limitedBy: request.draftText.endIndex) {
            conversationDrafts[request.draftKey] = String(request.draftText[..<at])
        }
        dismissConversationAttachment()
    }

    func prewarmConversationReferences() async {
        guard let wid = selectedID else { return }
        let host = terminalHost
        guard !prewarmedConversationHosts.contains(host) else { return }
        prewarmedConversationHosts.insert(host)
        do {
            let _: ConversationReferenceResult = try await call("conversation.references", [
                "workspaceId": wid, "query": "", "agent": "", "scope": "all", "limit": 1
            ], as: ConversationReferenceResult.self)
        } catch {
            prewarmedConversationHosts.remove(host)
        }
    }

    func attachConversationReference(_ reference: ConversationReference) {
        let key = conversationDraftKey
        var references = conversationReferenceSelections[key] ?? []
        guard references.count < 5, !references.contains(where: { $0.id == reference.id }) else { return }
        references.append(reference)
        conversationReferenceSelections[key] = references
    }

    func removeConversationReference(_ reference: ConversationReference) {
        let key = conversationDraftKey
        conversationReferenceSelections[key] = (conversationReferenceSelections[key] ?? []).filter { $0.id != reference.id }
    }

    func attachConversationFiles(_ urls: [URL]) {
        let key = conversationDraftKey
        do {
            var attachments = conversationFileSelections[key] ?? []
            guard attachments.count + urls.count <= 8 else {
                throw BridgeError(message: "Attach up to 8 files per message.")
            }
            for url in urls {
                let path = url.standardizedFileURL.path
                if attachments.contains(where: { $0.sourcePath == path }) { continue }
                let accessed = url.startAccessingSecurityScopedResource()
                defer { if accessed { url.stopAccessingSecurityScopedResource() } }
                let values = try url.resourceValues(forKeys: [.isRegularFileKey, .contentTypeKey, .fileSizeKey])
                guard values.isRegularFile == true else { throw BridgeError(message: "Choose files rather than folders.") }
                guard let fileSize = values.fileSize, fileSize > 0, fileSize <= 12_000_000 else {
                    throw BridgeError(message: "Each attachment must be between 1 byte and 12 MB.")
                }
                let type = values.contentType ?? UTType(filenameExtension: url.pathExtension)
                let mime = type?.preferredMIMEType ?? "application/octet-stream"
                let allowedApplicationTypes = ["application/pdf", "application/json", "application/xml", "application/zip",
                                               "application/octet-stream", "application/x-yaml", "application/toml"]
                guard mime.hasPrefix("image/") || mime.hasPrefix("audio/") || mime.hasPrefix("video/") ||
                        mime.hasPrefix("text/") || allowedApplicationTypes.contains(mime) else {
                    throw BridgeError(message: "\(url.lastPathComponent) is not a supported image, PDF, audio, video, text, or code file.")
                }
                let data = try Data(contentsOf: url, options: .mappedIfSafe)
                let kind: String
                if mime.hasPrefix("image/") { kind = "image" }
                else if mime.hasPrefix("audio/") { kind = "audio" }
                else if mime.hasPrefix("video/") { kind = "video" }
                else if mime == "application/pdf" { kind = "pdf" }
                else { kind = "text" }
                attachments.append(.init(sourcePath: path, name: url.lastPathComponent, mimeType: mime, kind: kind, data: data))
            }
            guard attachments.reduce(0, { $0 + $1.size }) <= 24_000_000 else {
                throw BridgeError(message: "Attachments can use up to 24 MB per message.")
            }
            conversationFileSelections[key] = attachments
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    func removeConversationFile(_ attachment: ConversationFileAttachment) {
        let key = conversationDraftKey
        conversationFileSelections[key] = (conversationFileSelections[key] ?? []).filter { $0.id != attachment.id }
    }
    func selectProfile(_ profile: AgentProfile) {
        selectedAgent = profile.runner; selectedProfileID = profile.id
        if let recent = conversations.first(where: { $0.profileId == profile.id }) { openConversation(recent) }
        else { newConversation() }
    }

    func editAgent(_ profile: AgentProfile? = nil) {
        editingProfile = profile; showingAgentEditor = true
    }

    var conversationModelSelection: ConversationModelSelection {
        if let conversation { return .init(model: conversation.model, effort: conversation.effort ?? "", routing: conversation.routing ?? "fixed") }
        return conversationModelSelections[conversationDraftKey]
            ?? .init(model: selectedProfile?.model ?? "", effort: selectedProfile?.effort ?? "")
    }

    func configureConversationModel(_ selection: ConversationModelSelection, key: String) async throws {
        guard key == conversationDraftKey, !busy, let wid = selectedID else {
            throw BridgeError(message: "Return to the conversation before applying this model.")
        }
        if let conversation {
            busy = true
            defer { busy = false }
            let host = terminalHost
            let updated = try await terminalCall("conversation.configure", [
                "workspaceId": wid, "conversationId": conversation.id,
                "modelSelection": ["model": selection.model, "effort": selection.effort, "routing": selection.routing]
            ], host: host, as: AgentConversation.self)
            guard terminalHost == host else { return }
            if let index = snapshot.conversations?.firstIndex(where: { $0.id == updated.id }) {
                snapshot.conversations?[index] = updated
            }
        } else { conversationModelSelections[key] = selection }
    }

    func loadModels() async {
        let host = terminalHost
        do {
            let result = try await call("agentProfiles.models", as: AgentModelsResult.self)
            guard terminalHost == host else { return }
            availableModels = result.models; modelsError = nil
            modelCatalogSource = result.codexSource ?? "Codex model cache"
            modelCatalogWarning = result.warning ?? ""
        } catch {
            if terminalHost == host, !Task.isCancelled, !isRequestCancellation(error) {
                availableModels = []; modelsError = error.localizedDescription
            }
        }
    }

    func loadPersonalMemory(query: String = "") async throws -> PersonalMemoryProfile {
        guard let wid = selectedID else { throw BridgeError(message: "Select a project to inspect its memory.") }
        let host = terminalHost
        return try await terminalCall("memory.profile", ["workspaceId": wid, "query": query, "limit": 12],
                                      host: host, as: PersonalMemoryProfile.self)
    }

    func recommendModel(runner: String, task: String, routing: String, attachmentKinds: [String]) async throws -> ModelRoute {
        let host = terminalHost
        let request = task.trimmingCharacters(in: .whitespacesAndNewlines)
        return try await terminalCall("modelRouter.recommend", [
            "runner": runner, "task": request.isEmpty ? "Continue this work" : request,
            "routing": routing, "attachments": attachmentKinds.map { ["kind": $0] }
        ], host: host, as: ModelRoute.self)
    }

    var approvedCount: Int { sources.filter(\.approved).count }
    var visibleWorkspaces: [Workspace] {
        snapshot.workspaces.filter { search.isEmpty || $0.name.localizedCaseInsensitiveContains(search) || $0.goal.localizedCaseInsensitiveContains(search) }
    }

    func call<T: Decodable & Sendable>(_ method: String, _ params: [String: Any] = [:], as type: T.Type) async throws -> T {
        let body = try JSONSerialization.data(withJSONObject: ["method": method, "params": params])
        return try await bridge.call(method, body: body, as: type)
    }

    func terminalCall<T: Decodable & Sendable>(_ method: String, _ params: [String: Any], host: String, as type: T.Type) async throws -> T {
        guard host == terminalHost, !switchingHost else {
            throw BridgeError(message: "Return to this terminal's host to continue.")
        }
        let body = try JSONSerialization.data(withJSONObject: ["method": method, "params": params])
        return try await bridge.call(method, body: body, as: type, expectedHost: host)
    }

    func refresh() async {
        guard !refreshing, !switchingHost else { return }
        let generation = hostGeneration
        refreshing = true
        defer { if generation == hostGeneration { refreshing = false; loading = false } }
        do {
            let result: Snapshot = try await call("snapshot", as: Snapshot.self)
            guard generation == hostGeneration else { return }
            snapshot = result
            connectionError = nil
            if selectedID == nil {
                let saved = UserDefaults.standard.string(forKey: selectionKey)
                selectedID = snapshot.workspaces.first(where: { $0.id == saved })?.id
                    ?? snapshot.workspaces.first(where: { $0.provider == "local" && $0.projectPath != nil })?.id
                    ?? snapshot.workspaces.first(where: { $0.provider == "local" })?.id
                    ?? snapshot.workspaces.first?.id
            }
        } catch {
            if generation == hostGeneration, !Task.isCancelled, !isRequestCancellation(error) {
                self.connectionError = error.localizedDescription
            }
        }
    }

    func connectServer(url: String, token: String) async -> Bool {
        guard !busy else { return false }
        busy = true; switchingHost = true
        defer { busy = false; switchingHost = false }
        hostGeneration += 1; refreshing = false
        do {
            let state = try await bridge.probe(url, credential: token)
            var credentialNotice: String?
            do { try await Keychain.save(token, account: "stack-server") }
            catch { credentialNotice = "Connected for this session. Keychain could not remember the token; re-enter it after restarting. " + error.localizedDescription }
            try await bridge.useServerCredential(url, credential: token)
            let canonical = try Bridge.serverEndpoint(url).deletingLastPathComponent().absoluteString
            UserDefaults.standard.set(canonical, forKey: "serverURL")
            UserDefaults.standard.set(true, forKey: "serverEnabled")
            isRemote = true; serverURL = canonical; selectedProfileID = nil; selectedConversationID = nil; selectedAgent = "codex"
            snapshot = state; selectedID = state.workspaces.first?.id; accounts = []; error = credentialNotice; connectionError = nil
            await refreshAccounts()
            return true
        } catch { self.error = error.localizedDescription; return false }
    }

    func useThisMac() async {
        guard !busy else { return }
        busy = true; switchingHost = true
        hostGeneration += 1; refreshing = false
        UserDefaults.standard.set(false, forKey: "serverEnabled")
        isRemote = false; selectedProfileID = nil; selectedConversationID = nil; selectedAgent = "codex"; selectedID = nil; snapshot = .empty; accounts = []; error = nil; connectionError = nil
        switchingHost = false
        await refresh(); await refreshAccounts()
        busy = false
    }

    func openProject(path: String) async -> Bool {
        guard !busy else { return false }
        busy = true; error = nil
        defer { busy = false }
        do {
            let project: Workspace = try await call("project.open", ["path": path], as: Workspace.self)
            await refresh(); selectedID = project.id; section = .graph
            return true
        } catch { self.error = error.localizedDescription; return false }
    }

    func openProjectPicker() {
        if isRemote { showingRemoteProject = true; return }
        let panel = NSOpenPanel()
        panel.canChooseFiles = false; panel.canChooseDirectories = true
        panel.message = "Open a repository to manage its Agentic Stack."
        present(panel) { response in
            guard response == .OK, let url = panel.url else { return }
            ProjectAccess.shared.remember(url)
            Task {
                await self.bridge.restart()
                _ = await self.openProject(path: url.path)
            }
        }
    }

    func perform(_ method: String, _ params: [String: Any] = [:]) async -> Bool {
        guard !busy else { return false }
        busy = true; error = nil
        defer { busy = false }
        do {
            var startedRunID: String?
            if method == "run.start" {
                let run: AgentRun = try await call(method, params, as: AgentRun.self)
                startedRunID = run.id
            } else {
                let _: EmptyResult = try await call(method, params, as: EmptyResult.self)
            }
            await refresh()
            if let startedRunID { focusedRunID = startedRunID }
            return true
        } catch { self.error = error.localizedDescription; return false }
    }

    func create(name: String, goal: String, provider: String, ttl: Int, inherit: Bool) async -> Bool {
        guard !busy else { return false }
        busy = true; error = nil
        defer { busy = false }
        do {
            let workspace: Workspace = try await call("workspace.create", ["name": name, "goal": goal,
                "provider": provider, "ttlMinutes": ttl, "inheritCredentials": inherit], as: Workspace.self)
            await refresh()
            selectedID = workspace.id; tab = .overview; section = .graph
            return true
        } catch { self.error = error.localizedDescription; return false }
    }

    private func present(_ panel: NSSavePanel, completion: @escaping (NSApplication.ModalResponse) -> Void) {
        if let window = NSApp.mainWindow ?? NSApp.keyWindow {
            panel.beginSheetModal(for: window, completionHandler: completion)
        } else {
            panel.begin(completionHandler: completion)
        }
    }

    func importFiles() {
        guard let wid = selectedID else { return }
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowedContentTypes = [.plainText, .text, .sourceCode, UTType(filenameExtension: "md") ?? .text, UTType(filenameExtension: "markdown") ?? .text]
        panel.allowsMultipleSelection = true
        panel.message = "Choose text or Markdown documents for this workspace. Each source will wait for your review."
        present(panel) { response in
            guard response == .OK else { return }
            let urls = panel.urls
            Task { @MainActor in
                for url in urls {
                    let granted = url.startAccessingSecurityScopedResource()
                    defer { if granted { url.stopAccessingSecurityScopedResource() } }
                    do {
                        let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
                        guard size <= 800_000 else { throw BridgeError(message: "\(url.lastPathComponent) is too large. Import a shorter text document.") }
                        let content = try String(contentsOf: url, encoding: .utf8)
                        _ = await self.perform("source.add", ["workspaceId": wid, "name": url.lastPathComponent, "text": content])
                        self.tab = .knowledge
                    } catch { self.error = error.localizedDescription }
                }
            }
        }
    }

    private func invalidateHandover() {
        handoverGeneration += 1
        handoverPreviewGeneration += 1
        handover = ""
    }

    private func freshHandover(previewRequest: Int? = nil) async -> (text: String, projectName: String)? {
        guard let wid = selectedID, !switchingHost else { return nil }
        let host = terminalHost, request = handoverGeneration
        let projectName = selected?.name ?? "Workspace"
        do {
            let result = try await terminalCall("handover.export", ["workspaceId": wid], host: host, as: TextResult.self)
            guard !Task.isCancelled, request == handoverGeneration, selectedID == wid, terminalHost == host, !switchingHost,
                  previewRequest == nil || previewRequest == handoverPreviewGeneration else { return nil }
            return (result.text, projectName)
        } catch {
            guard !Task.isCancelled, request == handoverGeneration, selectedID == wid, terminalHost == host, !switchingHost,
                  previewRequest == nil || previewRequest == handoverPreviewGeneration else { return nil }
            self.error = error.localizedDescription
            return nil
        }
    }

    func loadHandover() async {
        handoverPreviewGeneration += 1
        let request = handoverPreviewGeneration
        handover = ""
        guard let export = await freshHandover(previewRequest: request) else { return }
        handover = export.text
    }

    func saveHandover() async {
        guard let export = await freshHandover(), !export.text.isEmpty else { return }
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "\(export.projectName) handover.md"
        panel.allowedContentTypes = [UTType(filenameExtension: "md") ?? .plainText]
        let content = export.text
        present(panel) { response in
            guard response == .OK, let url = panel.url else { return }
            do { try content.write(to: url, atomically: true, encoding: .utf8) }
            catch { self.error = error.localizedDescription }
        }
    }

    func cloud(_ action: String) async {
        guard let wid = selectedID else { return }
        guard !busy else { return }
        busy = true; error = nil
        defer { busy = false }
        do {
            let key = try await Keychain.read("box")
            let result: Workspace = try await call("cloud.action", ["workspaceId": wid, "action": action, "credential": key], as: Workspace.self)
            await refresh()
            if action == "fork" { selectedID = result.id }
        } catch { self.error = error.localizedDescription; await refresh() }
    }

    func openDesktop() async {
        guard let wid = selectedID, !busy else { return }
        busy = true
        defer { busy = false }
        do {
            let result: DesktopResult = try await call("cloud.action", ["workspaceId": wid, "action": "desktop", "credential": try await Keychain.read("box")], as: DesktopResult.self)
            guard let raw = result.desktopUrl, let url = URL(string: raw), url.scheme == "https", url.host != nil, url.user == nil else {
                throw BridgeError(message: result.provisioning == true ? "The desktop is being prepared. Try Open desktop again shortly." : "Box has not returned a usable desktop URL.")
            }
            NSWorkspace.shared.open(url)
        } catch { self.error = error.localizedDescription }
    }

    func refreshRun(_ run: AgentRun) async {
        do { _ = await perform("run.refresh", ["id": run.id, "credential": try await Keychain.read("box")]) }
        catch { self.error = error.localizedDescription }
    }

    func draftHandover() {
        runTemplate = "Create a practical handover from the reviewed sources. Include responsibilities, active work, open decisions, relationships, recurring procedures, and missing knowledge. For each factual claim cite the source ID and line numbers. Label inference and say when evidence is absent. Return a concise Markdown document."
        showingRun = true
    }

    func saveBundle() async {
        guard let wid = selectedID else { return }
        do {
            let result: BundleResult = try await call("bundle.export", ["workspaceId": wid], as: BundleResult.self)
            let panel = NSSavePanel()
            panel.nameFieldStringValue = "\(selected?.name ?? "Workspace").agentic-bundle.txt"
            panel.allowedContentTypes = [.plainText]
            present(panel) { response in
                guard response == .OK, let url = panel.url else { return }
                do { try result.payload.write(to: url, atomically: true, encoding: .utf8) }
                catch { self.error = error.localizedDescription }
            }
        } catch { self.error = error.localizedDescription }
    }

    func cancel(_ run: AgentRun) async {
        do {
            let key = run.provider == "box" ? try await Keychain.read("box") : ""
            _ = await perform("run.cancel", ["id": run.id, "credential": key])
        } catch { self.error = error.localizedDescription }
    }

    func refreshAccounts() async {
        guard !refreshingAccounts else { return }
        let generation = hostGeneration
        refreshingAccounts = true
        defer { refreshingAccounts = false }
        do {
            let result: AgentAccountsResult = try await call("agents.list", ["refresh": true], as: AgentAccountsResult.self)
            guard generation == hostGeneration else { return }
            accounts = result.agents
            accountError = nil
        } catch {
            if generation == hostGeneration, !Task.isCancelled, !isRequestCancellation(error) {
                accountError = error.localizedDescription
            }
        }
    }

    func signIn(_ account: AgentAccount) async {
        guard !isRemote else {
            error = "Sign in on the server using \(account.id == "codex" ? "codex login --device-auth" : "claude auth login"), then refresh agents here."
            return
        }
        do {
            let result: PathResult = try await call("agents.login", ["agent": account.id], as: PathResult.self)
            NSWorkspace.shared.open(URL(fileURLWithPath: result.path))
        } catch { self.error = error.localizedDescription }
    }

    func chooseProject() {
        guard let wid = selectedID else { return }
        let panel = NSOpenPanel()
        panel.canChooseFiles = false; panel.canChooseDirectories = true
        panel.message = "Choose the project whose agentic-stack configuration you want to manage."
        present(panel) { response in
            guard response == .OK, let url = panel.url else { return }
            ProjectAccess.shared.remember(url)
            Task {
                await self.bridge.restart()
                _ = await self.perform("stack.attach", ["workspaceId": wid, "path": url.path])
            }
        }
    }

    func stop() async { await bridge.stop() }
}
