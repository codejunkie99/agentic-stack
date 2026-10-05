import SwiftUI

struct AgentModelPicker: View {
    let runner: String
    let choices: [AgentModelChoice]
    @Binding var modelID: String
    @Binding var effort: String
    @State private var custom = false
    private var models: [AgentModelChoice] { choices.filter { $0.runner == runner } }
    private var customSelected: Bool { custom || (!modelID.isEmpty && !models.contains { $0.id == modelID }) }
    private var efforts: [String] {
        let available = models.first { $0.id == modelID }?.efforts ?? (runner == "codex" ? ["low", "medium", "high", "xhigh", "max", "ultra"] : ["low", "medium", "high", "max"])
        return available.contains(effort) || effort.isEmpty ? available : available + [effort]
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Model", selection: Binding(get: { customSelected ? "__custom__" : modelID }, set: {
                custom = $0 == "__custom__"; modelID = custom ? "" : $0; effort = ""
            })) {
                Text("Runner default").tag("")
                ForEach(models) { item in Text(item.name).tag(item.id) }
                Text("Enter a model ID…").tag("__custom__")
            }
            if customSelected { TextField("Model ID", text: $modelID).textFieldStyle(.roundedBorder) }
            Picker("Reasoning effort", selection: $effort) {
                Text("Configured default").tag("")
                ForEach(efforts, id: \.self) { Text($0.capitalized).tag($0) }
            }
            Text(runner == "codex" ? "Models come from this host’s configured Codex catalog, with the local cache as a fallback. You can also enter a model ID for your provider." : "Aliases use your existing Claude account or provider. Runner default selects the account’s default model. Availability and effort limits follow that account.")
                .font(StackType.caption).foregroundStyle(Palette.secondary)
        }.onChange(of: runner) { _, _ in modelID = ""; effort = ""; custom = false }
    }
}

struct InlineModelPicker: View {
    let runner: String
    let choices: [AgentModelChoice]
    let selection: ConversationModelSelection
    let task: String
    let attachmentKinds: [String]
    let onSelect: (ConversationModelSelection) async throws -> Void
    let recommend: (String, String, [String]) async throws -> ModelRoute
    let refresh: () async -> Void
    var catalogWarning = ""
    @State private var presented = false

    private var isAuto: Bool { selection.routing != "fixed" }
    private var modelName: String {
        if isAuto { return "Auto · " + routingName(selection.routing) }
        return choices.first { $0.runner == runner && $0.id == selection.model }?.name
            ?? (selection.model.isEmpty ? "Default" : selection.model)
    }
    var body: some View {
        Button { presented.toggle() } label: {
            HStack(spacing: 5) {
                Image(systemName: isAuto ? "point.3.connected.trianglepath.dotted" : "bolt.fill").font(.system(size: 12))
                Text(modelName).lineLimit(1).truncationMode(.middle)
                if !isAuto && !selection.effort.isEmpty { Text(effortName(selection.effort)).foregroundStyle(effortColor(selection.effort)) }
                Image(systemName: "chevron.down").font(.system(size: 8, weight: .semibold))
            }.font(StackType.caption).padding(.horizontal, 8).padding(.vertical, 5)
                .background(Palette.line.opacity(0.45), in: Capsule())
        }.buttonStyle(.plain).frame(maxWidth: 245)
            .accessibilityLabel(isAuto ? "Change model routing: " + modelName : "Change model and effort: " + modelName + ", " + effortName(selection.effort))
            .help("Choose automatic routing or a fixed model for the next message")
            .popover(isPresented: $presented, attachmentAnchor: .rect(.bounds), arrowEdge: .top) {
                InlineModelPopover(runner: runner, choices: choices, selection: selection,
                    task: task, attachmentKinds: attachmentKinds, onSelect: onSelect,
                    recommend: recommend, refresh: refresh, catalogWarning: catalogWarning)
            }
            .onChange(of: runner) { _, _ in presented = false }
    }
}

private func effortName(_ value: String) -> String {
    modelEffortName(value)
}
private func effortColor(_ value: String) -> Color {
    switch value {
    case "ultra", "max": .pink
    case "xhigh", "high": .purple
    case "low", "minimal", "none": .teal
    default: Palette.accent
    }
}

private struct InlineModelPopover: View {
    let runner: String
    let choices: [AgentModelChoice]
    let onSelect: (ConversationModelSelection) async throws -> Void
    let task: String
    let attachmentKinds: [String]
    let recommend: (String, String, [String]) async throws -> ModelRoute
    let refresh: () async -> Void
    let catalogWarning: String
    @Environment(\.dismiss) private var dismiss
    @State private var selected: ConversationModelSelection
    @State private var confirmed: ConversationModelSelection
    @State private var showManual = false
    @State private var manualID = ""
    @State private var search = ""
    @State private var route: ModelRoute?
    @State private var routing = false
    @State private var saving = false
    @State private var editingEffort = false
    @State private var error: String?
    private var models: [AgentModelChoice] { choices.filter { $0.runner == runner } }
    private var filteredModels: [AgentModelChoice] {
        let value = search.trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? models : models.filter {
            $0.name.localizedCaseInsensitiveContains(value) || $0.id.localizedCaseInsensitiveContains(value) ||
            ($0.summary?.localizedCaseInsensitiveContains(value) ?? false)
        }
    }
    private var isAuto: Bool { selected.routing != "fixed" }
    private var modelName: String {
        isAuto ? "Auto · " + routingName(selected.routing) : models.first { $0.id == selected.model }?.name ?? (selected.model.isEmpty ? "Default" : selected.model)
    }
    private var levels: [String] { isAuto ? [] : [""] + (models.first { $0.id == selected.model }?.efforts ?? []) }
    private var recommendationID: String {
        [runner, selected.routing, task, attachmentKinds.sorted().joined(separator: ",")].joined(separator: "|")
    }

    init(runner: String, choices: [AgentModelChoice], selection: ConversationModelSelection,
         task: String, attachmentKinds: [String],
         onSelect: @escaping (ConversationModelSelection) async throws -> Void,
         recommend: @escaping (String, String, [String]) async throws -> ModelRoute,
         refresh: @escaping () async -> Void, catalogWarning: String) {
        self.runner = runner; self.choices = choices; self.task = task; self.attachmentKinds = attachmentKinds
        self.onSelect = onSelect; self.recommend = recommend; self.refresh = refresh; self.catalogWarning = catalogWarning
        _selected = State(initialValue: selection); _confirmed = State(initialValue: selection)
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 3) {
                    Text("Choose how this message runs").font(StackType.heading)
                    Text(runner == "codex" ? "Codex" : "Claude Code").font(StackType.caption).foregroundStyle(Palette.secondary)
                }
                Spacer()
                Button { Task { await refresh() } } label: { Image(systemName: "arrow.clockwise") }
                    .buttonStyle(.plain).help("Refresh available models")
            }
            Picker("Selection mode", selection: Binding(get: { isAuto }, set: { automatic in
                if automatic { chooseRoute("auto:balanced") }
                else { chooseModel(selected.model) }
            })) {
                Text("Auto").tag(true)
                Text("Fixed model").tag(false)
            }.pickerStyle(.segmented).labelsHidden()

            if isAuto { automaticRouter } else { fixedModels }
            if let error { Text(error).font(StackType.caption).foregroundStyle(.red).fixedSize(horizontal: false, vertical: true) }
            if saving { ProgressView("Updating…").controlSize(.small).font(StackType.caption) }
            if !catalogWarning.isEmpty { Text(catalogWarning).font(StackType.caption).foregroundStyle(Palette.secondary) }
        }.padding(18).frame(width: 440).disabled(saving)
            .onExitCommand { dismiss() }
            .task(id: recommendationID) { await loadRecommendation() }
    }

    private var automaticRouter: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Priority", selection: Binding(get: { selected.routing }, set: { chooseRoute($0) })) {
                Text("Faster").tag("auto:cost")
                Text("Balanced").tag("auto:balanced")
                Text("Stronger").tag("auto:intelligence")
            }.pickerStyle(.segmented)
            Text(routeDescription(selected.routing)).font(StackType.caption).foregroundStyle(Palette.secondary)

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Label("For this message", systemImage: "wand.and.stars").font(StackType.caption.weight(.semibold))
                    Spacer()
                    if routing { ProgressView().controlSize(.mini) }
                    else if let route { Text(route.complexity.capitalized).font(StackType.caption).foregroundStyle(Palette.secondary) }
                }
                if let route {
                    HStack(spacing: 8) {
                        Text(models.first { $0.id == route.model }?.name ?? (route.model.isEmpty ? "Runner default" : route.model))
                            .font(.system(size: 15, weight: .semibold)).lineLimit(1)
                        if !route.effort.isEmpty { Text(modelEffortName(route.effort)).font(StackType.caption).foregroundStyle(effortColor(route.effort)) }
                        Spacer()
                        if let confidence = route.confidence, confidence > 0 {
                            Text(confidence >= 0.85 ? "Strong match" : confidence >= 0.6 ? "Good match" : "Fallback")
                                .font(StackType.caption).foregroundStyle(Palette.secondary)
                        }
                    }
                    Text(route.reason).font(StackType.caption).foregroundStyle(Palette.secondary).fixedSize(horizontal: false, vertical: true)
                    if let choice = models.first(where: { $0.id == route.model }) { capabilityBadges(choice.capabilities ?? []) }
                } else if !routing {
                    Text("Write a message to preview the model and reasoning effort before you send it.")
                        .font(StackType.caption).foregroundStyle(Palette.secondary)
                }
            }
            .padding(12).background(Palette.accent.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(Palette.accent.opacity(0.2)))

            Text("Auto stays on \(runner == "codex" ? "Codex" : "Claude Code") and records the chosen model with the reply.")
                .font(StackType.caption).foregroundStyle(Palette.secondary)
        }
    }

    private var fixedModels: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass").foregroundStyle(Palette.secondary)
                TextField("Search available models", text: $search).textFieldStyle(.plain)
                if !search.isEmpty {
                    Button { search = "" } label: { Image(systemName: "xmark.circle.fill") }
                        .buttonStyle(.plain).foregroundStyle(Palette.secondary).accessibilityLabel("Clear model search")
                }
            }.padding(.horizontal, 10).frame(height: 34)
                .background(Palette.surface, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.line))
            ScrollView {
                VStack(alignment: .leading, spacing: 2) {
                    modelRow(id: "", title: "Runner default", subtitle: "Use the default configured by this account", capabilities: [])
                    ForEach(filteredModels) { item in
                        modelRow(id: item.id, title: item.name, subtitle: item.summary, capabilities: item.capabilities ?? [])
                    }
                    if filteredModels.isEmpty { Text("No available model matches this search.").font(StackType.caption).foregroundStyle(Palette.secondary).padding(10) }
                }
            }.frame(maxHeight: 270)

            if levels.count > 1 {
                Picker("Reasoning effort", selection: Binding(get: { selected.effort }, set: { value in
                    Task { await apply(.init(model: selected.model, effort: value, routing: "fixed")) }
                })) {
                    ForEach(levels, id: \.self) { Text(modelEffortName($0)).tag($0) }
                }
            } else {
                Text(selected.model.isEmpty ? "The runner chooses its configured reasoning effort." : "This model exposes no effort variants.")
                    .font(StackType.caption).foregroundStyle(Palette.secondary)
            }
            DisclosureGroup("Use a model ID") {
                HStack {
                    TextField("Model ID", text: $manualID).textFieldStyle(.roundedBorder)
                        .onSubmit { chooseModel(manualID.trimmingCharacters(in: .whitespacesAndNewlines)) }
                    Button("Use") { chooseModel(manualID.trimmingCharacters(in: .whitespacesAndNewlines)) }
                        .disabled(manualID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }.font(StackType.caption)
        }
    }

    private func modelRow(id: String, title: String, subtitle: String? = nil, capabilities: [String]) -> some View {
        Button { chooseModel(id) } label: {
            HStack(spacing: 10) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(StackType.detail).lineLimit(1)
                    if let subtitle { Text(subtitle).font(StackType.caption).foregroundStyle(Palette.secondary) }
                    capabilityBadges(capabilities)
                }
                Spacer()
                if selected.routing == "fixed" && selected.model == id { Image(systemName: "checkmark").font(StackType.caption).foregroundStyle(Palette.secondary) }
            }.padding(.vertical, 7).padding(.horizontal, 5).contentShape(Rectangle())
        }.buttonStyle(.plain)
    }
    private func chooseModel(_ id: String) {
        let supported = models.first { $0.id == id }?.efforts ?? []
        let next = ConversationModelSelection(model: id, effort: supported.contains(selected.effort) ? selected.effort : "", routing: "fixed")
        Task { if await apply(next) { showManual = false } }
    }
    private func chooseRoute(_ policy: String) {
        Task { _ = await apply(.init(model: "", effort: "", routing: policy)) }
    }
    private func capabilityBadges(_ values: [String]) -> some View {
        HStack(spacing: 5) {
            ForEach(values.filter { ["image", "files", "tools"].contains($0) }, id: \.self) { value in
                Text(value == "image" ? "VISION" : value.uppercased()).font(.system(size: 8, weight: .semibold))
                    .foregroundStyle(Palette.secondary).padding(.horizontal, 5).padding(.vertical, 2)
                    .background(Palette.line.opacity(0.55), in: Capsule())
            }
        }
    }
    @MainActor private func loadRecommendation() async {
        guard isAuto else { route = nil; return }
        routing = true
        do { route = try await recommend(task, selected.routing, attachmentKinds) }
        catch { if !Task.isCancelled { self.error = error.localizedDescription } }
        routing = false
    }
    @discardableResult private func apply(_ value: ConversationModelSelection) async -> Bool {
        guard !saving else { return false }
        if value.model == confirmed.model && value.effort == confirmed.effort && value.routing == confirmed.routing { selected = value; return true }
        selected = value; saving = true; error = nil
        defer { saving = false }
        do {
            try await onSelect(value)
            confirmed = value
            return true
        } catch {
            selected = confirmed; self.error = error.localizedDescription
            return false
        }
    }
}

private func routeDescription(_ policy: String) -> String {
    switch policy {
    case "auto:cost": return "Prefer a fast model and conservative reasoning effort."
    case "auto:intelligence": return "Prefer the strongest available reasoning for complex or high-impact work."
    default: return "Match model and effort to the message, attachments, and task complexity."
    }
}

struct AgentEditorView: View {
    @Bindable var model: AppModel
    let profile: AgentProfile?
    @Environment(\.dismiss) private var dismiss
    @State private var name: String
    @State private var role: String
    @State private var instructions: String
    @State private var runner: String
    @State private var modelID: String
    @State private var effort: String
    @State private var mode: String
    @State private var saving = false
    @State private var error: String?
    init(model: AppModel, profile: AgentProfile?) {
        self.model = model; self.profile = profile
        _name = State(initialValue: profile?.name ?? "")
        _role = State(initialValue: profile?.role ?? "")
        _instructions = State(initialValue: profile?.instructions ?? "")
        _runner = State(initialValue: profile?.runner ?? "codex")
        _modelID = State(initialValue: profile?.model ?? "")
        _effort = State(initialValue: profile?.effort ?? "")
        _mode = State(initialValue: profile?.mode ?? "read-only")
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 6) {
                Text(profile == nil ? "Create an agent" : "Edit \(profile!.name)").font(.title2.weight(.semibold))
                Text("Give it a role, choose how it runs, and start a conversation in any project.").font(StackType.detail).foregroundStyle(Palette.secondary)
            }.padding(24)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    TextField("Agent name", text: $name).textFieldStyle(.roundedBorder)
                    TextField("Role · for example, Code reviewer", text: $role).textFieldStyle(.roundedBorder)
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Instructions").font(StackType.heading)
                        TextEditor(text: $instructions).font(.body).frame(minHeight: 125)
                            .padding(6).background(Palette.surface, in: RoundedRectangle(cornerRadius: 8))
                            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.line)).accessibilityLabel("Agent instructions")
                        Text("Describe its responsibilities and how it should respond. Project rules and the access setting below still apply.").font(StackType.caption).foregroundStyle(Palette.secondary)
                    }
                    Divider()
                    Picker("Runner", selection: $runner) {
                        Text("Codex").tag("codex"); Text("Claude Code").tag("claude-code")
                    }
                    AgentModelPicker(runner: runner, choices: model.availableModels, modelID: $modelID, effort: $effort)
                    if model.modelsError != nil {
                        HStack { Text("Model list unavailable; configured default and manual IDs still work.").font(StackType.caption); Button("Retry") { Task { await model.loadModels() } } }
                    }
                    Picker("File access", selection: $mode) {
                        Text("Read only").tag("read-only"); Text("Edit project files").tag("workspace-write")
                    }
                    if profile != nil { Text("Changes apply to new conversations. Existing conversations keep their original agent settings.").font(StackType.caption).foregroundStyle(Palette.secondary) }
                    if let error { Text(error).foregroundStyle(.red).textSelection(.enabled) }
                }.padding(24)
            }
            Divider()
            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction).disabled(saving)
                Spacer()
                if saving { ProgressView().controlSize(.small) }
                Button(profile == nil ? "Create agent" : "Save agent") { Task { await save() } }
                    .buttonStyle(.borderedProminent).tint(Palette.accent).keyboardShortcut(.defaultAction)
                    .disabled(saving || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || instructions.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }.padding(20)
        }.frame(width: DesktopSizing.sheetWidth(540), height: DesktopSizing.sheetHeight(640)).interactiveDismissDisabled(saving)
            .task { await model.loadModels() }
    }
    private func save() async {
        saving = true; error = nil
        defer { saving = false }
        let host = model.terminalHost
        var p: [String: Any] = ["name": name, "role": role, "instructions": instructions, "runner": runner, "model": modelID, "effort": effort, "mode": mode]
        if let profile { p["id"] = profile.id }
        do {
            let saved = try await model.terminalCall("agentProfiles.save", p, host: host, as: AgentProfile.self)
            await model.refresh()
            if host == model.terminalHost && profile == nil { model.selectProfile(saved) }
            dismiss()
        } catch { self.error = error.localizedDescription }
    }
}
