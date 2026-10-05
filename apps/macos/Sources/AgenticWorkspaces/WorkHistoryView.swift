import SwiftUI

struct WorkHistoryView: View {
    @Bindable var model: AppModel
    @State private var query = ""
    @State private var filter = "all"
    private func matches(_ text: String) -> Bool { query.isEmpty || text.localizedCaseInsensitiveContains(query) }
    private var items: [WorkItem] {
        model.workItems.filter { matches($0.title + " " + $0.objective) && (filter == "all" || (filter == "active" ? $0.status != "completed" : $0.status == "needs_review")) }
    }
    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 14) {
                StackSearchField(title: "Find work, conversations, and tasks", text: $query)
                Picker("Show", selection: $filter) {
                    Text("All work").tag("all"); Text("Ongoing").tag("active"); Text("Needs review").tag("review")
                }.frame(width: 165)
                Button("Run history") { model.section = .runs }
                Button("New work", systemImage: "plus") { model.newConversation() }.buttonStyle(.borderedProminent).tint(Palette.accent)
            }.padding(20)
            Divider()
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    if model.workItems.isEmpty && model.conversations.isEmpty && model.runs.isEmpty {
                        QuietEmpty(symbol: "square.stack.3d.up", title: "A place for ongoing work.", detail: "Start a request from the graph. Its conversations, decisions, and results stay together as the work develops.").padding(36)
                    }
                    ForEach(items) { item in
                        HStack(alignment: .top, spacing: 14) {
                            Image(systemName: item.status == "completed" ? "checkmark.circle" : "circle.dotted").foregroundStyle(Palette.link).padding(.top, 2)
                            VStack(alignment: .leading, spacing: 7) {
                                Button(item.title) { model.openWork(item) }.buttonStyle(.plain).font(StackType.detail.weight(.semibold))
                                let nextAction = item.checkpoint?.nextAction ?? ""
                                Text(nextAction.isEmpty ? item.objective : nextAction).font(StackType.caption).foregroundStyle(Palette.secondary).lineLimit(2)
                                Text("\(item.conversationIds.count) sessions · \(item.status.replacingOccurrences(of: "_", with: " ").capitalized)").font(StackType.caption).foregroundStyle(Palette.secondary)
                            }
                            Spacer()
                            Menu("Continue with…") {
                                Button("Codex") { Task { await model.continueWork(item, agent: "codex") } }
                                Button("Claude Code") { Task { await model.continueWork(item, agent: "claude-code") } }
                            }.fixedSize().disabled(model.busy || model.runs.contains(where: \.isActive))
                        }.padding(.vertical, 18)
                        Divider()
                    }
                    ForEach(model.conversations.filter { $0.workId == nil && matches($0.title) && filter == "all" }) { conversation in
                        Button { model.openConversation(conversation) } label: {
                            HStack(spacing: 14) {
                                Image(systemName: "bubble.left").foregroundStyle(Palette.link)
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(conversation.title).font(StackType.detail.weight(.medium))
                                    Text(conversation.agentName ?? conversation.agent).font(StackType.caption).foregroundStyle(Palette.secondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right").foregroundStyle(Palette.secondary)
                            }.padding(.vertical, 18).contentShape(Rectangle())
                        }.buttonStyle(.plain)
                        Divider()
                    }
                    ForEach(model.runs.filter { $0.workId == nil && $0.conversationId == nil && matches($0.task) && (filter == "all" || (filter == "review" ? $0.status == "needs_review" : $0.isActive)) }) { run in
                        Button { model.openStandaloneRun(run.id) } label: {
                            HStack(spacing: 14) {
                                Image(systemName: "play.circle").foregroundStyle(Palette.link)
                                VStack(alignment: .leading, spacing: 5) {
                                    Text(run.task).font(StackType.detail.weight(.medium)).lineLimit(2)
                                    Text("Standalone task · " + run.statusLabel).font(StackType.caption).foregroundStyle(Palette.secondary)
                                }
                                Spacer()
                                Image(systemName: "chevron.right").foregroundStyle(Palette.secondary)
                            }.padding(.vertical, 18).contentShape(Rectangle())
                        }.buttonStyle(.plain)
                        Divider()
                    }
                }.padding(.horizontal, 24).frame(maxWidth: 1040).frame(maxWidth: .infinity)
            }
        }
    }
}
