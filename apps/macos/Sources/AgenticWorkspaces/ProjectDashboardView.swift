import SwiftUI

/// An operational overview: prioritize the work, then the context that supports it.
struct ProjectDashboardView: View {
    @Bindable var model: AppModel
    @State private var stack: StackSnapshot?
    @State private var knowledge: DashboardKnowledge?
    @State private var filter = DashboardTaskFilter.all
    @State private var message = ""
    @State private var loading = false
    @State private var showingDiagnostics = false
    @FocusState private var composing: Bool

    private var draftKey: String { model.terminalHost + ":" + (model.selectedID ?? "") }
    private var draft: Binding<String> {
        Binding(get: { model.dashboardDrafts[draftKey] ?? "" }, set: { model.dashboardDrafts[draftKey] = $0 })
    }
    private var active: [AgentRun] { model.runs.filter(\.isActive) }
    private var review: [AgentRun] { model.runs.filter { $0.status == "needs_review" && !$0.reviewed } }
    private var ready: [AgentAccount] { model.accounts.filter { $0.installed && $0.signedIn } }
    private var tasks: [AgentRun] {
        model.runs.filter { run in
            switch filter {
            case .all: true
            case .active: run.isActive
            case .review: run.status == "needs_review" && !run.reviewed
            }
        }.sorted { lhs, rhs in
            func rank(_ run: AgentRun) -> Int {
                if run.isActive { return 0 }
                if run.status == "needs_review" && !run.reviewed { return 1 }
                return 2
            }
            return rank(lhs) == rank(rhs) ? lhs.createdAt > rhs.createdAt : rank(lhs) < rank(rhs)
        }
    }

    var body: some View {
        GeometryReader { geometry in
            let narrow = geometry.size.width < 760
            ScrollView {
                VStack(alignment: .leading, spacing: narrow ? 16 : 20) {
                    StackPageHeading(title: "Project overview", detail: "What is running, what needs review, and what to start next.")
                    heading
                    metrics
                    if !message.isEmpty {
                        Label(message, systemImage: "exclamationmark.circle")
                            .font(StackType.detail).foregroundStyle(Palette.secondary).textSelection(.enabled)
                    }
                    let columns = narrow ? AnyLayout(VStackLayout(alignment: .leading, spacing: 24)) : AnyLayout(HStackLayout(alignment: .top, spacing: 24))
                    columns {
                        VStack(alignment: .leading, spacing: 22) {
                            composer
                            workQueue
                        }.frame(maxWidth: .infinity)
                        VStack(alignment: .leading, spacing: 24) {
                            agents
                            context
                        }.frame(maxWidth: narrow ? .infinity : 280)
                    }
                }
                .padding(narrow ? 18 : 24)
                .frame(maxWidth: 1360, alignment: .topLeading)
                .frame(maxWidth: .infinity)
            }
        }
        .background(Palette.surface.opacity(0.35))
        .task(id: model.selectedID) {
            while !Task.isCancelled {
                await load()
                do { try await Task.sleep(for: .seconds(30)) } catch { break }
            }
        }
        .sheet(isPresented: $showingDiagnostics) {
            DashboardDiagnostics(model: model, domains: stack?.domains ?? [])
        }
    }

    private var heading: some View {
        HStack(alignment: .center, spacing: 12) {
            Label(model.selected?.projectPath ?? model.selected?.name ?? "Project", systemImage: "folder")
                .font(.system(size: 12)).foregroundStyle(Palette.secondary)
                .lineLimit(1).truncationMode(.middle).textSelection(.enabled)
            Spacer(minLength: 8)
            Button { Task { await load(); await model.refreshAccounts() } } label: {
                Image(systemName: "arrow.clockwise")
            }.help("Refresh project and agent status").accessibilityLabel("Refresh dashboard")
                .disabled(loading).buttonStyle(.borderless)
            Menu {
                Button("Project diagnostics…") { showingDiagnostics = true }
                Divider()
                ForEach(StackAction.commands) { action in Button(action.title) { action.perform(model) } }
            } label: { Image(systemName: "ellipsis") }
                .menuStyle(.borderlessButton).fixedSize().help("Project tools")
                .accessibilityLabel("Project tools")
        }
    }

    private var metrics: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 180), spacing: 16)], alignment: .leading, spacing: 20) {
            metric("Running", value: String(active.count), symbol: "circle.dotted", color: .blue) { filter = .active }
            metric("Needs review", value: String(review.count), symbol: "checkmark.circle", color: Palette.link) { filter = .review }
            metric("Agents ready", value: model.accounts.isEmpty ? "—" : String(ready.count), symbol: "terminal", color: .green) { model.section = .integrations }
            metric("Imported notes", value: knowledge.map { $0.total.formatted() } ?? "—", symbol: "point.3.connected.trianglepath.dotted", color: .secondary) { model.section = .graph }
        }
        .padding(.vertical, 12)
        .background(Palette.canvas, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Palette.line, lineWidth: 1))
    }

    private func metric(_ title: String, value: String, symbol: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 7) {
                Label(title, systemImage: symbol).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.secondary)
                    .lineLimit(1).minimumScaleFactor(0.8)
                Text(value).font(.system(size: 27, weight: .medium, design: .rounded)).monospacedDigit()
                    .foregroundStyle(value == "0" || value == "—" ? Color.secondary : color)
            }.frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 18).contentShape(Rectangle())
        }.buttonStyle(DashboardMetricStyle()).help("\(title): \(value)")
    }

    private var composer: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Start a task").font(.system(size: 15, weight: .semibold))
            VStack(alignment: .leading, spacing: 0) {
                ZStack(alignment: .topLeading) {
                    if draft.wrappedValue.isEmpty {
                        Text("What would you like to build, fix, or explore?")
                            .font(.system(size: 13)).foregroundStyle(Palette.secondary)
                            .padding(.horizontal, 14).padding(.top, 14).allowsHitTesting(false)
                    }
                    TextEditor(text: draft).font(.system(size: 13)).scrollContentBackground(.hidden)
                        .padding(9).frame(height: 78).focused($composing)
                        .accessibilityLabel("Task prompt")
                }
                HStack(spacing: 10) {
                    Button { model.section = .terminal } label: {
                        Label("Terminal", systemImage: "apple.terminal")
                    }.buttonStyle(.borderless).foregroundStyle(Palette.secondary).help("Open interactive agent terminals")
                    Spacer(minLength: 2)
                    Button("Create task…", systemImage: "arrow.up") {
                        model.runTemplate = draft.wrappedValue
                        model.showingRun = true
                    }.buttonStyle(.borderedProminent).tint(Palette.accent)
                        .disabled(draft.wrappedValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.busy)
                }.controlSize(.regular).padding(.horizontal, 12).padding(.bottom, 12)
            }
            .background(Palette.canvas, in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(composing ? Palette.accent.opacity(0.6) : Palette.line, lineWidth: 1))
            HStack(spacing: 12) {
                suggestion("Review changes", prompt: "Review the current uncommitted changes. Identify concrete bugs and missing checks, with file references. Do not modify files.")
                suggestion("Explore project", prompt: "Explain this project's architecture, its main entry points, and how to run and test it. Do not modify files.")
                Spacer(minLength: 0)
            }
        }
    }

    private func suggestion(_ title: String, prompt: String) -> some View {
        Button(title) { draft.wrappedValue = prompt; composing = true }
            .buttonStyle(.plain).font(.system(size: 12)).foregroundStyle(Palette.secondary)
            .help("Fill the task prompt: \(title)")
    }

    private var workQueue: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Work queue").font(.system(size: 15, weight: .semibold))
                Spacer()
                Button("View all", systemImage: "arrow.up.right") { model.section = .runs }
                    .buttonStyle(.plain).font(.system(size: 12)).foregroundStyle(Palette.secondary)
            }
            HStack(spacing: 18) {
                ForEach(DashboardTaskFilter.allCases) { item in
                    Button {
                        filter = item
                    } label: {
                        VStack(spacing: 8) {
                            Text(item.rawValue).font(.system(size: 12, weight: filter == item ? .semibold : .regular))
                                .foregroundStyle(filter == item ? Color.primary : Color.secondary)
                            Rectangle().fill(filter == item ? Palette.accent : .clear).frame(height: 2)
                        }.fixedSize(horizontal: true, vertical: false)
                    }.buttonStyle(.plain).accessibilityAddTraits(filter == item ? .isSelected : [])
                }
                Spacer(minLength: 0)
            }.overlay(alignment: .bottom) { Rectangle().fill(Palette.line).frame(height: 1) }
            if tasks.isEmpty {
                VStack(alignment: .leading, spacing: 9) {
                    Image(systemName: filter == .review ? "checkmark.circle" : "tray")
                        .font(.system(size: 23, weight: .light)).foregroundStyle(Palette.secondary).padding(.bottom, 3)
                    Text(emptyTitle).font(.system(size: 14, weight: .medium))
                    Text(emptyDetail).font(.system(size: 12)).foregroundStyle(Palette.secondary)
                        .fixedSize(horizontal: false, vertical: true).lineSpacing(3)
                    if model.runs.isEmpty {
                        Button("Write your first task", systemImage: "arrow.up") { composing = true }
                            .buttonStyle(.plain).foregroundStyle(Palette.link).font(.system(size: 12, weight: .medium)).padding(.top, 3)
                    } else if filter != .all {
                        Button("Show all tasks") { filter = .all }.buttonStyle(.link).font(StackType.caption)
                    }
                }.padding(.vertical, 18).padding(.horizontal, 2).frame(maxWidth: .infinity, alignment: .leading)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(tasks.prefix(5))) { run in
                        DashboardTaskRow(run: run) {
                            model.focusedRunID = run.id; model.section = .runs
                        }
                        if run.id != tasks.prefix(5).last?.id { Divider().opacity(0.6) }
                    }
                }
            }
        }
    }
    private var emptyTitle: String {
        switch filter {
        case .all: "A clear space for your next task"
        case .active: "No tasks running"
        case .review: "You're all caught up"
        }
    }
    private var emptyDetail: String {
        switch filter {
        case .all: "Give an agent a task above. Its progress and results will appear here, ready for your review."
        case .active: "Start a task above, or open Terminal for an interactive session."
        case .review: "Tasks that need your review will appear here when they finish."
        }
    }

    private var agents: some View {
        VStack(alignment: .leading, spacing: 14) {
            panelHeading("Your agents", action: "Manage") { model.section = .integrations }
            if model.accounts.isEmpty {
                Text(model.accountError == nil ? "Detect installed agents to get started." : "Agent status unavailable.")
                    .font(.system(size: 12)).foregroundStyle(Palette.secondary)
                Button("Detect agents") { Task { await model.refreshAccounts() } }.controlSize(.small)
            } else {
                ForEach(model.accounts) { account in
                    HStack(spacing: 10) {
                        Image(systemName: "terminal").font(.system(size: 17, weight: .regular)).foregroundStyle(Palette.secondary)
                            .frame(width: 28, height: 32)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(account.name).font(.system(size: 12, weight: .medium))
                            Label(account.installed ? (account.signedIn ? "Signed in" : "Sign in required") : "Not installed",
                                  systemImage: account.installed && account.signedIn ? "checkmark.circle.fill" : "circle")
                                .font(.system(size: 12)).foregroundStyle(account.installed && account.signedIn ? Color.green : .secondary)
                        }
                        Spacer(minLength: 0)
                        Button {
                            if account.installed && account.signedIn {
                                model.section = .terminal
                                Task { await model.terminalWorkspace.launch(account.id, model: model) }
                            } else { model.section = .integrations }
                        } label: { Image(systemName: "arrow.up.right").font(.system(size: 12, weight: .medium)).frame(width: 24, height: 24).contentShape(Rectangle()) }
                            .buttonStyle(.borderless)
                            .disabled(model.terminalWorkspace.launching)
                            .accessibilityLabel(account.installed && account.signedIn ? "Open \(account.name) terminal" : "Set up \(account.name)")
                            .help(account.installed && account.signedIn ? "Open \(account.name) terminal" : "Set up \(account.name)")
                    }
                }
            }
            projectSetup
            Divider()
            Button { model.section = .terminal } label: {
                HStack {
                    Label("Open terminal", systemImage: "apple.terminal")
                    Spacer()
                    Text("⌘⇧T").foregroundStyle(.tertiary)
                }.font(.system(size: 12)).contentShape(Rectangle())
            }.buttonStyle(.plain).foregroundStyle(Palette.secondary)
        }
        .padding(16).background(Palette.canvas, in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Palette.line, lineWidth: 1))
    }

    private var context: some View {
        VStack(alignment: .leading, spacing: 14) {
            panelHeading("Project knowledge", action: "Explore") { model.section = .graph }
            if let knowledge {
                if knowledge.total > 0 {
                    Text("\(knowledge.sources.reduce(0) { $0 + $1.count }.formatted()) files imported")
                        .font(.system(size: 12)).foregroundStyle(Palette.secondary)
                    ForEach(knowledge.sources.sorted { $0.count > $1.count }.prefix(4)) { source in
                        VStack(spacing: 6) {
                            HStack {
                                Text(source.displayName).lineLimit(1)
                                Spacer()
                                Text(source.count.formatted()).monospacedDigit()
                            }.font(.system(size: 12)).foregroundStyle(Palette.secondary)
                            GeometryReader { size in
                                Capsule().fill(Palette.line)
                                Capsule().fill(Palette.accent.opacity(0.6))
                                    .frame(width: max(3, size.size.width * CGFloat(source.count) / CGFloat(max(1, knowledge.sources.map(\.count).max() ?? 1))))
                            }.frame(height: 3).accessibilityHidden(true)
                        }.accessibilityElement(children: .combine)
                    }
                    if knowledge.sources.count > 4 {
                        Text("+\(knowledge.sources.count - 4) more sources").font(.system(size: 12)).foregroundStyle(Palette.secondary)
                    }
                } else {
                    Text("Bring your existing memories and rules into this project.")
                        .font(.system(size: 12)).foregroundStyle(Palette.secondary).fixedSize(horizontal: false, vertical: true)
                }
            } else {
                Text(loading ? "Reading project knowledge…" : "Knowledge status unavailable")
                    .font(.system(size: 12)).foregroundStyle(Palette.secondary)
            }
            Button("Import from another tool", systemImage: "square.and.arrow.down") { model.section = .integrations }
                .buttonStyle(.plain).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.link)
            Divider()
            Button { model.section = .skills } label: {
                HStack {
                    Label("Installed skills", systemImage: "sparkles")
                    Spacer()
                    Text(stack.map { String($0.skills.count) } ?? "—").fontWeight(.semibold).monospacedDigit()
                    Image(systemName: "chevron.right").font(.system(size: 12))
                }.font(.system(size: 12)).contentShape(Rectangle())
            }.buttonStyle(.plain)
        }
    }

    @ViewBuilder private var projectSetup: some View {
        if let stack, !stack.initialized || stack.installed.isEmpty {
            Button("Finish project setup", systemImage: "arrow.right") { model.showingOnboarding = true }
                .buttonStyle(.plain).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.link)
                .help("Install project adapters to share instructions, skills and memory with your agents")
        }
    }

    private func panelHeading(_ title: String, action: String, perform: @escaping () -> Void) -> some View {
        HStack {
            Text(title).font(.system(size: 13, weight: .semibold))
            Spacer(minLength: 4)
            Button(action, action: perform).buttonStyle(.plain).font(.system(size: 12)).foregroundStyle(Palette.secondary)
        }
    }

    private func load() async {
        guard let wid = model.selectedID, !loading else { return }
        let host = model.terminalHost
        loading = true
        defer { loading = false }
        var errors: [String] = []
        do {
            let value: StackSnapshot = try await model.call("stack.snapshot", ["workspaceId": wid], as: StackSnapshot.self)
            guard wid == model.selectedID, host == model.terminalHost, !Task.isCancelled else { return }
            stack = value
        } catch { errors.append("Project status: " + error.localizedDescription) }
        guard !Task.isCancelled else { return }
        do {
            let value: DashboardKnowledge = try await model.call("knowledge.query", ["workspaceId": wid], as: DashboardKnowledge.self)
            guard wid == model.selectedID, host == model.terminalHost, !Task.isCancelled else { return }
            knowledge = value
        } catch { errors.append("Knowledge: " + error.localizedDescription) }
        guard wid == model.selectedID, host == model.terminalHost, !Task.isCancelled else { return }
        message = errors.joined(separator: " · ")
    }
}

private enum DashboardTaskFilter: String, CaseIterable, Identifiable {
    case all = "All tasks", active = "Active", review = "Needs review"
    var id: String { rawValue }
}
private struct DashboardKnowledge: Decodable, Sendable {
    let total: Int
    let sources: [GraphCount]
}
private extension GraphCount {
    var displayName: String {
        ["codex": "Codex", "codex-session": "Codex conversations", "claude": "Claude Code", "claude-session": "Claude Code conversations",
         "stack": "Agentic Stack", "brain": "Brain", "folder": "Imported folders", "cursor": "Cursor",
         "cursor-session": "Cursor conversations", "opencode": "OpenCode", "opencode-session": "OpenCode conversations"][id] ?? id.capitalized
    }
}
private struct DashboardMetricStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.opacity(configuration.isPressed ? 0.6 : 1)
    }
}
private struct DashboardTaskRow: View {
    let run: AgentRun
    let open: () -> Void
    @State private var hovering = false
    private var color: Color {
        if run.isActive { return .blue }
        if run.status == "needs_review" && !run.reviewed { return Palette.accent }
        if ["failed", "error"].contains(run.status) { return .red }
        return .secondary
    }
    private var symbol: String {
        if run.isActive { return "circle.dotted" }
        if run.status == "needs_review" && !run.reviewed { return "circle.lefthalf.filled" }
        if ["failed", "error"].contains(run.status) { return "exclamationmark.circle" }
        if ["cancelled", "canceled"].contains(run.status) { return "minus.circle" }
        return "checkmark.circle"
    }
    private var date: String {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let value = parser.date(from: run.createdAt) ?? ISO8601DateFormatter().date(from: run.createdAt) else { return "" }
        return value.formatted(.dateTime.month(.abbreviated).day().hour().minute())
    }
    var body: some View {
        Button(action: open) {
            HStack(alignment: .top, spacing: 11) {
                Image(systemName: symbol).font(.system(size: 15)).foregroundStyle(color).padding(.top, 2)
                VStack(alignment: .leading, spacing: 7) {
                    Text(run.task).font(.system(size: 13, weight: .medium)).lineLimit(2).multilineTextAlignment(.leading)
                    ViewThatFits(in: .horizontal) {
                        HStack(spacing: 7) { metadata; Text("·"); Text(date) }
                        HStack(spacing: 7) { metadata }
                    }.font(.system(size: 12)).foregroundStyle(Palette.secondary)
                }.frame(maxWidth: .infinity, alignment: .leading)
                Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.tertiary).padding(.top, 4)
            }.padding(.vertical, 14).padding(.horizontal, 7)
                .background(hovering ? Palette.line.opacity(0.55) : .clear, in: RoundedRectangle(cornerRadius: 6))
                .contentShape(Rectangle())
        }.buttonStyle(.plain).onHover { hovering = $0 }
            .accessibilityLabel("\(run.task), \(run.reviewed ? "Reviewed" : run.statusLabel)")
    }
    @ViewBuilder private var metadata: some View {
        Text(run.agent == "claude-code" ? "Claude Code" : run.agent == "codex" ? "Codex" : run.provider == "box" ? "Box" : "Agent")
        Text("·")
        Text(run.reviewed ? "Reviewed" : run.statusLabel).foregroundStyle(color)
    }
}

/// Keep the detailed collector inspection available without competing with everyday work.
private struct DashboardDiagnostics: View {
    @Bindable var model: AppModel
    let domains: [StackDomain]
    @Environment(\.dismiss) private var dismiss
    @State private var selection: String?
    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Project diagnostics").font(StackType.heading)
                Spacer()
                Button("Done") { dismiss() }.keyboardShortcut(.cancelAction)
            }.padding(16)
            Divider()
            HSplitView {
                Table(domains, selection: $selection) {
                    TableColumn("Area", value: \.name)
                    TableColumn("State") { domain in DomainState(status: domain.status) }.width(85)
                }.frame(minWidth: 230, idealWidth: 300)
                if let domain = domains.first(where: { $0.id == selection }) ?? domains.first {
                    DomainInspector(domain: domain, model: model).frame(minWidth: 300)
                }
            }
        }.frame(minWidth: 680, idealWidth: 780, minHeight: 430, idealHeight: 520)
            .onChange(of: model.section) { _, _ in dismiss() }
    }
}

private struct DomainState: View {
    let status: String
    private var color: Color { status == "pass" ? .green : ["warn", "fail"].contains(status) ? Palette.link : Palette.secondary }
    private var label: String { ["pass": "Ready", "warn": "Review", "fail": "Attention"][status] ?? (status.isEmpty ? "—" : status.capitalized) }
    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 5, height: 5)
            Text(label).font(StackType.caption)
        }.accessibilityElement(children: .combine)
    }
}

private struct DomainInspector: View {
    let domain: StackDomain
    @Bindable var model: AppModel
    private var destination: DesktopSection {
        let path = domain.id
        if path.contains("brain") { return .memory }
        if path.contains("harness") { return .agents }
        if path.contains("trust") || path.contains("protocol") { return .protocols }
        if path.contains("handoff") { return .handover }
        if path.contains("run") { return .runs }
        if path.contains("ops") || path.contains("flywheel") { return .maintenance }
        if path.contains("skill") || path.contains("capabilit") { return .skills }
        if path.contains("setting") { return .settings }
        return .maintenance
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(domain.name).font(StackType.heading).lineLimit(2)
                Spacer()
                DomainState(status: domain.status)
            }.padding(16)
            Text(domain.summary).font(StackType.detail).foregroundStyle(Palette.secondary).padding(.horizontal, 16).padding(.bottom, 12)
            HStack {
                Button("Open \(destination.searchTitle)", systemImage: "arrow.up.right") { model.section = destination }
                if domain.id.contains("harness") || domain.id.contains("trust") {
                    Button("Set up…") { model.showingOnboarding = true }
                }
            }.controlSize(.small).padding(.horizontal, 16).padding(.bottom, 16)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(domain.items) { item in
                        DisclosureGroup {
                            Text(item.detail).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 8)
                        } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(item.label).font(StackType.detail.weight(.medium))
                                Text(item.summary).font(StackType.caption).foregroundStyle(Palette.secondary).lineLimit(3)
                            }
                        }.padding(.vertical, 12)
                        Divider()
                    }
                    if domain.items.isEmpty { Text("No recorded details").foregroundStyle(Palette.secondary).padding(.vertical, 12) }
                }.padding(.horizontal, 16)
            }
        }.frame(maxHeight: .infinity, alignment: .topLeading).background(Palette.surface.opacity(0.4)).id(domain.id)
    }
}
