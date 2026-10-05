import AppKit
import SwiftUI

struct LoopManagementView: View {
    @Bindable var model: AppModel
    @State private var snapshot: LoopSnapshot?
    @State private var message = ""
    @State private var selectedContract: LoopContract?
    @State private var resume: LoopRun?
    @State private var configuring: LoopContract?
    @State private var editingPath: String?
    @State private var fetching = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HStack {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Verified loops").font(StackType.title)
                        Text("Run a repeatable cycle: make a change, verify it, and review the result. Project limits and permissions apply.").foregroundStyle(Palette.secondary)
                    }
                    Spacer()
                    Button("Refresh", systemImage: "arrow.clockwise") { Task { await reload() } }.disabled(fetching)
                }
                if let snapshot {
                    if let accessError = snapshot.projectAccessError, !accessError.isEmpty {
                        HStack(alignment: .center, spacing: 14) {
                            Image(systemName: "folder.badge.questionmark").font(.title2).foregroundStyle(Palette.link)
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Reconnect project folder").font(StackType.heading)
                                Text(accessError).font(StackType.detail).foregroundStyle(Palette.secondary)
                            }
                            Spacer()
                            Button("Choose folder…") { model.chooseProject() }.buttonStyle(.borderedProminent).tint(Palette.accent)
                        }
                        .padding(16)
                        .background(Palette.surface, in: RoundedRectangle(cornerRadius: 12))
                    }
                    if snapshot.contracts.isEmpty {
                        if snapshot.projectAccessError?.isEmpty != false {
                            Button("Initialize loop contracts") { Task { await action("stack.command", ["operation": "loop-init"]) } }.buttonStyle(.borderedProminent).tint(Palette.accent)
                        }
                    }
                    ForEach(snapshot.contracts) { contract in
                        VStack(alignment: .leading, spacing: 14) {
                            HStack {
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(contract.name).font(StackType.heading)
                                    Text(contract.description).font(StackType.detail).foregroundStyle(Palette.secondary)
                                }
                                Spacer()
                                StatusLabel(title: contract.error.isEmpty ? contract.autonomy : "Invalid contract")
                            }
                            if !contract.error.isEmpty { Text(contract.error).font(StackType.caption).foregroundStyle(Palette.link) }
                            HStack {
                                Button("Run loop", systemImage: "play.fill") { resume = nil; selectedContract = contract }
                                    .buttonStyle(.borderedProminent).tint(Palette.accent).disabled(!contract.error.isEmpty || snapshot.runs.contains(where: \.isActive))
                                Button("Connect agents") { configuring = contract }.disabled(!contract.error.isEmpty)
                                Button("Edit contract") { editingPath = ".agent/loops/\(contract.id).json" }
                            }
                            DisclosureGroup("Limits and capabilities") {
                                Text(contract.limits).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                                Text(contract.capabilities.joined(separator: ", ")).font(StackType.caption)
                            }
                        }.padding(20).background(Palette.surface, in: RoundedRectangle(cornerRadius: 12))
                    }
                    HStack {
                        Button("Edit agent profiles") { editingPath = ".agent/loops/harnesses.json" }
                        Button("Edit budget") { editingPath = ".agent/loops/budget.json" }
                        Button("Edit constraints") { editingPath = ".agent/loops/constraints.json" }
                    }.disabled(snapshot.contracts.isEmpty)
                    Divider()
                    Text("Loop history").font(StackType.heading)
                    if snapshot.runs.isEmpty { Text("Run a loop to see its attempts, verification and worktree here.").foregroundStyle(Palette.secondary) }
                    ForEach(snapshot.runs) { run in
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(run.name).font(StackType.heading)
                                    Text(run.task).font(StackType.detail).lineLimit(3)
                                    Text("\(run.attempts) attempts · \(run.phase.isEmpty ? "Not started" : run.phase)").font(StackType.caption).foregroundStyle(Palette.secondary)
                                }
                                Spacer()
                                StatusLabel(title: run.status.replacingOccurrences(of: "_", with: " ").capitalized, active: run.isActive)
                                if run.isActive {
                                    Button("Stop", role: .destructive) { Task { await action("loops.cancel", ["runId": run.id]) } }
                                        .disabled(run.status == "cancelling")
                                } else if run.canResume, let contract = snapshot.contracts.first(where: { $0.name == run.name }) {
                                    Button("Resume…") { resume = run; selectedContract = contract }
                                }
                            }
                            if !run.error.isEmpty { Text(run.error).font(StackType.detail).foregroundStyle(Palette.link) }
                            if !run.worktree.isEmpty {
                                HStack {
                                    Text(run.worktree).font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
                                    if !model.isRemote { Button("Open worktree") { NSWorkspace.shared.open(URL(fileURLWithPath: run.worktree)) } }
                                }
                            }
                            DisclosureGroup("Attempts and verification") {
                                Text(run.detail).font(.system(.caption, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                            }
                            Divider()
                        }
                    }
                } else { ProgressView("Reading loop contracts…") }
                if !message.isEmpty { Text(message).font(StackType.detail).textSelection(.enabled) }
            }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
        }
        .task(id: model.selectedID) {
            snapshot = nil
            await reload()
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(snapshot?.runs.contains(where: \.isActive) == true ? 2 : 30))
                guard !Task.isCancelled else { break }
                await reload()
            }
        }
        .sheet(item: $selectedContract, onDismiss: { Task { await reload() } }) { contract in
            LoopRunSheet(model: model, contract: contract, resuming: resume)
        }
        .sheet(item: $configuring, onDismiss: { Task { await reload() } }) { contract in
            LoopAgentSheet(model: model, contract: contract, digest: snapshot?.profileDigest ?? "")
        }
        .sheet(isPresented: Binding(get: { editingPath != nil }, set: { if !$0 { editingPath = nil } }), onDismiss: { Task { await reload() } }) {
            if let path = editingPath { StackFileEditor(model: model, path: path) }
        }
    }
    private func reload() async {
        guard let wid = model.selectedID, !fetching else { return }
        fetching = true
        defer { fetching = false }
        do {
            let state: LoopSnapshot = try await model.call("loops.snapshot", ["workspaceId": wid], as: LoopSnapshot.self)
            if wid == model.selectedID { snapshot = state }
        } catch { message = error.localizedDescription }
    }
    private func action(_ method: String, _ parameters: [String: String]) async {
        guard let wid = model.selectedID else { return }
        var values: [String: Any] = parameters; values["workspaceId"] = wid
        do { let result: TextResult = try await model.call(method, values, as: TextResult.self); message = result.text; await reload() }
        catch { message = error.localizedDescription }
    }
}

struct LoopRunSheet: View {
    @Bindable var model: AppModel
    let contract: LoopContract
    let resuming: LoopRun?
    @Environment(\.dismiss) private var dismiss
    @State private var task = ""
    @State private var approved = false
    @State private var busy = false
    @State private var message = ""
    @State private var wid: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(resuming == nil ? "Run \(contract.name)" : "Resume \(contract.name)").font(.title2.weight(.semibold))
            Text("\(contract.autonomy) · executor: \(contract.executor)" + (contract.checker.isEmpty ? "" : " · checker: \(contract.checker)")).foregroundStyle(Palette.secondary)
            TextEditor(text: $task).frame(height: 110).padding(8).overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.line)).disabled(resuming != nil)
            Text(contract.limits).font(.system(.caption, design: .monospaced))
            Text("Verifier: \(contract.verification.isEmpty ? "None" : contract.verification)").font(.system(.caption, design: .monospaced)).textSelection(.enabled)
            Text("Location: \(contract.isolation == "worktree" ? "separate Git worktree" : "current project") · capabilities: \(contract.capabilities.joined(separator: ", "))").font(StackType.caption)
            Text("This runs the project's configured commands. Review the contract, verifier and agent profiles before proceeding.").font(StackType.detail).foregroundStyle(Palette.secondary)
            Toggle("I approve this task under the displayed contract and limits", isOn: $approved)
            if !message.isEmpty { Text(message).font(StackType.detail).foregroundStyle(Palette.link) }
            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button(resuming == nil ? "Start loop" : "Resume loop") {
                    Task {
                        guard let wid else { return }
                        busy = true; defer { busy = false }
                        do {
                            let _: TextResult = try await model.call(resuming == nil ? "loops.start" : "loops.resume", ["workspaceId": wid, "loop": contract.id, "task": task, "runId": resuming?.id ?? "", "approved": approved, "digest": contract.digest], as: TextResult.self)
                            dismiss()
                        } catch { message = error.localizedDescription }
                    }
                }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(!approved || task.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || busy)
            }
        }.padding(28).frame(width: 590).interactiveDismissDisabled(busy)
            .onAppear { wid = model.selectedID; task = resuming?.task ?? "" }
    }
}

struct LoopAgentSheet: View {
    @Bindable var model: AppModel
    let contract: LoopContract
    let digest: String
    @Environment(\.dismiss) private var dismiss
    @State private var maker = "codex"
    @State private var checker = "claude-code"
    @State private var message = ""
    @State private var busy = false
    private var hasChecker: Bool { !contract.checker.isEmpty }
    private var profileDescription: String {
        if hasChecker {
            return "Updates the \(contract.executor) and \(contract.checker) profiles in this project's harnesses.json. The executor keeps its existing file-access permissions; the checker uses read-only or planning permissions."
        }
        return "Updates the \(contract.executor) profile in this project's harnesses.json. File access follows the profile's existing permissions and the loop contract."
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text(hasChecker ? "Connect the loop's agents" : "Connect the loop's agent").font(.title2.weight(.semibold))
            Text(profileDescription).font(StackType.detail).foregroundStyle(Palette.secondary)
            Picker(contract.executor.capitalized, selection: $maker) { Text("Codex").tag("codex"); Text("Claude Code").tag("claude-code") }
            if hasChecker {
                Picker(contract.checker.capitalized, selection: $checker) { Text("Claude Code").tag("claude-code"); Text("Codex").tag("codex") }
            }
            if !message.isEmpty { Text(message).font(StackType.detail).foregroundStyle(Palette.link) }
            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button(hasChecker ? "Save agent profiles" : "Save agent profile") {
                    Task {
                        guard let wid = model.selectedID else { return }
                        busy = true; defer { busy = false }
                        do {
                            var parameters = ["workspaceId": wid, "loop": contract.id, "digest": digest, "makerAgent": maker]
                            if hasChecker { parameters["checkerAgent"] = checker }
                            let _: TextResult = try await model.call("loops.configure", parameters, as: TextResult.self)
                            dismiss()
                        } catch { message = error.localizedDescription }
                    }
                }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(busy)
            }
        }.padding(28).frame(width: 540).interactiveDismissDisabled(busy)
    }
}
