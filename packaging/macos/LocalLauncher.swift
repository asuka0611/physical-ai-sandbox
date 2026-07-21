import Cocoa
import Foundation

private let projectPath = "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
private let appName = "Physical AI Sandbox Launcher"

final class Logger {
    let logDir: URL
    let logFile: URL

    init() throws {
        let home = FileManager.default.homeDirectoryForCurrentUser
        logDir = home.appendingPathComponent("Library/Logs/Physical AI Sandbox Launcher", isDirectory: true)
        try FileManager.default.createDirectory(at: logDir, withIntermediateDirectories: true)
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        logFile = logDir.appendingPathComponent("launcher-\(formatter.string(from: Date())).log")
        let latest = logDir.appendingPathComponent("latest.log")
        try? FileManager.default.removeItem(at: latest)
        try? FileManager.default.createSymbolicLink(at: latest, withDestinationURL: logFile)
        write("[\(Self.timestamp())] launcher requested")
    }

    func write(_ message: String) {
        let line = message + "\n"
        if let data = line.data(using: .utf8) {
            if FileManager.default.fileExists(atPath: logFile.path) {
                if let handle = try? FileHandle(forWritingTo: logFile) {
                    _ = try? handle.seekToEnd()
                    try? handle.write(contentsOf: data)
                    try? handle.close()
                }
            } else {
                try? data.write(to: logFile)
            }
        }
    }

    private static func timestamp() -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return formatter.string(from: Date())
    }
}

final class LauncherApp: NSObject, NSApplicationDelegate {
    private var logger: Logger!
    private var controlPanelProcess: Process?
    private var accessURL: URL?
    private var startedSecurityScope = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        do {
            logger = try Logger()
            try launch()
        } catch {
            showError("起動に失敗しました", error.localizedDescription)
            NSApp.terminate(nil)
        }
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if let process = controlPanelProcess, process.isRunning {
            process.terminate()
        }
        stopSecurityScope()
        return .terminateNow
    }

    private func launch() throws {
        logger.write("project: \(projectPath)")
        guard FileManager.default.fileExists(atPath: projectPath) else {
            throw LauncherError.message("プロジェクトフォルダが見つかりません: \(projectPath)")
        }

        if let existingPID = existingControlPanelPID() {
            writePID(existingPID)
            logger.write("既に起動中です: PID \(existingPID)")
            NSApp.terminate(nil)
            return
        }

        try ensureProjectAccess()
        let uvPath = try findUV()
        logger.write("uv: \(uvPath)")
        try verifyMJPython(uvPath: uvPath)
        try startControlPanel(uvPath: uvPath)
    }

    private func ensureProjectAccess() throws {
        let url = URL(fileURLWithPath: projectPath, isDirectory: true)
        if let bookmarkURL = try restoreBookmarkedProjectURL(expectedURL: url) {
            accessURL = bookmarkURL
            startedSecurityScope = bookmarkURL.startAccessingSecurityScopedResource()
            logger.write("project access: restored bookmark")
            return
        }

        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        let panel = NSOpenPanel()
        panel.title = "プロジェクトフォルダへのアクセス許可"
        panel.message = "Physical AI Sandbox Launcher がローカル開発環境を起動するため、プロジェクトフォルダへのアクセスを許可してください。"
        panel.prompt = "許可"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.directoryURL = url.deletingLastPathComponent()

        guard panel.runModal() == .OK, let selected = panel.url else {
            throw LauncherError.message("プロジェクトフォルダへのアクセスが許可されませんでした。")
        }
        let selectedPath = selected.standardizedFileURL.path
        guard selectedPath == url.standardizedFileURL.path else {
            throw LauncherError.message("指定されたプロジェクトフォルダを選択してください: \(projectPath)")
        }
        accessURL = selected
        startedSecurityScope = selected.startAccessingSecurityScopedResource()
        try saveBookmark(for: selected)
        logger.write("project access: selected by user")
        NSApp.setActivationPolicy(.accessory)
    }

    private func bookmarkFileURL() throws -> URL {
        let base = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Physical AI Sandbox Launcher", isDirectory: true)
        try FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base.appendingPathComponent("project-folder.bookmark")
    }

    private func saveBookmark(for url: URL) throws {
        let data = try url.bookmarkData(options: [.withSecurityScope], includingResourceValuesForKeys: nil, relativeTo: nil)
        try data.write(to: try bookmarkFileURL(), options: .atomic)
    }

    private func restoreBookmarkedProjectURL(expectedURL: URL) throws -> URL? {
        let fileURL = try bookmarkFileURL()
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            return nil
        }
        do {
            let data = try Data(contentsOf: fileURL)
            var stale = false
            let restored = try URL(resolvingBookmarkData: data, options: [.withSecurityScope], relativeTo: nil, bookmarkDataIsStale: &stale)
            if stale || restored.standardizedFileURL.path != expectedURL.standardizedFileURL.path {
                try? FileManager.default.removeItem(at: fileURL)
                return nil
            }
            return restored
        } catch {
            logger?.write("project bookmark ignored: \(error.localizedDescription)")
            try? FileManager.default.removeItem(at: fileURL)
            return nil
        }
    }

    private func findUV() throws -> String {
        let output = try runAndCapture(
            executable: "/bin/zsh",
            arguments: ["-l", "-c", "command -v uv"],
            currentDirectory: URL(fileURLWithPath: "/")
        ).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !output.isEmpty else {
            throw LauncherError.message("uv が見つかりません。uv をインストールし、ログインシェルの PATH から見えるようにしてください。")
        }
        return output
    }

    private func verifyMJPython(uvPath: String) throws {
        _ = try runAndCapture(
            executable: uvPath,
            arguments: ["run", "mjpython", "-c", "import sys; print(sys.executable)"],
            currentDirectory: URL(fileURLWithPath: projectPath, isDirectory: true)
        )
    }

    private func startControlPanel(uvPath: String) throws {
        let logHandle = try FileHandle(forWritingTo: logger.logFile)
        try logHandle.seekToEnd()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: uvPath)
        process.arguments = ["run", "mjpython", "scripts/run_control_panel.py"]
        process.currentDirectoryURL = URL(fileURLWithPath: projectPath, isDirectory: true)
        var environment = ProcessInfo.processInfo.environment
        environment["ApplePersistenceIgnoreState"] = "YES"
        process.environment = environment
        process.standardOutput = logHandle
        process.standardError = logHandle
        process.terminationHandler = { [weak self] child in
            self?.logger.write("Control Panel exited: status \(child.terminationStatus)")
            self?.stopSecurityScope()
            DispatchQueue.main.async {
                NSApp.terminate(nil)
            }
        }

        logger.write("起動コマンド: cd '\(projectPath)' && uv run mjpython scripts/run_control_panel.py")
        try process.run()
        controlPanelProcess = process
        writePID(Int(process.processIdentifier))
        logger.write("起動しました: PID \(process.processIdentifier)")
    }

    private func runAndCapture(executable: String, arguments: [String], currentDirectory: URL) throws -> String {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.currentDirectoryURL = currentDirectory
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        try process.run()
        process.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8) ?? ""
        if process.terminationStatus != 0 {
            logger.write(output.trimmingCharacters(in: .whitespacesAndNewlines))
            throw LauncherError.message(output.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "コマンドが失敗しました: \(executable)" : output)
        }
        return output
    }

    private func existingControlPanelPID() -> Int? {
        let command = "/bin/ps -ax -o pid=,command= | /usr/bin/awk '/[r]un_control_panel.py/ {print $1; exit}'"
        guard let output = try? runAndCapture(
            executable: "/bin/zsh",
            arguments: ["-c", command],
            currentDirectory: URL(fileURLWithPath: "/")
        ) else {
            return nil
        }
        return Int(output.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    private func writePID(_ pid: Int) {
        let pidFile = logger.logDir.appendingPathComponent("control-panel.pid")
        try? "\(pid)\n".write(to: pidFile, atomically: true, encoding: .utf8)
    }

    private func stopSecurityScope() {
        if startedSecurityScope, let accessURL {
            accessURL.stopAccessingSecurityScopedResource()
            startedSecurityScope = false
        }
    }

    private func showError(_ title: String, _ message: String) {
        logger?.write("\(title): \(message)")
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.alertStyle = .critical
        alert.messageText = "Physical AI Sandbox の起動に失敗しました。"
        alert.informativeText = "\(title)\n\n\(message)\n\nログ: \(logger?.logFile.path ?? "未作成")"
        alert.addButton(withTitle: "OK")
        alert.runModal()
    }
}

enum LauncherError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let message):
            return message
        }
    }
}

let app = NSApplication.shared
let delegate = LauncherApp()
app.delegate = delegate
app.run()
