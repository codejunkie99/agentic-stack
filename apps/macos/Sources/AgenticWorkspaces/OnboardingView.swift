import AppKit
import SwiftUI

struct SetupSnapshot: Decodable, Sendable {
    let customized: Bool
    let preferencesDigest: String
    let featuresDigest: String
    let features: [String: Bool]
}
private struct SetupResult: Decodable, Sendable { let text: String; let warnings: [String] }

struct OnboardingView: View {
    @Bindable var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var step = 0
    @State private var stack: StackSnapshot?
    @State private var setup: SetupSnapshot?
    @State private var selectedAdapters: Set<String> = []
    @State private var name = ""
    @State private var languages = ""
    @State private var style = "concise"
    @State private var tests = "test-after"
    @State private var commits = "conventional commits"
    @State private var review = "critical issues only"
    @State private var features: [String: Bool] = [:]
    @State private var path = ""
    @State private var busy = false
    @State private var message = ""
    @State private var result: SetupResult?
    private let steps = ["Project", "Agents", "Preferences", "Review", "Ready"]

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            HStack {
                VStack(alignment: .leading, spacing: 7) {
                    SectionEyebrow(text: "Guided setup · \(min(step + 1, 5)) of 5")
                    Text(step == 4 ? "Your project is ready." : "Set up your workspace").font(.title2.weight(.semibold))
                }
                Spacer()
                if busy { ProgressView().controlSize(.small) }
            }
            HStack(spacing: 16) {
                ForEach(Array(steps.enumerated()), id: \.offset) { index, title in
                    Label(title, systemImage: index < step ? "checkmark.circle.fill" : "\(index + 1).circle")
                        .font(StackType.caption.weight(index == step ? .semibold : .regular))
                        .foregroundStyle(index == step ? Palette.link : Palette.secondary)
                }
            }
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    switch step {
                    case 0: projectStep
                    case 1: agentsStep
                    case 2: preferencesStep
                    case 3: reviewStep
                    default: readyStep
                    }
                    if !message.isEmpty { Text(message).font(StackType.detail).foregroundStyle(Palette.link).textSelection(.enabled) }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 8)
            }
            Divider()
            HStack {
                Button(step == 4 ? "Done" : "Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                if step > 0 && step < 4 { Button("Back") { step -= 1 } }
                if step < 3 {
                    Button("Continue") { step += 1 }.buttonStyle(.borderedProminent).tint(Palette.accent)
                        .disabled(model.selectedID == nil || setup == nil || busy)
                } else if step == 3 {
                    Button("Set up project") { Task { await apply() } }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(busy)
                } else {
                    Button("Start a conversation") { model.newConversation(); dismiss() }.buttonStyle(.borderedProminent).tint(Palette.accent)
                }
            }.disabled(busy)
        }.padding(28).frame(width: DesktopSizing.sheetWidth(720), height: DesktopSizing.sheetHeight(620)).interactiveDismissDisabled(busy)
        .task(id: model.selectedID) { await load() }
    }

    private var projectStep: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Start with a project folder.").font(.title3.weight(.semibold))
            Text("Setup adds portable skills, memory and agent instructions to this folder. Existing project files are preserved.").foregroundStyle(Palette.secondary)
            if let project = model.selected {
                Label(project.name, systemImage: "folder.fill").font(StackType.heading)
                Text(project.projectPath.map(userFacingPath) ?? "Managed project folder").font(StackType.caption).textSelection(.enabled)
            }
            if model.isRemote {
                TextField("Project path on the server", text: $path).textFieldStyle(.roundedBorder)
                Button("Open server project") { Task { _ = await model.openProject(path: path) } }.disabled(path.isEmpty)
            } else {
                Button("Choose or create a folder…", systemImage: "folder.badge.plus") {
                    let panel = NSOpenPanel(); panel.canChooseFiles = false; panel.canChooseDirectories = true; panel.canCreateDirectories = true
                    panel.message = "Select a project, or use New Folder to create one."
                    let completion: (NSApplication.ModalResponse) -> Void = { response in
                        if response == .OK, let url = panel.url { Task { _ = await model.openProject(path: url.path) } }
                    }
                    if let window = NSApp.keyWindow ?? NSApp.mainWindow {
                        panel.beginSheetModal(for: window, completionHandler: completion)
                    } else {
                        panel.begin(completionHandler: completion)
                    }
                }
            }
            Text("You can connect a hosted stack later from Settings → Hosting.").font(StackType.caption).foregroundStyle(Palette.secondary)
        }
    }

    private var agentsStep: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Choose the tools for this project.").font(.title3.weight(.semibold))
            Text("Share this project's instructions, skills and memory with your coding tools. Add more later in Tools → Project adapters. Codex and Claude Code keep their existing sign-in.").foregroundStyle(Palette.secondary)
            ForEach(primaryAdapters) { adapter in adapterChoice(adapter) }
            let others = (stack?.adapters ?? []).filter { adapter in !primaryAdapters.contains { $0.id == adapter.id } }
            if !others.isEmpty {
                DisclosureGroup("Other coding tools (\(others.count))") {
                    ForEach(others) { adapter in adapterChoice(adapter).padding(.vertical, 5) }
                }
            }
            Text("This installs project configuration. Manage account sign-in in Tools → Connections. Existing adapters remain installed when unchecked.").font(StackType.caption).foregroundStyle(Palette.secondary)
        }
    }

    private var primaryAdapters: [StackAdapter] {
        (stack?.adapters ?? []).filter { ["codex", "claude-code"].contains($0.id) || stack?.installed.contains($0.id) == true }
    }

    private func adapterChoice(_ adapter: StackAdapter) -> some View {
        HStack(alignment: .top) {
            Toggle(adapter.displayName, isOn: Binding(get: { selectedAdapters.contains(adapter.id) }, set: { on in
                if on { selectedAdapters.insert(adapter.id) } else { selectedAdapters.remove(adapter.id) }
            })).toggleStyle(.checkbox)
            Spacer()
            if stack?.installed.contains(adapter.id) == true {
                Text("Already installed").font(StackType.caption).foregroundStyle(Palette.secondary)
            } else if model.accounts.contains(where: { $0.id == adapter.id && $0.installed }) {
                Text("Detected on this host").font(StackType.caption).foregroundStyle(Palette.secondary)
            }
        }
    }

    private var preferencesStep: some View {
        VStack(alignment: .leading, spacing: 14) {
            if setup?.customized == true {
                Label("Your existing preferences will be kept.", systemImage: "checkmark.shield")
                Text("Review or edit them from Knowledge → Lessons → Project preferences after setup.").foregroundStyle(Palette.secondary)
            } else {
                StackField(title: "Your name (optional)", text: $name)
                StackField(title: "Primary languages", prompt: "Swift, Python", text: $languages)
                Picker("Explanation style", selection: $style) { Text("Concise").tag("concise"); Text("Detailed").tag("detailed") }
                Picker("Tests", selection: $tests) { Text("Test after changes").tag("test-after"); Text("Test driven").tag("tdd"); Text("Minimal").tag("minimal") }
                Picker("Commits", selection: $commits) { Text("Conventional commits").tag("conventional commits"); Text("Free form").tag("free-form"); Text("Emoji").tag("emoji") }
                Picker("Review depth", selection: $review) { Text("Critical issues").tag("critical issues only"); Text("Everything").tag("everything") }
            }
            Divider()
            DisclosureGroup("Advanced compatibility options") {
            feature("memory_search_fts", "FTS memory search (beta)")
            feature("tldraw", "tldraw visual memory (beta)")
            feature("mission_control", "Mission Control compatibility (beta)")
            Text("These are the repository’s existing feature flags. They do not start services or install external tools. The native graph and Dashboard work independently.").font(StackType.caption).foregroundStyle(Palette.secondary)
            }
        }
    }

    private func feature(_ key: String, _ title: String) -> some View {
        Toggle(title, isOn: Binding(get: { features[key] == true }, set: { features[key] = $0 })).toggleStyle(.checkbox)
    }

    private var reviewStep: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(model.selected?.name ?? "Project").font(.title3.weight(.semibold))
            Label("Initialize missing stack files", systemImage: "shippingbox")
            Label(setup?.customized == true ? "Preserve existing preferences" : "Save your preferences", systemImage: "person.crop.circle")
            Label(selectedAdapters.isEmpty ? "Keep current adapters" : "Add: " + (stack?.adapters ?? []).filter { selectedAdapters.contains($0.id) }.map(\.displayName).joined(separator: ", "), systemImage: "puzzlepiece.extension")
            Text("After setup, import knowledge from Tools → Connections, choose skills, then start a task or an interactive terminal.").foregroundStyle(Palette.secondary)
            Text("No account credentials are copied. Conflicting adapter files are reported for review.").font(StackType.caption).foregroundStyle(Palette.secondary)
        }
    }

    private var readyStep: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(result?.text ?? "Setup complete.")
            ForEach(result?.warnings ?? [], id: \.self) { Text($0).foregroundStyle(Palette.link).font(StackType.detail) }
            Button("Import knowledge from another tool", systemImage: "square.and.arrow.down") { model.section = .integrations; dismiss() }
            Button("Choose skills", systemImage: "sparkles") { model.section = .skills; dismiss() }
            Button("Open overview", systemImage: "square.grid.2x2") { model.section = .insights; dismiss() }
        }
    }

    private func load() async {
        guard let wid = model.selectedID else { return }
        busy = true; message = ""; setup = nil
        defer { busy = false }
        do {
            let config = try await model.call("setup.snapshot", ["workspaceId": wid], as: SetupSnapshot.self)
            let project = try await model.call("stack.snapshot", ["workspaceId": wid], as: StackSnapshot.self)
            guard wid == model.selectedID, !Task.isCancelled else { return }
            setup = config; features = config.features; stack = project
            selectedAdapters = Set(model.accounts.filter(\.installed).map(\.id)).subtracting(project.installed)
        } catch { message = error.localizedDescription }
    }

    private func apply() async {
        guard let wid = model.selectedID, let setup else { return }
        busy = true; message = ""
        defer { busy = false }
        do {
            result = try await model.call("setup.apply", ["workspaceId": wid, "preferencesDigest": setup.preferencesDigest, "featuresDigest": setup.featuresDigest,
                "answers": ["name": name, "languages": languages, "style": style, "tests": tests, "commits": commits, "review": review],
                "features": features, "adapters": selectedAdapters.sorted()], as: SetupResult.self)
            await model.refresh(); step = 4
        } catch { message = error.localizedDescription }
    }
}
