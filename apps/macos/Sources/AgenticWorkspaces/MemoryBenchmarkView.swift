import AppKit
import SwiftUI
import UniformTypeIdentifiers

private struct MemoryBenchmarkReport: Decodable {
    let schema_version: Int
    let dataset_name: String?
    let dataset_input_sha256: String?
    let split: String
    let variant: String
    let network_enabled: Bool
    let quality: Quality
    let timing: Timing
    let limits: [String]
    struct Quality: Decodable {
        let cases: Int
        let failed_cases: Int
        let turn_source_recall: Double?
        let session_recall: Double?
        let integrity_errors: Int
    }
    struct Timing: Decodable {
        let cold: Phase
        let warm: Phase
    }
    struct Phase: Decodable {
        let samples: Int
        let p50_ms: Double?
        let p95_ms: Double?
        let failures: Int
    }
}

struct MemoryBenchmarkView: View {
    @State private var report: MemoryBenchmarkReport?
    @State private var filename = ""
    @State private var error = ""
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Benchmark results").font(StackType.heading)
                Spacer()
                Button("Open report…", systemImage: "doc") { openReport() }
            }
            Text("Retrieval performance and source recall. Answer accuracy is not measured.").font(StackType.detail).foregroundStyle(Palette.secondary)
            if let report {
                Text("\(report.dataset_name ?? "Dataset") · \(report.split) · \(report.variant) · \(report.quality.cases) questions").font(StackType.detail.weight(.medium))
                Grid(alignment: .leading, horizontalSpacing: 24, verticalSpacing: 8) {
                    GridRow { Text("Turn / source recall"); Text(percent(report.quality.turn_source_recall)) }
                    GridRow { Text("Session recall"); Text(percent(report.quality.session_recall)) }
                    GridRow { Text("Fresh retrieval p50 / p95"); Text(latency(report.timing.cold)) }
                    GridRow { Text("Repeated retrieval p50 / p95"); Text(latency(report.timing.warm)) }
                    GridRow { Text("Failed questions / integrity errors"); Text("\(report.quality.failed_cases) / \(report.quality.integrity_errors)") }
                    GridRow { Text("Timing samples / failures"); Text("\(report.timing.cold.samples + report.timing.warm.samples) / \(report.timing.cold.failures + report.timing.warm.failures)") }
                }.font(StackType.detail)
                Divider()
                Text("\(filename) · \(report.network_enabled ? "Network enabled" : "Local only") · schema \(report.schema_version)").font(StackType.caption).foregroundStyle(Palette.secondary).textSelection(.enabled)
                if let digest = report.dataset_input_sha256 { Text("Dataset fingerprint: " + digest).font(.system(.caption2, design: .monospaced)).textSelection(.enabled) }
                ForEach(Array(report.limits.enumerated()), id: \.offset) { _, limit in Text(limit).font(StackType.caption).foregroundStyle(Palette.secondary) }
            } else {
                Text("Open a generated benchmark JSON report to inspect actual measurements.").font(StackType.detail).foregroundStyle(Palette.secondary)
            }
            if !error.isEmpty { Text(error).font(StackType.detail).foregroundStyle(Palette.warning).textSelection(.enabled) }
        }.padding(16).background(Palette.surface, in: RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Palette.line, lineWidth: 1))
    }
    private func percent(_ value: Double?) -> String { value.map { String(format: "%.1f%%", $0 * 100) } ?? "Not measured" }
    private func latency(_ value: MemoryBenchmarkReport.Phase) -> String {
        guard let p50 = value.p50_ms, let p95 = value.p95_ms else { return "Not measured" }
        return String(format: "%.1f / %.1f ms", p50, p95)
    }
    private func openReport() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.json]; panel.allowsMultipleSelection = false; panel.canChooseDirectories = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            guard try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0 <= 16_000_000 else { throw BridgeError(message: "Choose a report smaller than 16 MB.") }
            let data = try Data(contentsOf: url)
            // Comparison files show the measured change report, clearly identified.
            let object = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            let payload = try object?["change"].map { try JSONSerialization.data(withJSONObject: $0) } ?? data
            let decoded = try JSONDecoder().decode(MemoryBenchmarkReport.self, from: payload)
            guard decoded.schema_version == 1 else { throw BridgeError(message: "This report version is not supported.") }
            report = decoded; filename = url.lastPathComponent + (object?["change"] == nil ? "" : " · change result"); error = ""
        } catch { self.error = "Could not open this benchmark report: " + error.localizedDescription }
    }
}
