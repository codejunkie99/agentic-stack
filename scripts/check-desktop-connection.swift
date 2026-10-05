// Standalone integration check: works with Command Line Tools without XCTest.
import Foundation

@main
struct ConnectionCheck {
    static func main() async throws {
        guard try Bridge.serverEndpoint("https://stack.example.com").absoluteString == "https://stack.example.com/rpc",
              try Bridge.serverEndpoint("http://127.0.0.1:8765/").absoluteString == "http://127.0.0.1:8765/rpc" else {
            throw BridgeError(message: "Endpoint normalization failed")
        }
        for value in ["http://server.example", "http://192.168.1.2:8765", "https://user:password@stack.example.com",
                      "https://stack.example.com/?token=secret", "https://stack.example.com/#token", "file:///tmp/server", "https://stack.example.com/another-service"] {
            var rejected = false
            do { _ = try Bridge.serverEndpoint(value) } catch { rejected = true }
            guard rejected else { throw BridgeError(message: "Unsafe endpoint accepted") }
        }
        let env = ProcessInfo.processInfo.environment
        guard let address = env["STACK_TEST_URL"], let token = env["STACK_TEST_TOKEN"],
              let redirect = env["STACK_TEST_REDIRECT"] else {
            throw BridgeError(message: "Run this check with scripts/check-desktop-connection.py")
        }
        let state = try await Bridge().probe(address, credential: token)
        guard !state.version.isEmpty, !state.dataPath.isEmpty else { throw BridgeError(message: "Hosted snapshot was empty") }
        var authRejected = false
        do { _ = try await Bridge().probe(address, credential: String(repeating: "x", count: 48)) }
        catch { authRejected = error.localizedDescription.contains("rejected this control token") }
        guard authRejected else { throw BridgeError(message: "Authentication failure was not handled") }
        var redirectRejected = false
        do { _ = try await Bridge().probe(redirect, credential: token) }
        catch { redirectRejected = error.localizedDescription.contains("redirects") }
        guard redirectRejected else { throw BridgeError(message: "Redirect was followed") }
        var hostRejected = false
        do {
            let _: EmptyResult = try await Bridge().call("terminal.write", body: Data("{}".utf8), as: EmptyResult.self,
                                                        expectedHost: "https://not-the-connected-host.invalid/")
        } catch { hostRejected = error.localizedDescription.contains("host changed") }
        guard hostRejected else { throw BridgeError(message: "Stale terminal host was accepted") }
        print("PASS: terminal input rejected before transport when its host changed")
        print("PASS: URL validation, authenticated native connection, invalid token, redirect refusal")
    }
}
