import Foundation

// Run: swiftc apps/macos/Sources/AgenticWorkspaces/SpotlightSearchRules.swift tests/SpotlightSearchCheck.swift -o /tmp/spotlight-check && /tmp/spotlight-check
@main enum SpotlightSearchCheck {
    static func main() {
        assert(SpotlightSearchRules.score("ship", title: "Ship")! > SpotlightSearchRules.score("ship", title: "Shipping launch")!)
        assert(SpotlightSearchRules.score("shipping", title: "Shipping launch")! > SpotlightSearchRules.score("shipping", title: "Prepare launch", detail: "Shipping soon")!)
        assert(SpotlightSearchRules.score("routing codex", title: "Codex", detail: "Model routing") != nil)
        assert(SpotlightSearchRules.score("routing codex", title: "Codex", detail: "Memory only") == nil)
        assert(SpotlightSearchRules.score("cafe", title: "Café") == 100)
        assert(SpotlightSearchRules.score("  ", title: "Anything") == 0)
        assert(SpotlightSearchRules.moving("c", in: ["a", "b", "c"], by: 1) == "a")
        assert(SpotlightSearchRules.moving("a", in: ["a", "b", "c"], by: -1) == "c")
        assert(SpotlightSearchRules.moving(nil, in: [], by: 1) == nil)
        assert(SpotlightSearchRules.moving("removed", in: ["a", "b"], by: 1) == "a")
        let excerpt = SpotlightSearchRules.excerpt(String(repeating: "before ", count: 50) + "needle" + String(repeating: " after", count: 50), query: "needle", limit: 100)
        assert(excerpt.contains("needle") && excerpt.hasPrefix("…") && excerpt.count <= 102)
        assert(SpotlightSearchRules.excerpt("Hello\n  world", query: "") == "Hello world")
        assert(SpotlightSearchRules.conversationQuery("@Codex Fix Launch").agent == "codex")
        assert(SpotlightSearchRules.conversationQuery("@Codex Fix Launch").query == "Fix Launch")
        assert(SpotlightSearchRules.conversationQuery("Claude Code Memory").agent == "claude-code")
        assert(SpotlightSearchRules.conversationQuery("Claude Code Memory").query == "Memory")
        assert(SpotlightSearchRules.conversationQuery("@cursor").query.isEmpty)
        assert(SpotlightSearchRules.conversationQuery("open code").agent == "opencode")
        assert(SpotlightSearchRules.conversationQuery("CodexSomething").agent.isEmpty)
        assert(SpotlightSearchRules.conversationQuery("How does Codex work").query == "How does Codex work")
        print("Spotlight search rules: 20 checks passed")
    }
}
