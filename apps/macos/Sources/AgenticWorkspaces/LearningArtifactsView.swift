import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct LearningArtifact: Decodable, Identifiable, Sendable {
    let id: String; let path: String; let name: String; let kind: String; let type: String
    let size: Int; let status: String
    var displayStatus: String { status == "existing" ? "Existing file" : status.capitalized }
}
struct LearningArtifactSnapshot: Decodable, Sendable {
    let artifacts: [LearningArtifact]; let counts: [String: Int]; let issues: [String]
    let runs: [LearningArtifactRun]
}
struct LearningArtifactRun: Decodable, Identifiable, Sendable {
    let id: String; let task: String; let agent: String; let model: String; let status: String
    let reviewed: Bool; let eligible: Bool; let reason: String; let createdAt: String
}
struct LearningArtifactPreview: Decodable, Identifiable, Sendable {
    let workspaceId: String; let previewId: String; let kind: String; let text: String; let digest: String
    let recordCount: Int; let redactions: Int; let sourceCount: Int; let artifacts: [String]; let warnings: [String]
    var id: String { previewId }
}
struct LearningArtifactResult: Decodable, Sendable {
    let artifacts: [LearningArtifact]; let text: String; let digest: String; let kind: String
}
struct LearningArtifactFile: Decodable, Identifiable, Sendable {
    let text: String; let path: String; let digest: String; let type: String
    var id: String { path + digest }
}

struct LearningArtifactsView: View {
    @Bindable var model: AppModel
    @State private var snapshot: LearningArtifactSnapshot?
    @State private var selectedRuns: Set<String> = []
    @State private var preview: LearningArtifactPreview?
    @State private var file: LearningArtifactFile?
    @State private var busy = false
    @State private var error: String?
    @State private var message = ""
    @State private var trainingSource = "desktop"
    @State private var choseInitialSource = false
    @State private var snapshotLoading = false
    @State private var snapshotGeneration = 0
    @State private var runsExpanded = true
    static func preferredTrainingSource(_ snapshot: LearningArtifactSnapshot) -> String {
        !snapshot.runs.contains(where: \.eligible) && (snapshot.counts["approvedFileRuns"] ?? 0) > 0 ? "approved" : "desktop"
    }
    private var eligibleRuns: [LearningArtifactRun] { snapshot?.runs.filter(\.eligible) ?? [] }
    private var canTrain: Bool { trainingSource == "desktop" ? !selectedRuns.isEmpty : (snapshot?.counts["approvedFileRuns"] ?? 0) > 0 }
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 5) {
                    Text("Training, evaluation, and metrics").font(StackType.heading)
                    Text("Preview the inputs and files before generating an export.").font(StackType.detail).foregroundStyle(Palette.secondary)
                }
                Spacer()
                Button { Task { await reload() } } label: { Image(systemName: "arrow.clockwise") }.buttonStyle(.plain).help("Refresh learning artifacts").disabled(busy || snapshotLoading || !model.hostReady)
            }
            if snapshotLoading { ProgressView("Reading export inputs and files…").controlSize(.small) }
            if !model.hostReady { Text("Waiting for the host connection…").font(StackType.caption).foregroundStyle(Palette.secondary) }
            if let snapshot {
                Text("\(snapshot.counts["eligibleRuns"] ?? 0) eligible desktop runs · \(snapshot.counts["approvedFileRuns"] ?? 0) approved file records · \(snapshot.counts["metricsRecords"] ?? 0) metric records")
                    .font(StackType.caption).foregroundStyle(Palette.secondary).fixedSize(horizontal: false, vertical: true)
            }
            ForEach(snapshot?.issues ?? [], id: \.self) { issue in Text(issue).font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled) }
            Picker("Training inputs", selection: $trainingSource) {
                Text("Desktop runs · \(eligibleRuns.count)").tag("desktop")
                Text("Approved records · \(snapshot?.counts["approvedFileRuns"] ?? 0)").tag("approved")
            }.pickerStyle(.segmented).labelsHidden()
            if trainingSource == "approved" {
                Text("Uses \(snapshot?.counts["approvedFileRuns"] ?? 0) eligible records from .agent/flywheel/approved-runs.jsonl in this project.")
                    .font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
            } else {
            DisclosureGroup("Reviewed desktop runs · \(selectedRuns.count) selected", isExpanded: $runsExpanded) {
                if eligibleRuns.isEmpty {
                    Text("Review a completed run in Work before including it in training or evaluation exports.")
                        .font(StackType.caption).foregroundStyle(Palette.secondary).padding(.vertical, 8)
                } else {
                    VStack(alignment: .leading, spacing: 9) {
                        Text("Choose the reviewed runs to include in this export.")
                            .font(StackType.caption).foregroundStyle(Palette.secondary)
                        ForEach(eligibleRuns) { run in
                            Toggle(isOn: Binding(get: { selectedRuns.contains(run.id) }, set: { include in
                                if include { selectedRuns.insert(run.id) } else { selectedRuns.remove(run.id) }
                            })) {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(run.task).font(StackType.detail).lineLimit(2)
                                    Text([run.agent, run.model].filter { !$0.isEmpty }.joined(separator: " · ")).font(StackType.caption).foregroundStyle(Palette.secondary).lineLimit(1)
                                }
                            }.toggleStyle(.checkbox)
                        }
                    }.padding(.vertical, 9)
                }
            }.font(StackType.detail)
            }
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 12) { trainingButton; metricsButton }
                VStack(alignment: .leading, spacing: 10) { trainingButton; metricsButton }
            }.disabled(busy || snapshotLoading || snapshot == nil || !model.hostReady)
            if busy { ProgressView().controlSize(.small) }
            if let error { Text(error).font(StackType.detail).foregroundStyle(.red).textSelection(.enabled) }
            if !message.isEmpty { Text(message).font(StackType.detail).foregroundStyle(Palette.secondary).textSelection(.enabled) }
            if let artifacts = snapshot?.artifacts {
                Divider()
                Text("Export files · \(artifacts.count)").font(StackType.heading)
                if artifacts.isEmpty {
                    Text("No export files yet. Preview metrics or select reviewed training inputs to create an export. Existing files in this project's export folders will appear here too.")
                        .font(StackType.detail).foregroundStyle(Palette.secondary).fixedSize(horizontal: false, vertical: true)
                }
                ForEach(artifacts) { artifact in
                    HStack(spacing: 12) {
                        Image(systemName: artifact.kind == "training" ? "doc.text" : "chart.bar.doc.horizontal").foregroundStyle(Palette.link)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(artifact.name).font(StackType.detail.weight(.medium)).lineLimit(2)
                            if artifact.status == "existing" { Text(userFacingPath(artifact.path)).font(StackType.caption).foregroundStyle(Palette.secondary).lineLimit(2) }
                            Text("\(artifact.type) · \(ByteCountFormatter.string(fromByteCount: Int64(artifact.size), countStyle: .file)) · \(artifact.displayStatus)")
                                .font(StackType.caption).foregroundStyle(Palette.secondary)
                        }
                        Spacer()
                        Button("Open") { Task { await open(artifact) } }.disabled(busy)
                    }.padding(.vertical, 5)
                }
            }
        }
        .task(id: model.handoverPreviewKey) {
            selectedRuns = []; snapshot = nil; message = ""; error = nil; preview = nil; file = nil; choseInitialSource = false
            await reload()
        }
        .sheet(item: $preview) { preview in
            LearningArtifactApproval(model: model, preview: preview) { result in
                message = result.text; selectedRuns = []
                Task { await reload() }
            }
        }
        .sheet(item: $file) { file in LearningArtifactFileView(file: file) }
    }
    private var trainingButton: some View {
        Button("Preview training & evaluation", systemImage: "doc.text.magnifyingglass") { Task { await makePreview("training") } }
            .buttonStyle(.borderedProminent).tint(Palette.accent).disabled(!canTrain)
    }
    private var metricsButton: some View {
        Button("Preview metrics", systemImage: "chart.bar.doc.horizontal") { Task { await makePreview("metrics") } }
            .buttonStyle(.bordered)
    }
    private func reload() async {
        snapshotGeneration += 1
        let request = snapshotGeneration, key = model.handoverPreviewKey
        guard let wid = model.selectedID, model.hostReady else { snapshotLoading = false; return }
        let host = model.terminalHost
        snapshotLoading = true; error = nil
        defer { if request == snapshotGeneration { snapshotLoading = false } }
        do {
            let result = try await model.terminalCall("artifacts.snapshot", ["workspaceId": wid], host: host, as: LearningArtifactSnapshot.self)
            guard !Task.isCancelled, request == snapshotGeneration, model.handoverPreviewKey == key else { return }
            snapshot = result; error = nil
            selectedRuns.formIntersection(eligibleRuns.map(\.id))
            if !choseInitialSource { trainingSource = Self.preferredTrainingSource(result); choseInitialSource = true }
        } catch {
            guard !Task.isCancelled, request == snapshotGeneration, model.handoverPreviewKey == key else { return }
            self.error = error.localizedDescription
        }
    }
    private func makePreview(_ kind: String) async {
        guard !busy, let wid = model.selectedID else { return }
        busy = true; error = nil
        let host = model.terminalHost, key = model.handoverPreviewKey
        defer { busy = false }
        do {
            var params: [String: Any] = ["workspaceId": wid, "kind": kind, "window": "30d", "bucket": "day"]
            if kind == "training" && trainingSource == "desktop" { params["runIds"] = selectedRuns.sorted() }
            let result = try await model.terminalCall("artifacts.preview", params, host: host, as: LearningArtifactPreview.self)
            guard !Task.isCancelled, model.handoverPreviewKey == key else { return }
            preview = result
        } catch { if !Task.isCancelled, model.handoverPreviewKey == key { self.error = error.localizedDescription } }
    }
    private func open(_ artifact: LearningArtifact) async {
        guard !busy, let wid = model.selectedID else { return }
        busy = true; error = nil
        let host = model.terminalHost, key = model.handoverPreviewKey
        defer { busy = false }
        do {
            let result = try await model.terminalCall("artifacts.read", ["workspaceId": wid, "artifactId": artifact.id], host: host, as: LearningArtifactFile.self)
            guard !Task.isCancelled, model.handoverPreviewKey == key else { return }
            file = result
        } catch { if !Task.isCancelled, model.handoverPreviewKey == key { self.error = error.localizedDescription } }
    }
}

private struct LearningArtifactApproval: View {
    @Bindable var model: AppModel
    let preview: LearningArtifactPreview
    let onGenerated: (LearningArtifactResult) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var saving = false
    @State private var error: String?
    @State private var host = ""
    @State private var workspaceID = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(preview.kind == "training" ? "Review training & evaluation export" : "Review metrics export").font(.title2.weight(.semibold))
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Inputs").font(StackType.heading)
                    Text("\(preview.recordCount) records · \(preview.sourceCount) sources · \(preview.redactions) redactions").font(StackType.detail)
                    Text(preview.text).font(.system(size: 12, design: .monospaced)).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading).padding(10)
                        .background(Palette.surface, in: RoundedRectangle(cornerRadius: 8))
                    Divider()
                    Text("Files to generate").font(StackType.heading)
                    ForEach(preview.artifacts, id: \.self) { name in Text(userFacingPath(name)).font(StackType.caption).textSelection(.enabled) }
                    ForEach(preview.warnings, id: \.self) { warning in Text(warning).font(StackType.caption).foregroundStyle(Palette.secondary) }
                    Text("Generate only after reviewing these inputs. If they change, create a fresh preview.").font(StackType.caption).foregroundStyle(Palette.secondary)
                }
            }.frame(maxHeight: 350)
            if let error { Text(error).font(StackType.caption).foregroundStyle(.red).textSelection(.enabled) }
            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction).disabled(saving)
                Spacer()
                if saving { ProgressView().controlSize(.small) }
                Button("Approve & generate") { Task { await generate() } }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(saving)
            }
        }.padding(26).frame(width: 540).interactiveDismissDisabled(saving)
            .onAppear { host = model.terminalHost; workspaceID = preview.workspaceId }
    }
    private func generate() async {
        guard !saving else { return }
        saving = true; error = nil
        defer { saving = false }
        do {
            let result = try await model.terminalCall("artifacts.generate", ["workspaceId": workspaceID, "previewId": preview.id, "approved": true], host: host, as: LearningArtifactResult.self)
            guard model.selectedID == workspaceID, model.terminalHost == host else { dismiss(); return }
            onGenerated(result); dismiss()
        } catch { self.error = error.localizedDescription }
    }
}

private struct LearningArtifactFileView: View {
    let file: LearningArtifactFile
    @Environment(\.dismiss) private var dismiss
    @State private var error: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(URL(fileURLWithPath: file.path).lastPathComponent).font(.title2.weight(.semibold))
            Text(userFacingPath(file.path)).font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
            ScrollView {
                Text(file.text).font(.system(size: 12, design: .monospaced)).textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(10)
            }.frame(height: 360).background(Palette.surface, in: RoundedRectangle(cornerRadius: 8))
            if let error { Text(error).font(StackType.caption).foregroundStyle(.red) }
            HStack {
                Button("Close") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button("Save a copy…", systemImage: "square.and.arrow.down") { save() }.buttonStyle(.borderedProminent).tint(Palette.accent)
            }
        }.padding(24).frame(width: DesktopSizing.sheetWidth(660))
    }
    private func save() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = URL(fileURLWithPath: file.path).lastPathComponent
        let write: (NSApplication.ModalResponse) -> Void = { response in
            guard response == .OK, let url = panel.url else { return }
            do { try file.text.write(to: url, atomically: true, encoding: .utf8) }
            catch { self.error = error.localizedDescription }
        }
        if let window = NSApp.keyWindow { panel.beginSheetModal(for: window, completionHandler: write) }
        else { panel.begin(completionHandler: write) }
    }
}
