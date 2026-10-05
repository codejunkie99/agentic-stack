import SwiftUI

struct WorkspaceRoot: View {
    @Bindable var model: AppModel

    var body: some View {
        NavigationSplitView {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 10) {
                    Image(systemName: "square.stack.3d.up.fill").font(.title2).foregroundStyle(Palette.link)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("agentic").font(.system(size: 18, weight: .semibold))
                        Text("WORKSPACES").font(.system(size: 12, weight: .medium)).tracking(2).foregroundStyle(Palette.secondary)
                    }
                }.padding(20).padding(.bottom, 10)
                HStack {
                    SectionEyebrow(text: "Your workspaces")
                    Spacer()
                    Button { model.showingNewWorkspace = true } label: { Image(systemName: "plus") }
                        .buttonStyle(.plain).help("New workspace (⌘N)")
                }.padding(.horizontal, 20).padding(.bottom, 10)
                List(selection: $model.selectedID) {
                    ForEach(model.visibleWorkspaces) { workspace in
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: workspace.provider == "local" ? "laptopcomputer" : "cloud")
                                .foregroundStyle(Palette.secondary).frame(width: 18).padding(.top, 2)
                            VStack(alignment: .leading, spacing: 5) {
                                Text(workspace.name).font(.system(size: 13, weight: .medium)).lineLimit(1)
                                Text(userFacingPath(workspace.location)).font(.system(size: 12)).foregroundStyle(Palette.secondary)
                            }
                        }.padding(.vertical, 6).tag(workspace.id)
                    }
                }.listStyle(.sidebar)
                Divider().padding(.horizontal, 16)
                HStack {
                    Image(systemName: "lock.shield").foregroundStyle(Palette.secondary)
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Private by default").font(.system(size: 12, weight: .medium))
                        Text("Your library stays on this Mac").font(.system(size: 12)).foregroundStyle(Palette.secondary)
                    }
                    Spacer(minLength: 0)
                    SettingsLink { Image(systemName: "gearshape") }.buttonStyle(.plain).help("Settings")
                }.padding(16)
            }
            .searchable(text: $model.search, placement: .sidebar, prompt: "Find a workspace")
            .frame(minWidth: 230, idealWidth: 245, maxWidth: 300)
            .navigationSplitViewColumnWidth(min: 230, ideal: 245, max: 300)
        } detail: {
            VStack(spacing: 0) {
                if let error = model.error {
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "exclamationmark.circle")
                        Text(error).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                        Button { model.error = nil } label: { Image(systemName: "xmark") }.buttonStyle(.plain)
                    }.font(StackType.detail).padding(14).background(Palette.accent.opacity(0.10))
                }
                if model.loading {
                    VStack(alignment: .leading, spacing: 20) {
                        RoundedRectangle(cornerRadius: 5).fill(Palette.line).frame(width: 240, height: 22)
                        RoundedRectangle(cornerRadius: 5).fill(Palette.line).frame(height: 14)
                        RoundedRectangle(cornerRadius: 5).fill(Palette.line).frame(width: 380, height: 14)
                        Text("Opening your workspace library…").font(StackType.detail).foregroundStyle(Palette.secondary)
                        Spacer()
                    }.padding(40).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                } else if let workspace = model.selected {
                    WorkspaceDetail(model: model, workspace: workspace)
                } else {
                    welcome
                }
            }.background(Palette.canvas)
        }
        .navigationSplitViewStyle(.balanced)
        .toolbar {
            ToolbarItem { Text("Agentic Workspaces").font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.secondary) }
            ToolbarItem(placement: .primaryAction) {
                Button { model.showingNewWorkspace = true } label: { Label("New Workspace", systemImage: "plus") }
            }
        }
        .sheet(isPresented: $model.showingNewWorkspace) { NewWorkspaceSheet(model: model) }
        .sheet(isPresented: $model.showingSource) { AddSourceSheet(model: model) }
        .sheet(isPresented: $model.showingRun) { NewRunSheet(model: model) }
    }

    private var welcome: some View {
        VStack(alignment: .leading, spacing: 30) {
            SectionEyebrow(text: "A place for work to continue")
            QuietEmpty(symbol: "square.stack.3d.up", title: "Give your agents a place to work.",
                       detail: "Bring the knowledge. Review what matters. Start an agent on your Mac or in the cloud, with the context it needs to carry the work forward.")
            Button("Create a workspace") { model.showingNewWorkspace = true }
                .buttonStyle(.borderedProminent).tint(Palette.accent).controlSize(.large)
            HStack(alignment: .top, spacing: 28) {
                step("01", "Bring the context", "Import the documents behind the work.")
                step("02", "Make it yours", "Review sources before an agent uses them.")
                step("03", "Move the work forward", "Run a task and inspect the result.")
            }.padding(.top, 32)
        }.padding(48).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
    }

    private func step(_ number: String, _ title: String, _ subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(number).font(.system(size: 12, design: .monospaced)).foregroundStyle(Palette.link)
            Text(title).font(.system(size: 12, weight: .semibold))
            Text(subtitle).font(.system(size: 12)).foregroundStyle(Palette.secondary).fixedSize(horizontal: false, vertical: true)
        }.frame(maxWidth: 190, alignment: .leading)
    }
}

struct WorkspaceDetail: View {
    @Bindable var model: AppModel
    let workspace: Workspace

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 8) {
                    SectionEyebrow(text: workspace.location)
                    Text(workspace.name).font(.system(size: 27, weight: .semibold)).textSelection(.enabled)
                    Text(workspace.goal).font(StackType.detail).foregroundStyle(Palette.secondary).lineLimit(3).textSelection(.enabled)
                }
                Spacer(minLength: 20)
                StatusLabel(title: workspace.stateLabel, active: ["local", "ready", "idle"].contains(workspace.state))
            }.padding(32)
            HStack {
                Picker("Workspace section", selection: $model.tab) {
                    ForEach(WorkspaceTab.allCases) { tab in Text(tab.rawValue).tag(tab) }
                }.pickerStyle(.segmented).labelsHidden().accessibilityLabel("Workspace section").frame(maxWidth: 490)
                Spacer()
                Button { model.showingRun = true } label: { Label("New run", systemImage: "play.fill") }
                    .buttonStyle(.borderedProminent).tint(Palette.accent).disabled(model.approvedCount == 0 || model.busy || model.runs.contains(where: \.isActive))
            }.padding(.horizontal, 32).padding(.bottom, 20)
            Divider()
            Group {
                switch model.tab {
                case .overview: OverviewView(model: model, workspace: workspace)
                case .knowledge: KnowledgeView(model: model)
                case .runs: RunsView(model: model)
                case .handover: HandoverView(model: model)
                case .stack: StackManagementView(model: model, section: "Overview")
                }
            }.frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}
