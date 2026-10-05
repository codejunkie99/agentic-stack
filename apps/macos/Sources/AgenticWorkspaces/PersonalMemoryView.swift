import AppKit
import SwiftUI

struct PersonalMemoryView: View {
    @Bindable var model: AppModel
    @State private var profile: PersonalMemoryProfile?
    @State private var query = ""
    @State private var loading = false
    @State private var error: String?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HStack(alignment: .top, spacing: 18) {
                    Image(systemName: "person.crop.circle.badge.checkmark")
                        .font(.system(size: 32, weight: .light)).foregroundStyle(Palette.link)
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Personal memory").font(StackType.title)
                        Text("Stable preferences stay separate from current project state. Agentic Stack retrieves only relevant reviewed memory for each request and keeps the source visible here.")
                            .font(StackType.detail).foregroundStyle(Palette.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                    Spacer(minLength: 12)
                    Button("Reveal profile files", systemImage: "folder") { revealProfileFiles() }
                        .disabled(model.selected?.projectPath == nil)
                }

                HStack(spacing: 10) {
                    Image(systemName: "magnifyingglass").foregroundStyle(Palette.secondary)
                    TextField("Find a preference, decision, or current focus", text: $query)
                        .textFieldStyle(.plain).onSubmit { Task { await reload() } }
                    if !query.isEmpty {
                        Button { query = ""; Task { await reload() } } label: { Image(systemName: "xmark.circle.fill") }
                            .buttonStyle(.plain).foregroundStyle(Palette.secondary).accessibilityLabel("Clear memory search")
                    }
                    Button("Search") { Task { await reload() } }.buttonStyle(.borderedProminent).tint(Palette.accent)
                }
                .padding(.horizontal, 14).frame(height: 42)
                .background(Palette.surface, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(Palette.line))

                if loading && profile == nil {
                    ProgressView("Reading personal memory…").frame(maxWidth: .infinity, alignment: .leading)
                } else if let error {
                    QuietEmpty(symbol: "exclamationmark.triangle", title: "Personal memory is unavailable", detail: error)
                } else if let profile {
                    if !query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        memorySection("Relevant now", detail: "Matches for this search, ranked from the reviewed profile and retrieved project memory.") {
                            if profile.relevant.isEmpty {
                                emptyRow("No reviewed memory matched this search.")
                            } else {
                                ForEach(profile.relevant) { item in
                                    memoryRow(title: item.title, content: item.content, source: item.source, symbol: "sparkle")
                                }
                            }
                        }
                    }

                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 310), spacing: 18, alignment: .top)], alignment: .leading, spacing: 18) {
                        memorySection("Stable profile", detail: "Preferences and durable facts that are available to agents when relevant.") {
                            if profile.static.isEmpty {
                                emptyRow("No stable profile has been written for this project yet.")
                            } else {
                                ForEach(profile.static) { item in
                                    memoryRow(title: displayName(item.source), content: item.content, source: item.source, symbol: "person.text.rectangle")
                                }
                            }
                        }
                        memorySection("Current focus", detail: "Live project state. This changes as work progresses and is not treated as a permanent preference.") {
                            if profile.dynamic.content.isEmpty {
                                emptyRow("No current project state has been recorded.")
                            } else {
                                memoryRow(title: "Working context", content: profile.dynamic.content, source: profile.dynamic.source, symbol: "scope")
                            }
                        }
                    }
                }
            }
            .padding(24).frame(maxWidth: 1180, alignment: .leading)
        }
        .task(id: model.terminalHost + (model.selectedID ?? "")) { await reload() }
        .refreshable { await reload() }
    }

    private func memorySection<Content: View>(_ title: String, detail: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(title).font(StackType.heading)
            Text(detail).font(StackType.caption).foregroundStyle(Palette.secondary).fixedSize(horizontal: false, vertical: true)
            Divider()
            content()
        }
        .padding(18).frame(maxWidth: .infinity, alignment: .topLeading)
        .background(Palette.surface, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Palette.line))
    }

    private func memoryRow(title: String, content: String, source: String, symbol: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: symbol).foregroundStyle(Palette.link)
                Text(title).font(.system(size: 13, weight: .semibold)).lineLimit(1)
                Spacer(minLength: 8)
                Button { openSource(source) } label: { Image(systemName: "arrow.up.right") }
                    .buttonStyle(.plain).foregroundStyle(Palette.secondary).disabled(model.selected?.projectPath == nil)
                    .accessibilityLabel("Open " + source)
            }
            Text(content).font(.system(size: 12)).foregroundStyle(Palette.secondary)
                .lineLimit(9).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
            Text(source).font(.system(size: 12, design: .monospaced)).foregroundStyle(.tertiary)
                .lineLimit(1).truncationMode(.middle).textSelection(.enabled)
        }.padding(.vertical, 3)
    }

    private func emptyRow(_ message: String) -> some View {
        Text(message).font(StackType.detail).foregroundStyle(Palette.secondary).padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func displayName(_ source: String) -> String {
        URL(fileURLWithPath: source).deletingPathExtension().lastPathComponent
            .replacingOccurrences(of: "_", with: " ").capitalized
    }

    private func revealProfileFiles() {
        guard let root = model.selected?.projectPath else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: root).appendingPathComponent(".agent/memory/personal"))
    }

    private func openSource(_ source: String) {
        guard let root = model.selected?.projectPath else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: root).appendingPathComponent(source))
    }

    @MainActor private func reload() async {
        guard !loading else { return }
        loading = true; error = nil
        defer { loading = false }
        do { profile = try await model.loadPersonalMemory(query: query) }
        catch { self.error = error.localizedDescription }
    }
}
