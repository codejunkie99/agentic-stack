import SwiftUI

struct OverviewView: View {
    @Bindable var model: AppModel
    let workspace: Workspace

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 32) {
                HStack(spacing: 36) {
                    metric("Sources", value: String(model.sources.count))
                    metric("Reviewed", value: String(model.approvedCount))
                    metric("Runs", value: String(model.runs.count))
                    Spacer()
                }.padding(.bottom, 8)
                VStack(alignment: .leading, spacing: 18) {
                    SectionEyebrow(text: "Next step")
                    if model.sources.isEmpty {
                        Text("Start with what you know.").font(.title2.weight(.semibold))
                        Text("A runbook, project brief, meeting notes or a handover. Import only the material this workspace needs.")
                            .foregroundStyle(Palette.secondary).fixedSize(horizontal: false, vertical: true)
                        HStack {
                            Button("Import documents…", systemImage: "doc.badge.plus") { model.importFiles() }.buttonStyle(.borderedProminent).tint(Palette.accent)
                            Button("Paste a note") { model.showingSource = true }
                        }
                    } else if model.approvedCount < model.sources.count {
                        Text("Put the context through your eyes.").font(.title2.weight(.semibold))
                        Text("\(model.sources.count - model.approvedCount) source(s) are waiting for review. Only approved sources enter the agent’s context.")
                            .foregroundStyle(Palette.secondary)
                        Button("Review knowledge", systemImage: "checkmark.shield") { model.tab = .knowledge }.buttonStyle(.borderedProminent).tint(Palette.accent)
                    } else {
                        Text("The context is ready. Choose the work.").font(.title2.weight(.semibold))
                        Text("Give the agent a specific task. Its result returns here for your review, with the source material alongside it.")
                            .foregroundStyle(Palette.secondary)
                        Button("Create a run", systemImage: "play") { model.showingRun = true }.buttonStyle(.borderedProminent).tint(Palette.accent)
                    }
                }.padding(24).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Palette.surface, in: RoundedRectangle(cornerRadius: 12))

                VStack(alignment: .leading, spacing: 16) {
                    HStack { SectionEyebrow(text: "Execution"); Spacer(); Text(userFacingPath(workspace.location)).font(StackType.caption).foregroundStyle(Palette.secondary) }
                    if workspace.provider == "local" {
                        Label(model.snapshot.localAvailable ? "A coding agent is available on this Mac" : "No supported coding agent was found", systemImage: "terminal")
                        Text("Runs use a separate workspace folder and your existing agent sign-in. The default mode is read-only; writable runs stay in their workspace.")
                            .font(StackType.detail).foregroundStyle(Palette.secondary)
                    } else {
                        Text("A cloud computer with a time limit.").font(StackType.heading)
                        Text("Auto-stop after \(workspace.ttlMinutes) minutes. Compute is billed by Box. Files survive stop and resume.")
                            .font(StackType.detail).foregroundStyle(Palette.secondary)
                        if let boxID = workspace.boxId { Text(boxID).font(.system(.caption, design: .monospaced)).textSelection(.enabled) }
                        HStack {
                            if workspace.boxId == nil {
                                Button("Start cloud workspace", systemImage: "cloud") { Task { await model.cloud("start") } }.buttonStyle(.borderedProminent).tint(Palette.accent)
                            } else {
                                Button("Refresh state", systemImage: "arrow.clockwise") { Task { await model.cloud("refresh") } }
                                if workspace.state == "archived" {
                                    Button("Resume", systemImage: "play") { Task { await model.cloud("resume") } }
                                } else {
                                    Button("Stop machine", systemImage: "stop") { Task { await model.cloud("stop") } }
                                }
                            }
                            if workspace.boxId != nil {
                                Button("Desktop", systemImage: "display") { Task { await model.openDesktop() } }
                                Button("Fork", systemImage: "arrow.triangle.branch") { Task { await model.cloud("fork") } }
                            }
                            Link("Box dashboard", destination: URL(string: "https://box.ascii.dev/dashboard")!)
                        }.disabled(model.busy)
                        if !workspace.inheritCredentials {
                            Label("No Box account secrets are inherited. Configure an agent on the machine before running cloud tasks.", systemImage: "lock")
                                .font(StackType.caption).foregroundStyle(Palette.secondary)
                        }
                    }
                }
                Divider()
                VStack(alignment: .leading, spacing: 12) {
                    SectionEyebrow(text: "Portable by design")
                    Text("Your knowledge belongs to the workspace.").font(StackType.heading)
                    Text("Every reviewed source keeps its original text, a fingerprint and a review date. Export the handover whenever you need to move the work.")
                        .font(StackType.detail).foregroundStyle(Palette.secondary)
                    Button("View handover", systemImage: "doc.text") { model.tab = .handover }
                }
            }.padding(32)
        }
    }

    private func metric(_ title: String, value: String) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Text(value).font(.system(size: 28, weight: .medium, design: .rounded)).monospacedDigit()
            Text(title).font(StackType.caption).foregroundStyle(Palette.secondary)
        }.frame(minWidth: 70, alignment: .leading)
    }
}

struct KnowledgeView: View {
    @Bindable var model: AppModel
    @State private var expandedID: String?
    @State private var category = "project"
    @State private var importedCount: Int?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("References").font(StackType.heading)
                Spacer()
                Button("Paste note", systemImage: "text.badge.plus") { model.showingSource = true }
                Button("Import…", systemImage: "doc.badge.plus") { model.importFiles() }
            }.padding(.horizontal, 24).padding(.top, 24).padding(.bottom, 16)
            Picker("Reference library", selection: $category) {
                Text(importedCount.map { "Imported sources · \($0)" } ?? "Imported sources").tag("imported")
                Text("Project references · \(model.sources.count)").tag("project")
            }.pickerStyle(.segmented).labelsHidden().padding(.horizontal, 24).padding(.bottom, 16)
            if category == "imported" {
                ScrollView {
                    ImportedSourceLibrary(model: model, onCount: { importedCount = $0 }).padding(.horizontal, 24).padding(.bottom, 24)
                }
            } else {
            Text("\(model.approvedCount) of \(model.sources.count) project references reviewed").font(StackType.detail).foregroundStyle(Palette.secondary).padding(.horizontal, 24)
            if model.sources.isEmpty {
                QuietEmpty(symbol: "doc.text.magnifyingglass", title: "Add references for your tasks.",
                           detail: "Paste or import a project document, then review it for future tasks. Your existing imported material is available in Imported sources.")
                    .padding(40).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(model.sources) { source in
                            VStack(alignment: .leading, spacing: 14) {
                                HStack(alignment: .top, spacing: 12) {
                                    Image(systemName: source.approved ? "checkmark.seal" : "doc.text")
                                        .font(.title3).foregroundStyle(source.approved ? Palette.link : Palette.secondary)
                                    VStack(alignment: .leading, spacing: 5) {
                                        Text(source.name).font(StackType.heading).textSelection(.enabled)
                                        Text(source.approved ? "Reviewed · included in context" : "Waiting for your review")
                                            .font(StackType.caption).foregroundStyle(Palette.secondary)
                                    }
                                    Spacer()
                                    Button(expandedID == source.id ? "Collapse" : "Read source") {
                                        expandedID = expandedID == source.id ? nil : source.id
                                    }
                                }
                                if expandedID == source.id {
                                    Text(source.text).font(.system(size: 12, design: .monospaced)).lineSpacing(4)
                                        .textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                                        .padding(16).background(Palette.surface, in: RoundedRectangle(cornerRadius: 8))
                                    Text("SHA-256  " + source.digest).font(.system(size: 12, design: .monospaced)).foregroundStyle(Palette.secondary).textSelection(.enabled)
                                    HStack {
                                        Text(source.approved ? "Withdraw to exclude it from future runs." : "Approve this source for future agent runs.")
                                            .font(StackType.caption).foregroundStyle(Palette.secondary)
                                        Spacer()
                                        Button(source.approved ? "Withdraw approval" : "Approve source", systemImage: source.approved ? "arrow.uturn.backward" : "checkmark") {
                                            Task { _ = await model.perform("source.review", ["id": source.id, "approved": !source.approved]) }
                                        }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(model.busy)
                                    }
                                } else {
                                    Text(source.text).font(StackType.detail).foregroundStyle(Palette.secondary).lineLimit(2)
                                }
                            }.padding(24)
                            Divider()
                        }
                    }
                }
            }
            }
        }
        .task(id: model.handoverPreviewKey) {
            expandedID = nil; importedCount = nil
            category = model.sources.isEmpty ? "imported" : "project"
        }
        .onChange(of: model.sources.count) { old, new in
            if old == 0 && new > 0 { category = "project" }
        }
    }
}

struct RunsView: View {
    @Bindable var model: AppModel
    @State private var query = ""
    @State private var filter = "All"
    @State private var followOutput = true
    private var visible: [AgentRun] {
        model.runs.filter { run in
            let matches = query.isEmpty || (run.task + " " + (run.agent ?? "") + " " + run.statusLabel).localizedCaseInsensitiveContains(query)
            let state = filter == "All" || (filter == "Active" && run.isActive) ||
                (filter == "Needs review" && run.status == "needs_review" && !run.reviewed) ||
                (filter == "Finished" && !run.isActive)
            return matches && state
        }.sorted { $0.createdAt > $1.createdAt }
    }
    private var current: AgentRun? { visible.first { $0.id == model.focusedRunID } ?? visible.first }
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 14) {
                StackSearchField(title: "Search task history", text: $query)
                Picker("Status", selection: $filter) {
                    ForEach(["All", "Active", "Needs review", "Finished"], id: \.self) { Text($0).tag($0) }
                }.frame(width: 175)
            }.padding(16)
            Divider()
            if model.runs.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Image(systemName: "tray").font(.system(size: 26, weight: .light)).foregroundStyle(Palette.secondary)
                    Text("No tasks yet").font(.system(size: 17, weight: .semibold))
                    Text("Choose New task to start a bounded agent run. Its progress, result and review stay together here.")
                        .font(StackType.detail).foregroundStyle(Palette.secondary).frame(maxWidth: 420, alignment: .leading)
                    Text("Interactive terminal sessions stay in Terminal. Verified multi-step runs are under Loops.")
                        .font(StackType.caption).foregroundStyle(Palette.secondary).frame(maxWidth: 420, alignment: .leading)
                }.padding(28).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            } else if visible.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text("No matching tasks").font(StackType.heading)
                    Text("Try a different search or status.").foregroundStyle(Palette.secondary)
                    Button("Clear filters") { query = ""; filter = "All" }
                }.padding(28).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            } else {
                HSplitView {
                    List(selection: $model.focusedRunID) {
                        ForEach(visible) { run in
                            VStack(alignment: .leading, spacing: 7) {
                                Text(run.task).font(.system(size: 12, weight: .medium)).lineLimit(3)
                                Text(run.reviewed ? "Reviewed" : run.statusLabel).font(StackType.caption)
                                    .foregroundStyle(run.isActive ? Palette.link : Palette.secondary)
                            }.padding(.vertical, 6).tag(run.id)
                        }
                    }.frame(minWidth: 190, idealWidth: 240, maxWidth: 280)
                    if let run = current { detail(run).frame(minWidth: 320, maxWidth: .infinity) }
                }
            }
            Divider()
            HStack {
                Text("\(visible.count) of \(model.runs.count) tasks")
                Spacer()
                Text("\(model.runs.filter(\.isActive).count) active · \(model.runs.filter { $0.status == "needs_review" && !$0.reviewed }.count) need review")
            }.font(StackType.caption).foregroundStyle(Palette.secondary).padding(.horizontal, 16).padding(.vertical, 9)
        }
        .onAppear { model.focusedRunID = current?.id }
        .onChange(of: query) { _, _ in model.focusedRunID = visible.first?.id }
        .onChange(of: filter) { _, _ in model.focusedRunID = visible.first?.id }
    }

    private func detail(_ run: AgentRun) -> some View {
        VStack(spacing: 0) {
            taskControls(run).padding(16)
            Divider()
        ScrollViewReader { scroll in
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text(run.task).font(.system(size: 15, weight: .medium)).textSelection(.enabled)
                if let id = run.conversationId, let conversation = model.conversations.first(where: { $0.id == id }) {
                    Button("Open conversation", systemImage: "bubble.left.and.bubble.right") { model.openConversation(conversation) }
                        .buttonStyle(.plain).foregroundStyle(Palette.link).font(StackType.caption)
                }
                Text("\(run.provider == "local" ? (model.isRemote ? "Connected server · " : "This Mac · ") + run.mode : "Box Cloud · Box agent access") · \(run.timeoutSeconds / 60) minute limit")
                    .font(StackType.caption).foregroundStyle(Palette.secondary)
                Text(run.modelSummary).font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
                if let refs = run.memoryRefs, !refs.isEmpty {
                    DisclosureGroup("\(refs.count) retrieved memory references") {
                        ForEach(refs) { ref in
                            VStack(alignment: .leading, spacing: 5) {
                                Text(ref.title).font(StackType.detail.weight(.medium))
                                Text(ref.origins.map { "\(userFacingPath($0.path)):\($0.line)" }.joined(separator: "\n")).font(StackType.caption).textSelection(.enabled)
                                Text("SHA-256: \(ref.digest)").font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
                            }.padding(.vertical, 6)
                        }
                    }
                }
                Divider()
                if ["needs_review", "completed"].contains(run.status), !run.output.isEmpty {
                    Button("Save to References", systemImage: "doc.badge.plus") {
                        Task {
                            if await model.perform("run.saveSource", ["id": run.id]) { model.section = .references }
                        }
                    }.disabled(model.busy)
                }
                if !run.error.isEmpty {
                    Label("Task needs attention", systemImage: "exclamationmark.circle").font(StackType.heading)
                    Text(run.error).font(.system(.callout, design: .monospaced)).textSelection(.enabled)
                }
                if let activity = run.activity, !activity.isEmpty {
                    if run.isActive {
                        Text("Recent activity").font(StackType.caption.weight(.semibold)).foregroundStyle(Palette.secondary)
                        activityRows(Array(activity.suffix(6)))
                    } else {
                        DisclosureGroup("Task activity · \(activity.count) events") { activityRows(activity) }
                    }
                }
                if run.isActive {
                    HStack {
                        Text("Live output").font(StackType.heading)
                        Spacer()
                        Toggle("Follow output", isOn: $followOutput).toggleStyle(.checkbox).font(StackType.caption)
                    }
                    if let started = run.startedDate {
                        HStack(spacing: 4) { Text("Elapsed"); Text(started, style: .timer).monospacedDigit() }
                            .font(StackType.caption).foregroundStyle(Palette.secondary)
                    }
                    if let live = run.liveOutput, !live.isEmpty {
                        Text(live).font(.system(size: 13)).lineSpacing(5).textSelection(.enabled)
                    } else {
                        ProgressView("Waiting for the agent’s next message…").controlSize(.small)
                        Text(run.provider == "box" ? "Box returns the result when its task finishes." : "Tool activity appears above. Assistant messages appear here as the agent emits them.")
                            .font(StackType.detail).foregroundStyle(Palette.secondary)
                    }
                } else if !run.output.isEmpty {
                    Text((try? AttributedString(markdown: run.output, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace))) ?? AttributedString(run.output))
                        .font(.system(size: 13)).lineSpacing(5).textSelection(.enabled)
                } else if let live = run.liveOutput, !live.isEmpty {
                    Text("Partial output").font(StackType.heading)
                    Text(live).font(.system(size: 13)).lineSpacing(5).textSelection(.enabled)
                } else { Text("This task returned no output.").foregroundStyle(Palette.secondary) }
                Color.clear.frame(height: 1).id("task-output-end")
            }.padding(20).frame(maxWidth: .infinity, alignment: .leading)
        }.id(run.id)
            .onChange(of: run.liveOutput) { _, _ in
                if run.isActive && followOutput { scroll.scrollTo("task-output-end", anchor: .bottom) }
            }
        }
        }
    }

    private func taskControls(_ run: AgentRun) -> some View {
        HStack {
            StatusLabel(title: run.reviewed ? "Reviewed" : run.statusLabel, active: run.isActive)
            Spacer()
            if run.provider == "box", run.promptId != nil {
                Button("Refresh", systemImage: "arrow.clockwise") { Task { await model.refreshRun(run) } }.disabled(model.busy)
            }
            if run.isActive {
                Button("Stop task", systemImage: "stop") { Task { await model.cancel(run) } }.disabled(model.busy)
            }
            if run.status == "needs_review" && !run.reviewed {
                Button("Mark reviewed", systemImage: "checkmark") {
                    Task { _ = await model.perform("run.review", ["id": run.id]) }
                }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(model.busy)
            }
        }.controlSize(.small)
    }

    private func activityRows(_ items: [TaskActivity]) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            ForEach(items) { item in
                HStack(spacing: 8) {
                    Image(systemName: item.status == "completed" ? "checkmark.circle" : item.status == "running" ? "circle.dotted" : "exclamationmark.circle")
                        .foregroundStyle(item.status == "running" ? Palette.link : Palette.secondary)
                    Text(item.title).lineLimit(2)
                    Spacer(minLength: 6)
                    Text(item.status.capitalized).foregroundStyle(Palette.secondary)
                }.font(StackType.caption)
            }
        }.padding(.vertical, 4)
    }
}

struct HandoverView: View {
    @Bindable var model: AppModel
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Reviewed knowledge").font(StackType.heading)
                    Text("Save reviewed references as a handover or a portable Agentic Stack bundle.").font(StackType.detail).foregroundStyle(Palette.secondary)
                    HStack {
                        Button("Save handover…", systemImage: "doc.text") { Task { await model.saveHandover() } }
                        Button("Save portable bundle…", systemImage: "shippingbox") { Task { await model.saveBundle() } }
                        Spacer()
                        Button("Draft from references", systemImage: "text.badge.star") { model.draftHandover() }
                            .disabled(model.approvedCount == 0 || model.runs.contains(where: \.isActive))
                    }.buttonStyle(.bordered)
                    DisclosureGroup("Reviewed handover preview") {
                        Text(model.handover).font(.system(size: 12, design: .monospaced)).lineSpacing(5)
                            .textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading).padding(.vertical, 12)
                    }.font(StackType.detail)
                }
                Divider()
                LearningArtifactsView(model: model)
            }.padding(24).frame(maxWidth: 1040).frame(maxWidth: .infinity)
        }.task(id: model.handoverPreviewKey) { await model.loadHandover() }
    }
}
