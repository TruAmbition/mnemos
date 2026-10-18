// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "MnemosDesktop", platforms: [.macOS(.v13)],
    products: [.executable(name: "MnemosManager", targets: ["MnemosDesktop"])],
    targets: [.target(name: "MnemosKit"),
              .executableTarget(name: "MnemosDesktop", dependencies: ["MnemosKit"]),
              .testTarget(name: "MnemosKitTests", dependencies: ["MnemosKit"])])
