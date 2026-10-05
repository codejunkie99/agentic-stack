import Foundation

/// Keeps user-selected project folders available across app launches.
///
/// The Python workspace service starts after these security scopes are restored,
/// so it inherits access to projects selected through NSOpenPanel.
@MainActor
final class ProjectAccess {
    static let shared = ProjectAccess()

    private let defaultsKey = "projectSecurityBookmarks"
    private var active: [String: URL] = [:]

    private init() {}

    func restore() {
        let stored = UserDefaults.standard.dictionary(forKey: defaultsKey) as? [String: String] ?? [:]
        var refreshed = stored
        for (path, encoded) in stored {
            guard let data = Data(base64Encoded: encoded) else {
                refreshed.removeValue(forKey: path)
                continue
            }
            var stale = false
            guard let url = try? URL(
                resolvingBookmarkData: data,
                options: [.withSecurityScope],
                relativeTo: nil,
                bookmarkDataIsStale: &stale
            ) else {
                refreshed.removeValue(forKey: path)
                continue
            }
            _ = url.startAccessingSecurityScopedResource()
            active[url.path] = url
            if stale, let replacement = try? bookmark(for: url) {
                refreshed[url.path] = replacement.base64EncodedString()
                if url.path != path { refreshed.removeValue(forKey: path) }
            }
        }
        UserDefaults.standard.set(refreshed, forKey: defaultsKey)
    }

    func remember(_ url: URL) {
        let resolved = url.standardizedFileURL
        _ = resolved.startAccessingSecurityScopedResource()
        active[resolved.path] = resolved
        guard let data = try? bookmark(for: resolved) else { return }
        var stored = UserDefaults.standard.dictionary(forKey: defaultsKey) as? [String: String] ?? [:]
        stored[resolved.path] = data.base64EncodedString()
        UserDefaults.standard.set(stored, forKey: defaultsKey)
    }

    private func bookmark(for url: URL) throws -> Data {
        try url.bookmarkData(options: [.withSecurityScope], includingResourceValuesForKeys: nil, relativeTo: nil)
    }
}
