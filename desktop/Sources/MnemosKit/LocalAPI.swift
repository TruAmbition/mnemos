import Foundation

public struct Runtime: Decodable {
    public let kind: String
    public let managed: Bool
    public let stopping: Bool
    public let installation: String?
    public let data_path: String
    public let workspace_id: String
    public let initialized: Bool
    public func belongs(to installation: String) -> Bool {
        kind == "mnemos-local-runtime-v1" && self.installation == installation
    }
}
public struct Backup: Codable, Equatable {
    public var provider: String
    public var destination: String
    public var remote: String
    public init(provider: String = "local", destination: String = "", remote: String = "") {
        self.provider = provider; self.destination = destination; self.remote = remote
    }
}
public struct Obsidian: Decodable { public let installed: Bool }
public struct Setup: Decodable {
    public let initialized: Bool
    public let data_path: String
    public let author: String
    public let assistant_mode: String
    public let backup: Backup
    public let obsidian: Obsidian
    public let workspace_id: String?
    public let settings_revision: String
    public let setup_modes: [String]?
    public let commands: [String: String]
    public let warnings: [String]?

    public func payload(mode: String, path: String, author: String, assistant: String,
                        backup: Backup, installObsidian: Bool, inspected: Setup? = nil) throws -> [String: Any] {
        guard let revision = workspace_id else { throw LocalError("Reload workspace settings first.") }
        var value: [String: Any] = ["mode": mode, "data_path": path,
            "expected_workspace": ["data_path": data_path, "revision": revision],
            "expected_settings_revision": settings_revision]
        if mode == "select" {
            guard let target = inspected, target.data_path == path else {
                throw LocalError("Inspect the selected folder before activating it.")
            }
            value["expected_target_settings_revision"] = target.settings_revision
        } else {
            value["author"] = author; value["assistant_mode"] = assistant
            value["backup"] = ["provider": backup.provider, "destination": backup.destination, "remote": backup.remote]
            value["install_obsidian"] = installObsidian
        }
        return value
    }
}
public struct Inspection: Decodable { public let workspace: Setup }
public struct Connection: Decodable, Identifiable {
    public let id: String; public let name: String; public let status: String
    public let detail: String; public let workspace: String?
    public let matches_active: Bool?; public let testable: Bool
}
public struct Connections: Decodable { public let connections: [Connection] }
public struct Project: Decodable, Identifiable {
    public let id: String; public let name: String; public let path: String; public let auto_refresh: Bool
}
public struct KnowledgeProject: Decodable, Identifiable {
    public let id: String; public let name: String; public let purpose: String
    public let repository_ids: [String]; public let document_count: Int
    public let privacy: String?
    public var privacyLabel: String { privacy == "team" ? "Approved for team sharing" : privacy == "reviewed-ai" ? "Allow reviewed AI sharing" : "Local only" }
}
public struct Projects: Decodable {
    public let projects: [Project]
    public let knowledge_projects: [KnowledgeProject]?
}
public struct Backups: Decodable { public let backups: [BackupRecord] }
public struct BackupRecord: Decodable, Identifiable {
    public var id: String { created + (path ?? "") }
    public let created: String; public let status: String; public let path: String?
}
public struct LocalError: LocalizedError {
    public let message: String
    public init(_ message: String) { self.message = message }
    public var errorDescription: String? { message }
}
private final class NoRedirect: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask,
                    willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest,
                    completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}
public final class LocalAPI {
    public let base: URL
    private let session: URLSession
    public var installation: String?
    public var localKey: String? {
        guard let installation else { return nil }
        let folder = URL(fileURLWithPath: installation).deletingLastPathComponent()
        let path = folder.deletingLastPathComponent().appendingPathComponent(".mnemos-access/\(folder.lastPathComponent)-\(base.port!).key")
        return try? String(contentsOf: path, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
    }
    public init(port: Int) {
        precondition((1...65535).contains(port))
        base = URL(string: "http://127.0.0.1:\(port)")!
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        configuration.timeoutIntervalForRequest = 120
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        session = URLSession(configuration: configuration, delegate: NoRedirect(), delegateQueue: nil)
    }
    public func data(_ path: String, payload: [String: Any]? = nil, workspace: String? = nil) async throws -> Data {
        guard path.hasPrefix("/api/"), !path.contains("?"), !path.contains("#") else { throw LocalError("Invalid local API path.") }
        var request = URLRequest(url: base.appendingPathComponent(String(path.dropFirst())))
        if let key = localKey { request.setValue(key, forHTTPHeaderField: "X-Mnemos-Local-Key") }
        if let payload {
            guard let workspace, !workspace.isEmpty else { throw LocalError("Reload the active workspace before making changes.") }
            request.httpMethod = "POST"
            request.httpBody = try JSONSerialization.data(withJSONObject: payload)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue(workspace, forHTTPHeaderField: "X-Mnemos-Workspace")
        }
        if path == "/api/runtime" { request.timeoutInterval = 2 }
        let (data, response) = try await session.data(for: request)
        guard let response = response as? HTTPURLResponse else { throw LocalError("No response from Mnemos.") }
        guard (200..<300).contains(response.statusCode) else {
            let detail = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            throw LocalError(detail?["error"] as? String ?? "Mnemos returned HTTP \(response.statusCode).")
        }
        return data
    }
    public func get<T: Decodable>(_ path: String, as: T.Type) async throws -> T {
        try JSONDecoder().decode(T.self, from: await data(path))
    }
}
