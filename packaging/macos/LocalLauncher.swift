import Cocoa
import Darwin
import Foundation

private let projectPath = "/Users/miyachiasuka/Documents/prog/Physical AI Sandbox"
private let jobLabel = "com.asuka0611.physical-ai-sandbox.control-panel"

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
        guard let data = line.data(using: .utf8) else { return }
        if FileManager.default.fileExists(atPath: logFile.path),
           let handle = try? FileHandle(forWritingTo: logFile) {
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: data)
            try? handle.close()
        } else {
            try? data.write(to: logFile)
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

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        do {
            logger = try Logger()
            try launch()
            NSApp.terminate(nil)
        } catch {
            showError("起動に失敗しました", error.localizedDescription)
            NSApp.terminate(nil)
        }
    }

    private func launch() throws {
        logger.write("project: \(projectPath)")
        guard FileManager.default.fileExists(atPath: projectPath) else {
            throw LauncherError.message("プロジェクトフォルダが見つかりません: \(projectPath)")
        }
        if let existingPID = existingControlPanelPID() {
            writePID(existingPID)
            logger.write("既に起動中です: PID \(existingPID)")
            return
        }
        let uvPath = try findUV()
        logger.write("uv: \(uvPath)")
        cleanupLegacyLaunchAgent()
        try launchControlPanel(uvPath: uvPath)
        guard let pid = waitForControlPanelPID(timeoutSeconds: 10.0) else {
            throw LauncherError.message("Control Panelプロセスを確認できませんでした。ログ: \(logger.logFile.path)")
        }
        writePID(pid)
        logger.write("起動しました: PID \(pid)")
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

    private func launchControlPanel(uvPath: String) throws {
        let command = "cd \(shellQuote(projectPath)) && exec \(shellQuote(uvPath)) run python scripts/run_control_panel.py"
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = ["-l", "-c", command]
        process.currentDirectoryURL = URL(fileURLWithPath: projectPath)
        let handle = try FileHandle(forWritingTo: logger.logFile)
        try handle.seekToEnd()
        process.standardOutput = handle
        process.standardError = handle
        try process.run()
        try? handle.close()
        logger.write("起動コマンド: cd '\(projectPath)' && uv run python scripts/run_control_panel.py")
        logger.write("直接起動しました: launcher child PID \(process.processIdentifier)")
    }

    private func cleanupLegacyLaunchAgent() {
        let plistURL = legacyLaunchAgentURL()
        let domain = "gui/\(getuid())"
        _ = try? runAndCapture(
            executable: "/bin/launchctl",
            arguments: ["bootout", domain, plistURL.path],
            currentDirectory: URL(fileURLWithPath: "/"),
            logFailure: false
        )
    }

    private func legacyLaunchAgentURL() -> URL {
        let supportDir = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/Physical AI Sandbox Launcher", isDirectory: true)
        return supportDir.appendingPathComponent("\(jobLabel).plist")
    }

    private func waitForControlPanelPID(timeoutSeconds: TimeInterval) -> Int? {
        let deadline = Date().addingTimeInterval(timeoutSeconds)
        while Date() < deadline {
            if let pid = existingControlPanelPID() {
                return pid
            }
            Thread.sleep(forTimeInterval: 0.2)
        }
        return nil
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

    private func runAndCapture(
        executable: String,
        arguments: [String],
        currentDirectory: URL,
        logFailure: Bool = true
    ) throws -> String {
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
            let trimmed = output.trimmingCharacters(in: .whitespacesAndNewlines)
            if logFailure, !trimmed.isEmpty {
                logger.write(trimmed)
            }
            throw LauncherError.message(trimmed.isEmpty ? "コマンドが失敗しました: \(executable)" : output)
        }
        return output
    }

    private func writePID(_ pid: Int) {
        let pidFile = logger.logDir.appendingPathComponent("control-panel.pid")
        try? "\(pid)\n".write(to: pidFile, atomically: true, encoding: .utf8)
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

private func shellQuote(_ value: String) -> String {
    return "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
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
