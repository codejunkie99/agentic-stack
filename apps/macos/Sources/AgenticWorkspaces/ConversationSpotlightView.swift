import SwiftUI

private struct ConversationSpotlightPage: Decodable, Sendable {
    let references: [ConversationReference]
    let total: Int
    let models: [String]?
    let roles: [String]?
    let hasMore: Bool?
    let nextOffset: Int?
}

/// Attachment search owns its results so it cannot replace the main search or another draft's context.
struct ConversationSpotlightView: View {
    @Bindable var model: AppModel
    var initialQuery = ""
    var initialAgent = ""
    var context = ""
    var onSelect: @MainActor (ConversationReference) -> Void
    var onDismiss: @MainActor () -> Void
    @State private var query = ""
    @State private var tool = ""
    @State private var modelFilter = ""
    @State private var roleFilter = ""
    @State private var scope = "all"
    @State private var references: [ConversationReference] = []
    @State private var models: [String] = []
    @State private var selectedID: String?
    @State private var total = 0
    @State private var nextOffset: Int?
    @State private var loading = false
    @State private var error = ""
    @State private var loadedKey = ""
    @State private var loadMoreTask: Task<Void, Never>?
    @State private var focusRequest = 0

    private let tools = [("", "All tools", "square.stack"), ("codex", "Codex", "terminal"),
                         ("claude-code", "Claude Code", "sparkle"), ("cursor", "Cursor", "cursorarrow.rays"),
                         ("opencode", "OpenCode", "chevron.left.forwardslash.chevron.right")]
    private var parsedQuery: (agent: String, query: String) { SpotlightSearchRules.conversationQuery(query) }
    private var effectiveTool: String { parsedQuery.agent.isEmpty ? tool : parsedQuery.agent }
    private var searchKey: String {
        [model.conversationDraftKey, effectiveTool, parsedQuery.query, modelFilter, roleFilter, scope].joined(separator: "|")
    }
    private var rows: [ConversationReference] { loadedKey == searchKey ? references : [] }
    private var attachedIDs: Set<String> { Set(model.selectedConversationReferences.map(\.id)) }

    var body: some View {
        VStack(spacing: 0) {
            searchHeader
            filters
            Divider()
            resultList
            footer
        }
        .frame(maxWidth: 780, maxHeight: 640)
        .background { StackFrostedSurface().clipShape(RoundedRectangle(cornerRadius: 20)) }
        .overlay { RoundedRectangle(cornerRadius: 20).strokeBorder(.primary.opacity(0.1)) }
        .clipShape(RoundedRectangle(cornerRadius: 20))
        .shadow(color: .black.opacity(0.22), radius: 32, y: 16)
        .onAppear { query = String(initialQuery.prefix(300)); tool = initialAgent }
        .onExitCommand { onDismiss() }
        .onChange(of: query) { _, value in if value.count > 300 { query = String(value.prefix(300)) } }
        .onChange(of: rows.map(\.id), initial: true) { _, ids in
            if !ids.contains(selectedID ?? "") { selectedID = ids.first(where: { !attachedIDs.contains($0) }) ?? ids.first }
        }
        .task(id: searchKey) {
            loadMoreTask?.cancel()
            error = ""; loading = true; nextOffset = nil
            do { try await Task.sleep(for: .milliseconds(160)) } catch { return }
            await loadPage(offset: 0)
        }
        .onDisappear { loadMoreTask?.cancel() }
        .accessibilityIdentifier("conversation-spotlight")
    }

    private var searchHeader: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Label("Conversations", systemImage: "at").font(.system(size: 12, weight: .semibold)).foregroundStyle(Palette.secondary)
                Spacer()
                if !attachedIDs.isEmpty { Text("\(attachedIDs.count) of 5 attached").font(StackType.caption).foregroundStyle(Palette.secondary) }
                Button { onDismiss() } label: {
                    Text("esc").font(StackType.caption.monospaced()).foregroundStyle(Palette.secondary).padding(5)
                        .background(.primary.opacity(0.05), in: RoundedRectangle(cornerRadius: 5))
                }.buttonStyle(.plain).accessibilityLabel("Close conversation search")
            }
            HStack(spacing: 14) {
                Image(systemName: "magnifyingglass").font(.system(size: 23, weight: .light)).foregroundStyle(Palette.secondary)
                NativeSpotlightField(text: $query, placeholder: "Search every connected conversation…",
                    accessibilityName: "Search conversations", focusRequest: focusRequest,
                    onSubmit: { if let reference = rows.first(where: { $0.id == selectedID }) { select(reference) } },
                    onMove: { move($0) }, onEscape: onDismiss,
                    canFocus: { model.conversationAttachmentRequest != nil && !model.showingCommandPalette && model.knowledgeFilterRequest == nil })
                    .frame(height: 30)
                if loading { ProgressView().controlSize(.small) }
            }
        }.padding(.horizontal, 24).padding(.top, 20).padding(.bottom, 18)
    }

    private var filters: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 6) {
                ForEach(tools, id: \.0) { value, name, symbol in
                    Button {
                        query = parsedQuery.query; tool = value; modelFilter = ""; focusRequest += 1
                    } label: {
                        Label(name, systemImage: symbol).font(.system(size: 12, weight: effectiveTool == value ? .semibold : .regular))
                            .padding(.horizontal, 10).padding(.vertical, 7)
                            .background(effectiveTool == value ? Palette.selection : .clear, in: RoundedRectangle(cornerRadius: 7))
                            .foregroundStyle(effectiveTool == value ? Palette.link : Palette.secondary)
                    }.buttonStyle(.plain).accessibilityAddTraits(effectiveTool == value ? .isSelected : [])
                }
                Spacer(minLength: 0)
            }
            HStack(spacing: 16) {
                Menu {
                    Button("All projects") { scope = "all" }
                    Button("This project") { scope = "project" }
                } label: { Label(scope == "all" ? "All projects" : model.selected?.name ?? "This project", systemImage: "folder") }
                    .menuStyle(.borderlessButton).fixedSize().accessibilityLabel("Conversation project filter")
                Menu {
                    Button("All models") { modelFilter = "" }
                    if !models.isEmpty { Divider() }
                    ForEach(models, id: \.self) { value in Button(value) { modelFilter = value } }
                } label: { Label(modelFilter.isEmpty ? "All models" : modelFilter, systemImage: "cpu").lineLimit(1) }
                    .menuStyle(.borderlessButton).frame(maxWidth: 200, alignment: .leading).accessibilityLabel("Conversation model filter")
                Menu {
                    Button("Agents & subagents") { roleFilter = "" }
                    Button("Primary agents") { roleFilter = "agent" }
                    Button("Subagents") { roleFilter = "subagent" }
                    Button("Automations") { roleFilter = "automation" }
                    Button("Review agents") { roleFilter = "review" }
                } label: { Label(roleName(roleFilter), systemImage: "person.2").lineLimit(1) }
                    .menuStyle(.borderlessButton).fixedSize().accessibilityLabel("Conversation role filter")
                Spacer(minLength: 0)
            }.font(StackType.caption).foregroundStyle(Palette.secondary)
        }.padding(.horizontal, 20).padding(.bottom, 15)
    }

    private var resultList: some View {
        ScrollViewReader { scroll in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 3) {
                    HStack {
                        Text(parsedQuery.query.isEmpty ? "ALL CONVERSATIONS" : "MATCHING CONVERSATIONS")
                        Spacer()
                        if loadedKey == searchKey { Text("\(total) found") }
                    }.font(.system(size: 12, weight: .semibold)).foregroundStyle(Palette.secondary)
                        .padding(.horizontal, 12).padding(.vertical, 12)
                    ForEach(rows) { reference in resultRow(reference).id(reference.id) }
                    if rows.isEmpty && loading {
                        VStack(spacing: 12) {
                            ProgressView(parsedQuery.query.isEmpty ? "Scanning connected conversations…" : "Searching connected conversations…")
                            Text("The first scan can take a moment. Your draft stays here.")
                                .font(StackType.caption).foregroundStyle(Palette.secondary)
                        }.frame(maxWidth: .infinity).padding(.vertical, 48)
                    }
                    if rows.isEmpty && !loading && error.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "bubble.left.and.bubble.right").font(.system(size: 30, weight: .light))
                            Text("No matching conversations").font(StackType.detail.weight(.medium))
                            Text("Search by topic, title, model or project, or choose another tool.")
                                .font(StackType.caption).multilineTextAlignment(.center)
                            if effectiveTool.isEmpty && parsedQuery.query.isEmpty {
                                Text("Available conversations from Codex, Claude Code, Cursor and OpenCode appear here after those tools have saved chats on this host.")
                                    .font(StackType.caption).multilineTextAlignment(.center).frame(maxWidth: 440)
                            }
                        }.foregroundStyle(Palette.secondary).frame(maxWidth: .infinity).padding(.vertical, 48)
                    }
                    if !error.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(error).font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
                            Button("Retry") { loadMoreTask = Task { await loadPage(offset: rows.isEmpty ? 0 : nextOffset ?? 0) } }
                                .buttonStyle(.plain).font(StackType.caption).foregroundStyle(Palette.link)
                        }.padding(12)
                    }
                    if let offset = nextOffset, loadedKey == searchKey {
                        Button {
                            loadMoreTask = Task { await loadPage(offset: offset) }
                        } label: {
                            HStack {
                                Spacer()
                                if loading { ProgressView().controlSize(.small) }
                                Text(loading ? "Loading conversations…" : "Load more conversations").font(StackType.detail)
                                Spacer()
                            }.padding(14)
                        }.buttonStyle(.plain).disabled(loading)
                    }
                }.padding(.horizontal, 10).padding(.bottom, 10)
            }.onChange(of: selectedID) { _, id in if let id { scroll.scrollTo(id, anchor: .center) } }
        }.frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func resultRow(_ reference: ConversationReference) -> some View {
        let attached = attachedIDs.contains(reference.id)
        return Button { select(reference) } label: {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: tools.first(where: { $0.0 == reference.agent })?.2 ?? "bubble.left")
                    .font(.system(size: 18)).foregroundStyle(Palette.link).frame(width: 36, height: 36)
                    .background(Palette.accent.opacity(0.08), in: RoundedRectangle(cornerRadius: 9))
                VStack(alignment: .leading, spacing: 5) {
                    HStack(spacing: 8) {
                        Text(reference.title).font(.system(size: 13, weight: .medium)).lineLimit(1)
                        Spacer(minLength: 2)
                        Text(reference.agentName).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.secondary)
                    }
                    Text(SpotlightSearchRules.excerpt(reference.excerpt, query: parsedQuery.query, limit: 180))
                        .font(.system(size: 12)).foregroundStyle(Palette.secondary).lineLimit(2)
                    Text(details(reference)).font(.system(size: 12)).foregroundStyle(.tertiary).lineLimit(1)
                }
                if attached { Image(systemName: "checkmark.circle.fill").foregroundStyle(Palette.link).accessibilityLabel("Already attached") }
                else if selectedID == reference.id { Image(systemName: "return").font(StackType.caption).foregroundStyle(Palette.secondary).padding(.top, 4) }
            }.padding(.horizontal, 12).padding(.vertical, 11)
                .background(selectedID == reference.id ? Palette.accent.opacity(0.12) : .clear, in: RoundedRectangle(cornerRadius: 10))
                .contentShape(Rectangle())
        }.buttonStyle(.plain).disabled(attached || attachedIDs.count >= 5)
            .accessibilityAddTraits(selectedID == reference.id ? .isSelected : [])
    }

    private var footer: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 14) {
                Text("↑ ↓  Navigate"); Text("↵  Attach"); Text("esc  Back to draft")
                Spacer()
                Text(attachedIDs.count >= 5 ? "Remove an attachment to add another" : "Attach up to 5 conversations")
            }.font(.system(size: 12)).foregroundStyle(Palette.secondary).padding(.horizontal, 24).padding(.vertical, 14)
        }
    }

    private func roleName(_ value: String) -> String {
        ["agent": "Primary agents", "subagent": "Subagents", "automation": "Automations", "review": "Review agents"][value] ?? "Agents & subagents"
    }

    private func details(_ reference: ConversationReference) -> String {
        let project = reference.workspaceName?.isEmpty == false ? reference.workspaceName : reference.projectPath.map(userFacingPath)
        return [project, reference.model, reference.role == "agent" ? nil : reference.roleName,
                reference.updatedAt.isEmpty ? nil : String(reference.updatedAt.prefix(10))]
            .compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")
    }

    private func move(_ direction: Int) {
        selectedID = SpotlightSearchRules.moving(selectedID, in: rows.filter { !attachedIDs.contains($0.id) }.map(\.id), by: direction)
    }

    private func select(_ reference: ConversationReference) {
        guard attachedIDs.count < 5, !attachedIDs.contains(reference.id), loadedKey == searchKey else { return }
        onSelect(reference)
    }

    private func loadPage(offset: Int) async {
        let key = searchKey, host = model.terminalHost
        guard let wid = model.selectedID else { loading = false; return }
        loading = true; error = ""
        defer { if key == searchKey { loading = false } }
        do {
            let result = try await model.terminalCall("conversation.references", ["workspaceId": wid,
                "query": parsedQuery.query, "agent": effectiveTool, "model": modelFilter, "role": roleFilter,
                "scope": scope, "context": String(context.suffix(600)), "limit": 80, "offset": offset,
                "excludeConversationId": model.conversation?.id ?? ""], host: host, as: ConversationSpotlightPage.self)
            guard !Task.isCancelled, key == searchKey else { return }
            if offset == 0 { references = result.references }
            else {
                let present = Set(references.map(\.id))
                references.append(contentsOf: result.references.filter { !present.contains($0.id) })
            }
            models = result.models ?? []; total = result.total; loadedKey = key
            let following = offset + result.references.count
            nextOffset = result.hasMore == false || result.references.isEmpty || following >= total ? nil : result.nextOffset ?? following
        } catch {
            if !Task.isCancelled, key == searchKey { self.error = error.localizedDescription }
        }
    }
}
