import SwiftUI

private struct MemoryDecision: Identifiable {
    var id: String { operation + recordID }
    let operation: String
    let recordID: String
    let digest: String
    let claim: String
    let detail: String
    var title: String {
        switch operation {
        case "teach": "Stage a lesson"
        case "graduate": "Accept lesson"
        case "reject": "Reject candidate"
        case "reopen": "Reopen candidate"
        default: "Retract lesson"
        }
    }
}

struct MemoryManagementView: View {
    @Bindable var model: AppModel
    @State private var snapshot: MemorySnapshot?
    @State private var category = "staged"
    @State private var query = ""
    @State private var message = ""
    @State private var decision: MemoryDecision?
    @State private var editing = false
    @State private var choseInitialCategory = false
    @State private var loading = false
    @State private var generation = 0
    @State private var recallGeneration = 0
    private var acceptedCount: Int { snapshot?.lessons.filter { ["accepted", "provisional"].contains($0.status) }.count ?? 0 }
    private var stagedCount: Int { snapshot?.candidates.filter { $0.status == "staged" }.count ?? 0 }
    private var rejectedCount: Int { snapshot?.candidates.filter { $0.status == "rejected" }.count ?? 0 }

    static func preferredCategory(_ snapshot: MemorySnapshot) -> String {
        if snapshot.candidates.contains(where: { $0.status == "staged" }) { return "staged" }
        if snapshot.lessons.contains(where: { ["accepted", "provisional"].contains($0.status) }) { return "lessons" }
        if !snapshot.lessons.isEmpty { return "history" }
        if snapshot.candidates.contains(where: { $0.status == "rejected" }) { return "rejected" }
        return "staged"
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HStack {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Lessons").font(StackType.title)
                        Text("Review what agents learn before it guides future work. Each decision keeps its evidence and history.").foregroundStyle(Palette.secondary)
                    }
                    Spacer()
                    Button("Stage a lesson", systemImage: "plus") { decision = MemoryDecision(operation: "teach", recordID: "", digest: "", claim: "", detail: "") }.buttonStyle(.borderedProminent).tint(Palette.accent)
                }
                ViewThatFits(in: .horizontal) {
                    HStack { recallControls; managementControls }
                    VStack(alignment: .leading, spacing: 10) { recallControls; managementControls }
                }
                Picker("Memory records", selection: $category) {
                    Text("Review · \(stagedCount)").tag("staged")
                    Text("Accepted · \(acceptedCount)").tag("lessons")
                    Text("Rejected · \(rejectedCount)").tag("rejected")
                    Text("History · \(snapshot?.lessons.count ?? 0)").tag("history")
                }.pickerStyle(.segmented)
                if let snapshot {
                    if category == "lessons" || category == "history" {
                        let rows = snapshot.lessons.filter { category == "history" || $0.status == "accepted" || $0.status == "provisional" }
                        if rows.isEmpty { empty("No accepted lessons yet. Review a staged candidate to add one.") }
                        ForEach(rows) { lesson in
                            VStack(alignment: .leading, spacing: 14) {
                                HStack(alignment: .top) {
                                    Text(lesson.claim).font(StackType.heading).textSelection(.enabled)
                                    Spacer()
                                    StatusLabel(title: lesson.status.capitalized)
                                }
                                DisclosureGroup("Evidence and decision history") {
                                    Text(lesson.detail).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                                }
                                if lesson.status == "accepted" {
                                    Button("Retract…", role: .destructive) { decision = MemoryDecision(operation: "retract", recordID: lesson.id, digest: lesson.digest, claim: lesson.claim, detail: lesson.detail) }
                                }
                            }.padding(20).background(Palette.surface, in: RoundedRectangle(cornerRadius: 12))
                        }
                    } else {
                        let rows = snapshot.candidates.filter { $0.status == category }
                        if rows.isEmpty { empty(category == "staged" ? "The review queue is clear. Stage a lesson or review candidates produced by the stack." : "No rejected candidates.") }
                        ForEach(rows) { candidate in
                            VStack(alignment: .leading, spacing: 14) {
                                Text(candidate.claim).font(StackType.heading).textSelection(.enabled)
                                if !candidate.conditions.isEmpty {
                                    Text("Applies to: " + candidate.conditions.joined(separator: ", ")).font(StackType.caption).foregroundStyle(Palette.secondary)
                                }
                                DisclosureGroup("Evidence and decision history") {
                                    Text(candidate.detail).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                                }
                                HStack {
                                    if candidate.status == "staged" {
                                        Button("Accept…") { choose("graduate", candidate) }.buttonStyle(.borderedProminent).tint(Palette.accent)
                                        Button("Reject…") { choose("reject", candidate) }
                                    } else {
                                        Button("Reopen…") { choose("reopen", candidate) }
                                    }
                                }
                            }.padding(20).background(Palette.surface, in: RoundedRectangle(cornerRadius: 12))
                        }
                    }
                } else if loading { ProgressView("Reading project memory…") }
                else if !model.hostReady { Text("Waiting for the host connection…").font(StackType.detail).foregroundStyle(Palette.secondary) }
                if !message.isEmpty {
                    Divider()
                    Text(message).font(.system(.callout, design: .monospaced)).textSelection(.enabled)
                }
                Divider()
                ImportedSourceLibrary(model: model, kind: "lessons")
            }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
        }
        .task(id: model.handoverPreviewKey) { snapshot = nil; message = ""; choseInitialCategory = false; await reload() }
        .sheet(item: $decision, onDismiss: { Task { await reload() } }) { item in MemoryDecisionSheet(model: model, decision: item) }
        .sheet(isPresented: $editing) { StackFileEditor(model: model, path: ".agent/memory/personal/PREFERENCES.md") }
    }
    private var recallControls: some View {
        HStack {
            TextField("Recall an intent or search memory", text: $query).textFieldStyle(.roundedBorder).frame(minWidth: 190)
            Button("Recall") { Task { await recall() } }.disabled(query.isEmpty || !model.hostReady)
        }
    }
    private var managementControls: some View {
        HStack {
            Button("Project preferences") { editing = true }
            Button("Refresh", systemImage: "arrow.clockwise") { Task { await reload() } }.disabled(loading || !model.hostReady)
        }
    }
    private func empty(_ text: String) -> some View { Text(text).foregroundStyle(Palette.secondary).padding(.vertical, 32) }
    private func choose(_ operation: String, _ item: MemoryCandidate) {
        decision = MemoryDecision(operation: operation, recordID: item.id, digest: item.digest, claim: item.claim, detail: item.detail)
    }
    private func reload() async {
        generation += 1
        let request = generation, key = model.handoverPreviewKey
        guard let wid = model.selectedID, model.hostReady else { loading = false; return }
        let host = model.terminalHost
        loading = true
        defer { if generation == request { loading = false } }
        do {
            let state = try await model.terminalCall("memory.snapshot", ["workspaceId": wid], host: host, as: MemorySnapshot.self)
            guard !Task.isCancelled, request == generation, model.handoverPreviewKey == key else { return }
            snapshot = state; message = ""
            if !choseInitialCategory { category = Self.preferredCategory(state); choseInitialCategory = true }
        } catch {
            guard !Task.isCancelled, request == generation, model.handoverPreviewKey == key else { return }
            message = error.localizedDescription
        }
    }
    private func recall() async {
        recallGeneration += 1
        let request = recallGeneration, key = model.handoverPreviewKey
        guard let wid = model.selectedID, model.hostReady else { return }
        let host = model.terminalHost
        do {
            let result = try await model.terminalCall("stack.command", ["workspaceId": wid, "operation": "recall", "query": query], host: host, as: TextResult.self)
            guard !Task.isCancelled, request == recallGeneration, model.handoverPreviewKey == key else { return }
            message = result.text
        } catch {
            guard !Task.isCancelled, request == recallGeneration, model.handoverPreviewKey == key else { return }
            message = error.localizedDescription
        }
    }
}

private struct MemoryDecisionSheet: View {
    @Bindable var model: AppModel
    let decision: MemoryDecision
    @Environment(\.dismiss) private var dismiss
    @State private var claim = ""
    @State private var rationale = ""
    @State private var message = ""
    @State private var busy = false
    @State private var wid: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(decision.title).font(.title2.weight(.semibold))
            if decision.operation == "teach" {
                Text("Write a reusable rule. It enters the review queue before becoming accepted memory.").foregroundStyle(Palette.secondary)
                TextEditor(text: $claim).accessibilityLabel("Lesson").frame(height: 120).padding(8).overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.line))
            } else {
                Text(decision.claim).font(StackType.heading).textSelection(.enabled)
                ScrollView { Text(decision.detail).font(.system(.caption, design: .monospaced)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }.frame(height: 200)
            }
            Text("Reason for this decision").font(StackType.heading)
            TextField("Reason for this decision", text: $rationale, axis: .vertical).lineLimit(3...5).textFieldStyle(.roundedBorder)
            if !message.isEmpty { Text(message).font(StackType.detail).foregroundStyle(Palette.link) }
            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button(decision.title) {
                    Task {
                        guard let wid else { return }
                        busy = true; defer { busy = false }
                        do {
                            let _: TextResult = try await model.call("memory.action", ["workspaceId": wid, "operation": decision.operation, "id": decision.recordID, "digest": decision.digest, "claim": claim, "rationale": rationale], as: TextResult.self)
                            dismiss()
                        } catch { message = error.localizedDescription }
                    }
                }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(busy || rationale.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || (decision.operation == "teach" && claim.count < 20))
            }
        }.padding(28).frame(width: 620).interactiveDismissDisabled(busy)
            .onAppear { wid = model.selectedID; claim = decision.claim }
    }
}
