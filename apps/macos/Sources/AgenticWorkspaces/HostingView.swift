import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct HostingView: View {
    @Bindable var model: AppModel
    @State private var url = ""
    @State private var token = ""
    @State private var connected = false
    @State private var exportMessage: String?
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Server connection").font(StackType.title)
                    Text("Host Agentic Stack on your own server. This desktop becomes its client: projects, installed agents, skills, memory and task history come from the server you connect to.")
                        .foregroundStyle(Palette.secondary).fixedSize(horizontal: false, vertical: true)
                }
                HStack {
                    Label(model.isRemote ? "Connected to \(model.serverURL)" : "Using this Mac", systemImage: model.isRemote ? "server.rack" : "laptopcomputer")
                    Spacer()
                    if model.isRemote { Button("Use this Mac") { Task { await model.useThisMac() } }.disabled(model.busy) }
                }.padding(16).background(Palette.surface, in: RoundedRectangle(cornerRadius: 10))
                VStack(alignment: .leading, spacing: 14) {
                    Text("Connect a server").font(StackType.heading)
                    StackField(title: "Server address", prompt: "https://stack.example.com", text: $url)
                    VStack(alignment: .leading, spacing: 7) {
                        Text("Server control token").font(StackType.detail.weight(.medium))
                        SecureField("Server control token", text: $token).textFieldStyle(.roundedBorder)
                    }
                    Text("The token grants access to this stack and is stored in your Mac’s Keychain. HTTPS is required; localhost HTTP works for an SSH tunnel.")
                        .font(StackType.caption).foregroundStyle(Palette.secondary)
                    HStack {
                        Button("Test and connect", systemImage: "network") {
                            Task { connected = await model.connectServer(url: url, token: token.trimmingCharacters(in: .whitespacesAndNewlines)) }
                        }.buttonStyle(.borderedProminent).tint(Palette.accent).disabled(model.busy || url.isEmpty || token.isEmpty)
                        if model.busy { ProgressView().controlSize(.small) }
                        if connected && model.isRemote { Label("Connected", systemImage: "checkmark.circle").font(StackType.detail) }
                    }
                }
                Divider()
                VStack(alignment: .leading, spacing: 14) {
                    Text("Host Agentic Stack").font(StackType.heading)
                    Text("The repository includes a Docker Compose deployment with persistent storage and automatic HTTPS through Caddy. Deploy it on a server, sign in to the agents there, then connect above.")
                        .foregroundStyle(Palette.secondary)
                    Button("Export server package…", systemImage: "shippingbox") {
                        guard let source = Bundle.main.resourceURL?.appending(path: "Agentic Stack-server.zip"), FileManager.default.fileExists(atPath: source.path) else {
                            exportMessage = "Build a packaged app to include the server archive."; return
                        }
                        let panel = NSSavePanel(); panel.nameFieldStringValue = "Agentic Stack-server.zip"; panel.allowedContentTypes = [.zip]
                        panel.begin { response in
                            guard response == .OK, let target = panel.url else { return }
                            do {
                                try Data(contentsOf: source).write(to: target, options: .atomic)
                                exportMessage = "Server package saved. Unzip it on your server and follow START-HERE.md."
                            } catch { exportMessage = error.localizedDescription }
                        }
                    }
                    if let exportMessage { Text(exportMessage).font(StackType.detail).foregroundStyle(Palette.secondary) }
                    Button("Open hosting guide", systemImage: "book") {
                        if let path = Bundle.main.resourceURL?.appending(path: "Hosting.md") { NSWorkspace.shared.open(path) }
                    }
                    Text("For a private SSH tunnel, run the service on server localhost and forward port 8765. Closing this desktop leaves a hosted service running.")
                        .font(StackType.caption).foregroundStyle(Palette.secondary)
                }
                if let project = model.selected, project.provider == "box" {
                    Divider()
                    Text("Box execution provider").font(StackType.heading)
                    OverviewView(model: model, workspace: project).frame(minHeight: 370)
                }
            }.padding(20).frame(maxWidth: 800, alignment: .leading).frame(maxWidth: .infinity, alignment: .leading)
        }.task {
            url = model.serverURL
            token = (try? await Keychain.read("stack-server")) ?? ""
        }
    }
}
