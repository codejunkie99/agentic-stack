import SwiftUI

/// Public status contains no credentials. Setup sends the key only to the selected host.
struct JevProviderStatus: Decodable, Sendable {
    let enabled: Bool
    let configured: Bool
    let consent: Bool?
    let available: Bool?
    let model: String?
    var isAvailable: Bool { available == true && enabled && configured && consent == true }
    var description: String {
        if isAvailable { return "Configured · Hosted processing enabled" }
        if !configured { return "Not connected · Add a TypeSafe key" }
        if !enabled { return "Disabled · Reconnect to enable Jev" }
        if consent != true { return "Hosted processing permission required" }
        return "Unavailable · Check provider settings"
    }
    static func fixture(_ name: String) -> JevProviderStatus? {
        if name.hasSuffix("checking") { return nil }
        let missing = name.hasSuffix("missing"), disabled = name.hasSuffix("disabled")
        return JevProviderStatus(enabled: !missing && !disabled, configured: !missing,
            consent: !missing, available: !missing && !disabled, model: "jev")
    }
}

enum JevProviderModes {
    static func allows(_ mode: String, available: Bool) -> Bool {
        available || !["fast", "standard", "jev-fast", "jev"].contains(mode)
    }
    static func shows(_ mode: String, selected: String, available: Bool) -> Bool {
        allows(mode, available: available) || selected == mode
    }
}

struct JevProviderSettingsView: View {
    @Bindable var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var token = ""
    @State private var consent = false
    @State private var busy = false
    @State private var message = ""
    @State private var generation = 0

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(model.currentJevProviderStatus?.configured == true ? "Change TypeSafe key" : "Connect Jev").font(StackType.title)
            Text(model.jevProviderStatusMessage).font(StackType.caption).foregroundStyle(Palette.secondary)
            Text("Desktop and connected agents share this setting on the selected host.").foregroundStyle(Palette.secondary)
            SecureField("TypeSafe API key", text: $token).textFieldStyle(.roundedBorder)
                .disabled(busy || !model.hostReady)
            Text("Enter a new key to connect or replace the saved key. The saved key is never displayed. It is stored in an owner-only file on this host.").font(StackType.caption).foregroundStyle(Palette.secondary)
            Toggle("Allow hosted memory processing", isOn: $consent).disabled(busy || !model.hostReady)
            Text("Selected task queries, memory claims, evidence passages, and source metadata may be sent to api.typesafe.ai. Jev recommends changes; applying them still requires review. This permission covers projects on this host.").font(StackType.detail).foregroundStyle(Palette.secondary)
            if !message.isEmpty { Text(message).font(StackType.detail).textSelection(.enabled) }
            HStack {
                Button("Cancel") { dismiss() }.disabled(busy)
                if model.currentJevProviderStatus?.configured == true {
                    Button("Disconnect", role: .destructive) { Task { await configure(disconnect: true) } }.disabled(busy || !model.hostReady || model.jevProviderFixture != nil)
                }
                Spacer()
                if busy { ProgressView().controlSize(.small) }
                Button(model.currentJevProviderStatus?.configured == true ? "Save and enable Jev" : "Enable Jev") { Task { await configure(disconnect: false) } }
                    .buttonStyle(.borderedProminent)
                    .disabled(busy || !consent || token.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || !model.hostReady || model.jevProviderFixture != nil)
            }
        }.padding(24).frame(width: 560).interactiveDismissDisabled(busy)
            .task(id: model.jevProviderHostKey) {
                generation += 1; token = ""; consent = false; message = ""; busy = false
                await model.refreshJevProviderStatus()
            }
            .onDisappear { token = ""; consent = false; generation += 1 }
    }

    private func configure(disconnect: Bool) async {
        guard model.hostReady, model.jevProviderFixture == nil else { return }
        let key = model.jevProviderHostKey, host = model.terminalHost, request = generation
        busy = true; message = ""
        do {
            let params: [String: Any] = disconnect ? [:] : ["token": token.trimmingCharacters(in: .whitespacesAndNewlines), "enabled": true, "consent": consent]
            let status = try await model.terminalCall(disconnect ? "memory.provider.disconnect" : "memory.provider.configure", params, host: host, as: JevProviderStatus.self)
            guard !Task.isCancelled, key == model.jevProviderHostKey, request == generation else { return }
            token = ""; model.acceptJevProviderStatus(status, key: key); busy = false; dismiss()
        } catch {
            guard !Task.isCancelled, key == model.jevProviderHostKey, request == generation else { return }
            token = ""; message = "Provider update failed. Re-enter the key to retry."; busy = false
            await model.refreshJevProviderStatus()
        }
    }
}
