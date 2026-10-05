import SwiftUI

struct ImportedLibrarySource: Decodable, Identifiable, Sendable {
    let id: String
    let title: String
    let path: String
    let provider: String
    let digest: String
    let noteCount: Int
    let importedAt: String
}

struct ImportedLibraryPage: Decodable, Sendable {
    let sources: [ImportedLibrarySource]
    let total: Int
    let hasMore: Bool
    let nextOffset: Int?
}

struct ImportedLibrarySourcePage: Decodable, Sendable {
    let source: ImportedLibrarySource
    let notes: [GraphNote]
    let total: Int
    let hasMore: Bool
    let nextOffset: Int?
}

private struct ImportedSourceSelection: Identifiable {
    let source: ImportedLibrarySource
    let workspaceID: String
    let host: String
    let targetKey: String
    var id: String { targetKey + source.id }
}

/// A view of stored imports. Browsing does not copy, approve, or reimport their content.
struct ImportedSourceLibrary: View {
    @Bindable var model: AppModel
    var kind = "all"
    var onCount: (Int) -> Void = { _ in }
    @State private var query = ""
    @State private var provider = ""
    @State private var sources: [ImportedLibrarySource] = []
    @State private var total: Int?
    @State private var nextOffset: Int?
    @State private var loading = false
    @State private var error: String?
    @State private var generation = 0
    @State private var selection: ImportedSourceSelection?
    private var requestKey: String { model.handoverPreviewKey + "|" + kind + "|" + provider + "|" + query }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text(kind == "lessons" ? "Imported lesson files" : "Imported sources").font(StackType.heading)
                Text(kind == "lessons"
                     ? "Original lesson and learning files from connected tools. Their text and review status remain separate from this project's lesson queue."
                     : "Read the original stored material behind your graph, including its source and review status.")
                    .font(StackType.detail).foregroundStyle(Palette.secondary)
            }
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 12) { searchField; providerPicker }
                VStack(alignment: .leading, spacing: 10) { searchField; providerPicker }
            }
            HStack {
                if let total { Text("\(sources.count) of \(total) source files").font(StackType.caption).foregroundStyle(Palette.secondary) }
                if loading { ProgressView().controlSize(.small) }
                Spacer()
                Button("Refresh", systemImage: "arrow.clockwise") { Task { await load(reset: true) } }
                    .font(StackType.caption).buttonStyle(.plain).disabled(loading || !model.hostReady)
            }
            if let error { Text(error).font(StackType.detail).foregroundStyle(.red).textSelection(.enabled) }
            if !model.hostReady {
                Text("Waiting for the host connection…").font(StackType.detail).foregroundStyle(Palette.secondary)
            } else if sources.isEmpty && !loading && error == nil {
                Text(kind == "lessons"
                     ? "No imported lesson files match. Lessons you stage or accept in this project appear above."
                     : "No imported sources match. Import memories from Browse or try another search.")
                    .font(StackType.detail).foregroundStyle(Palette.secondary).padding(.vertical, 16)
            }
            LazyVStack(alignment: .leading, spacing: 0) {
                ForEach(sources) { source in
                    Button {
                        guard let wid = model.selectedID else { return }
                        selection = ImportedSourceSelection(source: source, workspaceID: wid, host: model.terminalHost, targetKey: model.handoverPreviewKey)
                    } label: {
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "doc.text").font(.title3).foregroundStyle(Palette.link).frame(width: 22)
                            VStack(alignment: .leading, spacing: 5) {
                                Text(source.title).font(StackType.detail.weight(.semibold)).foregroundStyle(.primary).lineLimit(2)
                                Text("\(source.provider) · \(source.noteCount) stored notes").font(StackType.caption).foregroundStyle(Palette.secondary)
                                Text(userFacingPath(source.path)).font(StackType.caption).foregroundStyle(Palette.secondary).lineLimit(2)
                            }
                            Spacer(minLength: 8)
                            Image(systemName: "chevron.right").font(StackType.caption).foregroundStyle(Palette.secondary)
                        }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 15).contentShape(Rectangle())
                    }.buttonStyle(.plain).accessibilityLabel("Read imported source \(source.title)")
                    Divider()
                }
            }
            if nextOffset != nil {
                Button("Load more source files") { Task { await load(reset: false) } }
                    .buttonStyle(.bordered).disabled(loading)
            }
        }
        .task(id: requestKey) { await load(reset: true) }
        .onChange(of: model.handoverPreviewKey) { _, _ in selection = nil }
        .sheet(item: $selection) { selected in
            ImportedSourceDetail(model: model, source: selected.source, workspaceID: selected.workspaceID,
                                 host: selected.host, targetKey: selected.targetKey)
        }
    }

    private var searchField: some View {
        TextField("Search source files and stored text", text: $query).textFieldStyle(.roundedBorder)
            .frame(minWidth: 190).accessibilityLabel("Search imported sources")
            .onChange(of: query) { _, value in if value.count > 300 { query = String(value.prefix(300)) } }
    }
    private var providerPicker: some View {
        Picker("Tool", selection: $provider) {
            Text("All tools").tag("")
            Text("Codex memories").tag("codex")
            Text("Claude memories").tag("claude")
            Text("Codex conversations").tag("codex-session")
            Text("Claude conversations").tag("claude-session")
            Text("Cursor conversations").tag("cursor-session")
            Text("OpenCode conversations").tag("opencode-session")
            Text("Brain").tag("brain")
            Text("Agentic Stack").tag("stack")
            Text("Selected folder").tag("folder")
        }.labelsHidden().frame(width: 150).accessibilityLabel("Imported source tool")
    }
    private func load(reset: Bool) async {
        guard reset || (!loading && nextOffset != nil) else { return }
        generation += 1
        let current = generation, key = requestKey
        if reset { sources = []; total = nil; nextOffset = nil; error = nil }
        guard let wid = model.selectedID, model.hostReady else { loading = false; return }
        let host = model.terminalHost, offset = reset ? 0 : (nextOffset ?? sources.count)
        loading = true
        defer { if current == generation { loading = false } }
        do {
            if reset && !query.isEmpty { try await Task.sleep(for: .milliseconds(180)) }
            let result = try await model.terminalCall("knowledge.library", ["workspaceId": wid, "query": query,
                "provider": provider, "kind": kind, "offset": offset, "limit": 80], host: host, as: ImportedLibraryPage.self)
            guard !Task.isCancelled, current == generation, key == requestKey else { return }
            let existing = Set(sources.map(\.id))
            sources += result.sources.filter { !existing.contains($0.id) }
            total = result.total
            nextOffset = result.hasMore ? (result.nextOffset ?? offset + result.sources.count) : nil
            error = nil
            if query.isEmpty && provider.isEmpty { onCount(result.total) }
        } catch {
            guard !Task.isCancelled, current == generation, key == requestKey else { return }
            self.error = error.localizedDescription
        }
    }
}

private struct ImportedSourceDetail: View {
    @Bindable var model: AppModel
    let source: ImportedLibrarySource
    let workspaceID: String
    let host: String
    let targetKey: String
    @Environment(\.dismiss) private var dismiss
    @State private var notes: [GraphNote] = []
    @State private var total: Int?
    @State private var nextOffset: Int?
    @State private var loading = false
    @State private var error: String?
    @State private var expanded: Set<String> = []

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(source.title).font(.title2.weight(.semibold)).lineLimit(3)
            Text("\(source.provider) · Imported \(source.importedAt)").font(StackType.caption).foregroundStyle(Palette.secondary)
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    Text(userFacingPath(source.path)).font(StackType.caption).textSelection(.enabled)
                    if let total { Text("\(notes.count) of \(total) stored notes").font(StackType.detail.weight(.medium)) }
                    ForEach(notes) { note in
                        VStack(alignment: .leading, spacing: 10) {
                            HStack(alignment: .top) {
                                Text(note.displayTitle).font(StackType.heading).textSelection(.enabled)
                                Spacer()
                                StatusLabel(title: (note.status ?? "reference").capitalized)
                            }
                            DisclosureGroup("Stored text", isExpanded: Binding(get: { expanded.contains(note.id) }, set: {
                                if $0 { expanded.insert(note.id) } else { expanded.remove(note.id) }
                            })) {
                                Text(note.body).font(.system(size: 12, design: .monospaced)).lineSpacing(4).textSelection(.enabled)
                                    .frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
                            }
                            ForEach(note.origins, id: \.self) { origin in
                                Text("\(origin.provider) · \(userFacingPath(origin.path)):\(origin.line)")
                                    .font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
                            }
                            DisclosureGroup("Evidence details") {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("Note ID · " + note.id)
                                    Text("Source ID · " + source.id)
                                    Text("Source SHA-256 · " + source.digest)
                                }.font(.system(size: 12, design: .monospaced)).textSelection(.enabled)
                            }.font(StackType.caption)
                            if let review = note.review {
                                if let reason = review.reason { Text(reason).font(StackType.detail).textSelection(.enabled) }
                                if let replacement = review.supersededBy { Text("Replaced by note \(replacement)").font(StackType.caption).textSelection(.enabled) }
                                if let history = review.history, !history.isEmpty {
                                    DisclosureGroup("Review history") {
                                        ForEach(Array(history.enumerated()), id: \.offset) { _, event in
                                            Text("\(event.updatedAt) · \(event.status) · \(event.reason)").font(StackType.caption).textSelection(.enabled)
                                        }
                                    }
                                }
                            }
                        }.padding(16).background(Palette.surface, in: RoundedRectangle(cornerRadius: 10))
                    }
                    if loading { ProgressView("Reading stored notes…") }
                    if let error { Text(error).font(StackType.detail).foregroundStyle(.red).textSelection(.enabled) }
                    if nextOffset != nil { Button("Load more stored notes") { Task { await load() } }.disabled(loading) }
                }.frame(maxWidth: .infinity, alignment: .leading)
            }
            HStack { Spacer(); Button("Close") { dismiss() }.keyboardShortcut(.cancelAction) }
        }.padding(24).frame(width: DesktopSizing.sheetWidth(680), height: DesktopSizing.sheetHeight(660))
            .task { await load() }
            .onChange(of: model.handoverPreviewKey) { _, key in if key != targetKey { dismiss() } }
    }
    private func load() async {
        guard !loading, model.handoverPreviewKey == targetKey, model.hostReady else { return }
        let offset = nextOffset ?? notes.count
        loading = true
        defer { loading = false }
        do {
            let result = try await model.terminalCall("knowledge.source", ["workspaceId": workspaceID,
                "sourceId": source.id, "offset": offset, "limit": 40], host: host, as: ImportedLibrarySourcePage.self)
            guard !Task.isCancelled, model.handoverPreviewKey == targetKey else { return }
            guard result.source.id == source.id, result.source.digest == source.digest else {
                nextOffset = nil
                error = "This source changed. Close this view and refresh the source list before reading it again."
                return
            }
            let existing = Set(notes.map(\.id))
            notes += result.notes.filter { !existing.contains($0.id) }
            total = result.total
            nextOffset = result.hasMore ? (result.nextOffset ?? offset + result.notes.count) : nil
            if expanded.isEmpty, let first = result.notes.first { expanded.insert(first.id) }
            error = nil
        } catch {
            guard !Task.isCancelled, model.handoverPreviewKey == targetKey else { return }
            self.error = error.localizedDescription
        }
    }
}
