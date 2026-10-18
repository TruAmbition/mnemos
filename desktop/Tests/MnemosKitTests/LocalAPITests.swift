import XCTest
@testable import MnemosKit

final class LocalAPITests: XCTestCase {
    private func setup(_ path: String = "/work/a", workspace: String? = "session-a") throws -> Setup {
        var value: [String: Any] = ["initialized": true, "data_path": path, "author": "Engineer",
            "assistant_mode": "local", "backup": ["provider": "local", "destination": "/backup", "remote": ""],
            "obsidian": ["installed": true], "settings_revision": "settings-a", "commands": [:]]
        if let workspace { value["workspace_id"] = workspace }
        return try JSONDecoder().decode(Setup.self, from: JSONSerialization.data(withJSONObject: value))
    }
    func testUpdateCarriesBothRevisionGuards() throws {
        let snapshot = try setup()
        let value = try snapshot.payload(mode: "update", path: snapshot.data_path, author: "New author", assistant: "handoff", backup: snapshot.backup, installObsidian: false)
        XCTAssertEqual(value["expected_settings_revision"] as? String, "settings-a")
        XCTAssertEqual((value["expected_workspace"] as? [String: String])?["revision"], "session-a")
        XCTAssertEqual(value["author"] as? String, "New author")
    }
    func testSelectionLoadsTargetSettingsWithoutOverwritingThem() throws {
        let snapshot = try setup(); let target = try setup("/work/b", workspace: nil)
        let value = try snapshot.payload(mode: "select", path: target.data_path, author: "Must not submit", assistant: "connected", backup: snapshot.backup, installObsidian: true, inspected: target)
        XCTAssertEqual(Set(value.keys), ["mode", "data_path", "expected_workspace", "expected_settings_revision", "expected_target_settings_revision"])
        XCTAssertEqual(value["expected_target_settings_revision"] as? String, target.settings_revision)
    }
    func testInspectionMustMatchSelectedPath() throws {
        let snapshot = try setup()
        XCTAssertThrowsError(try snapshot.payload(mode: "select", path: "/work/c", author: "", assistant: "local", backup: snapshot.backup, installObsidian: false, inspected: setup("/work/b")))
    }
    func testRuntimeIdentityIncludesInstallationAndKind() throws {
        let data = Data(#"{"kind":"mnemos-local-runtime-v1","managed":true,"stopping":false,"installation":"/work/installation.json","data_path":"/work/a","workspace_id":"session-a","initialized":true}"#.utf8)
        let runtime = try JSONDecoder().decode(Runtime.self, from: data)
        XCTAssertTrue(runtime.belongs(to: "/work/installation.json"))
        XCTAssertFalse(runtime.belongs(to: "/different/installation.json"))
    }
    func testNoMutationWithoutWorkspaceMarker() async throws {
        let api = LocalAPI(port: 1)
        do { _ = try await api.data("/api/setup", payload: [:]); XCTFail("Must reject locally") }
        catch { XCTAssertTrue(error.localizedDescription.contains("Reload the active workspace")) }
    }
    func testRealServiceLifecycle() async throws {
        guard let text = ProcessInfo.processInfo.environment["MNEMOS_TEST_PORT"], let port = Int(text),
              let root = ProcessInfo.processInfo.environment["MNEMOS_TEST_ROOT"] else {
            throw XCTSkip("Run scripts/test_desktop.py to exercise the real service in an isolated workspace.")
        }
        let api = LocalAPI(port: port)
        let initial = try await api.get("/api/setup", as: Setup.self)
        XCTAssertFalse(initial.initialized)
        func apply(_ snapshot: Setup, mode: String, path: String, inspected: Setup? = nil) async throws -> Setup {
            let payload = try snapshot.payload(mode: mode, path: path, author: "Native test", assistant: "handoff", backup: Backup(), installObsidian: false, inspected: inspected)
            return try JSONDecoder().decode(Setup.self, from: await api.data("/api/setup", payload: payload, workspace: snapshot.workspace_id))
        }
        let first = try await apply(initial, mode: "create", path: root + "/first")
        XCTAssertTrue(first.initialized)
        XCTAssertEqual(first.assistant_mode, "handoff")
        _ = try await api.get("/api/connections", as: Connections.self)
        _ = try await api.get("/api/projects", as: Projects.self)
        _ = try await api.data("/api/backups", payload: [:], workspace: first.workspace_id)
        let backups = try await api.get("/api/backups", as: Backups.self)
        XCTAssertEqual(backups.backups.count, 1)
        XCTAssertEqual(backups.backups.first?.status, "complete")
        let updated = try await apply(first, mode: "update", path: first.data_path)
        let second = try await apply(updated, mode: "create", path: root + "/second")
        XCTAssertNotEqual(first.workspace_id, second.workspace_id)
        do { _ = try await apply(first, mode: "update", path: first.data_path); XCTFail("Stale workspace must fail") }
        catch { XCTAssertTrue(error.localizedDescription.contains("workspace changed")) }
        let inspection = try JSONDecoder().decode(Inspection.self, from: await api.data("/api/setup/inspect", payload: ["data_path": first.data_path,
            "expected_workspace": ["data_path": second.data_path, "revision": second.workspace_id!],
            "expected_settings_revision": second.settings_revision], workspace: second.workspace_id))
        let selected = try await apply(second, mode: "select", path: first.data_path, inspected: inspection.workspace)
        XCTAssertEqual(selected.data_path, first.data_path)
        let restored = try await api.get("/api/backups", as: Backups.self)
        XCTAssertEqual(restored.backups.count, 1)
        _ = try await api.data("/api/runtime/stop", payload: [:], workspace: selected.workspace_id)
    }
}
