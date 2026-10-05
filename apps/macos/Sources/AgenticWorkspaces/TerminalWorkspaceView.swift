import AppKit
import Observation
import SwiftUI
@preconcurrency import SwiftTerm

struct TerminalSessionInfo: Decodable, Identifiable, Sendable {
    let id: String
    let workspaceId: String
    let kind: String
    let path: String
    let status: String
    let exitCode: Int?
    let cols: Int
    let rows: Int
    var title: String {
        switch kind {
        case "codex": "Codex"
        case "claude-code": "Claude Code"
        case "stack-dashboard": "Stack dashboard"
        case "stack-manage": "Manage adapters"
        case "stack-transfer": "Transfer memory"
        case "stack-status": "Stack status"
        case "stack-doctor": "Project health"
        case "stack-upgrade": "Preview upgrade"
        case "stack-brain": "Brain status"
        case "stack-onboard": "Stack setup"
        case "stack-brain-onboard": "Connect Brain"
        case "stack-brain-tui": "Brain explorer"
        case "stack-brain-log": "Brain history"
        case "stack-brain-doctor": "Brain health"
        case "stack-brain-mcp": "Brain MCP command"
        case "stack-loop-status": "Loop status"
        case "stack-loop-validate": "Validate loops"
        case "stack-manifest": "Skill manifest"
        default: "Shell"
        }
    }
}
private struct TerminalList: Decodable, Sendable { let sessions: [TerminalSessionInfo] }
private struct TerminalOutput: Decodable, Sendable {
    let data: String
    let cursor: Int
    let dropped: Bool
    let session: TerminalSessionInfo
}

/// Retained by AppModel so navigating to Skills or Memory doesn't destroy terminal tabs.
@MainActor @Observable
final class TerminalWorkspace {
    var sessions: [TerminalPane] = []
    var selections: [String: String] = [:]
    var message: String?
    var launching = false

    func key(_ model: AppModel) -> String { model.terminalHost + ":" + (model.selectedID ?? "") }
    func panes(_ model: AppModel) -> [TerminalPane] {
        sessions.filter { $0.host == model.terminalHost && $0.info.workspaceId == model.selectedID }
    }
    func selected(_ model: AppModel) -> TerminalPane? {
        let available = panes(model)
        return available.first { $0.id == selections[key(model)] } ?? available.first
    }
    func refresh(_ model: AppModel) async {
        guard let wid = model.selectedID, model.selected?.provider == "local" else { return }
        let host = model.terminalHost
        do {
            let list = try await model.terminalCall("terminal.list", ["workspaceId": wid], host: host, as: TerminalList.self)
            for info in list.sessions {
                if let existing = sessions.first(where: { $0.id == info.id && $0.host == host }) { existing.info = info }
                else { sessions.append(TerminalPane(info: info, host: host, model: model)) }
            }
            // Keep other projects and hosts, but remove sessions closed by another client.
            let ids = Set(list.sessions.map(\.id))
            sessions.removeAll { $0.host == host && $0.info.workspaceId == wid && !ids.contains($0.id) }
            if host == model.terminalHost && wid == model.selectedID { message = nil }
        } catch { if host == model.terminalHost && wid == model.selectedID { message = error.localizedDescription } }
    }
    func launch(_ kind: String, model: AppModel) async {
        guard !launching, let wid = model.selectedID else { return }
        launching = true; message = nil
        defer { launching = false }
        let host = model.terminalHost
        let selectionKey = key(model)
        do {
            let info = try await model.terminalCall("terminal.create", ["workspaceId": wid, "kind": kind,
                "requestId": UUID().uuidString, "cols": 110, "rows": 32], host: host, as: TerminalSessionInfo.self)
            let pane = TerminalPane(info: info, host: host, model: model)
            sessions.append(pane)
            selections[selectionKey] = pane.id
        } catch { message = error.localizedDescription + " Refresh to recover a session if the connection dropped." }
    }
    func close(_ pane: TerminalPane, model: AppModel) async {
        do {
            let _: EmptyResult = try await model.terminalCall("terminal.close", ["workspaceId": pane.info.workspaceId, "id": pane.id], host: pane.host, as: EmptyResult.self)
            pane.disconnect()
            sessions.removeAll { $0.id == pane.id && $0.host == pane.host }
        } catch { message = error.localizedDescription }
    }
}

@MainActor @Observable
final class TerminalPane: NSObject, Identifiable, @preconcurrency TerminalViewDelegate {
    var info: TerminalSessionInfo
    let host: String
    nonisolated let id: String
    var error: String?
    var connected = false
    @ObservationIgnored let view: TerminalView
    @ObservationIgnored private weak var model: AppModel?
    @ObservationIgnored private var cursor = 0
    @ObservationIgnored private var queued = Data()
    @ObservationIgnored private var writer: Task<Void, Never>?
    @ObservationIgnored private var resizer: Task<Void, Never>?
    @ObservationIgnored private var visible = false
    @ObservationIgnored private var columns = 110
    @ObservationIgnored private var rows = 32

    init(info: TerminalSessionInfo, host: String, model: AppModel) {
        self.info = info; self.id = info.id; self.host = host; self.model = model
        view = TerminalView(frame: NSRect(x: 0, y: 0, width: 900, height: 500),
                            font: .monospacedSystemFont(ofSize: 13, weight: .regular),
                            options: TerminalOptions(cols: info.cols, rows: info.rows, scrollback: 5000))
        super.init()
        view.nativeBackgroundColor = NSColor(calibratedRed: 0.075, green: 0.083, blue: 0.09, alpha: 1)
        view.nativeForegroundColor = NSColor(calibratedWhite: 0.91, alpha: 1)
        view.caretColor = NSColor(calibratedRed: 0.94, green: 0.58, blue: 0.35, alpha: 1)
        view.terminalDelegate = self
        view.setAccessibilityLabel("\(info.title) terminal in \(info.path)")
    }

    func poll() async {
        guard let model else { return }
        visible = true; error = nil
        defer { visible = false; connected = false }
        resize()
        while !Task.isCancelled && host == model.terminalHost {
            do {
                let output = try await model.terminalCall("terminal.read", ["workspaceId": info.workspaceId,
                    "id": id, "cursor": cursor], host: host, as: TerminalOutput.self)
                guard !Task.isCancelled else { return }
                connected = true
                if output.dropped {
                    view.feed(text: "\r\n[Older terminal output was trimmed while this tab was away.]\r\n")
                }
                if let data = Data(base64Encoded: output.data), !data.isEmpty { view.feed(byteArray: Array(data)[...]) }
                cursor = output.cursor; info = output.session
                if output.session.status == "exited" && output.data.isEmpty { return }
                error = nil
            } catch {
                guard !Task.isCancelled else { return }
                connected = false; self.error = error.localizedDescription
                try? await Task.sleep(for: .seconds(2))
            }
        }
    }

    func send(source: TerminalView, data: ArraySlice<UInt8>) { input(Data(data)) }
    func input(_ data: Data) {
        guard visible, connected, info.status == "running", let model, host == model.terminalHost else { return }
        guard queued.count + data.count <= 65536 else { error = "Paste is too large. Send a smaller section."; return }
        queued.append(data)
        guard writer == nil else { return }
        writer = Task { [weak self] in
            guard let self else { return }
            defer { self.writer = nil }
            while !self.queued.isEmpty && !Task.isCancelled {
                let chunk = self.queued.prefix(16384)
                self.queued.removeFirst(chunk.count)
                do {
                    let _: EmptyResult = try await model.terminalCall("terminal.write", ["workspaceId": self.info.workspaceId,
                        "id": self.id, "data": chunk.base64EncodedString(), "requestId": UUID().uuidString], host: self.host, as: EmptyResult.self)
                } catch {
                    self.queued.removeAll()
                    self.error = "Input could not be confirmed. Check the terminal before typing again. " + error.localizedDescription
                    return
                }
            }
        }
    }
    func disconnect() {
        visible = false; connected = false; queued.removeAll()
        writer?.cancel(); resizer?.cancel()
    }
    func sizeChanged(source: TerminalView, newCols: Int, newRows: Int) {
        columns = min(500, max(2, newCols)); rows = min(200, max(2, newRows))
        resize()
    }
    private func resize() {
        guard visible, let model else { return }
        resizer?.cancel()
        resizer = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(100))
            guard let self, !Task.isCancelled else { return }
            do {
                let _: TerminalSessionInfo = try await model.terminalCall("terminal.resize", ["workspaceId": self.info.workspaceId,
                    "id": self.id, "cols": self.columns, "rows": self.rows], host: self.host, as: TerminalSessionInfo.self)
            } catch { if !Task.isCancelled { self.error = error.localizedDescription } }
        }
    }
    func focus() { view.window?.makeFirstResponder(view) }
    func setTerminalTitle(source: TerminalView, title: String) {} // CLI titles never rename a project.
    func hostCurrentDirectoryUpdate(source: TerminalView, directory: String?) {}
    func scrolled(source: TerminalView, position: Double) {}
    func rangeChanged(source: TerminalView, startY: Int, endY: Int) {}
    func clipboardCopy(source: TerminalView, content: Data) {} // Explicit Cmd-C/Cmd-V remains available.
    func clipboardRead(source: TerminalView) -> Data? { nil }
    func requestOpenLink(source: TerminalView, link: String, params: [String: String]) {
        guard let url = URL(string: link), ["https", "http"].contains(url.scheme?.lowercased() ?? "") else { return }
        NSWorkspace.shared.open(url) // SwiftTerm invokes this only for a user click.
    }
}

private struct NativeTerminal: NSViewRepresentable {
    let pane: TerminalPane
    func makeNSView(context: Context) -> TerminalView { pane.view }
    func updateNSView(_ nsView: TerminalView, context: Context) {}
}

struct TerminalWorkspaceView: View {
    @Bindable var model: AppModel
    @State private var retry = 0
    private var workspace: TerminalWorkspace { model.terminalWorkspace }
    private var pane: TerminalPane? { workspace.selected(model) }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Label(model.isRemote ? "Server" : "This Mac", systemImage: model.isRemote ? "server.rack" : "laptopcomputer")
                    .font(StackType.detail.weight(.medium))
                Text(userFacingPath(model.selected?.projectPath ?? pane?.info.path ?? "Project workspace"))
                    .font(.system(size: 12, design: .monospaced)).foregroundStyle(Palette.secondary).lineLimit(1).truncationMode(.middle).textSelection(.enabled)
                Spacer(minLength: 8)
                Menu("Stack commands") {
                    Button("CLI health dashboard") { launch("stack-dashboard") }
                    Button("Manage adapters…") { launch("stack-manage") }
                    Button("Transfer memory…") { launch("stack-transfer") }
                    Divider()
                    Button("Stack status") { launch("stack-status") }
                    Button("Project health") { launch("stack-doctor") }
                    Button("Preview upgrade") { launch("stack-upgrade") }
                    Button("Brain status") { launch("stack-brain") }
                    Divider()
                    ForEach(StackAction.commands.filter { ["setup", "brain-connect", "brain-explore", "brain-log", "brain-health", "brain-mcp", "loop-check", "loop-status", "manifest", "cli-setup"].contains($0.id) }) { action in
                        Button(action.title) { action.perform(model) }
                    }
                }.disabled(workspace.launching || model.selected?.provider != "local")
                Menu {
                    Button("Codex") { launch("codex") }
                    Button("Claude Code") { launch("claude-code") }
                    Button("Shell") { launch("shell") }
                } label: { Label("New terminal", systemImage: "plus") }
                    .disabled(workspace.launching || model.selected?.provider != "local")
                Button { Task { await workspace.refresh(model) }; retry += 1 } label: { Image(systemName: "arrow.clockwise") }.help("Reconnect and refresh terminals")
            }.padding(.horizontal, 24).padding(.vertical, 14)
            if let message = workspace.message {
                Text(message).font(StackType.detail).foregroundStyle(Palette.link).textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal, 24).padding(.bottom, 12)
            }
            if let pane {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(workspace.panes(model)) { tab in
                            HStack(spacing: 12) {
                                Button {
                                    workspace.selections[workspace.key(model)] = tab.id
                                } label: {
                                    HStack(spacing: 7) {
                                        Circle().fill(tab.info.status == "running" ? Palette.link : Palette.secondary).frame(width: 6, height: 6)
                                        Text(tab.info.title).font(StackType.detail.weight(.medium))
                                    }
                                }.buttonStyle(.plain)
                                Button { Task { await workspace.close(tab, model: model) } } label: { Image(systemName: "xmark").font(.system(size: 12, weight: .semibold)) }
                                    .buttonStyle(.plain).help("Close terminal and stop its processes")
                            }.padding(.horizontal, 14).padding(.vertical, 10)
                                .background(tab.id == pane.id ? Palette.surface : Color.clear, in: RoundedRectangle(cornerRadius: 7))
                                .overlay(RoundedRectangle(cornerRadius: 7).stroke(tab.id == pane.id ? Palette.line : .clear))
                        }
                    }.padding(.horizontal, 24).padding(.bottom, 10)
                }
                VStack(spacing: 0) {
                    NativeTerminal(pane: pane).id(pane.id)
                        .task(id: pane.id + String(retry)) { await pane.poll() }
                        .onDisappear { pane.disconnect() }
                    HStack(spacing: 14) {
                        Text(pane.info.status == "exited" ? "Exited · \(pane.info.exitCode ?? 0)" : pane.connected ? "Connected" : "Connecting…")
                            .font(StackType.caption.weight(.medium))
                        if let error = pane.error { Text(error).font(StackType.caption).lineLimit(2).textSelection(.enabled) }
                        Spacer()
                        Button("Focus terminal") { pane.focus() }.buttonStyle(.plain)
                        Button("Interrupt ⌃C") { pane.input(Data([3])); pane.focus() }.buttonStyle(.plain).disabled(!pane.connected || pane.info.status != "running")
                    }.font(StackType.caption).foregroundStyle(Palette.secondary).padding(12).background(Palette.surface)
                }.clipShape(RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Palette.line))
                    .padding(.horizontal, 24).padding(.bottom, 14)
                Text("Terminal sessions use the selected agent’s own permissions. Bounded tasks and saved results are in Tasks.")
                    .font(StackType.caption).foregroundStyle(Palette.secondary).frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 24).padding(.bottom, 18)
            } else {
                VStack(alignment: .leading, spacing: 18) {
                    Text("Terminal").font(StackType.title)
                    Text("Use an agent or shell in this project. Tabs stay open as you move around the app.")
                        .font(StackType.detail).foregroundStyle(Palette.secondary).frame(maxWidth: 440, alignment: .leading)
                    HStack(spacing: 12) {
                        Button("Open Codex", systemImage: "terminal") { launch("codex") }
                        Button("Open Claude Code") { launch("claude-code") }
                        Button("Open shell") { launch("shell") }
                    }.disabled(workspace.launching || model.selected?.provider != "local")
                    if workspace.launching { ProgressView("Opening terminal…").controlSize(.small) }
                    Text(model.isRemote ? "Commands run on the connected server." : "Local terminal processes stop when you quit Agentic Stack.")
                        .font(StackType.caption).foregroundStyle(Palette.secondary)
                    if model.selected?.provider != "local" {
                        Text("Select a local project or connect a hosted stack to use terminals.").foregroundStyle(Palette.link)
                    }
                }.padding(28).frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }

        }.task(id: workspace.key(model)) { await workspace.refresh(model) }
    }
    private func launch(_ kind: String) { Task { await workspace.launch(kind, model: model) } }
}
