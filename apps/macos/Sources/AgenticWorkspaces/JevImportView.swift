import SwiftUI

private struct MigrationNote: Decodable, Identifiable {
    let id: String
    let title: String
    let body: String
    let status: String
    let revisionToken: String
}
private struct MigrationPage: Decodable {
    let rows: [MigrationNote]
    let nextOffset: Int
    let hasMore: Bool
}
private struct MigrationResult: Decodable {
    let evidenceId: String
    let status: String
    let warning: String
}
private struct ImportCapture: Decodable {
    let status: String
    let warning: String
    let nextSpan: Int
    let remainingSpans: Int
}

struct JevImportView: View {
    @Bindable var model: AppModel
    let providerAvailable: Bool
    @Environment(\.dismiss) private var dismiss
    @State private var page: MigrationPage?
    @State private var offset = 0
    @State private var busy = false
    @State private var message = ""
    @State private var migrated: Set<String> = []
    @State private var resume: [String: (String, Int)] = [:]

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Bring in imported memories").font(StackType.title)
            Text("Original notes stay intact. Each selection creates an evidence snapshot. With Jev enabled, proposed memories appear in the review queue.").foregroundStyle(Palette.secondary)
            if !message.isEmpty { Text(message).font(StackType.detail).textSelection(.enabled) }
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 16) {
                    if let page, page.rows.isEmpty { Text("No current imported memories on this page.").foregroundStyle(Palette.secondary) }
                    ForEach(page?.rows ?? []) { note in
                        VStack(alignment: .leading, spacing: 10) {
                            Text(note.title).font(StackType.heading)
                            Text("Original status: " + note.status).font(StackType.caption).foregroundStyle(Palette.secondary)
                            DisclosureGroup("Read source") { Text(note.body).textSelection(.enabled) }
                            Button(resume[note.id] != nil ? "Continue capture" : migrated.contains(note.id) ? "Evidence saved" : providerAvailable ? "Import and propose memories" : "Save as evidence") {
                                Task { await migrate(note) }
                            }.disabled(busy || migrated.contains(note.id) || !model.hostReady)
                        }.padding(14).frame(maxWidth: .infinity, alignment: .leading)
                            .background(Palette.surface, in: RoundedRectangle(cornerRadius: 8))
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.line, lineWidth: 0.5))
                    }
                }
            }
            HStack {
                Button("Previous") { offset = max(0, offset - 20); Task { await load() } }.disabled(offset == 0 || busy)
                Button("Next") { offset = page?.nextOffset ?? offset; Task { await load() } }.disabled(page?.hasMore != true || busy)
                Button("Refresh preview", systemImage: "arrow.clockwise") { Task { await load() } }.disabled(busy || !model.hostReady)
                if busy { ProgressView().controlSize(.small) }
                Spacer()
                Button("Done") { dismiss() }.disabled(busy)
            }
        }.padding(24).frame(width: 680, height: 600).interactiveDismissDisabled(busy)
        .task(id: model.handoverPreviewKey) { offset = 0; page = nil; migrated = []; resume = [:]; await load() }
    }

    private func load() async {
        guard let wid = model.selectedID, model.hostReady else { return }
        let key = model.handoverPreviewKey, host = model.terminalHost
        busy = true
        do {
            let result = try await model.terminalCall("memory.migration.preview", ["workspaceId": wid, "offset": offset], host: host, as: MigrationPage.self)
            guard !Task.isCancelled, key == model.handoverPreviewKey else { return }
            page = result; message = ""; busy = false
        } catch {
            guard key == model.handoverPreviewKey else { return }
            message = error.localizedDescription; busy = false
        }
    }

    private func migrate(_ note: MigrationNote) async {
        guard let wid = model.selectedID, model.hostReady else { return }
        let key = model.handoverPreviewKey, host = model.terminalHost
        busy = true; message = ""
        do {
            let evidence: String
            let start: Int
            if let pending = resume[note.id] {
                evidence = pending.0; start = pending.1
            } else {
                let result = try await model.terminalCall("memory.migration.apply", ["workspaceId": wid, "noteId": note.id, "revisionToken": note.revisionToken], host: host, as: MigrationResult.self)
                guard !Task.isCancelled, key == model.handoverPreviewKey else { return }
                evidence = result.evidenceId; start = 0
            }
            if providerAvailable {
                resume[note.id] = (evidence, start)
                let result = try await model.terminalCall("memory.capture", ["workspaceId": wid, "evidenceId": evidence, "startSpan": start], host: host, as: ImportCapture.self)
                guard !Task.isCancelled, key == model.handoverPreviewKey else { return }
                if result.remainingSpans > 0 {
                    resume[note.id] = (evidence, result.nextSpan)
                    message = result.warning + " Remaining passages: " + String(result.remainingSpans)
                } else {
                    resume.removeValue(forKey: note.id); migrated.insert(note.id)
                    message = "Capture complete. Proposed memories are ready for review."
                }
            } else {
                migrated.insert(note.id); message = "Evidence saved. Enable Jev and import again to propose memories."
            }
            busy = false
        } catch {
            guard key == model.handoverPreviewKey else { return }
            message = error.localizedDescription; busy = false
        }
    }
}
