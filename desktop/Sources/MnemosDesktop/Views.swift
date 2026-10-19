import SwiftUI
import AppKit
import MnemosKit

struct ManagerView: View {
    @ObservedObject var model: Manager
    private let sections = [("Overview", "square.grid.2x2"), ("Knowledge brain", "brain"), ("Workspace", "folder"),
                            ("Backups", "externaldrive.badge.timemachine"), ("Projects", "point.3.connected.trianglepath.dotted"),
                            ("Assistants", "sparkles")]
    @State private var confirmStop = false
    @State private var confirmSwitch = false
    var body: some View {
        NavigationSplitView {
            VStack(alignment: .leading, spacing: 24) {
                HStack(spacing: 12) {
                    Image(nsImage: NSApplication.shared.applicationIconImage).resizable().frame(width: 46, height: 46)
                    VStack(alignment: .leading) {
                        Text("MNEMOS").font(.system(size: 19, weight: .bold, design: .rounded)).tracking(2)
                        Text("Local workspace").font(.caption).foregroundStyle(.secondary)
                    }
                }.padding(.top, 22).padding(.horizontal, 16)
                List(selection: $model.section) {
                    ForEach(sections, id: \.0) { item in Label(item.0, systemImage: item.1).tag(item.0).padding(.vertical, 6) }
                }.listStyle(.sidebar)
                VStack(alignment: .leading, spacing: 9) {
                    Label(model.ownsService ? "Local service running" : "Service not connected", systemImage: "circle.fill")
                        .font(.caption).foregroundStyle(model.ownsService ? Color.cyan : Color.secondary)
                }.padding(18)
            }.background(Color(red: 0.055, green: 0.075, blue: 0.14)).preferredColorScheme(.dark)
            .navigationSplitViewColumnWidth(240)
        } detail: {
            VStack(spacing: 0) {
                HStack {
                    Text(model.section).font(.headline)
                    Spacer()
                    if model.busy { ProgressView().controlSize(.small); Text("Working…").font(.caption).foregroundStyle(.secondary) }
                    Button { model.action { try await model.refresh() } } label: { Image(systemName: "arrow.clockwise") }.help("Reload configuration; replaces unsaved changes").accessibilityLabel("Reload configuration").disabled(model.busy)
                    Button("Open Library") { model.openWeb() }.buttonStyle(.borderedProminent).disabled(!model.ownsService)
                }.padding(22)
                Divider()
                ScrollView {
                    VStack(alignment: .leading, spacing: 22) {
                        if !model.error.isEmpty { banner(model.error, symbol: "exclamationmark.triangle", color: .orange) }
                        if !model.notice.isEmpty { banner(model.notice, symbol: "checkmark.circle", color: .cyan) }
                        if model.stale && model.ownsService { banner("The service or workspace changed. Reload to use the current configuration; unsaved edits will be replaced.", symbol: "arrow.clockwise", color: .orange) }
                        if let runtime = model.runtime, !model.ownsService {
                            foreignService(runtime)
                        } else if model.runtime == nil {
                            stopped
                        } else {
                            switch model.section {
                            case "Workspace": workspace
                            case "Knowledge brain": brain
                            case "Backups": backups
                            case "Projects": projects
                            case "Assistants": assistants
                            default: overview
                            }
                        }
                    }.padding(28).frame(maxWidth: 850, alignment: .leading).frame(maxWidth: .infinity)
                }
            }.background(Color(nsColor: .windowBackgroundColor))
        }
        .confirmationDialog("Stop the local service?", isPresented: $confirmStop, titleVisibility: .visible) {
            Button("Stop local service", role: .destructive) { model.action { try await model.stop() } }
        } message: { Text("Documentation stays on disk. The browser and project refresh pause; separate assistant and tunnel processes keep running.") }
        .confirmationDialog("Activate this workspace?", isPresented: $confirmSwitch, titleVisibility: .visible) {
            Button("Activate workspace") { model.action { try await model.save() } }
        } message: { Text("Only this workspace will be the active default. Existing notes are preserved. Assistant connections pinned to other folders will keep using those folders.") }
    }
    var brain: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let url = model.brainURL {
                KnowledgeBrainView(url: url).frame(minHeight: 720)
            } else {
                Text("Start your local service to explore the knowledge brain.").foregroundStyle(.secondary)
            }
        }
    }
    func banner(_ text: String, symbol: String, color: Color) -> some View {
        Label(text, systemImage: symbol).font(.callout).textSelection(.enabled).padding(14)
            .frame(maxWidth: .infinity, alignment: .leading).background(color.opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
    }
    func heading(_ title: String, _ subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.system(size: 25, weight: .semibold, design: .rounded))
            Text(subtitle).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
        }
    }
    func card<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(title).font(.headline)
            content()
        }.padding(22).frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(nsColor: .controlBackgroundColor), in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(Color.primary.opacity(0.07)))
    }
    var overview: some View {
        VStack(alignment: .leading, spacing: 26) {
            heading("Your workspace", "Open your library to read, capture, or find useful context.")
            card("Active library") {
                HStack {
                    Label(model.setup?.initialized == true ? "Ready" : "Setup needed", systemImage: "checkmark.circle")
                        .foregroundStyle(model.setup?.initialized == true ? Color.cyan : Color.orange)
                    Spacer()
                    Text(model.setup?.author ?? "").foregroundStyle(.secondary)
                }
                HStack(spacing: 12) {
                    Button("Open in Obsidian") { model.openVault() }.disabled(!model.initialized)
                    Button("Workspace settings") { model.section = "Workspace" }
                }
                DisclosureGroup("Location & files") {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(model.runtime?.data_path ?? "").font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                        Button("Show vault in Finder") { NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: model.vault) }.disabled(!model.initialized)
                    }.padding(.top, 12)
                }.font(.callout).foregroundStyle(.secondary)
            }
            VStack(alignment: .leading, spacing: 12) {
                Text("Work with your AI assistant").font(.headline)
                Text("Use ChatGPT, Claude, or a local agent for the work. Bring the useful context and results back to Mnemos.").foregroundStyle(.secondary)
                HStack {
                    Button("Summarize my session") { model.openWeb("/#inbox") }.disabled(!model.initialized)
                    Button("Prepare a handoff") { model.openWeb("/#handoff") }.disabled(!model.initialized)
                    Button("Browse skills") { model.openWeb("/#skills") }.disabled(!model.initialized)
                }
            }.padding(.horizontal, 4)
            Divider()
            DisclosureGroup("Service & installation") {
                VStack(alignment: .leading, spacing: 14) {
                    Text("The local service keeps running when you close this window. Stop it to pause the browser library and automatic project refresh.").foregroundStyle(.secondary)
                    Text(model.installation).font(.system(.caption, design: .monospaced)).foregroundStyle(.secondary).textSelection(.enabled)
                    Button("Stop local service") { confirmStop = true }.disabled(model.busy || !model.ready || model.runtime?.managed != true)
                }.padding(.top, 12)
            }.font(.callout)
            Button("Getting started") { model.openWeb("/#getting-started") }.buttonStyle(.link)
        }
    }
    var stopped: some View {
        VStack(alignment: .leading, spacing: 22) {
            heading("Your notes are still here.", "Start the local service to manage your workspace and open the library.")
            card("Mnemos on this computer") {
                Text(model.installation).font(.system(.callout, design: .monospaced)).textSelection(.enabled)
                Button("Start local service") { model.action { try await model.start() } }.buttonStyle(.borderedProminent).disabled(model.busy)
                Button("Choose existing installation…") { model.chooseInstallation() }.disabled(model.busy)
                Text("If another installation already uses this port, select its installation.json to authenticate locally. Its notes are not moved.").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
    func foreignService(_ runtime: Runtime) -> some View {
        VStack(alignment: .leading, spacing: 22) {
            heading("Mnemos is already running.", "A different installation is using the local port. You can manage it here without moving its files.")
            card("Existing workspace") {
                Text(runtime.data_path).font(.system(.callout, design: .monospaced)).textSelection(.enabled)
                Text("This choice remembers the existing installation for future starts. It does not migrate or retarget assistant connections.").foregroundStyle(.secondary)
                Button("Manage this installation") { model.action { try await model.adopt() } }
                    .buttonStyle(.borderedProminent).disabled(model.busy || runtime.installation == nil || !runtime.managed)
            }
        }
    }
    var workspace: some View {
        VStack(alignment: .leading, spacing: 22) {
            heading("Workspace settings", "One active workspace. Your other libraries stay intact.")
            card("Workspace setup") {
                Picker("Action", selection: $model.mode) {
                    if model.setup?.setup_modes?.contains("update") == true { Text("Update current").tag("update") }
                    if model.setup?.setup_modes?.contains("create") == true { Text("Create new").tag("create") }
                    if model.setup?.setup_modes?.contains("select") == true { Text("Use existing").tag("select") }
                }.pickerStyle(.segmented).labelsHidden()
                    .onChange(of: model.mode) { mode in
                        model.inspected = nil
                        if mode == "update", let setup = model.setup {
                            model.target = setup.data_path; model.author = setup.author
                            model.assistant = setup.assistant_mode; model.backup = setup.backup
                            model.installObsidian = false
                        }
                        else if mode == "select" { model.target = "" }
                        else if model.setup?.initialized == true {
                            model.target = ""; model.backup = Backup(); model.assistant = "local"
                        }
                    }
                folderField("Data folder", value: $model.target, disabled: model.mode == "update")
                    .onChange(of: model.target) { _ in model.inspected = nil }
                if model.mode == "select" {
                    Button("Inspect workspace") { model.action { try await model.inspect() } }.disabled(model.target.isEmpty)
                    if let inspected = model.inspected {
                        Text("Ready to activate · \(inspected.author) · \(inspected.assistant_mode)")
                        Text("Backup: \(inspected.backup.provider == "local" ? inspected.backup.destination : inspected.backup.remote)").font(.caption).textSelection(.enabled)
                    }
                    Text("Selecting an existing workspace loads its saved settings. No notes are merged or copied.").font(.callout).foregroundStyle(.secondary)
                } else {
                    TextField("Author name", text: $model.author).textFieldStyle(.roundedBorder)
                    Picker("Assistant workflow", selection: $model.assistant) {
                        Text("Local tools").tag("local")
                        Text("Cloud file handoff — no tunnel").tag("handoff")
                        Text("Existing direct connection").tag("connected")
                    }
                    Text("This preference does not install skills, authenticate accounts, or start a tunnel. Assistant setup remains an explicit step.").font(.caption).foregroundStyle(.secondary)
                    Divider()
                    if model.mode == "update" {
                        DisclosureGroup("Backup destination") { backupFields.padding(.top, 12) }
                    } else { backupFields }
                    Divider()
                    if model.setup?.obsidian.installed == true { Label("Obsidian is installed", systemImage: "checkmark.circle") }
                    else { Toggle("Install Obsidian when saving", isOn: $model.installObsidian) }
                    Text("Mnemos creates its own vault inside the selected data folder. Choose a folder outside other Obsidian vaults.").font(.caption).foregroundStyle(.secondary)
                }
                HStack {
                    Spacer()
                    Button(model.mode == "update" ? "Save configuration" : "Activate workspace") {
                        if model.mode == "update" { model.action { try await model.save() } }
                        else { confirmSwitch = true }
                    }.buttonStyle(.borderedProminent)
                        .disabled(model.target.isEmpty || (model.mode == "select" && model.inspected == nil))
                }
            }.disabled(model.busy || !model.ready)
            Text("Switching the default preserves your previous workspace. Existing assistant and tunnel connections keep their explicitly configured folders.").font(.callout).foregroundStyle(.secondary)
        }
    }
    func folderField(_ label: String, value: Binding<String>, disabled: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label).font(.callout.weight(.medium))
            HStack {
                TextField("Absolute folder path", text: value).textFieldStyle(.roundedBorder).disabled(disabled)
                Button("Choose…") { model.chooseFolder { value.wrappedValue = $0 } }.disabled(disabled)
            }
        }
    }
    var backupFields: some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("Backup storage", selection: $model.backup.provider) {
                Text("Local folder or drive").tag("local"); Text("Cloud via rclone").tag("rclone")
            }
            folderField(model.backup.provider == "local" ? "Backup folder" : "Local staging folder", value: $model.backup.destination)
            if model.backup.provider == "rclone" {
                TextField("Remote, e.g. drive:Mnemos", text: $model.backup.remote).textFieldStyle(.roundedBorder)
                Text("Configure rclone separately. No cloud credentials are entered here; saving does not test a cloud upload.").font(.caption).foregroundStyle(.secondary)
            }
            Text("Backups run on request. Use a separate device or cloud destination for recovery from a lost workstation.").font(.caption).foregroundStyle(.secondary)
        }
    }
    var backups: some View {
        VStack(alignment: .leading, spacing: 22) {
            heading("Backups", "Keep a recoverable copy of your library.")
            if model.initialized {
                card("Git remote") {
                    HStack {
                        Circle().fill(model.gitBackup?.color == "green" ? Color.green : model.gitBackup?.color == "amber" ? Color.orange : Color.red).frame(width: 12, height: 12)
                        Text(model.gitBackup?.label ?? "Git remote backup not confirmed")
                    }
                    Text("Red: no Git repository or backup needs attention. Amber: local Git only or changes await a push. Green: latest documentation pushed successfully. Local-only use is supported.").font(.caption).foregroundStyle(.secondary)
                    if let pushed = model.gitBackup?.last_push { Text("Last successful push: " + pushed).font(.caption) }
                    Button("Configure Git remote & backup") { model.openWeb("#settings") }
                    Text("Choose or create a dedicated documentation repository, configure its remote, and optionally enable automatic commits and pushes.").font(.caption).foregroundStyle(.secondary)
                }
                card("Complete workspace recovery") {
                    Text("Back up notes, saved skill builds, proposals, and the session inbox. Restore into an inactive workspace with reviewed repository paths.").foregroundStyle(.secondary)
                    Button("Open backup & recovery") { model.openWeb("/#recovery") }
                    Button("Configure local meaning search") { model.openWeb("/#search-settings") }
                }
                card("Saved backup destination") {
                    Text(model.setup?.backup.provider == "local" ? model.setup?.backup.destination ?? "" : model.setup?.backup.remote ?? "").textSelection(.enabled)
                    HStack {
                        Button("Change destination") { model.section = "Workspace" }
                        Button("Back up now") { model.action { try await model.backupNow() } }.buttonStyle(.borderedProminent)
                    }.disabled(model.busy)
                }
                card("Recent backups") {
                    if model.backups.isEmpty { Text("No backups recorded yet.").foregroundStyle(.secondary) }
                    ForEach(Array(model.backups.sorted { $0.created > $1.created }.prefix(8))) { record in
                        VStack(alignment: .leading, spacing: 5) {
                            HStack { Text(record.created); Spacer(); Text(record.status == "complete" ? "Completed" : "Cloud upload failed").foregroundStyle(record.status == "complete" ? Color.secondary : .orange) }
                            if let path = record.path { Text(path).font(.caption).foregroundStyle(.secondary).textSelection(.enabled) }
                        }
                        Divider()
                    }
                }
            } else { Text("Finish Workspace setup to configure backups.") }
        }
    }
    var projects: some View {
        VStack(alignment: .leading, spacing: 22) {
            heading("Projects", "Understand your systems across their apps and services.")
            if model.initialized {
                ForEach(model.knowledgeProjects) { system in
                    card(system.name) {
                        Text(system.purpose).foregroundStyle(.secondary)
                        Label(system.privacyLabel, systemImage: "lock.shield")
                        Button("Privacy & sharing") { model.openWeb("/#privacy") }
                        Text("\(system.repository_ids.count) repositories · \(system.document_count) notes").font(.caption)
                        ForEach(model.projects.filter { system.repository_ids.contains($0.id) }) { repo in
                            Label(repo.name, systemImage: "folder")
                        }
                        Button("Search this project") { model.openWeb("/#library/" + system.id) }
                    }
                }
                if model.knowledgeProjects.isEmpty { Text("Create a top-level project in Library, then assign its repositories. Existing checkouts are preserved.").foregroundStyle(.secondary) }
                Text("Repository refresh").font(.headline)
                if model.projects.isEmpty { card("No repositories connected") { Text("Add an existing local Git checkout in the library to start capturing project context.").foregroundStyle(.secondary) } }
                ForEach(model.projects) { project in
                    card(project.name) {
                        Text(project.path).font(.caption).textSelection(.enabled)
                        Toggle("Automatically refresh when local commits change", isOn: Binding(get: { project.auto_refresh }, set: { enabled in model.action { try await model.setAutomatic(project, enabled: enabled) } }))
                            .disabled(model.busy)
                    }
                }
                Text("Automatic refresh checks local commits about every 60 seconds while the service runs. It does not fetch, pull, or read uncommitted changes.").font(.caption).foregroundStyle(.secondary)
                Button("Add or manage projects in Library") { model.openWeb("/#projects") }
            } else { Text("Finish Workspace setup to connect projects.") }
        }
    }
    var assistants: some View {
        VStack(alignment: .leading, spacing: 22) {
            heading("Assistants", "Use your existing AI workspace alongside Mnemos.")
            DisclosureGroup("How Mnemos works with your assistant") {
                Text("Mnemos stores your documentation. Your existing chat app does the AI work. This is not a chat wrapper.\n\nLocal tools: your assistant uses local skills and the Mnemos runtime.\n\nFile handoff: review and attach a context file in ChatGPT or Claude, then import the returned draft. No inbound access or tunnel is needed.\n\nOptional tunnel: a cloud assistant can call your local tools directly while the tunnel runs. It requires account setup, scoped credentials, a running workstation, and enterprise approval where applicable. Connected tools may access drafts in the selected vault.").foregroundStyle(.secondary)
                Button("Setup instructions and portable skills") { model.openWeb("/setup.html") }
            }
            if model.initialized {
                ForEach(model.connections) { connection in
                    card(connection.name) {
                        Text(connection.status.replacingOccurrences(of: "-", with: " ").capitalized).font(.caption.weight(.semibold))
                        if connection.workspace != nil && connection.matches_active != true {
                            Label("Uses a different workspace", systemImage: "exclamationmark.triangle").font(.caption).foregroundStyle(.orange)
                        }
                        DisclosureGroup("Connection details") {
                            VStack(alignment: .leading, spacing: 10) {
                                Text(connection.detail).foregroundStyle(.secondary)
                                if let path = connection.workspace { Text(path).font(.caption).textSelection(.enabled) }
                            }.padding(.top, 10)
                        }.font(.callout)
                        if connection.testable { Button("Test locally") { model.action { try await model.test(connection) } }.disabled(model.busy) }
                    }
                }
                Text("Local tests do not verify the cloud account connection. Ask your assistant to recall relevant Mnemos context for an end-to-end check.").font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}
