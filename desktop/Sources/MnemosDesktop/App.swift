import SwiftUI
import AppKit
import Darwin

// Preserve the original executable's CLI and MCP stdio contract for existing connections.
@main enum Entry {
    static func main() {
        let arguments = CommandLine.arguments
        if ["--tool", "--cli"].contains(arguments.dropFirst().first ?? "") {
            let helper = Bundle.main.bundleURL.appendingPathComponent("Contents/MacOS/MnemosRuntime").path
            let argv = ([helper] + arguments.dropFirst()).map { strdup($0) } + [nil]
            argv.withUnsafeBufferPointer { _ = execv(helper, $0.baseAddress!) }
            fputs("Mnemos runtime could not start. Reinstall the complete app.\n", stderr)
            exit(1)
        }
        MnemosApp.main()
    }
}
struct MnemosApp: App {
    @StateObject private var manager = Manager()
    var body: some Scene {
        Window("Mnemos", id: "manager") {
            ManagerView(model: manager)
                .frame(minWidth: 920, minHeight: 660)
                .tint(Color(red: 0.48, green: 0.35, blue: 0.94))
                .task {
                    manager.action {
                        // Do not start a second installation over an existing local portal.
                        do { try await manager.refresh() }
                        catch { try await manager.start() }
                    }
                    while !Task.isCancelled {
                        try? await Task.sleep(nanoseconds: 5_000_000_000)
                        if Task.isCancelled { break }
                        await manager.poll()
                    }
                }
        }
        .defaultSize(width: 1080, height: 780)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandGroup(after: .appInfo) {
                Button("Open Library") { manager.openWeb() }.keyboardShortcut("l", modifiers: [.command, .shift])
                Button("Reload Configuration") { manager.action { try await manager.refresh() } }.keyboardShortcut("r")
            }
        }
    }
}
