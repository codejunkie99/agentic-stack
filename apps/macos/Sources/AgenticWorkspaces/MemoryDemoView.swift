import SwiftUI

private struct MemoryDemoFixture: Decodable, Sendable {
    let workspaceId: String
    let fixtureVersion: String
    let sourceCount: Int
    let cases: [Case]
    struct Case: Decodable, Identifiable, Sendable {
        let id: String
        let title: String
        let query: String
    }
}

/// An evaluation surface over the same context.prepare bridge used by chat.
struct MemoryDemoView: View {
    @Bindable var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var fixture: MemoryDemoFixture?
    @State private var query = ""
    @State private var result: ContextPack?
    @State private var message = "Choose a project and ask a question."
    @State private var busy = false
    @State private var generation = 0
    @State private var request: Task<Void, Never>?
    @State private var history: [String] = []
    @State private var sourceMode = "fixture"
    @State private var showingBenchmarks = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Memory workspace").font(StackType.title)
                Spacer()
                Button("Benchmark results") { showingBenchmarks = true }
                Button("Done") { interrupt(); dismiss() }
            }
            Text("Find project knowledge. Inspect the sources and retrieval performance.").foregroundStyle(Palette.secondary)
            Picker("Evidence source", selection: $sourceMode) {
                Text("Sample project").tag("fixture")
                Text("My project").tag("project")
            }.pickerStyle(.segmented).disabled(busy)
            Text(sourceMode == "fixture" ? "Sample data: three authored facts about the fictional Lantern project. Stored separately from your project; processed locally." : "Search the selected project’s imported and reviewed knowledge. Evidence stays on this host.").font(StackType.detail)
            if sourceMode == "fixture" { HStack {
                Button(fixture == nil ? "Load sample" : "Reset sample") { launch(reset: fixture != nil) }
                    .disabled(busy || !model.hostReady)
                if let fixture { Text("Sample project · \(fixture.sourceCount) sources").font(StackType.caption) }
                Spacer()
                if busy { ProgressView().controlSize(.small); Button("Interrupt") { interrupt() } }
            } }
            else {
                Text(model.selected?.name ?? "Select a project in the main window first.").font(StackType.heading)
                if busy { HStack { ProgressView().controlSize(.small); Button("Interrupt") { interrupt() } } }
            }
            if sourceMode == "fixture", let fixture {
                HStack {
                    ForEach(fixture.cases) { item in
                        Button(item.title) { query = item.query }.disabled(busy)
                    }
                }
            }
            if sourceMode == "project" || fixture != nil {
                TextField(sourceMode == "fixture" ? "Ask about the sample project" : "Ask about your project", text: $query, axis: .vertical).lineLimit(2...3).textFieldStyle(.roundedBorder)
                HStack {
                    Button(result == nil ? "Retrieve" : "Repeat retrieval") { retrieve() }
                        .buttonStyle(.borderedProminent).disabled(busy || query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !model.hostReady || (sourceMode == "project" && model.selectedID == nil))
                    Text(sourceMode == "fixture" ? "Repeat to compare retrieval time. Reset starts a fresh sample session." : "Searches existing project knowledge. Repeat to compare retrieval time.").font(StackType.caption).foregroundStyle(Palette.secondary)
                }
            }
            Text(message).font(StackType.detail).textSelection(.enabled)
            if let pack = result {
                HStack {
                    Label("\(pack.elapsedMs) ms", systemImage: "clock")
                    Text(pack.cacheHit ? "Cache hit" : "Fresh retrieval")
                    Text("\(pack.estimatedTokens) / \(pack.budgetTokens) estimated tokens")
                    Text("\(pack.refs.count) sources · \(pack.status)")
                }.font(StackType.caption)
                if !pack.warning.isEmpty { Text(pack.warning).foregroundStyle(.orange) }
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        ForEach(pack.refs) { ref in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(ref.title).font(StackType.heading)
                                Text("\(ref.kind) · \(ref.status) · \(ref.reason)").font(StackType.caption)
                                ForEach(Array(ref.origins.enumerated()), id: \.offset) { _, origin in
                                    Text("\(origin.path):\(origin.line)").font(.system(.caption, design: .monospaced))
                                }
                                Text("Source fingerprint · \(ref.digest)").font(.system(.caption2, design: .monospaced))
                                Text(ref.excerpt).textSelection(.enabled)
                            }
                            Divider()
                        }
                        DisclosureGroup("How performance is measured") {
                            Text("Time measures evidence retrieval on this host, including source selection and cache lookup. It excludes an agent’s answer generation. Tokens are estimated. Repeat uses the same query and project; compare fresh and cached runs separately.").font(StackType.detail).foregroundStyle(Palette.secondary)
                            Text("Retrieval ID: \(pack.id)").font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                        }
                        DisclosureGroup("Evidence prepared for your agent") {
                            Text(pack.text).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                        }
                    }
                }
            }
            if !history.isEmpty {
                Text(history.suffix(5).joined(separator: "\n")).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
            }
        }
        .padding(24).frame(width: DesktopSizing.sheetWidth(900), height: DesktopSizing.sheetHeight(740))
        .sheet(isPresented: $showingBenchmarks) { VStack { HStack { Spacer(); Button("Done") { showingBenchmarks = false }.keyboardShortcut(.cancelAction) }.padding([.top, .horizontal], 24); ScrollView { MemoryBenchmarkView().padding(24) } }.frame(width: DesktopSizing.sheetWidth(720), height: DesktopSizing.sheetHeight(620)) }
        .onAppear { if model.selectedID != nil { sourceMode = "project" } }
        .onDisappear { interrupt() }
        .onChange(of: model.terminalHost) { _, _ in interrupt(); fixture = nil; result = nil }
        .onChange(of: sourceMode) { _, _ in interrupt(); result = nil; query = sourceMode == "fixture" ? fixture?.cases.first?.query ?? "" : ""; message = "Choose a question and retrieve local evidence." }
        .onChange(of: model.selectedID) { _, _ in if sourceMode == "project" { interrupt(); result = nil; message = "Selected project changed. Enter a question to retrieve its evidence." } }
    }

    private func launch(reset: Bool) {
        generation += 1
        let token = generation, host = model.terminalHost
        busy = true; result = nil
        request = Task { @MainActor in
            do {
                let value = try await model.terminalCall(reset ? "memory.demo.reset" : "memory.demo.prepare", [:], host: host, as: MemoryDemoFixture.self)
                guard token == generation, !Task.isCancelled else { return }
                fixture = value; query = value.cases.first?.query ?? ""
                message = reset ? "Sample reset. The next search uses a fresh sample session." : "Sample ready. Choose a question and search."
            } catch { if token == generation { message = error.localizedDescription } }
            if token == generation { busy = false; request = nil }
        }
    }

    private func retrieve() {
        guard let wid = sourceMode == "fixture" ? fixture?.workspaceId : model.selectedID else { return }
        generation += 1
        let token = generation, host = model.terminalHost, prompt = query
        busy = true; message = "Finding relevant project knowledge…"
        request = Task { @MainActor in
            do {
                let pack = try await model.terminalCall("context.prepare", ["workspaceId": wid, "prompt": prompt,
                    "contextOptions": ["mode": "local", "tokenBudget": 2500]], host: host, as: ContextPack.self)
                guard token == generation, !Task.isCancelled else { return }
                result = pack; message = "Sources ready. Review the original passages below."
                history.append("\(pack.elapsedMs) ms · \(pack.cacheHit ? "cached" : "fresh") · \(pack.refs.count) sources · retrieval \(pack.id)")
            } catch { if token == generation { message = error.localizedDescription } }
            if token == generation { busy = false; request = nil }
        }
    }

    private func interrupt() {
        guard busy else { return }
        generation += 1; request?.cancel(); request = nil; busy = false
        message = "Search interrupted. Processing already in progress may finish on the host; its result will be ignored. You can search again."
        history.append("Interrupted display; late response ignored")
    }
}
