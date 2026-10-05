import Foundation
import Sparkle

@MainActor
final class AppUpdater {
    private let controller: SPUStandardUpdaterController

    init() {
        controller = SPUStandardUpdaterController(
            startingUpdater: Bundle.main.object(forInfoDictionaryKey: "SUFeedURL") != nil && !ProcessInfo.processInfo.arguments.contains("--jev-ui-fixture") && !ProcessInfo.processInfo.arguments.contains("--jev-search-fixture"),
            updaterDelegate: nil,
            userDriverDelegate: nil
        )
    }

    func checkForUpdates() {
        guard Bundle.main.object(forInfoDictionaryKey: "SUFeedURL") != nil else { return }
        controller.checkForUpdates(nil)
    }
}
