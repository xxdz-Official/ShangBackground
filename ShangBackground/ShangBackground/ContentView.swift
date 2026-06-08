//
//  ContentView.swift
//  ShangBackground
//
//  Created by hjy_666 on 2026/5/8.
//

import SwiftUI
import AppKit

let pythonScriptPath: String = {
    if let path = Bundle.main.path(forResource: "main", ofType: "py") {
        return path
    }
    return "/Users/zhuangweiwei/ShangBackground/src/main.py"
}()

let pythonHomeDir: String = {
    if let path = Bundle.main.resourcePath {
        return path
    }
    return "/Users/zhuangweiwei/ShangBackground/src"
}()

struct WallpaperConfig: Identifiable, Codable {
    var id: String { mode }
    var mode: String
    var slideFolder: String
    var slideSeconds: Int
    var shuffle: Bool
    var fitMode: String
    var solidColor: String
    var gradientColor2: String
    var gradientAngle: Int

    enum CodingKeys: String, CodingKey {
        case mode = "mode"
        case slideFolder = "slide_folder"
        case slideSeconds = "slide_seconds"
        case shuffle = "shuffle"
        case fitMode = "fit_mode"
        case solidColor = "solid_color"
        case gradientColor2 = "gradient_color2"
        case gradientAngle = "gradient_angle"
    }
}

struct ContentView: View {
    @State private var config: WallpaperConfig?
    @State private var isSlideshowRunning = false
    @State private var selectedTab = 0
    @State private var customSolidColor = Color(hex: "#4facfe")
    @State private var customColorHex = "#4facfe"
    @State private var slideFolder = ""
    @State private var slideInterval = 300
    @State private var fitMode = "填充"
    @State private var shuffle = false
    @State private var currentMode = "幻灯片放映"
    @State private var autoStart = false

    var body: some View {
        TabView(selection: $selectedTab) {
            controlTab
                .tabItem {
                    Label("控制", systemImage: "play.circle")
                }
                .tag(0)

            solidColorTab
                .tabItem {
                    Label("纯色", systemImage: "paintbrush")
                }
                .tag(1)

            gradientTab
                .tabItem {
                    Label("渐变", systemImage: "paintbrush.fill")
                }
                .tag(2)

            settingsTab
                .tabItem {
                    Label("设置", systemImage: "gear")
                }
                .tag(3)
        }
        .frame(minWidth: 380, minHeight: 320)
        .onAppear {
            refreshConfig()
        }
    }

    var controlTab: some View {
        VStack(spacing: 10) {
            if let logoImage = NSImage(named: "文字logo.png") {
                Image(nsImage: logoImage)
                    .resizable()
                    .scaledToFit()
                    .frame(height: 50)
            } else if let logoImage = NSImage(named: "LOGO.png") {
                Image(nsImage: logoImage)
                    .resizable()
                    .scaledToFit()
                    .frame(height: 50)
            } else {
                Image(systemName: "photo.on.rectangle.angled")
                    .font(.system(size: 40))
                    .foregroundStyle(.tint)
            }

            HStack(spacing: 25) {
                Button(action: { callPython(["--action", "previous"]) }) {
                    VStack {
                        Image(systemName: "backward.fill")
                            .font(.title2)
                        Text("上一张")
                            .font(.caption)
                    }
                }
                .buttonStyle(.bordered)

                Button(action: { callPython(["--action", "random"]) }) {
                    VStack {
                        Image(systemName: "shuffle")
                            .font(.title2)
                        Text("随机")
                            .font(.caption)
                    }
                }
                .buttonStyle(.borderedProminent)

                Button(action: { callPython(["--action", "next"]) }) {
                    VStack {
                        Image(systemName: "forward.fill")
                            .font(.title2)
                        Text("下一张")
                            .font(.caption)
                    }
                }
                .buttonStyle(.bordered)
            }

            Divider()
                .padding(.horizontal, 40)

            HStack {
                Text("幻灯片")
                    .font(.headline)
                Spacer()
                Toggle("", isOn: $isSlideshowRunning)
                    .onChange(of: isSlideshowRunning) { newValue in
                        let action = newValue ? "start_slideshow" : "stop_slideshow"
                        callPython(["--action", action])
                    }
            }
            .padding(.horizontal, 40)
        }
        .padding()
    }

    var solidColorTab: some View {
        VStack(spacing: 20) {
            Text("纯色壁纸")
                .font(.headline)

            let colors: [(String, Color)] = [
                ("#4facfe", .blue),
                ("#00f2fe", .cyan),
                ("#43e97b", .green),
                ("#fa709a", .pink),
                ("#fee140", .yellow),
                ("#a8edea", .mint),
                ("#ffecd2", .orange),
                ("#667eea", .purple)
            ]

            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 4), spacing: 12) {
                ForEach(colors, id: \.0) { hex, color in
                    Button(action: {
                        callPython(["--action", "set_solid", "--color", hex])
                    }) {
                        RoundedRectangle(cornerRadius: 8)
                            .fill(color)
                            .frame(height: 45)
                            .overlay(
                                Text(hex)
                                    .font(.caption2)
                                    .foregroundColor(.white)
                            )
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal)

            Divider()
                .padding(.horizontal, 20)

            VStack(spacing: 10) {
                Text("自定义颜色")
                    .font(.subheadline)

                HStack {
                    RoundedRectangle(cornerRadius: 6)
                        .fill(customSolidColor)
                        .frame(width: 40, height: 30)
                        .overlay(
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(Color.gray.opacity(0.5), lineWidth: 1)
                        )

                    TextField("Hex 颜色", text: $customColorHex)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 100)
                        .onSubmit {
                            customSolidColor = Color(hex: customColorHex)
                        }

                    Button("应用") {
                        callPython(["--action", "set_solid", "--color", customColorHex])
                    }
                    .buttonStyle(.bordered)
                }
            }
            .padding()
        }
    }

    var gradientTab: some View {
        VStack(spacing: 20) {
            Text("渐变壁纸")
                .font(.headline)

            let gradients: [([String], String)] = [
                (["#4facfe", "#00f2fe"], "蓝天"),
                (["#43e97b", "#38f9d7"], "翠绿"),
                (["#fa709a", "#fee140"], "日出"),
                (["#667eea", "#764ba2"], "紫霞"),
                (["#ff9a9e", "#fecfef"], "粉红"),
                (["#a18cd1", "#fbc2eb"], "梦幻")
            ]

            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 2), spacing: 12) {
                ForEach(gradients.indices, id: \.self) { index in
                    let (colors, name) = gradients[index]
                    Button(action: {
                        callPython(["--action", "set_gradient", "--color1", colors[0], "--color2", colors[1], "--angle", "60"])
                    }) {
                        LinearGradient(
                            colors: [Color(hex: colors[0]), Color(hex: colors[1])],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                        .frame(height: 55)
                        .cornerRadius(10)
                        .overlay(
                            Text(name)
                                .font(.subheadline)
                                .foregroundColor(.white)
                        )
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal)
        }
    }

    var settingsTab: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Group {
                    Text("模式")
                        .font(.headline)
                    
                    Picker("模式", selection: $currentMode) {
                        Text("幻灯片放映").tag("幻灯片放映")
                        Text("单一图片").tag("单一图片")
                        Text("纯色").tag("纯色")
                        Text("渐变").tag("渐变")
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: currentMode) { newValue in
                        callPython(["--action", "set_mode", "--mode", newValue])
                    }

                    Divider()

                    Text("幻灯片设置")
                        .font(.headline)
                    
                    HStack {
                        Text("文件夹:")
                        TextField("选择文件夹", text: $slideFolder)
                            .textFieldStyle(.roundedBorder)
                        Button("浏览") {
                            selectFolder()
                        }
                    }

                    HStack {
                        Text("间隔(秒):")
                        TextField("", value: $slideInterval, format: .number)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 60)
                        Button("应用") {
                            callPython(["--action", "set_interval", "--interval", String(slideInterval)])
                        }
                    }

                    Toggle("随机顺序", isOn: $shuffle)
                        .onChange(of: shuffle) { newValue in
                            callPython(["--action", "set_shuffle", "--shuffle", newValue ? "true" : "false"])
                        }
                }

                Divider()

                Group {
                    Text("显示设置")
                        .font(.headline)
                    
                    Picker("适应模式", selection: $fitMode) {
                        Text("填充").tag("填充")
                        Text("适应").tag("适应")
                        Text("拉伸").tag("拉伸")
                        Text("居中").tag("居中")
                        Text("平铺").tag("平铺")
                    }
                    .onChange(of: fitMode) { newValue in
                        callPython(["--action", "set_fit_mode", "--fit", newValue])
                    }
                }

                Divider()

                Group {
                    Text("系统")
                        .font(.headline)
                    
                    Toggle("开机启动", isOn: $autoStart)
                        .onChange(of: autoStart) { newValue in
                            if newValue {
                                enableAutoStart()
                            } else {
                                disableAutoStart()
                            }
                        }
                }

                Divider()

                HStack {
                    Button("刷新配置") {
                        refreshConfig()
                    }
                    .buttonStyle(.bordered)

                    Button("打开图片文件夹") {
                        NSWorkspace.shared.open(URL(fileURLWithPath: "/Users/zhuangweiwei/ShangBackground/img"))
                    }
                    .buttonStyle(.bordered)
                }

                Divider()

                VStack(spacing: 8) {
                    Text("上一个桌面背景")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Button("GitHub") {
                        NSWorkspace.shared.open(URL(string: "https://github.com/xxdz-Official/ShangBackground")!)
                    }
                    .buttonStyle(.link)
                    .font(.caption)
                }
                .frame(maxWidth: .infinity)
            }
            .padding()
        }
    }

    func selectFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url {
            slideFolder = url.path
            callPython(["--action", "set_folder", "--folder", url.path])
        }
    }

    func refreshConfig() {
        let result = callPythonSync(["--action", "get_config"])
        if let data = result.data(using: .utf8) {
            let decoder = JSONDecoder()
            if let cfg = try? decoder.decode(WallpaperConfig.self, from: data) {
                config = cfg
                slideFolder = cfg.slideFolder
                slideInterval = cfg.slideSeconds
                fitMode = cfg.fitMode
                shuffle = cfg.shuffle
                currentMode = cfg.mode
            }
        }
        autoStart = checkAutoStart()
    }

    func checkAutoStart() -> Bool {
        let plistPath = NSHomeDirectory() + "/Library/LaunchAgents/org.dcstudio.ShangBackground.plist"
        return FileManager.default.fileExists(atPath: plistPath)
    }

    func enableAutoStart() {
        let appPath = Bundle.main.bundlePath
        let plistContent = """
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key>
            <string>org.dcstudio.ShangBackground</string>
            <key>ProgramArguments</key>
            <array>
                <string>\(appPath)</string>
            </array>
            <key>RunAtLoad</key>
            <true/>
        </dict>
        </plist>
        """
        let plistPath = NSHomeDirectory() + "/Library/LaunchAgents"
        try? FileManager.default.createDirectory(atPath: plistPath, withIntermediateDirectories: true)
        let fullPath = plistPath + "/org.dcstudio.ShangBackground.plist"
        try? plistContent.write(toFile: fullPath, atomically: true, encoding: .utf8)
        
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        process.arguments = ["load", fullPath]
        try? process.run()
    }

    func disableAutoStart() {
        let plistPath = NSHomeDirectory() + "/Library/LaunchAgents/org.dcstudio.ShangBackground.plist"
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        process.arguments = ["unload", plistPath]
        try? process.run()
        try? FileManager.default.removeItem(atPath: plistPath)
    }
}

func callPython(_ args: [String]) {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/local/bin/python3")
    var allArgs = [pythonScriptPath] + args
    process.arguments = allArgs
    process.currentDirectoryURL = URL(fileURLWithPath: pythonHomeDir)

    var env = ProcessInfo.processInfo.environment
    env["PYTHONPATH"] = pythonHomeDir
    process.environment = env

    let outPipe = Pipe()
    let errPipe = Pipe()
    process.standardOutput = outPipe
    process.standardError = errPipe

    do {
        try process.run()
        process.waitUntilExit()
        
        let outData = outPipe.fileHandleForReading.readDataToEndOfFile()
        let errData = errPipe.fileHandleForReading.readDataToEndOfFile()
        if let out = String(data: outData, encoding: .utf8), !out.isEmpty {
            print("Python out: \(out)")
        }
        if let err = String(data: errData, encoding: .utf8), !err.isEmpty {
            print("Python err: \(err)")
        }
    } catch {
        print("Failed to run Python: \(error)")
    }
}

func callPythonSync(_ args: [String]) -> String {
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/local/bin/python3")
    process.arguments = [pythonScriptPath] + args
    process.currentDirectoryURL = URL(fileURLWithPath: pythonHomeDir)

    var env = ProcessInfo.processInfo.environment
    env["PYTHONPATH"] = pythonHomeDir
    process.environment = env

    let pipe = Pipe()
    process.standardOutput = pipe
    process.standardError = pipe

    do {
        try process.run()
        process.waitUntilExit()

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let result = String(data: data, encoding: .utf8) ?? ""
        print("Python result: \(result)")
        return result
    } catch {
        print("Python error: \(error)")
        return "{}"
    }
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
    }
}

@main
struct ShangBackgroundApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @State private var showMainWindow = false

    var body: some Scene {
        Window("上一个桌面背景", id: "main") {
            ContentView()
                .frame(width: 380, height: 320)
                .onAppear {
                    NSApp.setActivationPolicy(.regular)
                }
        }
        .defaultSize(width: 380, height: 320)
        .windowResizability(.contentSize)

        MenuBarExtra("壁纸", systemImage: "photo.on.rectangle") {
            Button("上一张") {
                callPython(["--action", "previous"])
            }
            Button("随机") {
                callPython(["--action", "random"])
            }
            Button("下一张") {
                callPython(["--action", "next"])
            }

            Divider()

            Menu("纯色") {
                Button("蓝色") { callPython(["--action", "set_solid", "--color", "#4facfe"]) }
                Button("青色") { callPython(["--action", "set_solid", "--color", "#00f2fe"]) }
                Button("绿色") { callPython(["--action", "set_solid", "--color", "#43e97b"]) }
                Button("粉色") { callPython(["--action", "set_solid", "--color", "#fa709a"]) }
                Button("黄色") { callPython(["--action", "set_solid", "--color", "#fee140"]) }
                Button("紫色") { callPython(["--action", "set_solid", "--color", "#667eea"]) }
            }

            Menu("渐变") {
                Button("蓝天") { callPython(["--action", "set_gradient", "--color1", "#4facfe", "--color2", "#00f2fe", "--angle", "60"]) }
                Button("翠绿") { callPython(["--action", "set_gradient", "--color1", "#43e97b", "--color2", "#38f9d7", "--angle", "60"]) }
                Button("紫霞") { callPython(["--action", "set_gradient", "--color1", "#667eea", "--color2", "#764ba2", "--angle", "60"]) }
                Button("日出") { callPython(["--action", "set_gradient", "--color1", "#fa709a", "--color2", "#fee140", "--angle", "60"]) }
            }

            Divider()

            Button("打开主窗口") {
                DispatchQueue.main.async {
                    NSApp.windows.first?.makeKeyAndOrderFront(nil)
                    NSApp.activate(ignoringOtherApps: true)
                }
            }

            Divider()

            Button("退出") {
                NSApp.terminate(nil)
            }
        }
    }
}