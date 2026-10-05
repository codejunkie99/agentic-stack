import SwiftUI

struct AgentConnectionRows: View {
    @Bindable var model: AppModel
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            ForEach(model.accounts) { account in
                HStack(spacing: 14) {
                    Image(systemName: "terminal").font(.title3).foregroundStyle(Palette.link)
                    VStack(alignment: .leading, spacing: 5) {
                        Text(account.name).font(StackType.heading)
                        Text(account.version.isEmpty ? account.status : account.version).font(StackType.caption).foregroundStyle(Palette.secondary)
                    }
                    Spacer()
                    StatusLabel(title: account.status, active: account.signedIn)
                    if account.installed && !account.signedIn {
                        Button(model.isRemote ? "Sign-in instructions" : "Sign in…") { Task { await model.signIn(account) } }
                    }
                }
            }
            Button("Refresh agents", systemImage: "arrow.clockwise") { Task { await model.refreshAccounts() } }
                .font(StackType.caption).buttonStyle(.plain).foregroundStyle(Palette.secondary)
            Text(model.isRemote ? "These agents and their sign-ins are on the connected server." : "Uses your existing Claude Code and Codex sign-ins. Agent tokens stay with their official CLIs.")
                .font(StackType.caption).foregroundStyle(Palette.secondary)
        }
    }
}

struct StackFileEditor: View {
    @Bindable var model: AppModel
    let path: String
    @Environment(\.dismiss) private var dismiss
    @State private var content = ""
    @State private var digest = ""
    @State private var message = ""
    @State private var saving = false
    @State private var originalContent = ""
    @State private var confirmDiscard = false
    @State private var discardThenReload = false
    @State private var workspaceID: String?
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(path.components(separatedBy: "/").suffix(2).joined(separator: "/")).font(.title2.weight(.semibold))
            Text("Changes are saved in the selected project. Its adapters continue using the same portable stack.").font(StackType.detail).foregroundStyle(Palette.secondary)
            TextEditor(text: $content).accessibilityLabel("File contents").font(.system(.body, design: .monospaced)).padding(8)
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.line)).frame(height: DesktopSizing.sheetHeight(660) - 210)
            if !message.isEmpty { Text(message).foregroundStyle(Palette.link).textSelection(.enabled) }
            HStack {
                Button("Cancel") {
                    if content != originalContent { discardThenReload = false; confirmDiscard = true } else { dismiss() }
                }.keyboardShortcut(.cancelAction)
                Button("Reload") {
                    if content != originalContent { discardThenReload = true; confirmDiscard = true } else { Task { await load() } }
                }.disabled(saving)
                Spacer()
                Button("Save changes") {
                    Task {
                        guard let wid = workspaceID else { return }
                        saving = true
                        defer { saving = false }
                        do {
                            let result: ProjectFile = try await model.call("stack.file", ["workspaceId": wid, "path": path, "content": content, "digest": digest], as: ProjectFile.self)
                            digest = result.digest; dismiss()
                        } catch { message = error.localizedDescription }
                    }
                }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(digest.isEmpty || saving)
            }
        }.padding(28).frame(width: DesktopSizing.sheetWidth(800)).interactiveDismissDisabled(saving || content != originalContent)
            .confirmationDialog("Discard unsaved changes?", isPresented: $confirmDiscard, titleVisibility: .visible) {
                Button("Discard changes", role: .destructive) {
                    if discardThenReload { Task { await load() } } else { dismiss() }
                }
                Button("Keep editing", role: .cancel) {}
            }
            .task { workspaceID = model.selectedID; await load() }
    }
    private func load() async {
        guard let wid = workspaceID else { return }
        do {
            let result: ProjectFile = try await model.call("stack.file", ["workspaceId": wid, "path": path], as: ProjectFile.self)
            content = result.text; originalContent = result.text; digest = result.digest; message = ""
        } catch { message = error.localizedDescription }
    }
}
