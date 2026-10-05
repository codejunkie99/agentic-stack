import SwiftUI

@main
struct AgenticWorkspacesApp: App {
    @State private var model = AppModel()
    @State private var updater = AppUpdater()
    @AppStorage("appearance") private var appearance = "system"
    @AppStorage("autoDetectTools") private var autoDetect = true
    @State private var showingMemoryDemo = false

    private var jevFixture: String? {
        let arguments = ProcessInfo.processInfo.arguments
        guard let index = arguments.firstIndex(of: "--jev-ui-fixture") else { return nil }
        return arguments.indices.contains(index + 1) ? arguments[index + 1] : "results"
    }

    private var jevSearchFixture: String? {
        let arguments = ProcessInfo.processInfo.arguments
        guard let index = arguments.firstIndex(of: "--jev-search-fixture") else { return nil }
        return arguments.indices.contains(index + 1) ? arguments[index + 1] : "results"
    }

    private var fixtureColorScheme: ColorScheme? {
        let arguments = ProcessInfo.processInfo.arguments
        guard jevFixture != nil || jevSearchFixture != nil, let index = arguments.firstIndex(of: "--jev-ui-appearance"), arguments.indices.contains(index + 1) else { return nil }
        return arguments[index + 1] == "light" ? .light : arguments[index + 1] == "dark" ? .dark : nil
    }

    var body: some Scene {
        WindowGroup("Agentic Stack") {
            GeometryReader { window in
                Group {
                    if let jevSearchFixture, jevSearchFixture.hasPrefix("settings-") {
                        SettingsView(model: model, updater: updater)
                    } else if let jevSearchFixture {
                        SpotlightSearchView(model: model, fixture: jevSearchFixture)
                            .padding(24).frame(maxWidth: .infinity, maxHeight: .infinity).background(Palette.canvas)
                    } else if let jevFixture { JevMemoryPage(model: model, fixture: jevFixture) }
                    else { StackDesktopRoot(model: model, updater: updater, compact: window.size.width < 1000) }
                }
                    .frame(width: window.size.width, height: window.size.height, alignment: .topLeading)
                    .clipped()
            }
                .frame(minWidth: 800, minHeight: 560)
                .tint(Palette.link)
                .font(StackType.body)
                .foregroundStyle(Palette.text)
                .controlSize(.regular)
                .preferredColorScheme(jevFixture != nil || jevSearchFixture != nil ? fixtureColorScheme : appearance == "system" ? nil : appearance == "dark" ? .dark : .light)
                .sheet(isPresented: $model.showingJevProviderSettings) { JevProviderSettingsView(model: model) }
                .sheet(isPresented: $showingMemoryDemo) { MemoryDemoView(model: model) }
                .task { if ProcessInfo.processInfo.arguments.contains("--memory-demo") { showingMemoryDemo = true } }
                .task(id: model.jevProviderHostKey) { await model.refreshJevProviderStatus() }
                .task {
                    guard jevFixture == nil && jevSearchFixture == nil else { return }
                    await model.refresh()
                    Task { await model.prewarmConversationReferences() }
                    if autoDetect { await model.refreshAccounts() }
                    while !Task.isCancelled {
                        try? await Task.sleep(for: .seconds(2))
                        guard !Task.isCancelled else { break }
                        await model.refresh()
                    }
                }
                .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
                    if jevFixture == nil && jevSearchFixture == nil {
                        Task { await model.refreshJevProviderStatus() }
                        if autoDetect { Task { await model.refreshAccounts() } }
                    }
                }
        }
        .defaultSize(width: 1180, height: 780)
        .defaultPosition(.center)
        .windowResizability(.contentMinSize)
        .windowToolbarStyle(.unified(showsTitle: false))
        .commands {
            CommandGroup(after: .appInfo) {
                Button("Check for Updates…") { updater.checkForUpdates() }
            }
            CommandGroup(replacing: .newItem) {
                Button("Create Custom Agent…") { model.editAgent() }.keyboardShortcut("a", modifiers: [.command, .shift])
                Button("New Work") { model.newConversation() }.keyboardShortcut("n").disabled(model.selected == nil)
                Button("New Project…") { model.showingNewWorkspace = true }.keyboardShortcut("n", modifiers: [.command, .option])
                Button("Open Project…") { model.openProjectPicker() }.keyboardShortcut("o")
                Button("Import Sources…") { model.importFiles() }.keyboardShortcut("i").disabled(model.selected == nil)
            }
            CommandMenu("Project") {
                Button("Memory workspace…") { showingMemoryDemo = true }
                Button("Search…") { model.spotlightCategory = "All"; model.spotlightTopic = ""; model.spotlightQuery = ""; model.showingCommandPalette = true }.keyboardShortcut("k")
                Button("Guided setup…") { model.showingOnboarding = true }
                Button("Knowledge Graph") { model.section = .graph }
                Button("Overview") { model.section = .insights }
                Button("Skills") { model.section = .skills }
                Divider()
                Button("Open Terminal") { model.section = .terminal }.keyboardShortcut("t", modifiers: [.command, .shift]).disabled(model.selected == nil)
                Button("New Run…") { model.showingRun = true }.keyboardShortcut("r", modifiers: [.command, .shift]).disabled(model.selected == nil)
                Button("Export Handover…") { Task { await model.saveHandover() } }.keyboardShortcut("e").disabled(model.selected == nil)
                Divider()
                Button("Refresh") { Task { await model.refresh() } }.keyboardShortcut("r")
                Divider()
                Button("Compact window") { resizeWindow(width: 800, height: 560) }.keyboardShortcut("1", modifiers: [.command, .option])
                Button("Standard window") { resizeWindow(width: 1180, height: 780) }.keyboardShortcut("2", modifiers: [.command, .option])
                Button("Large window") { resizeWindow(width: 1440, height: 940) }.keyboardShortcut("3", modifiers: [.command, .option])
            }
        }
        Settings {
            SettingsView(model: model, updater: updater).frame(width: 660, height: 650).tint(Palette.link)
        }
    }
    private func resizeWindow(width: CGFloat, height: CGFloat) {
        guard let window = NSApplication.shared.keyWindow, window.sheetParent == nil else { return }
        let available = window.screen?.visibleFrame.size ?? NSSize(width: width, height: height + 60)
        window.setContentSize(NSSize(width: min(width, available.width - 24), height: min(height, available.height - 60)))
        window.center()
    }

}

struct StatusLabel: View {
    let title: String
    var active = false
    var body: some View {
        Label(title, systemImage: active ? "circle.inset.filled" : "circle")
            .font(.system(size: 12, weight: .medium)).foregroundStyle(active ? Palette.link : Palette.secondary)
            .padding(.horizontal, 9).padding(.vertical, 5)
            .background(Palette.surface, in: Capsule())
    }
}

struct SectionEyebrow: View {
    let text: String
    var body: some View {
        Text(text).font(StackType.caption.weight(.semibold)).foregroundStyle(Palette.secondary)
    }
}

struct QuietEmpty: View {
    let symbol: String
    let title: String
    let detail: String
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Image(systemName: symbol).font(.system(size: 28, weight: .regular)).foregroundStyle(Palette.secondary)
            Text(title).font(StackType.title).accessibilityAddTraits(.isHeader)
            Text(detail).font(.body).foregroundStyle(Palette.secondary).lineSpacing(4).fixedSize(horizontal: false, vertical: true)
        }.frame(maxWidth: 460, alignment: .leading)
    }
}
