// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "AgenticWorkspaces",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "AgenticWorkspaces", targets: ["AgenticWorkspaces"])],
    dependencies: [
        .package(url: "https://github.com/migueldeicaza/SwiftTerm.git", exact: "1.19.0"),
        .package(url: "https://github.com/sparkle-project/Sparkle", exact: "2.9.6"),
    ],
    targets: [
        .executableTarget(
            name: "AgenticWorkspaces",
            dependencies: [
                "SwiftTerm",
                .product(name: "Sparkle", package: "Sparkle"),
            ],
            linkerSettings: [
                .unsafeFlags([
                    "-Xlinker", "-rpath",
                    "-Xlinker", "@executable_path/../Frameworks",
                ]),
            ]
        )
    ]
)
