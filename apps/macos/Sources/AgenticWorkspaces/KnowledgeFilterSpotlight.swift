import SwiftUI

struct KnowledgeFilterValues: Equatable {
    var query = ""
    var provider = ""
    var topic = ""
    var includeActivity = false
}

struct KnowledgeFilterRequest: Identifiable {
    let id: UUID
    let ownerID: UUID
    let workspaceID: String
    let host: String
    let targetKey: String
    let values: KnowledgeFilterValues
    let sources: [GraphCount]
    let onChange: @MainActor (KnowledgeFilterValues) -> Void
}

struct KnowledgeFacetPage: Decodable, Sendable {
    let topics: [GraphCount]
    let sources: [GraphCount]
    let total: Int
    let hasMore: Bool
    let nextOffset: Int?
}

struct KnowledgeFacetRow: Identifiable {
    let kind: String
    let value: String
    let title: String
    let count: Int
    var id: String { kind + ":" + value }
}

enum KnowledgeFilterSearchRules {
    static func countLabel(_ count: Int, singular: String) -> String {
        "\(count) \(singular)\(count == 1 ? "" : "s")"
    }
    static func resultHeight(rowCount: Int, loading: Bool, hasError: Bool, hasActiveFilters: Bool) -> CGFloat {
        let rowsHeight = CGFloat(min(max(rowCount, 2), 8)) * 44 + 20
        let statusHeight: CGFloat = hasError ? 160 : (loading ? 112 : 108)
        return min(max(rowsHeight, statusHeight), hasActiveFilters ? 320 : 352)
    }
    static func sourceTitle(_ id: String) -> String {
        ["codex": "Codex", "claude": "Claude Code", "stack": "Agentic Stack", "brain": "Brain", "folder": "Folder",
         "codex-session": "Codex conversations", "claude-session": "Claude Code conversations",
         "cursor": "Cursor", "cursor-session": "Cursor conversations", "opencode": "OpenCode",
         "opencode-session": "OpenCode conversations"][id] ?? id
    }
    static func sourceRows(_ sources: [GraphCount], query: String) -> [KnowledgeFacetRow] {
        sources.compactMap { source -> (KnowledgeFacetRow, Int)? in
            let title = sourceTitle(source.id)
            guard let score = SpotlightSearchRules.score(query, title: title, detail: source.id) else { return nil }
            return (KnowledgeFacetRow(kind: "source", value: source.id, title: title, count: source.count), score)
        }.sorted {
            $0.1 == $1.1 ? ($0.0.count == $1.0.count ? $0.0.title < $1.0.title : $0.0.count > $1.0.count) : $0.1 > $1.1
        }.map(\.0)
    }
    static func selecting(_ row: KnowledgeFacetRow, in values: KnowledgeFilterValues) -> KnowledgeFilterValues {
        var result = values
        if row.kind == "source" { result.provider = row.value }
        else { result.topic = row.value }
        return result
    }
}

struct KnowledgeFilterSpotlight: View {
    @Bindable var model: AppModel
    let request: KnowledgeFilterRequest
    @State private var search = ""
    @State private var category = "all"
    @State private var filters: KnowledgeFilterValues
    @State private var topics: [GraphCount] = []
    @State private var sources: [GraphCount]
    @State private var total = 0
    @State private var nextOffset: Int?
    @State private var selectedID: String?
    @State private var loading = false
    @State private var error: String?
    @State private var requestGeneration = 0
    @State private var focusRequest = 0
    @State private var moreTask: Task<Void, Never>?
    private var searchKey: String { [request.targetKey, search, filters.provider, filters.query, String(filters.includeActivity)].joined(separator: "|") }
    private var isCurrent: Bool { model.knowledgeFilterRequest?.id == request.id && model.handoverPreviewKey == request.targetKey && model.hostReady }
    private var hasActiveFilters: Bool { !filters.topic.isEmpty || !filters.provider.isEmpty || !filters.query.isEmpty }
    private var rows: [KnowledgeFacetRow] {
        let sourceRows = category == "topics" ? [] : KnowledgeFilterSearchRules.sourceRows(sources, query: search)
        let topicRows = category == "sources" ? [] : topics.map { KnowledgeFacetRow(kind: "topic", value: $0.id, title: $0.id, count: $0.count) }
        return sourceRows + topicRows
    }

    init(model: AppModel, request: KnowledgeFilterRequest) {
        self.model = model
        self.request = request
        _filters = State(initialValue: request.values)
        _sources = State(initialValue: request.sources)
    }

    var body: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 14) {
                    Image(systemName: "magnifyingglass").font(.system(size: 23, weight: .light)).foregroundStyle(Palette.secondary)
                    NativeSpotlightField(text: $search, placeholder: "Find a topic or source…", accessibilityName: "Search topics and sources", focusRequest: focusRequest,
                        onSubmit: { if let row = rows.first(where: { $0.id == selectedID }) { select(row) } },
                        onMove: { selectedID = SpotlightSearchRules.moving(selectedID, in: rows.map(\.id), by: $0) },
                        onEscape: close, canFocus: { isCurrent && !model.showingCommandPalette && model.conversationAttachmentRequest == nil })
                        .frame(height: 30)
                    Button(action: close) { Text("esc").font(StackType.caption.monospaced()).foregroundStyle(Palette.secondary).padding(5).background(.primary.opacity(0.05), in: RoundedRectangle(cornerRadius: 5)) }
                        .buttonStyle(.plain).accessibilityLabel("Close topic and source search")
                }
                HStack(spacing: 8) {
                    categoryButton("All", value: "all")
                    categoryButton("Topics", value: "topics")
                    categoryButton("Sources", value: "sources")
                    Spacer()
                    if loading { ProgressView().controlSize(.small) }
                }
                if hasActiveFilters {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            if !filters.topic.isEmpty { chip(filters.topic, symbol: "number") { filters.topic = ""; apply() } }
                            if !filters.provider.isEmpty { chip(KnowledgeFilterSearchRules.sourceTitle(filters.provider), symbol: "doc.text") { filters.provider = ""; apply() } }
                            if !filters.query.isEmpty { chip(filters.query, symbol: "magnifyingglass") { filters.query = ""; apply() } }
                        }
                    }
                }
            }.padding(.horizontal, 22).padding(.top, 20).padding(.bottom, 16)
            Divider()
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 2) {
                        if let error {
                            VStack(alignment: .leading, spacing: 10) {
                                Text(error).font(StackType.detail).foregroundStyle(.red).textSelection(.enabled)
                                Button("Retry topic search") { Task { await load(reset: true) } }.buttonStyle(.bordered)
                            }.padding(14)
                        }
                        if rows.isEmpty && !loading && error == nil {
                            Text("No matching topics or sources.").font(StackType.detail).foregroundStyle(Palette.secondary).padding(24)
                        }
                        ForEach(rows) { row in
                            Button { select(row) } label: {
                                HStack(spacing: 12) {
                                    Image(systemName: row.kind == "topic" ? "number" : "doc.text").frame(width: 20).foregroundStyle(Palette.link)
                                    Text(row.title).font(StackType.detail).lineLimit(1)
                                    Spacer(minLength: 8)
                                    Text(KnowledgeFilterSearchRules.countLabel(row.count, singular: row.kind == "topic" ? "note" : "file")).font(StackType.caption).foregroundStyle(Palette.secondary)
                                    if (row.kind == "topic" ? filters.topic : filters.provider) == row.value {
                                        Image(systemName: "checkmark").font(StackType.caption.weight(.semibold)).foregroundStyle(Palette.link)
                                    }
                                }.padding(.horizontal, 12).frame(height: 42).contentShape(Rectangle())
                                    .background(selectedID == row.id ? Palette.accent.opacity(0.12) : .clear, in: RoundedRectangle(cornerRadius: 8))
                            }.buttonStyle(.plain).id(row.id).accessibilityLabel("\(row.kind == "topic" ? "Topic" : "Source") \(row.title), \(KnowledgeFilterSearchRules.countLabel(row.count, singular: row.kind == "topic" ? "note" : "file"))")
                        }
                        if category != "sources", nextOffset != nil {
                            Button("Load more topics") { moreTask?.cancel(); moreTask = Task { await load(reset: false) } }
                                .buttonStyle(.plain).font(StackType.detail).foregroundStyle(Palette.link).padding(12).disabled(loading)
                        }
                    }.padding(10)
                }.frame(height: KnowledgeFilterSearchRules.resultHeight(rowCount: rows.count, loading: loading, hasError: error != nil, hasActiveFilters: hasActiveFilters))
                    .onChange(of: selectedID) { _, id in if let id { proxy.scrollTo(id, anchor: .center) } }
            }
            Divider()
            HStack(spacing: 12) {
                Toggle("Include routine activity", isOn: Binding(get: { filters.includeActivity }, set: { filters.includeActivity = $0; apply() }))
                    .toggleStyle(.checkbox).font(StackType.caption)
                Spacer(minLength: 8)
                Text(category == "sources" ? "↑↓ choose · ↵ apply" : "\(KnowledgeFilterSearchRules.countLabel(total, singular: "topic")) · ↑↓ choose · ↵ apply").font(StackType.caption).foregroundStyle(Palette.secondary)
            }.padding(.horizontal, 22).padding(.vertical, 13)
        }
        .frame(maxWidth: 680, maxHeight: 550)
        .fixedSize(horizontal: false, vertical: true)
        .background { StackFrostedSurface().clipShape(RoundedRectangle(cornerRadius: 20)) }
        .overlay { RoundedRectangle(cornerRadius: 20).strokeBorder(.primary.opacity(0.1)) }
        .clipShape(RoundedRectangle(cornerRadius: 20))
        .shadow(color: .black.opacity(0.22), radius: 30, y: 14)
        .task(id: searchKey) {
            moreTask?.cancel()
            await load(reset: true)
        }
        .onChange(of: rows.map(\.id), initial: true) { _, ids in if !ids.contains(selectedID ?? "") { selectedID = ids.first } }
        .onChange(of: search) { _, value in if value.count > 300 { search = String(value.prefix(300)) } }
        .onExitCommand(perform: close)
        .onDisappear { moreTask?.cancel() }
        .accessibilityIdentifier("knowledge-filter-spotlight")
    }
    private func categoryButton(_ title: String, value: String) -> some View {
        Button { category = value; focusRequest += 1 } label: {
            Text(title).font(StackType.detail.weight(category == value ? .semibold : .regular)).padding(.horizontal, 12).padding(.vertical, 6)
                .background(category == value ? Palette.accent.opacity(0.13) : .clear, in: Capsule())
        }.buttonStyle(.plain)
    }
    private func chip(_ title: String, symbol: String, clear: @escaping () -> Void) -> some View {
        Button { clear(); focusRequest += 1 } label: {
            HStack(spacing: 6) {
                Label(title, systemImage: symbol).lineLimit(1).truncationMode(.middle).frame(maxWidth: 220)
                Image(systemName: "xmark").font(.system(size: 8, weight: .bold))
            }
        }.font(StackType.caption).buttonStyle(.bordered).controlSize(.small).accessibilityLabel("Clear filter \(title)").help(title)
    }
    private func apply() {
        guard isCurrent else { return }
        request.onChange(filters)
    }
    private func select(_ row: KnowledgeFacetRow) {
        guard isCurrent else { return }
        filters = KnowledgeFilterSearchRules.selecting(row, in: filters)
        apply(); close()
    }
    private func close() {
        guard model.knowledgeFilterRequest?.id == request.id else { return }
        model.knowledgeFilterRequest = nil
    }
    private func load(reset: Bool) async {
        guard isCurrent, reset || (!loading && nextOffset != nil) else { return }
        requestGeneration += 1
        let generation = requestGeneration, key = searchKey, offset = reset ? 0 : (nextOffset ?? topics.count)
        let labelQuery = search, provider = filters.provider, contentQuery = filters.query, routine = filters.includeActivity
        if reset { topics = []; nextOffset = nil; error = nil }
        loading = true
        defer { if generation == requestGeneration { loading = false } }
        do {
            if reset && !labelQuery.isEmpty { try await Task.sleep(for: .milliseconds(150)) }
            let page = try await model.terminalCall("knowledge.facets", ["workspaceId": request.workspaceID,
                "query": labelQuery, "provider": provider, "contentQuery": contentQuery, "includeActivity": routine,
                "offset": offset, "limit": 80], host: request.host, as: KnowledgeFacetPage.self)
            guard !Task.isCancelled, isCurrent, generation == requestGeneration, key == searchKey else { return }
            let existing = Set(topics.map(\.id))
            topics += page.topics.filter { !existing.contains($0.id) }
            sources = page.sources; total = page.total
            nextOffset = page.hasMore ? (page.nextOffset ?? offset + page.topics.count) : nil
            error = nil
        } catch {
            guard !Task.isCancelled, isCurrent, generation == requestGeneration, key == searchKey else { return }
            self.error = "Topic search is unavailable. " + error.localizedDescription
        }
    }
}
