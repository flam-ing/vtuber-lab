import Cocoa
import WebKit

class AppDelegate: NSObject, NSApplicationDelegate, WKUIDelegate {
    var window: NSWindow!
    var webView: WKWebView!

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Hide from Dock so it runs as a clean floating overlay
        NSApp.setActivationPolicy(.accessory)

        let windowWidth: CGFloat = 350
        let windowHeight: CGFloat = 350
        
        let screenRect = NSScreen.main?.visibleFrame ?? NSRect(x: 0, y: 0, width: 800, height: 600)
        let windowRect = NSRect(
            x: screenRect.maxX - windowWidth - 50,
            y: screenRect.minY + 50,
            width: windowWidth,
            height: windowHeight
        )

        window = NSWindow(
            contentRect: windowRect,
            styleMask: [.borderless, .resizable],
            backing: .buffered,
            defer: false
        )

        // Make NSWindow style properties transparent & always-on-top
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = false
        window.level = .floating // Keep floating on top of all other windows
        window.isMovableByWindowBackground = true // Drag window by clicking anywhere
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]

        let configuration = WKWebViewConfiguration()
        configuration.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")
        
        // Setup WebView with transparent background
        webView = WKWebView(frame: window.contentView!.bounds, configuration: configuration)
        webView.uiDelegate = self
        webView.autoresizingMask = [.width, .height]
        webView.setValue(false, forKey: "drawsBackground")
        
        window.contentView?.addSubview(webView)

        let currentDir = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        let htmlFile = currentDir.appendingPathComponent("index.html")
        webView.loadFileURL(htmlFile, allowingReadAccessTo: currentDir)

        window.makeKeyAndOrderFront(nil)
    }

    // Automatically grant media/microphone capture permissions inside WebKit
    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin, initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(.grant)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
