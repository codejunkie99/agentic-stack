import SwiftUI

struct StackDesktopRoot: View {
    @Bindable var model: AppModel
    let updater: AppUpdater
    var compact = false
    @State private var sidebarVisible = true
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @AppStorage("appearance") private var appearance = "system"

    var body: some View {
        desktopShell
        .animation(reduceMotion ? nil : .easeOut(duration: 0.12), value: sidebarVisible)
        .disabled(model.isSearchPresented)
        .accessibilityHidden(model.isSearchPresented)
        .toolbar {
            ToolbarItem(placement: .navigation) {
                Button("Toggle sidebar", systemImage: "sidebar.left") { sidebarVisible.toggle() }
                    .keyboardShortcut("s", modifiers: [.command, .control])
            }
            ToolbarItem { Button("Search", systemImage: "magnifyingglass") { model.spotlightCategory = "All"; model.spotlightTopic = ""; model.spotlightQuery = ""; model.showingCommandPalette = true } }
            ToolbarItem { Button("Open project", systemImage: "folder.badge.plus") { model.openProjectPicker() } }
        }
        .task(id: model.terminalHost) { await model.loadModels() }
        .sheet(isPresented: $model.showingAgentEditor) { AgentEditorView(model: model, profile: model.editingProfile) }
        .sheet(isPresented: $model.showingOnboarding) { OnboardingView(model: model) }
        .overlay {
            if let request = model.conversationAttachmentRequest {
                ZStack {
                    Color.black.opacity(0.25).ignoresSafeArea().onTapGesture { model.dismissConversationAttachment() }
                    ConversationSpotlightView(model: model, initialQuery: request.query, initialAgent: request.agent,
                        context: request.context, onSelect: { model.selectConversationAttachment($0, requestID: request.id) },
                        onDismiss: { model.dismissConversationAttachment() })
                        .id(request.id).padding(24)
                }.transition(.opacity)
            } else if model.showingCommandPalette {
                ZStack {
                    Color.black.opacity(0.25).ignoresSafeArea().onTapGesture { model.showingCommandPalette = false }
                    CommandPaletteView(model: model)
                        .padding(24)
                        .shadow(color: .black.opacity(0.25), radius: 30, y: 12)
                }.transition(.opacity)
            } else if let request = model.knowledgeFilterRequest {
                ZStack {
                    Color.black.opacity(0.25).ignoresSafeArea().onTapGesture { model.knowledgeFilterRequest = nil }
                    KnowledgeFilterSpotlight(model: model, request: request).id(request.id).padding(24)
                }.transition(.opacity)
            }
        }
        .onChange(of: model.conversationDraftKey) { _, key in
            if let request = model.conversationAttachmentRequest, request.draftKey != key { model.dismissConversationAttachment() }
        }
        .onChange(of: model.showingCommandPalette) { _, showing in
            if showing { model.dismissConversationAttachment() }
        }
        .onChange(of: model.section) { _, section in
            model.knowledgeFilterRequest = nil
            if section != .graph { model.graphFullPage = false }
            if ![DesktopSection.graph, .chat].contains(section) { model.dismissConversationAttachment() }
        }
        .onChange(of: model.handoverPreviewKey) { _, key in
            if model.knowledgeFilterRequest?.targetKey != key { model.knowledgeFilterRequest = nil }
        }
        .onChange(of: model.loading) { _, loading in
            if !loading && model.connectionError == nil && !model.snapshot.dataPath.isEmpty && model.snapshot.workspaces.isEmpty {
                model.showingOnboarding = true
            }
        }
        .sheet(isPresented: $model.showingNewWorkspace) { NewWorkspaceSheet(model: model) }
        .sheet(isPresented: $model.showingSource) { AddSourceSheet(model: model) }
        .sheet(isPresented: $model.showingRun) { NewRunSheet(model: model) }
        .sheet(isPresented: $model.showingRemoteProject) { RemoteProjectSheet(model: model) }
        .onChange(of: model.tab) { _, tab in
            switch tab {
            case .runs: model.section = .runs
            case .knowledge: model.section = .references
            case .handover: model.section = .handover
            default: break
            }
        }
    }

    private var desktopShell: some View {
        HStack(spacing: 0) {
            if sidebarVisible {
                sidebar
                Divider()
            }
            VStack(spacing: 0) {
                if let error = model.error ?? model.connectionError ?? model.accountError {
                    HStack(alignment: .top) {
                        Image(systemName: "exclamationmark.circle")
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Action needs attention").font(StackType.detail.weight(.semibold))
                            Text(error).textSelection(.enabled)
                        }.frame(maxWidth: .infinity, alignment: .leading)
                        Button("Retry") { Task { await model.refresh() } }.disabled(model.loading)
                        Button("Dismiss error", systemImage: "xmark") { model.error = nil; model.connectionError = nil; model.accountError = nil }
                            .labelStyle(.iconOnly).buttonStyle(.borderless).frame(width: 28, height: 28)
                    }.font(StackType.detail).foregroundStyle(Palette.warning).padding(16).background(Palette.warning.opacity(0.08))
                }
                workspaceHeader
                Divider()
                if model.section == .settings {
                    SettingsView(model: model, updater: updater)
                } else if model.section == .integrations {
                    IntegrationsView(model: model).id(model.terminalHost + (model.selectedID ?? ""))
                } else if model.section == .hosting {
                    HostingView(model: model)
                } else if model.loading {
                    ProgressView("Opening Agentic Stack…").frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if model.selected != nil {
                    GeometryReader { area in
                        content
                            .frame(width: area.size.width, height: area.size.height, alignment: .topLeading)
                            .clipped()
                    }
                } else {
                    VStack(alignment: .leading, spacing: 24) {
                        QuietEmpty(symbol: "folder.badge.gearshape", title: "Open a project to begin",
                                   detail: "Your tasks, memory, and agent connections stay together in one workspace. Choose a project folder or create a new workspace.")
                        HStack {
                            Button("Open project…", systemImage: "folder") { model.openProjectPicker() }.buttonStyle(.borderedProminent).tint(Palette.accent)
                            Button("Guided setup", systemImage: "wand.and.stars") { model.showingOnboarding = true }.buttonStyle(.bordered)
                            Button("Create new project") { model.showingNewWorkspace = true }
                        }
                        Button("Connect a hosted stack", systemImage: "arrow.up.right") { model.section = .hosting }.buttonStyle(.plain).foregroundStyle(Palette.link)
                    }.padding(44).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
                }
            }.frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading).background(Palette.canvas)
        }
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 10) {
                Image(systemName: "square.stack.3d.up.fill").foregroundStyle(Palette.link)
                Text("Agentic Stack").font(.system(size: 16, weight: .semibold))
            }.padding(.horizontal, 20).padding(.top, 22).padding(.bottom, 20)
            Menu {
                ForEach(model.snapshot.workspaces) { project in
                    Button(project.name) { model.selectedID = project.id }
                }
                Divider()
                Button("Open project…") { model.openProjectPicker() }
                Button("Create project…") { model.showingNewWorkspace = true }
                Button("Set up project…") { model.showingOnboarding = true }
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "folder")
                    Text(model.selected?.name ?? "Choose a project").lineLimit(1)
                    Spacer(minLength: 0)
                }.font(StackType.detail.weight(.medium)).padding(8)
            }.menuStyle(.borderlessButton).help(model.selected?.name ?? "Choose a project")
                .padding(.horizontal, 12)
            Button { model.newConversation() } label: {
                Label("New work", systemImage: "plus").font(StackType.detail.weight(.semibold))
                    .frame(maxWidth: .infinity, minHeight: 28, alignment: .leading)
            }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(model.selected == nil)
                .help("New work · ⌘N").padding(.horizontal, 14).padding(.top, 12)
            Button {
                model.spotlightCategory = "All"; model.spotlightTopic = ""; model.spotlightQuery = ""
                model.showingCommandPalette = true
            } label: {
                HStack {
                    Label("Search", systemImage: "magnifyingglass")
                    Spacer()
                    StackKeyboardBadge(keys: "⌘K")
                }.font(StackType.detail).frame(minHeight: 34).contentShape(Rectangle())
            }.buttonStyle(.borderless).foregroundStyle(Palette.text).padding(.horizontal, 20).padding(.vertical, 10)
            ScrollView {
                VStack(alignment: .leading, spacing: 5) {
                    sidebarCaption("Workspace")
                    navigationRow("Work", symbol: "square.stack.3d.up", section: .graph)
                    navigationRow("Memory", symbol: "brain", section: .memory)
                    sidebarCaption("Tools").padding(.top, 16)
                    navigationRow("Connections", symbol: "point.3.connected.trianglepath.dotted", section: .integrations)
                    navigationRow("Skills", symbol: "sparkles", section: .skills)
                    sidebarCaption("Recent work").padding(.top, 20)
                    ForEach(model.workItems.prefix(12)) { item in
                        Button { model.openWork(item) } label: {
                            Label(item.title, systemImage: item.status == "completed" ? "checkmark.circle" : "circle.dotted")
                                .lineLimit(1).font(StackType.detail).frame(maxWidth: .infinity, minHeight: 34, alignment: .leading)
                                .padding(.horizontal, 10).contentShape(Rectangle())
                        }.buttonStyle(.borderless).foregroundStyle(Palette.text).help(item.title)
                    }
                    ForEach(model.conversations.filter { $0.workId == nil }.prefix(12)) { item in
                        Button { model.openConversation(item) } label: {
                            Label(item.title, systemImage: "bubble.left").lineLimit(1).font(StackType.detail)
                                .frame(maxWidth: .infinity, minHeight: 34, alignment: .leading).padding(.horizontal, 10)
                        }.buttonStyle(.borderless).foregroundStyle(Palette.text).help(item.title)
                    }
                    ForEach(model.runs.filter { $0.workId == nil && $0.conversationId == nil }.prefix(8)) { run in
                        Button { model.openStandaloneRun(run.id) } label: {
                            Label(run.task, systemImage: "play.circle").lineLimit(1).font(StackType.detail)
                                .frame(maxWidth: .infinity, minHeight: 34, alignment: .leading).padding(.horizontal, 10)
                        }.buttonStyle(.borderless).foregroundStyle(Palette.text).help(run.task)
                    }
                    if model.workItems.isEmpty && model.conversations.isEmpty && model.runs.isEmpty {
                        Text("Start new work to keep its conversations and results here.")
                            .font(StackType.caption).foregroundStyle(Palette.secondary).lineSpacing(3).padding(10)
                    }
                }.padding(.horizontal, 10).padding(.bottom, 16)
            }
            Divider().padding(.horizontal, 16)
            navigationRow("Settings", symbol: "gearshape", section: .settings).padding(.horizontal, 10).padding(.top, 10)
            HStack(spacing: 9) {
                Image(systemName: model.isRemote ? "server.rack" : "laptopcomputer")
                VStack(alignment: .leading, spacing: 4) {
                    Text(model.isRemote ? "Connected server" : "This Mac").font(StackType.caption.weight(.medium))
                    Text(model.isRemote ? model.serverURL : "Local workspace").font(StackType.caption)
                        .foregroundStyle(Palette.secondary).lineLimit(1).help(model.isRemote ? model.serverURL : "Runs locally on this Mac")
                }
            }.padding(.horizontal, 16).padding(.vertical, 12)
            HStack {
                Text("Appearance").font(StackType.caption).foregroundStyle(Palette.secondary)
                Spacer()
                Picker("Appearance", selection: $appearance) { Text("Auto").tag("system"); Text("Light").tag("light"); Text("Dark").tag("dark") }.labelsHidden().frame(width: 92)
            }.padding(.horizontal, 16).padding(.bottom, 16)
        }
        .frame(width: compact ? 208 : 224).frame(maxHeight: .infinity)
        .background(Palette.sidebar)
    }

    private func sidebarCaption(_ title: String) -> some View {
        Text(title).font(StackType.caption.weight(.medium)).foregroundStyle(Palette.secondary)
            .padding(.horizontal, 10).padding(.bottom, 5).accessibilityAddTraits(.isHeader)
    }

    private func navigationRow(_ title: String, symbol: String, section: DesktopSection) -> some View {
        let selected = model.section.workspace == section.workspace
        return Button { model.section = section } label: {
            HStack(spacing: 10) {
                Image(systemName: symbol).font(.system(size: 15)).frame(width: 20)
                Text(title).font(StackType.detail.weight(selected ? .semibold : .regular))
                Spacer(minLength: 0)
                if selected { Image(systemName: "chevron.right").font(.system(size: 10, weight: .semibold)).foregroundStyle(Palette.link).accessibilityHidden(true) }
            }
            .foregroundStyle(Palette.text).padding(.horizontal, 10).frame(minHeight: 38)
            .background(selected ? Palette.selection : .clear, in: RoundedRectangle(cornerRadius: 8))
            .contentShape(Rectangle())
        }.buttonStyle(.borderless).accessibilityAddTraits(selected ? .isSelected : [])
    }

    private var workspaceHeader: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 16) {
                sectionTitle
                if [DesktopSection.graph, .chat].contains(model.section) {
                    Button("Toggle context inspector", systemImage: "sidebar.right") {
                        model.contextInspectorVisible.toggle()
                    }
                    .labelStyle(.iconOnly).buttonStyle(.borderless)
                    .frame(width: 28, height: 28).help("Toggle context inspector")
                }
                if canRun { runButton }
            }
            if !model.section.siblings.isEmpty {
                ViewThatFits(in: .horizontal) {
                    sectionTabs
                    Menu {
                        ForEach(model.section.siblings) { page in
                            Button(page.pageTitle) { model.section = page }
                                .disabled(model.selected == nil && ![DesktopSection.settings, .hosting, .integrations].contains(page))
                        }
                    } label: {
                        Label(model.section.pageTitle, systemImage: "chevron.down")
                    }
                    .accessibilityLabel(model.section.workspaceTitle + " sections")
                }
            }
        }
        .padding(.horizontal, compact ? 18 : 24)
        .padding(.vertical, 12)
    }

    private var sectionTabs: some View {
        HStack(spacing: 4) {
            ForEach(model.section.siblings) { page in
                Button { model.section = page } label: {
                    Text(page.pageTitle)
                        .font(.system(size: 13, weight: model.section == page ? .semibold : .regular))
                        .foregroundStyle(model.section == page ? Palette.text : Palette.secondary)
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .overlay(alignment: .bottom) { Rectangle().fill(model.section == page ? Palette.link : .clear).frame(height: 2) }
                        .fixedSize(horizontal: true, vertical: false)
                }
                .buttonStyle(.borderless)
                .accessibilityAddTraits(model.section == page ? .isSelected : [])
                .disabled(model.selected == nil && ![DesktopSection.settings, .hosting, .integrations].contains(page))
            }
        }
        .fixedSize(horizontal: true, vertical: false)
    }

    private var canRun: Bool {
        model.selected != nil && model.section == .runs
    }

    private var sectionTitle: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Text(model.selected?.name ?? "Agentic Stack").lineLimit(1)
                Image(systemName: "chevron.right").font(.system(size: 9)).accessibilityHidden(true)
                Text(model.section.workspaceTitle).lineLimit(1)
            }.font(StackType.caption).foregroundStyle(Palette.secondary)
            Text(model.section.pageTitle).font(.system(size: 20, weight: .semibold)).lineLimit(1).accessibilityAddTraits(.isHeader)
        }.frame(maxWidth: .infinity, alignment: .leading)
    }

    private var runButton: some View {
        Button("New task", systemImage: "play.fill") { model.showingRun = true }
            .buttonStyle(.borderedProminent).tint(Palette.accent)
            .fixedSize()
            .disabled(model.busy || model.runs.contains(where: \.isActive))
    }

    @ViewBuilder private var content: some View {
        switch model.section {
        case .chat, .graph: GraphWorkView(model: model).id(model.terminalHost + (model.selectedID ?? ""))
        case .overview: WorkHistoryView(model: model)
        case .insights: ProjectDashboardView(model: model).id(model.terminalHost + (model.selectedID ?? ""))
        case .terminal: TerminalWorkspaceView(model: model)
        case .references: KnowledgeView(model: model)
        case .handover: HandoverView(model: model)
        case .runs: RunsView(model: model).id(model.terminalHost + (model.selectedID ?? ""))
        case .loops: LoopManagementView(model: model).id(model.terminalHost + (model.selectedID ?? ""))
        case .memory: JevMemoryPage(model: model).id(model.terminalHost + (model.selectedID ?? ""))
        case .memoryBrowse: KnowledgeGraphView(model: model).id(model.terminalHost + (model.selectedID ?? ""))
        case .personal: PersonalMemoryView(model: model).id(model.terminalHost + (model.selectedID ?? ""))
        default: StackManagementView(model: model, section: model.section.rawValue).id(model.terminalHost + (model.selectedID ?? "") + model.section.rawValue)
        }
    }
}

struct RemoteProjectSheet: View {
    @Bindable var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var path = "/data/projects/"
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Open a server project").font(.title2.weight(.semibold))
            Text("Enter the repository's absolute path on the connected server.").foregroundStyle(Palette.secondary)
            TextField("/data/projects/my-project", text: $path).textFieldStyle(.roundedBorder)
            if let error = model.error { Text(error).font(StackType.detail).foregroundStyle(Palette.link) }
            HStack {
                Button("Cancel") { dismiss() }.keyboardShortcut(.cancelAction)
                Spacer()
                Button("Open project") { Task { if await model.openProject(path: path) { dismiss() } } }
                    .buttonStyle(.borderedProminent).tint(Palette.accent).disabled(model.busy || path.isEmpty)
            }
        }.padding(28).frame(width: 500)
    }
}
