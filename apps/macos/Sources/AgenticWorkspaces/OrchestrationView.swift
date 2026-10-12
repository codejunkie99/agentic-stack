import AppKit
import SwiftUI

/// Plan runs, proactive campaigns, the gated evolver and Markdown memory
/// tracks, read from the project's `.agent/` files. Read-only: commands are
/// copied for the user's terminal, never executed from here.
struct OrchestrationView: View {
    @Bindable var model: AppModel
    @State private var snapshot: OrchestrationSnapshot?
    @State private var message = ""
    @State private var fetching = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HStack {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Orchestration").font(StackType.title)
                        Text("DAG plan runs, unattended campaigns, gated harness evolution and memory tracks. Everything shown comes from files under .agent/; copy a command to act on it.").foregroundStyle(Palette.secondary)
                    }
                    Spacer()
                    Button("Refresh", systemImage: "arrow.clockwise") { Task { await reload() } }.disabled(fetching)
                }
                if let snapshot {
                    if !snapshot.projectAccessError.isEmpty {
                        Text(snapshot.projectAccessError).font(StackType.detail).foregroundStyle(Palette.link)
                            .padding(16).frame(maxWidth: .infinity, alignment: .leading)
                            .background(Palette.surface, in: RoundedRectangle(cornerRadius: 12))
                    }
                    group("Plan runs", "python3 .agent/tools/plan.py new --file plan.json", snapshot.plans,
                          empty: "No plan runs yet. Validate a plan, create a run and approve it from the terminal.")
                    group("Campaigns", "python3 .agent/tools/proactive.py list", snapshot.campaigns,
                          empty: "No campaigns. A campaign wakes on a schedule, measures with a model-free monitor and closes with a cited report.")
                    VStack(alignment: .leading, spacing: 14) {
                        HStack {
                            Text("Evolution").font(StackType.heading)
                            Spacer()
                            if !snapshot.evolutionStats.isEmpty {
                                Text(statsLine(snapshot.evolutionStats)).font(StackType.caption).foregroundStyle(Palette.secondary)
                            }
                        }
                        if snapshot.evolution.isEmpty {
                            Text("Run a diagnosis to start. Candidates reach the live harness only after a paired screen.").font(StackType.detail).foregroundStyle(Palette.secondary)
                        }
                        ForEach(snapshot.evolution) { item in row(item) }
                    }.padding(20).background(Palette.surface, in: RoundedRectangle(cornerRadius: 12))
                    group("Memory tracks", "python3 .agent/tools/track.py list episode", snapshot.tracks,
                          empty: "No Markdown tracks yet. Episodes, foresights and agent cases appear here as daily logs are written.")
                } else { ProgressView("Reading orchestration state…") }
                if !message.isEmpty { Text(message).font(StackType.detail).textSelection(.enabled) }
            }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
        }
        .task(id: model.selectedID) {
            snapshot = nil
            await reload()
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(30))
                guard !Task.isCancelled else { break }
                await reload()
            }
        }
    }

    private func group(_ title: String, _ hint: String, _ items: [OrchestrationItem], empty: String) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(title).font(StackType.heading)
                Spacer()
                CopyCommandButton(command: hint, title: "Copy CLI")
            }
            if items.isEmpty { Text(empty).font(StackType.detail).foregroundStyle(Palette.secondary) }
            ForEach(items) { item in row(item) }
        }.padding(20).background(Palette.surface, in: RoundedRectangle(cornerRadius: 12))
    }

    private func row(_ item: OrchestrationItem) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(item.label).font(StackType.body.weight(.semibold)).textSelection(.enabled)
                    Text(item.kind.replacingOccurrences(of: "_", with: " ")).font(StackType.caption).foregroundStyle(Palette.secondary)
                }
                Spacer()
                StatusLabel(title: item.statusTitle, active: item.status == "pass")
                if !item.command.isEmpty { CopyCommandButton(command: item.command, title: "Copy") }
            }
            Text(item.summary).font(StackType.detail).foregroundStyle(Palette.secondary).textSelection(.enabled)
            if !item.path.isEmpty {
                Text(item.path).font(.system(.caption, design: .monospaced)).foregroundStyle(Palette.secondary).lineLimit(1).truncationMode(.middle).textSelection(.enabled)
            }
            Divider()
        }
    }

    private func statsLine(_ stats: [String: Int]) -> String {
        "round \(stats["round"] ?? 0) · stagnation \(stats["stagnation"] ?? 0) · \(stats["diagnoses"] ?? 0) diagnoses · \(stats["candidates"] ?? 0) candidates · \(stats["confirmed"] ?? 0) confirmed · \(stats["cells"] ?? 0) cells"
    }

    private func reload() async {
        guard let wid = model.selectedID, !fetching else { return }
        fetching = true
        defer { fetching = false }
        do {
            let state: OrchestrationSnapshot = try await model.call("orchestration.snapshot", ["workspaceId": wid], as: OrchestrationSnapshot.self)
            if wid == model.selectedID { snapshot = state; message = "" }
        } catch { message = error.localizedDescription }
    }
}

struct CopyCommandButton: View {
    let command: String
    let title: String
    @State private var copied = false
    var body: some View {
        Button(copied ? "Copied" : title, systemImage: copied ? "checkmark" : "doc.on.doc") {
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(command, forType: .string)
            copied = true
            Task { try? await Task.sleep(for: .seconds(1.5)); copied = false }
        }
        .buttonStyle(.bordered).controlSize(.small).help(command)
    }
}
