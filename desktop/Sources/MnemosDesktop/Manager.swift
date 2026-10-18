import SwiftUI
import AppKit
import UniformTypeIdentifiers
import MnemosKit

@MainActor final class Manager: ObservableObject {
    @Published var runtime: Runtime?
    @Published var setup: Setup?
    @Published var connections: [Connection] = []
    @Published var projects: [Project] = []
    @Published var knowledgeProjects: [KnowledgeProject] = []
    @Published var gitBackup: GitBackupStatus?
    @Published var backups: [BackupRecord] = []
    @Published var busy = false
    @Published var error = ""
    @Published var notice = ""
    @Published var section = "Overview"
    @Published var stale = false
    @Published var author = "Local engineer"
    @Published var assistant = "local"
    @Published var backup = Backup()
    @Published var installObsidian = false
    @Published var mode = "update"
    @Published var target = ""
    @Published var inspected: Setup?
    @Published var installation: String
    let api: LocalAPI
    let port: Int
    let helper: URL
    private let preference: String
    var ownsService: Bool { runtime?.belongs(to: installation) == true && runtime?.stopping == false }
    var ready: Bool { ownsService && setup != nil && !stale }
    var initialized: Bool { ready && setup?.initialized == true }
    var vault: String { (runtime?.data_path ?? "") + "/vault" }

    init() {
        let args = CommandLine.arguments
        func argument(_ name: String) -> String? {
            guard let index = args.firstIndex(of: name), index + 1 < args.count else { return nil }
            return args[index + 1]
        }
        port = Int(argument("--port") ?? "4318").flatMap { (1...65535).contains($0) ? $0 : nil } ?? 4318
        api = LocalAPI(port: port)
        preference = "managed-installation-\(port)"
        let defaultPath = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Mnemos/data/installation.json").path
        installation = argument("--installation") ?? UserDefaults.standard.string(forKey: preference) ?? defaultPath
        helper = Bundle.main.bundleURL.appendingPathComponent("Contents/MacOS/MnemosRuntime")
        api.installation = installation
    }
    func action(_ operation: @escaping () async throws -> Void) {
        guard !busy else { return }
        busy = true; error = ""; notice = ""
        Task {
            defer { busy = false }
            do { try await operation() }
            catch { self.error = error.localizedDescription }
        }
    }
    func refresh() async throws {
        let current = try await api.get("/api/runtime", as: Runtime.self)
        guard current.kind == "mnemos-local-runtime-v1" else { throw LocalError("This port is not running Mnemos.") }
        runtime = current
        guard ownsService else { setup = nil; connections = []; projects = []; knowledgeProjects = []; backups = []; gitBackup = nil; return }
        let settings = try await api.get("/api/setup", as: Setup.self)
        guard settings.workspace_id == current.workspace_id else { stale = true; throw LocalError("The workspace changed while loading. Reload to continue.") }
        setup = settings; author = settings.author; assistant = settings.assistant_mode; backup = settings.backup
        mode = settings.initialized ? "update" : "create"; target = settings.data_path
        inspected = nil; installObsidian = false; stale = false
        connections = []; projects = []; knowledgeProjects = []; backups = []; gitBackup = nil
        if settings.initialized {
            // A secondary panel failing must not prevent access to setup/service controls.
            do {
                connections = try await api.get("/api/connections", as: Connections.self).connections
                let inventory = try await api.get("/api/projects", as: Projects.self)
                projects = inventory.projects; knowledgeProjects = inventory.knowledge_projects ?? []
                gitBackup = try await api.get("/api/git-backup", as: GitBackupStatus.self)
                backups = try await api.get("/api/backups", as: Backups.self).backups
            } catch { self.error = "Workspace loaded. Some details could not load: " + error.localizedDescription }
        } else { section = "Workspace" }
    }
    func poll() async {
        guard !busy else { return }
        do {
            let value = try await api.get("/api/runtime", as: Runtime.self)
            if value.workspace_id != runtime?.workspace_id || value.installation != runtime?.installation {
                stale = true
            }
            runtime = value
            if section == "Backups" && ownsService { gitBackup = try await api.get("/api/git-backup", as: GitBackupStatus.self) }
        } catch { runtime = nil; stale = true }
    }
    func start() async throws {
        let existing = try? await api.get("/api/runtime", as: Runtime.self)
        if let existing {
            runtime = existing
            guard existing.belongs(to: installation) else { throw LocalError("Another Mnemos installation is using this port. Choose Manage this installation to use it, or stop it from its own interface.") }
        }
        guard FileManager.default.isExecutableFile(atPath: helper.path) else {
            throw LocalError("The bundled Mnemos runtime is missing. Build or reinstall the complete macOS app.")
        }
        let process = Process()
        process.executableURL = helper
        process.arguments = ["--tool", "launch", "--background", "--no-browser", "--port", String(port), "--installation", installation]
        let pipe = Pipe(); process.standardOutput = pipe; process.standardError = pipe
        process.standardInput = FileHandle.nullDevice
        // The launcher emits only a bounded status/error line. Never invoke a shell.
        let output: String = try await withCheckedThrowingContinuation { continuation in
            process.terminationHandler = { child in
                let bytes = pipe.fileHandleForReading.readDataToEndOfFile()
                let message = String(data: bytes, encoding: .utf8) ?? ""
                if child.terminationStatus == 0 { continuation.resume(returning: message) }
                else { continuation.resume(throwing: LocalError(message.isEmpty ? "Mnemos could not start." : message)) }
            }
            do { try process.run() } catch { continuation.resume(throwing: error) }
        }
        _ = output
        try await refresh()
    }
    func chooseInstallation() {
        let panel = NSOpenPanel()
        panel.title = "Choose an existing Mnemos installation.json"
        panel.canChooseDirectories = false; panel.canChooseFiles = true
        panel.allowsMultipleSelection = false; panel.allowedContentTypes = [.json]
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard url.lastPathComponent == "installation.json" else {
            error = "Select the installation.json file created by your Mnemos launcher."; return
        }
        installation = url.path; api.installation = url.path
        UserDefaults.standard.set(url.path, forKey: preference)
        runtime = nil; setup = nil; stale = true
        action { try await self.start() }
    }
    func adopt() async throws {
        guard let runtime, runtime.managed, let pointer = runtime.installation,
              pointer.hasPrefix("/"), URL(fileURLWithPath: pointer).lastPathComponent == "installation.json" else {
            throw LocalError("This service has no manageable default installation. Use its original launcher.")
        }
        installation = pointer
        api.installation = pointer
        UserDefaults.standard.set(pointer, forKey: preference)
        try await refresh()
        notice = "Managing the existing installation. Its files and assistant connections stay in place."
    }
    func mutate(_ path: String, _ payload: [String: Any]) async throws -> Data {
        guard ready, let snapshot = setup, let workspace = snapshot.workspace_id else { throw LocalError("Reload this workspace before making changes.") }
        let current = try await api.get("/api/runtime", as: Runtime.self)
        guard current.belongs(to: installation), current.workspace_id == workspace, !current.stopping else {
            stale = true; throw LocalError("The running workspace changed. Reload before continuing.")
        }
        return try await api.data(path, payload: payload, workspace: workspace)
    }
    func stop() async throws {
        guard runtime?.managed == true else { throw LocalError("Stop this service using its original launcher.") }
        _ = try await mutate("/api/runtime/stop", [:])
        runtime = nil; setup = nil; stale = true
        notice = "Local service stopped. Notes are safe; separate assistants and tunnels keep running."
    }
    func inspect() async throws {
        guard let setup else { return }
        let payload: [String: Any] = ["data_path": target,
            "expected_workspace": ["data_path": setup.data_path, "revision": setup.workspace_id ?? ""],
            "expected_settings_revision": setup.settings_revision]
        let bytes = try await mutate("/api/setup/inspect", payload)
        inspected = try JSONDecoder().decode(Inspection.self, from: bytes).workspace
    }
    func save() async throws {
        guard let setup else { return }
        let payload = try setup.payload(mode: mode, path: target, author: author, assistant: assistant,
                                        backup: backup, installObsidian: installObsidian, inspected: inspected)
        let bytes = try await mutate("/api/setup", payload)
        let result = try JSONDecoder().decode(Setup.self, from: bytes)
        try await refresh()
        notice = (["Workspace settings saved."] + (result.warnings ?? [])).joined(separator: " ")
    }
    func backupNow() async throws {
        let bytes: Data
        do { bytes = try await mutate("/api/backups", [:]) }
        catch {
            if let history = try? await api.get("/api/backups", as: Backups.self) { backups = history.backups }
            throw error
        }
        let value = try JSONSerialization.jsonObject(with: bytes) as? [String: Any]
        let record = value?["backup"] as? [String: Any]
        backups = try await api.get("/api/backups", as: Backups.self).backups
        notice = record?["status"] as? String == "cloud-failed" ? "Local backup created, but the cloud upload failed. Check rclone and retry." : "Backup completed using the saved destination."
    }
    func setAutomatic(_ project: Project, enabled: Bool) async throws {
        _ = try await mutate("/api/projects/automatic", ["id": project.id, "auto_refresh": enabled])
        try await refresh()
        notice = "Automatic refresh \(enabled ? "enabled" : "disabled") for \(project.name)."
    }
    func test(_ connection: Connection) async throws {
        let bytes = try await mutate("/api/connections/test", ["client": connection.id])
        connections = try JSONDecoder().decode(Connections.self, from: bytes).connections
    }
    var brainURL: URL? {
        guard ownsService, let key = api.localKey else { return nil }
        var url = URLComponents(string: api.base.absoluteString)!
        url.queryItems = [URLQueryItem(name: "embedded", value: "graph")]
        url.fragment = "local-access=" + key + "&route=graph"
        return url.url
    }
    func openWeb(_ route: String = "") {
        guard ownsService, let key = api.localKey else { return }
        let parts = route.split(separator: "#", maxSplits: 1, omittingEmptySubsequences: false)
        let path = parts.first.map(String.init) ?? ""
        let fragment = parts.count > 1 ? String(parts[1]) : ""
        var url = URLComponents(string: api.base.absoluteString + path)!
        url.fragment = "local-access=" + key + "&route=" + fragment
        NSWorkspace.shared.open(url.url!)
    }
    func openVault() {
        var url = URLComponents(); url.scheme = "obsidian"; url.host = "open"
        url.queryItems = [URLQueryItem(name: "path", value: vault)]
        if let target = url.url, !NSWorkspace.shared.open(target) { error = "Obsidian could not open. Install it from Workspace setup, or open the vault folder manually." }
    }
    func chooseFolder(_ selected: (String) -> Void) {
        let panel = NSOpenPanel(); panel.canChooseDirectories = true; panel.canChooseFiles = false
        panel.canCreateDirectories = true; panel.allowsMultipleSelection = false
        panel.prompt = "Choose folder"
        if panel.runModal() == .OK, let url = panel.url { selected(url.path) }
    }
}
