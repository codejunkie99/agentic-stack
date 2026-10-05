import AppKit
import SwiftUI

private enum SpotlightCategory: String, CaseIterable, Identifiable {
    case all = "All", work = "Work", memory = "Memory", conversations = "Conversations", skills = "Skills", actions = "Actions"
    var id: String { rawValue }
}

private struct SpotlightMemoryClaim: Decodable, Identifiable {
    let id: String
    let body: String
    let kind: String
}
private struct SpotlightMemoryClaims: Decodable {
    let claims: [SpotlightMemoryClaim]
}

struct SpotlightJevMatch: Decodable, Identifiable, Sendable {
    let id: String
    let title: String
    let body: String
    let kind: String
    let source: String
    let score: Double?
    let confidence: Double?
    let digest: String
    let origins: [RunMemoryOrigin]?
}
struct SpotlightJevCoverage: Decodable, Sendable {
    let candidateCount: Int?
    let evaluatedCount: Int?
    let omittedCount: Int?
    let exhaustive: Bool?
    let hasMore: Bool?
}
struct SpotlightJevResponse: Decodable, Sendable {
    let matches: [SpotlightJevMatch]
    let status: String
    let warning: String?
    let coverage: SpotlightJevCoverage?
    let providerCalls: Int?
    let elapsedMs: Double?
    let cacheHit: Bool?
}

private struct SpotlightResult: Identifiable {
    enum Destination {
        case work(WorkItem), conversation(AgentConversation), memory(GraphNote), reference(ConversationReference)
        case claim(SpotlightMemoryClaim), jev(SpotlightJevMatch)
        case skill(InstalledSkill), action(StackAction), project(Workspace), newWork, newProject, openProject
    }
    let id: String
    let group: String
    let title: String
    let detail: String
    let source: String
    let symbol: String
    let score: Int
    let destination: Destination
}

struct SpotlightSearchView: View {
    @Bindable var model: AppModel
    var fixture: String? = nil
    @State private var showingProviderSettings = false
    @State private var selectedSearchMode: String?
    private var jevAvailable: Bool { fixture.map { JevProviderStatus.fixture($0)?.isAvailable == true } ?? model.jevProviderAvailable }
    private var searchMode: String {
        get { selectedSearchMode ?? (jevAvailable ? "fast" : "local") }
        nonmutating set {
            guard JevProviderModes.allows(newValue, available: jevAvailable) else { return }
            selectedSearchMode = newValue
        }
    }
    @State private var jevResponse: SpotlightJevResponse?
    @State private var jevKey = ""
    @State private var jevError = ""
    @State private var searchingJev = false
    @State private var requestElapsedMs: Double?
    @State private var previewJev: SpotlightJevMatch?
    @State private var query = ""
    @State private var category = SpotlightCategory.all
    @State private var allConversations = false
    @State private var conversationTool = ""
    @State private var conversationRole = ""
    @State private var conversationModel = ""
    @State private var conversationModels: [String] = []
    @State private var selectedID: String?
    @State private var notes: [GraphNote] = []
    @State private var claims: [SpotlightMemoryClaim] = []
    @State private var previewClaim: SpotlightMemoryClaim?
    @State private var references: [ConversationReference] = []
    @State private var skills: [InstalledSkill] = []
    @State private var memoryKey = ""
    @State private var referencesKey = ""
    @State private var skillsKey = ""
    @State private var searchingMemory = false
    @State private var searchingConversations = false
    @State private var memoryError = ""
    @State private var referencesError = ""
    @State private var skillsError = ""
    @State private var previewSkill: InstalledSkill?
    @State private var previewReference: ConversationReference?
    @State private var previewContent = ""
    @State private var previewError = ""
    @State private var focusRequest = 0

    private var trimmedQuery: String { query.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var projectKey: String { model.handoverPreviewKey }
    private var searchKey: String {
        [projectKey, category.rawValue, trimmedQuery, model.spotlightTopic, String(allConversations),
         conversationTool, conversationRole, conversationModel, searchMode, String(jevAvailable)].joined(separator: ":")
    }
    private var limit: Int { category == .all ? 5 : 40 }
    private var searching: Bool { searchingMemory || searchingConversations || searchingJev }
    private var jevFiltersSupported: Bool { !allConversations && conversationTool.isEmpty && conversationRole.isEmpty && conversationModel.isEmpty }
    private var results: [SpotlightResult] {
        var rows: [SpotlightResult] = []
        func add(_ id: String, _ group: String, _ title: String, _ detail: String, _ source: String, _ symbol: String, _ destination: SpotlightResult.Destination) {
            guard let score = SpotlightSearchRules.score(trimmedQuery, title: title, detail: detail + " " + source) else { return }
            rows.append(.init(id: id, group: group, title: title, detail: detail, source: source, symbol: symbol, score: score, destination: destination))
        }
        if category == .all || category == .work {
            for item in model.workItems {
                let nextAction = item.checkpoint?.nextAction ?? ""
                add("work:" + item.id, "Work", item.title, nextAction.isEmpty ? item.objective : nextAction,
                    item.status.replacingOccurrences(of: "_", with: " ").capitalized, "square.stack", .work(item))
            }
        }
        if (category == .all || category == .conversations) {
            for chat in model.conversations where
                (conversationTool.isEmpty || chat.agent == conversationTool) &&
                (conversationModel.isEmpty || chat.model.localizedCaseInsensitiveContains(conversationModel)) &&
                (conversationRole.isEmpty || conversationRole == "agent") {
                add("conversation:" + chat.id, searchMode == "local" ? "Conversations" : "Work", chat.title, chat.agentName ?? chat.agent,
                    chat.model.isEmpty ? "Agentic Stack" : chat.model, "bubble.left.and.bubble.right", .conversation(chat))
            }
            if searchMode == "local", referencesKey == searchKey {
                let nativeIDs = Set(model.conversations.map { "native:" + $0.id })
                for ref in references where !nativeIDs.contains(ref.id) {
                    let provenance = [ref.agentName, ref.roleName, ref.model, ref.workspaceName].compactMap { value in
                        value.flatMap { $0.isEmpty ? nil : $0 }
                    }.joined(separator: " · ")
                    rows.append(.init(id: "reference:" + ref.id, group: "Conversations", title: ref.title, detail: ref.excerpt,
                                      source: provenance, symbol: "bubble.left.and.text.bubble.right",
                                      score: ref.score ?? 0, destination: .reference(ref)))
                }
            }
        }
        if searchMode == "local", (category == .all || category == .memory), memoryKey == searchKey {
            for (index, claim) in claims.enumerated() {
                rows.append(.init(id: "claim:" + claim.id, group: "Memory", title: String(claim.body.prefix(160)), detail: claim.body,
                                  source: "Accepted · " + claim.kind.capitalized, symbol: "brain",
                                  score: notes.count + claims.count - index, destination: .claim(claim)))
            }
            for (index, note) in notes.enumerated() {
                rows.append(.init(id: "memory:" + note.id, group: "Memory", title: note.displayTitle, detail: note.body,
                                  source: (note.origins.first?.provider ?? "Memory") + (note.status.map { " · " + $0.capitalized } ?? ""),
                                  symbol: "brain", score: notes.count - index, destination: .memory(note)))
            }
        }
        if searchMode != "local", jevKey == searchKey, let response = jevResponse {
            for match in response.matches {
                let group = match.kind.contains("conversation") ? "Conversations" : match.id.hasPrefix("claim:") || ["memory", "claim", "fact", "lesson"].contains(match.kind) ? "Memory" : "Sources"
                rows.append(.init(id: "jev:" + match.id, group: group, title: match.title, detail: match.body, source: match.source,
                    symbol: group == "Memory" ? "brain" : group == "Conversations" ? "bubble.left.and.text.bubble.right" : "doc.text",
                    score: Int(min(10000, max(0, (match.score ?? 0) * 1000))), destination: .jev(match)))
            }
        }
        if (category == .all && !trimmedQuery.isEmpty || category == .skills), skillsKey == projectKey {
            for skill in skills {
                add("skill:" + skill.id, "Skills", skill.name, "Read this project’s skill instructions", "Installed in project", "sparkles", .skill(skill))
            }
        }
        if category == .all || category == .actions {
            if model.selectedID != nil { add("new-work", "Actions", "New work", "Start a new objective", "⌘N", "square.and.pencil", .newWork) }
            add("open-project", "Actions", "Open project…", "Choose a project folder", "⌘O", "folder", .openProject)
            add("new-project", "Actions", "New project…", "Create a project", "⌥⌘N", "folder.badge.plus", .newProject)
            let available = StackAction.all.filter { model.selectedID != nil || $0.section != nil || ["setup", "create-agent"].contains($0.id) }
            for action in available where !trimmedQuery.isEmpty || category == .actions || ["section-Knowledge graph", "section-Skills"].contains(action.id) {
                add("action:" + action.id, "Actions", action.title, action.detail, "Action", action.symbol, .action(action))
            }
            for project in model.snapshot.workspaces where !trimmedQuery.isEmpty && project.id != model.selectedID {
                add("project:" + project.id, "Projects", project.name, project.goal, "Switch project", "folder", .project(project))
            }
        }
        // Keep familiar groups stable while each group ranks by relevance, then recency.
        return ["Work", "Memory", "Conversations", "Sources", "Skills", "Projects", "Actions"].flatMap { group in
            rows.enumerated().filter { $0.element.group == group }.sorted {
                $0.element.score == $1.element.score ? $0.offset < $1.offset : $0.element.score > $1.element.score
            }.prefix(limit).map(\.element)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            if let match = previewJev { jevPreview(match) }
            else if let claim = previewClaim { claimPreview(claim) }
            else if let skill = previewSkill { skillPreview(skill) }
            else if let reference = previewReference { referencePreview(reference) }
            else {
                searchHeader
                filters
                contentSearchStatus
                Divider()
                resultList
                footer
            }
        }
        .frame(maxWidth: 740, maxHeight: 610)
        .background { StackFrostedSurface().clipShape(RoundedRectangle(cornerRadius: 16)) }
        .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Palette.line))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.22), radius: 28, y: 12)
        .onAppear {
            category = SpotlightCategory(rawValue: model.spotlightCategory) ?? .all
            query = fixture == nil ? String(model.spotlightQuery.prefix(300)) : "Which sources explain cancellation and exact memory evidence?"
        }
        .onExitCommand {
            if previewJev != nil || previewClaim != nil || previewSkill != nil || previewReference != nil { previewJev = nil; previewClaim = nil; previewSkill = nil; previewReference = nil; focusRequest += 1 }
            else { dismiss() }
        }
        .onChange(of: query) { _, value in
            if value.count > 300 { query = String(value.prefix(300)) }
        }
        .onChange(of: results.map(\.id), initial: true) { _, ids in
            if !ids.contains(selectedID ?? "") { selectedID = ids.first }
        }
        .onChange(of: projectKey) { _, _ in
            previewJev = nil; jevResponse = nil; jevKey = ""; previewSkill = nil; previewReference = nil; previewContent = ""; previewClaim = nil; notes = []; claims = []; references = []; skills = []
            conversationModels = []; conversationModel = ""
        }
        .sheet(isPresented: $showingProviderSettings) { JevProviderSettingsView(model: model) }
        .task(id: searchKey) { await search() }
        .task(id: projectKey) { await loadSkills() }
        .task(id: model.jevProviderHostKey) { await model.refreshJevProviderStatus() }
        .task(id: previewSkill?.id) { await loadSkillPreview() }
        .accessibilityIdentifier("spotlight-search")
    }

    private var searchHeader: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Search workspace").font(StackType.heading).fixedSize().accessibilityAddTraits(.isHeader)
                Spacer()
                Picker("Content search mode", selection: Binding(get: { searchMode }, set: { searchMode = $0 })) {
                    if JevProviderModes.shows("fast", selected: searchMode, available: jevAvailable) {
                        Text(jevAvailable ? "Ultra-fast (Jev)" : "Ultra-fast (Jev) · Unavailable").tag("fast")
                    }
                    if JevProviderModes.shows("standard", selected: searchMode, available: jevAvailable) {
                        Text(jevAvailable ? "Jev standard" : "Jev standard · Unavailable").tag("standard")
                    }
                    Text("Local search").tag("local")
                }.labelsHidden().frame(width: 172).accessibilityLabel("Content search mode")
                StackIconButton(title: "Close search", symbol: "xmark") { dismiss() }
            }
            HStack(spacing: 12) {
                Image(systemName: "magnifyingglass").font(.system(size: 18)).foregroundStyle(Palette.secondary)
                    .accessibilityHidden(true)
                NativeSpotlightField(text: $query, placeholder: "Search work, memories, and conversations…",
                    accessibilityName: "Search workspace", focusRequest: focusRequest,
                    onSubmit: { if let result = results.first(where: { $0.id == selectedID }) { activate(result) } },
                    onMove: { move($0) }, onEscape: { dismiss() },
                    canFocus: { (fixture != nil || model.showingCommandPalette) && model.conversationAttachmentRequest == nil && model.knowledgeFilterRequest == nil })
                    .frame(height: 28)
                ZStack { if searching { ProgressView().controlSize(.small).accessibilityLabel("Searching") } }.frame(width: 16, height: 16)
                if !query.isEmpty {
                    StackIconButton(title: "Clear search", symbol: "xmark.circle.fill") { query = ""; focusRequest += 1 }
                }
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(Palette.canvas, in: RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Palette.link, lineWidth: 1))
        }.padding(.horizontal, 20).padding(.top, 16).padding(.bottom, 14)
    }

    private var filters: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 6) {
                ForEach(SpotlightCategory.allCases) { item in
                    Button {
                        category = item; model.spotlightCategory = item.rawValue
                        if item != .memory { model.spotlightTopic = "" }
                        focusRequest += 1
                    } label: {
                        Text(item.rawValue).font(.system(size: 12, weight: category == item ? .semibold : .regular))
                            .padding(.horizontal, 11).padding(.vertical, 7)
                            .background(category == item ? Palette.selection : .clear, in: RoundedRectangle(cornerRadius: 7))
                            .foregroundStyle(category == item ? Palette.link : Palette.secondary)
                    }.buttonStyle(.plain).accessibilityAddTraits(category == item ? .isSelected : [])
                }
                Spacer(minLength: 0)
            }
            HStack(spacing: 8) {
                Label(model.selected?.name ?? "Choose a project to search its knowledge", systemImage: "folder")
                    .lineLimit(1).truncationMode(.middle)
                if !model.spotlightTopic.isEmpty {
                    Button { model.spotlightTopic = ""; focusRequest += 1 } label: {
                        Label(model.spotlightTopic, systemImage: "xmark.circle.fill")
                    }.buttonStyle(.plain).help("Clear topic filter")
                }
                Spacer(minLength: 8)
                if category == .all || category == .conversations {
                    Menu {
                        Button("This project") { allConversations = false }
                        Button("All conversations · Local search") { searchMode = "local"; allConversations = true }
                    } label: { Text(allConversations ? "All conversations" : "Project conversations") }
                        .menuStyle(.borderlessButton).fixedSize().accessibilityLabel("Conversation search scope")
                }
            }.font(StackType.caption).foregroundStyle(Palette.secondary)
            if category == .all || category == .conversations {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        Menu {
                            Button("All tools") { conversationTool = ""; focusRequest += 1 }
                            Divider()
                            ForEach(["claude-code", "codex", "opencode", "cursor"], id: \.self) { tool in
                                Button(conversationToolName(tool)) { conversationTool = tool; focusRequest += 1 }
                            }
                        } label: { Label(conversationToolName(conversationTool), systemImage: "terminal") }
                        .menuStyle(.borderlessButton).fixedSize()
                        Menu {
                            Button("All roles") { conversationRole = ""; focusRequest += 1 }
                            Divider()
                            Button("Agents") { conversationRole = "agent"; focusRequest += 1 }
                            Button("Subagents") { conversationRole = "subagent"; focusRequest += 1 }
                            Button("Automations") { conversationRole = "automation"; focusRequest += 1 }
                            Button("Reviews") { conversationRole = "review"; focusRequest += 1 }
                        } label: { Label(conversationRoleName, systemImage: "person.2") }
                        .menuStyle(.borderlessButton).fixedSize()
                        if !conversationModels.isEmpty {
                            Menu {
                                Button("Any model") { conversationModel = ""; focusRequest += 1 }
                                Divider()
                                ForEach(conversationModels, id: \.self) { item in
                                    Button(item) { conversationModel = item; focusRequest += 1 }
                                }
                            } label: { Label(conversationModel.isEmpty ? "Any model" : conversationModel, systemImage: "cpu") }
                            .menuStyle(.borderlessButton).fixedSize()
                        }
                        if !conversationTool.isEmpty || !conversationRole.isEmpty || !conversationModel.isEmpty {
                            Button {
                                conversationTool = ""; conversationRole = ""; conversationModel = ""; focusRequest += 1
                            } label: { Label("Clear", systemImage: "xmark.circle.fill") }
                            .buttonStyle(.plain)
                        }
                    }.font(StackType.caption).foregroundStyle(Palette.secondary)
                        .disabled(searchMode != "local").help(searchMode == "local" ? "Conversation filters" : "Choose Local search to filter by tool, role, or model")
                }
            }
        }.padding(.horizontal, 20).padding(.bottom, 8)
    }

    private var resultList: some View {
        ScrollViewReader { scroll in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 3) {
                    if trimmedQuery.isEmpty && category == .all {
                        Text("Continue your work").font(.system(size: 12, weight: .semibold)).foregroundStyle(Palette.secondary).padding(.horizontal, 12).padding(.top, 12)
                    }
                    let rows = results
                    ForEach(Array(rows.enumerated()), id: \.element.id) { index, result in
                        if index == 0 || rows[index - 1].group != result.group {
                            Text(result.group).font(.system(size: 12, weight: .semibold)).foregroundStyle(Palette.secondary)
                                .padding(.horizontal, 12).padding(.top, 12).padding(.bottom, 3)
                        }
                        resultRow(result).id(result.id)
                    }
                    if rows.isEmpty && !searching {
                        VStack(spacing: 10) {
                            Image(systemName: "magnifyingglass").font(.system(size: 28, weight: .light))
                            Text(trimmedQuery.isEmpty ? "Nothing here yet" : "No results for “\(trimmedQuery)”").font(StackType.detail.weight(.medium)).lineLimit(2)
                            Text("Try another term or choose a different category.").font(StackType.caption)
                        }.foregroundStyle(Palette.secondary).frame(maxWidth: .infinity).padding(.vertical, 55)
                    }
                    let errors = [jevError, memoryError, referencesError, skillsError].filter { !$0.isEmpty }
                    if !errors.isEmpty {
                        Text(errors.joined(separator: "\n")).font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled).padding(12)
                    }
                }.padding(.horizontal, 10).padding(.bottom, 10)
            }.onChange(of: selectedID) { _, id in if let id { scroll.scrollTo(id, anchor: .center) } }
        }.frame(maxWidth: .infinity, minHeight: 140, maxHeight: .infinity)
    }

    private func resultRow(_ result: SpotlightResult) -> some View {
        Button { activate(result) } label: {
            HStack(spacing: 12) {
                Image(systemName: result.symbol).font(.system(size: 18)).foregroundStyle(Palette.link)
                    .frame(width: 36, height: 36).background(Palette.accent.opacity(0.08), in: RoundedRectangle(cornerRadius: 9))
                VStack(alignment: .leading, spacing: 3) {
                    Text(result.title).font(StackType.detail.weight(.medium)).lineLimit(1).help(result.title)
                    Text(SpotlightSearchRules.excerpt(result.detail, query: trimmedQuery)).font(.system(size: 12)).foregroundStyle(Palette.secondary).lineLimit(1)
                }
                Spacer(minLength: 6)
                Text(result.source).font(.system(size: 12)).foregroundStyle(Palette.secondary).lineLimit(1).frame(maxWidth: 145, alignment: .trailing)
                if selectedID == result.id { Image(systemName: "return").font(StackType.caption).foregroundStyle(Palette.secondary) }
            }.padding(.horizontal, 12).padding(.vertical, 10)
                .background(selectedID == result.id ? Palette.selection : .clear, in: RoundedRectangle(cornerRadius: 10))
                .contentShape(Rectangle())
        }.buttonStyle(.plain).accessibilityAddTraits(selectedID == result.id ? .isSelected : [])
    }

    private var footer: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 14) {
                Text("↑ ↓  Navigate"); Text("↵  Open"); Text("esc  Close")
                Spacer()
                Text("⌘K").font(StackType.caption.monospaced())
            }.font(.system(size: 12)).foregroundStyle(Palette.secondary).padding(.horizontal, 24).padding(.vertical, 13)
        }
    }

    private func claimPreview(_ claim: SpotlightMemoryClaim) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Button { previewClaim = nil; focusRequest += 1 } label: { Label("Search", systemImage: "chevron.left") }.buttonStyle(.plain)
                Spacer()
                Button("Open project memory") { dismiss(); model.section = .memory }
            }.font(StackType.detail).padding(22)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Accepted · " + claim.kind.capitalized).font(StackType.caption).foregroundStyle(Palette.secondary)
                    Text(claim.body).font(StackType.detail).textSelection(.enabled)
                    Text("Open project memory and select Accepted to review its evidence and decision history.").font(StackType.caption).foregroundStyle(Palette.secondary)
                }.frame(maxWidth: .infinity, alignment: .leading).padding(24)
            }
        }
    }

    private func skillPreview(_ skill: InstalledSkill) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Button { previewSkill = nil; focusRequest += 1 } label: { Label("Search", systemImage: "chevron.left") }.buttonStyle(.plain)
                Spacer()
                Button("Open Skills") { dismiss(); model.section = .skills }
            }.font(StackType.detail).padding(22)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text(skill.name).font(.title2.weight(.semibold))
                    Text(".agent/skills/\(skill.id)/SKILL.md").font(StackType.caption).foregroundStyle(Palette.secondary)
                    if !previewError.isEmpty { Text(previewError).foregroundStyle(Palette.secondary) }
                    else if previewContent.isEmpty { ProgressView("Reading skill…") }
                    else { Text(previewContent).font(.system(.callout, design: .monospaced)).textSelection(.enabled) }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(24)
            }
        }
    }

    private func referencePreview(_ reference: ConversationReference) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Button { previewReference = nil; focusRequest += 1 } label: { Label("Search", systemImage: "chevron.left") }.buttonStyle(.plain)
                Spacer()
                Button("Attach to next message") {
                    model.attachConversationReference(reference)
                    dismiss(); model.graphFullPage = false; model.section = .chat
                }.buttonStyle(.borderedProminent).tint(Palette.accent)
                    .disabled(model.selectedConversationReferences.count >= 5 || model.selectedConversationReferences.contains(where: { $0.id == reference.id }))
            }.font(StackType.detail).padding(22)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(reference.title).font(.title2.weight(.semibold))
                    Text(reference.agentName + (reference.model.map { " · " + $0 } ?? "")).font(StackType.caption).foregroundStyle(Palette.secondary)
                    Text("Search excerpt").font(StackType.caption.weight(.semibold)).foregroundStyle(Palette.secondary)
                    Text(reference.excerpt.isEmpty ? "No excerpt is available for this conversation." : reference.excerpt).font(StackType.detail).textSelection(.enabled)
                    Divider()
                    Text("Source").font(StackType.caption.weight(.semibold))
                    Text(userFacingPath(reference.origin)).font(StackType.caption).textSelection(.enabled)
                    ForEach(Array((reference.origins ?? []).enumerated()), id: \.offset) { _, origin in
                        Text("\(userFacingPath(origin.path)):\(origin.line)").font(StackType.caption).textSelection(.enabled)
                    }
                    Text("Attach this conversation as context for your next message. You can review or remove it before sending.")
                        .font(StackType.caption).foregroundStyle(Palette.secondary)
                    if model.selectedConversationReferences.count >= 5 {
                        Text("Five conversations are already attached. Remove one from the composer to add this source.").font(StackType.caption).foregroundStyle(Palette.secondary)
                    }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(24)
            }
        }
    }

    private func move(_ direction: Int) { selectedID = SpotlightSearchRules.moving(selectedID, in: results.map(\.id), by: direction) }
    private func dismiss() { model.showingCommandPalette = false }

    private func conversationToolName(_ value: String) -> String {
        ["claude-code": "Claude Code", "codex": "Codex", "opencode": "OpenCode", "cursor": "Cursor"][value] ?? "All tools"
    }

    private var conversationRoleName: String {
        ["agent": "Agents", "subagent": "Subagents", "automation": "Automations", "review": "Reviews"][conversationRole] ?? "All roles"
    }

    private func activate(_ result: SpotlightResult) {
        if fixture != nil {
            if case .jev(let match) = result.destination { previewJev = match }
            return
        }
        switch result.destination {
        case .jev(let match): previewJev = match
        case .claim(let claim): previewClaim = claim
        case .skill(let skill): previewSkill = skill
        case .work(let item): dismiss(); model.openWork(item)
        case .conversation(let chat): dismiss(); model.openConversation(chat)
        case .memory(let note):
            dismiss(); model.section = .graph; model.graphFullPage = false
            Task { await model.inspectMemory(note.id, showGraph: true) }
        case .reference(let reference):
            let nativeID = reference.id.replacingOccurrences(of: "global-native:", with: "").replacingOccurrences(of: "native:", with: "")
            if reference.kind == "native", let chat = model.snapshot.conversations?.first(where: { $0.id == nativeID }) {
                dismiss(); model.selectedID = chat.workspaceId; model.openConversation(chat)
            } else {
                previewReference = reference
            }
        case .action(let action): dismiss(); action.perform(model)
        case .project(let project): dismiss(); model.selectedID = project.id
        case .newWork: dismiss(); model.newConversation()
        case .newProject: dismiss(); model.showingNewWorkspace = true
        case .openProject: dismiss(); model.openProjectPicker()
        }
    }

    private var contentSearchStatus: some View {
        HStack(spacing: 8) {
            Text(contentSearchMessage).lineLimit(1).help(contentSearchMessage)
            if searchMode != "local", !jevFiltersSupported {
                Button("Clear local filters") { allConversations = false; conversationTool = ""; conversationRole = ""; conversationModel = ""; focusRequest += 1 }.fixedSize()
            }
            if !jevAvailable || jevKey == searchKey && jevResponse?.status == "unavailable" {
                Button("Provider settings") { showingProviderSettings = true }.fixedSize()
            }
            Spacer(minLength: 8)
            if jevKey == searchKey, let elapsed = requestElapsedMs {
                Text("\(Int(elapsed.rounded())) ms request" + (jevResponse.map { "\($0.cacheHit == true ? " · Cache" : "") · \($0.providerCalls ?? 0) provider call(s)" } ?? ""))
                    .font(StackType.caption.monospaced()).fixedSize()
                    .help("Measured app request time after debounce. Host planning: \(Int((jevResponse?.elapsedMs ?? 0).rounded())) ms.")
            }
        }.font(StackType.caption).foregroundStyle(Palette.secondary)
            .padding(.horizontal, 20).frame(height: 28)
    }
    private var contentSearchMessage: String {
        if [.work, .skills, .actions].contains(category) { return "Instant local navigation" }
        if searchMode == "local" {
            if !jevAvailable { return (fixture != nil ? "Synthetic · " : "") + model.jevProviderStatusMessage + " · Local search available" }
            return "Local content search · Actions and work navigation remain instant"
        }
        if !jevAvailable { return model.jevProviderStatusMessage + " · Choose Local search or connect Jev" }
        if !jevFiltersSupported { return "These conversation filters require Local search." }
        if searching { return fixture != nil ? "Synthetic Jev search in progress…" : "Jev is selecting relevant source evidence…" }
        if !jevError.isEmpty { return jevError }
        if jevKey == searchKey, let result = jevResponse {
            let prefix = fixture != nil ? "Synthetic · " : ""
            if let warning = result.warning, !warning.isEmpty { return prefix + warning }
            switch result.status {
            case "unavailable": return prefix + "Jev unavailable · Check provider settings"
            case "abstained": return prefix + "Jev abstained · No relevant source selected"
            default:
                let coverage = result.coverage
                return prefix + "Jev · \(coverage?.evaluatedCount ?? 0)/\(coverage?.candidateCount ?? 0) candidates reviewed · Bounded sources"
            }
        }
        return "Jev content search · This project · Actions and work navigation stay local"
    }

    private func jevPreview(_ match: SpotlightJevMatch) -> some View {
        VStack(spacing: 0) {
            HStack {
                Button { previewJev = nil; focusRequest += 1 } label: { Label("Search", systemImage: "chevron.left") }.buttonStyle(.plain)
                Spacer()
                Button("Copy passage", systemImage: "doc.on.doc") {
                    NSPasteboard.general.clearContents(); NSPasteboard.general.setString(match.body, forType: .string)
                }
            }.font(StackType.detail).padding(16)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text(match.title).font(StackType.heading).textSelection(.enabled)
                    Text(match.source).font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
                    Text(match.body).font(StackType.body).lineSpacing(6).textSelection(.enabled)
                    Divider()
                    ForEach(Array((match.origins ?? []).enumerated()), id: \.offset) { _, origin in
                        Text("\(origin.path):\(origin.line)").font(StackType.caption.monospaced()).foregroundStyle(Palette.secondary).textSelection(.enabled)
                    }
                    Text("Digest · " + match.digest).font(StackType.caption.monospaced()).foregroundStyle(Palette.secondary).textSelection(.enabled)
                    if let confidence = match.confidence { Text("Jev confidence · \(Int(min(1, max(0, confidence)) * 100))%").font(StackType.caption).foregroundStyle(Palette.secondary) }
                    Text("Source evidence is a historical reference. Verify current claims before relying on it.").font(StackType.caption).foregroundStyle(Palette.secondary)
                }.padding(24).frame(maxWidth: 736, alignment: .leading).frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }

    private func searchWithJev() async {
        let key = searchKey, host = model.terminalHost
        jevError = ""; memoryError = ""; referencesError = ""; requestElapsedMs = nil
        searchingMemory = false; searchingConversations = false; searchingJev = false
        guard jevFiltersSupported, !trimmedQuery.isEmpty, category == .all || category == .memory || category == .conversations else { return }
        guard jevAvailable else { jevError = "Jev is not connected. Local search remains available."; return }
        guard fixture != nil || model.selectedID != nil && model.hostReady else { jevError = "Connect a project host to search its content with Jev."; return }
        do { try await Task.sleep(for: .milliseconds(160)) } catch { return }
        guard !Task.isCancelled, key == searchKey else { return }
        searchingJev = true
        defer { if key == searchKey { searchingJev = false } }
        let clock = ContinuousClock(), started = ContinuousClock.now
        func elapsedMs() -> Double {
            let duration = started.duration(to: clock.now).components
            return Double(duration.seconds) * 1000 + Double(duration.attoseconds) / 1_000_000_000_000_000
        }
        do {
            let result: SpotlightJevResponse
            if let fixture {
                if fixture == "failure" { throw BridgeError(message: "Synthetic host connection failed.") }
                if fixture == "loading" {
                    while !Task.isCancelled { try await Task.sleep(for: .seconds(30)) }
                    return
                }
                try await Task.sleep(for: .milliseconds(fixture == "cached" ? 24 : 180))
                result = Self.fixtureResponse(fixture)
            } else {
                result = try await model.terminalCall("search.context", ["workspaceId": model.selectedID ?? "", "query": trimmedQuery,
                    "category": category == .memory ? "memory" : category == .conversations ? "conversations" : "all",
                    "topic": model.spotlightTopic, "profile": searchMode], host: host, as: SpotlightJevResponse.self)
            }
            guard !Task.isCancelled, key == searchKey else { return }
            jevResponse = result; jevKey = key; requestElapsedMs = elapsedMs()
        } catch {
            guard !Task.isCancelled, key == searchKey else { return }
            jevResponse = nil; jevKey = key; jevError = error.localizedDescription; requestElapsedMs = elapsedMs()
        }
    }

    static func fixtureResponse(_ state: String) -> SpotlightJevResponse {
        let empty = ["unavailable", "abstained", "empty"].contains(state)
        let matches = [
            SpotlightJevMatch(id: "claim:fixture", title: "Preserve exact source evidence", body: "Every accepted memory retains its original evidence and revision history. Retrieval includes reviewed project claims.", kind: "memory", source: "Project memory · synthetic release requirement", score: 3, confidence: 0.96, digest: "synthetic-digest-memory", origins: []),
            SpotlightJevMatch(id: "conversation:fixture", title: "Cancellation decision from an earlier discussion", body: "A cancelled or stale request must not replace newer results. Keep the draft and selection during background work.", kind: "conversation", source: "Synthetic project conversation", score: 2.8, confidence: 0.94, digest: "synthetic-digest-conversation", origins: [RunMemoryOrigin(path: "fixture/desktop.md", line: 12)]),
            SpotlightJevMatch(id: "source:fixture", title: "Native release verification", body: "The isolated fixture exercises source selection, unavailable providers, cache indicators, and interrupted search without opening real project data.", kind: "source", source: "Synthetic reviewed source · verification.md:8", score: 2.7, confidence: 0.92, digest: "synthetic-digest-source", origins: [RunMemoryOrigin(path: "fixture/verification.md", line: 8)])
        ]
        return SpotlightJevResponse(matches: empty ? [] : matches, status: empty ? state == "empty" ? "completed" : state : "completed", warning: nil,
            coverage: SpotlightJevCoverage(candidateCount: empty ? 0 : 8, evaluatedCount: empty ? 0 : 8, omittedCount: 0, exhaustive: false, hasMore: false), providerCalls: empty || state == "cached" ? 0 : 1,
            elapsedMs: state == "cached" ? 24 : 180, cacheHit: state == "cached")
    }

    private func search() async {
        if searchMode != "local" { await searchWithJev(); return }
        searchingJev = false
        if fixture != nil { return }
        let key = searchKey, host = model.terminalHost
        memoryError = ""; referencesError = ""
        searchingMemory = false; searchingConversations = false
        guard let wid = model.selectedID else { return }
        let query = trimmedQuery, topic = model.spotlightTopic
        let needMemory = category == .memory || category == .all && !query.isEmpty
        let needConversations = category == .conversations || category == .all && !query.isEmpty
        guard needMemory || needConversations else { return }
        do { try await Task.sleep(for: .milliseconds(160)) } catch { return }
        guard key == searchKey else { return }
        async let memory: Void = searchMemory(enabled: needMemory, query: query, topic: topic, wid: wid, host: host, key: key)
        async let conversations: Void = searchConversations(enabled: needConversations, query: query, wid: wid, host: host, key: key)
        _ = await (memory, conversations)
    }

    private func searchMemory(enabled: Bool, query: String, topic: String, wid: String, host: String, key: String) async {
        guard enabled else { return }
        searchingMemory = true
        defer { if key == searchKey { searchingMemory = false } }
        claims = []; notes = []; memoryKey = key
        if topic.isEmpty {
            do {
                let state = try await model.terminalCall("memory.ledger.search", ["workspaceId": wid, "query": query], host: host, as: SpotlightMemoryClaims.self)
                guard !Task.isCancelled, key == searchKey else { return }
                claims = state.claims
            } catch { if !Task.isCancelled, key == searchKey { memoryError = "Project memory: " + error.localizedDescription } }
        }
        guard !Task.isCancelled, key == searchKey else { return }
        do {
            let state = try await model.terminalCall("knowledge.query", ["workspaceId": wid, "query": query, "topic": topic], host: host, as: GraphSnapshot.self)
            guard !Task.isCancelled, key == searchKey else { return }
            notes = state.notes
        } catch { if !Task.isCancelled, key == searchKey { memoryError += " Imported memory: " + error.localizedDescription } }
    }

    private func searchConversations(enabled: Bool, query: String, wid: String, host: String, key: String) async {
        guard enabled else { return }
        searchingConversations = true
        defer { if key == searchKey { searchingConversations = false } }
        do {
            let result = try await model.terminalCall("conversation.references", ["workspaceId": wid, "query": query,
                "scope": allConversations ? "all" : "project", "agent": conversationTool, "role": conversationRole,
                "model": conversationModel, "limit": 40], host: host, as: ConversationReferenceResult.self)
            guard !Task.isCancelled, key == searchKey else { return }
            references = result.references; referencesKey = key; conversationModels = result.models ?? []
        } catch { if !Task.isCancelled, key == searchKey { referencesError = "Conversation search: " + error.localizedDescription } }
    }

    private func loadSkills() async {
        guard fixture == nil else { return }
        let key = projectKey, host = model.terminalHost
        skillsError = ""
        guard let wid = model.selectedID else { return }
        do {
            let result = try await model.terminalCall("stack.snapshot", ["workspaceId": wid], host: host, as: StackSnapshot.self)
            guard !Task.isCancelled, key == projectKey else { return }
            skills = result.skills; skillsKey = key
        } catch { if !Task.isCancelled, key == projectKey { skillsError = "Skills: " + error.localizedDescription } }
    }

    private func loadSkillPreview() async {
        previewContent = ""; previewError = ""
        guard let skill = previewSkill, let wid = model.selectedID else { return }
        let key = projectKey, host = model.terminalHost
        do {
            let result = try await model.terminalCall("stack.file", ["workspaceId": wid, "path": ".agent/skills/\(skill.id)/SKILL.md"], host: host, as: ProjectFile.self)
            guard !Task.isCancelled, key == projectKey, previewSkill?.id == skill.id else { return }
            previewContent = result.text.isEmpty ? "This skill file is empty." : result.text
        } catch { if !Task.isCancelled, key == projectKey { previewError = error.localizedDescription } }
    }
}
