import SwiftUI
import WebKit

/// The local knowledge graph shares the authenticated portal; no remote chat UI is embedded.
struct KnowledgeBrainView: NSViewRepresentable {
    let url: URL
    func makeCoordinator() -> Coordinator { Coordinator() }
    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = context.coordinator
        return view
    }
    func updateNSView(_ view: WKWebView, context: Context) {
        guard context.coordinator.loaded != url else { return }
        context.coordinator.loaded = url
        view.load(URLRequest(url: url))
    }
    final class Coordinator: NSObject, WKNavigationDelegate {
        var loaded: URL?
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let target = navigationAction.request.url, let allowed = loaded,
                  target.scheme == "http", target.host == "127.0.0.1", target.port == allowed.port else {
                decisionHandler(.cancel); return
            }
            decisionHandler(.allow)
        }
    }
}
