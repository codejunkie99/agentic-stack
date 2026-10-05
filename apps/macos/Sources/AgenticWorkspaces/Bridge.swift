import Foundation

private final class NoRedirects: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping @Sendable (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}

actor Bridge {
    private var process: Process?
    private var endpoint: URL?
    private let token = UUID().uuidString + UUID().uuidString
    private var startup: Task<URL, Error>?
    private var serverCredential: (URL, String)?
    private let session = URLSession(configuration: .ephemeral, delegate: NoRedirects(), delegateQueue: nil)

    static func serverEndpoint(_ value: String) throws -> URL {
        guard var parts = URLComponents(string: value.trimmingCharacters(in: .whitespacesAndNewlines)),
              let host = parts.host, !host.isEmpty, parts.user == nil, parts.password == nil,
              parts.query == nil, parts.fragment == nil,
              ["", "/", "/rpc"].contains(parts.path),
              parts.scheme == "https" || (parts.scheme == "http" && ["localhost", "127.0.0.1", "[::1]"].contains(host)) else {
            throw BridgeError(message: "Enter an HTTPS server address, such as https://stack.example.com. HTTP is allowed only for a localhost SSH tunnel.")
        }
        parts.path = "/rpc"
        guard let url = parts.url else { throw BridgeError(message: "Invalid server address.") }
        return url
    }

    func probe(_ url: String, credential: String) async throws -> Snapshot {
        guard credential.count >= 32 else { throw BridgeError(message: "Enter the server's control token (at least 32 characters).") }
        return try await send(endpoint: Self.serverEndpoint(url), credential: credential,
                              body: Data("{\"method\":\"snapshot\",\"params\":{}}".utf8), as: Snapshot.self)
    }

    func useServerCredential(_ url: String, credential: String) throws {
        serverCredential = (try Self.serverEndpoint(url), credential)
    }

    func start() async throws -> URL {
        if let endpoint, process?.isRunning == true { return endpoint }
        if let startup { return try await startup.value }
        let task = Task { try await self.launch() }
        startup = task
        defer { startup = nil }
        let url = try await task.value
        endpoint = url
        return url
    }

    private func launch() async throws -> URL {
        let env = ProcessInfo.processInfo.environment
        let packaged = Bundle.main.resourceURL?.appending(path: "agentic-stack")
        var developmentRoots = [URL(fileURLWithPath: FileManager.default.currentDirectoryPath)]
        if var candidate = Bundle.main.executableURL?.deletingLastPathComponent() {
            for _ in 0..<8 {
                developmentRoots.append(candidate)
                candidate.deleteLastPathComponent()
            }
        }
        let sourceRoot = developmentRoots.first {
            FileManager.default.fileExists(atPath: $0.appending(path: "harness_manager/workspaces/server.py").path)
        }
        let root = env["AGENTIC_STACK_ROOT"].map { URL(fileURLWithPath: $0) }
            ?? ((packaged.map { FileManager.default.fileExists(atPath: $0.path) } == true) ? packaged! : sourceRoot)
        guard let root else {
            throw BridgeError(message: "The workspace service was not found. Set AGENTIC_STACK_ROOT when running an unpackaged development build.")
        }
        let support = env["AGENTIC_WORKSPACES_DATA"].map { URL(fileURLWithPath: $0) }
            ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appending(path: "Agentic Workspaces")
        try FileManager.default.createDirectory(at: support, withIntermediateDirectories: true)
        let portFile = FileManager.default.temporaryDirectory.appending(path: "agentic-port-\(UUID().uuidString).json")
        try Data().write(to: portFile)
        let output = try FileHandle(forWritingTo: portFile)
        defer { try? output.close(); try? FileManager.default.removeItem(at: portFile) }
        let python = Bundle.main.resourceURL?.appending(path: "python/bin/python3")
        let child = Process()
        if let python, FileManager.default.isExecutableFile(atPath: python.path) {
            child.executableURL = python
            child.arguments = ["-m", "harness_manager.workspaces.server"]
        } else {
            child.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            child.arguments = ["python3", "-m", "harness_manager.workspaces.server"]
        }
        child.arguments! += ["--data-root", support.path, "--parent-pid", String(ProcessInfo.processInfo.processIdentifier)]
        child.currentDirectoryURL = root
        var childEnv = env
        childEnv["AGENTIC_CONTROL_TOKEN"] = token
        childEnv["PYTHONPATH"] = root.path
        childEnv["PYTHONDONTWRITEBYTECODE"] = "1"
        childEnv["PATH"] = FileManager.default.homeDirectoryForCurrentUser.appending(path: ".local/bin").path + ":/opt/homebrew/bin:/usr/local/bin:" + (env["PATH"] ?? "/usr/bin:/bin")
        child.environment = childEnv
        child.standardOutput = output
        child.standardError = FileHandle.nullDevice
        try child.run()
        process = child
        // A large imported library can need time to migrate on its first launch.
        for _ in 0..<600 {
            if let data = try? Data(contentsOf: portFile),
               let hello = try? JSONDecoder().decode([String: Int].self, from: data),
               let port = hello["port"], (1...65535).contains(port) {
                return URL(string: "http://127.0.0.1:\(port)/rpc")!
            }
            guard child.isRunning else {
                throw BridgeError(message: "The workspace service could not start. Another copy may be running, or Python is unavailable.")
            }
            try await Task.sleep(for: .milliseconds(100))
        }
        child.terminate()
        throw BridgeError(message: "The workspace service did not start within 60 seconds. Try reopening the app.")
    }

    func call<T: Decodable & Sendable>(_ method: String, body: Data, as type: T.Type, expectedHost: String? = nil) async throws -> T {
        let remote = UserDefaults.standard.bool(forKey: "serverEnabled")
        let address = UserDefaults.standard.string(forKey: "serverURL") ?? ""
        let identity = remote ? address : "local"
        if let expectedHost, expectedHost != identity {
            throw BridgeError(message: "The connected host changed. Return to this terminal's host to continue.")
        }
        if remote {
            let endpoint = try Self.serverEndpoint(address)
            let credential: String
            if let cached = serverCredential, cached.0 == endpoint { credential = cached.1 }
            else {
                credential = try await Keychain.read("stack-server")
                guard !credential.isEmpty else { throw BridgeError(message: "Enter the server token in Hosting, or select Use this Mac.") }
                serverCredential = (endpoint, credential)
            }
            return try await send(endpoint: endpoint, credential: credential, body: body, as: type)
        }
        return try await send(endpoint: start(), credential: token, body: body, as: type)
    }

    private func send<T: Decodable & Sendable>(endpoint: URL, credential: String, body: Data, as type: T.Type) async throws -> T {
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.httpBody = body
        request.timeoutInterval = 75
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer " + credential, forHTTPHeaderField: "Authorization")
        let (data, responseInfo) = try await session.data(for: request)
        if let http = responseInfo as? HTTPURLResponse, (300...399).contains(http.statusCode) {
            throw BridgeError(message: "Server redirects are not followed. Use the final HTTPS server address.")
        }
        if let http = responseInfo as? HTTPURLResponse, http.statusCode == 401 {
            throw BridgeError(message: "The server rejected this control token.")
        }
        let response = try JSONDecoder().decode(RPCEnvelope<T>.self, from: data)
        guard response.ok, let result = response.result else {
            throw BridgeError(message: response.error ?? "The request did not complete.")
        }
        return result
    }

    func stop() {
        if process?.isRunning == true { process?.terminate() }
        process = nil
        endpoint = nil
    }

    func restart() async {
        startup?.cancel()
        startup = nil
        let previous = process
        if previous?.isRunning == true { previous?.terminate() }
        for _ in 0..<40 where previous?.isRunning == true {
            try? await Task.sleep(for: .milliseconds(50))
        }
        process = nil
        endpoint = nil
    }
}
