import { interpolate, useCurrentFrame } from "remotion";
import { COLORS, FONT, FONT_MONO } from "../tokens";

const LINES: Array<{ text: string; color?: string }> = [
  { text: "$ brew tap codejunkie99/agentic-stack \\" },
  { text: "    https://github.com/codejunkie99/agentic-stack", color: COLORS.textTertiary },
  { text: "$ brew install agentic-stack" },
  { text: "" },
  { text: "$ cd your-project" },
  { text: "$ agentic-stack claude-code" },
  { text: "" },
  { text: "  Copying .agent/ brain ...",       color: COLORS.textTertiary },
  { text: "  Installing Claude Code adapter ...", color: COLORS.textTertiary },
  { text: "" },
  { text: "✓  .agent/memory/personal/PREFERENCES.md", color: COLORS.green },
  { text: "✓  .agent/skills/_manifest.jsonl",          color: COLORS.green },
  { text: "✓  CLAUDE.md + .claude/settings.json",      color: COLORS.green },
];

const SPEED = 1.6;

export const Quickstart: React.FC = () => {
  const frame = useCurrentFrame();
  const panelOp = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  let budget = Math.floor(frame * SPEED);

  return (
    <div style={{
      background: COLORS.bg, width: "100%", height: "100%",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      fontFamily: FONT, opacity: panelOp,
    }}>
      <div style={{ fontSize: 13, letterSpacing: 3, color: COLORS.textTertiary, marginBottom: 20 }}>
        QUICKSTART
      </div>
      {/* macOS-style terminal window */}
      <div style={{
        background: "rgba(30,30,30,0.95)", borderRadius: 14, overflow: "hidden",
        border: `1px solid rgba(255,255,255,0.08)`,
        boxShadow: "0 32px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)",
        minWidth: 680,
      }}>
        {/* title bar */}
        <div style={{
          padding: "12px 18px", background: "rgba(255,255,255,0.04)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          {["#FF5F57", "#FFBD2E", "#28C840"].map(c => (
            <div key={c} style={{ width: 12, height: 12, borderRadius: "50%", background: c }} />
          ))}
          <div style={{ flex: 1, textAlign: "center", fontSize: 12, color: COLORS.textTertiary, fontFamily: FONT }}>
            Terminal — zsh
          </div>
        </div>
        {/* terminal body */}
        <div style={{ padding: "22px 28px" }}>
          {LINES.map((line, i) => {
            if (!line.text) { return <div key={i} style={{ height: 10 }} />; }
            const visible = Math.min(line.text.length, Math.max(0, budget));
            budget -= line.text.length;
            const blink = visible < line.text.length && visible > 0 && Math.sin(frame * 0.4) > 0;
            return (
              <div key={i} style={{ color: line.color ?? COLORS.text, fontSize: 15, lineHeight: 1.75, fontFamily: FONT_MONO }}>
                {line.text.slice(0, visible)}
                {blink && <span style={{ color: COLORS.blue }}>█</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
