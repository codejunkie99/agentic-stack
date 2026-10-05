import Foundation

enum SpotlightSearchRules {
    static func conversationQuery(_ text: String) -> (agent: String, query: String) {
        var value = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if value.hasPrefix("@") { value = String(value.dropFirst()).trimmingCharacters(in: .whitespaces) }
        let normalized = value.lowercased()
        let aliases = [("claude code", "claude-code"), ("open code", "opencode"), ("opencode", "opencode"),
                       ("claude", "claude-code"), ("codex", "codex"), ("cursor", "cursor")]
        for (name, agent) in aliases where normalized == name || normalized.hasPrefix(name + " ") {
            return (agent, String(value.dropFirst(name.count)).trimmingCharacters(in: .whitespaces))
        }
        return ("", value)
    }

    static func score(_ query: String, title: String, detail: String = "") -> Int? {
        let query = query.trimmingCharacters(in: .whitespacesAndNewlines).folding(options: [.caseInsensitive, .diacriticInsensitive], locale: .current)
        guard !query.isEmpty else { return 0 }
        let title = title.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: .current)
        let detail = detail.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: .current)
        let terms = query.split(whereSeparator: \.isWhitespace)
        guard terms.allSatisfy({ title.contains($0) || detail.contains($0) }) else { return nil }
        if title == query { return 100 }
        if title.hasPrefix(query) { return 80 }
        if title.contains(query) { return 60 }
        return terms.reduce(0) { $0 + (title.contains($1) ? 20 : 5) }
    }

    static func excerpt(_ text: String, query: String, limit: Int = 150) -> String {
        let line = text.split(whereSeparator: \.isWhitespace).joined(separator: " ")
        guard line.count > limit else { return line }
        let term = query.split(whereSeparator: \.isWhitespace).first.map(String.init) ?? ""
        let match = term.isEmpty ? nil : line.range(of: term, options: [.caseInsensitive, .diacriticInsensitive])
        let start = match.map { line.index($0.lowerBound, offsetBy: -30, limitedBy: line.startIndex) ?? line.startIndex } ?? line.startIndex
        let end = line.index(start, offsetBy: limit, limitedBy: line.endIndex) ?? line.endIndex
        return (start == line.startIndex ? "" : "…") + line[start..<end] + (end == line.endIndex ? "" : "…")
    }

    static func moving(_ selection: String?, in ids: [String], by offset: Int) -> String? {
        guard !ids.isEmpty else { return nil }
        guard let selection, let index = ids.firstIndex(of: selection) else { return offset < 0 ? ids.last : ids.first }
        return ids[(index + offset % ids.count + ids.count) % ids.count]
    }
}
