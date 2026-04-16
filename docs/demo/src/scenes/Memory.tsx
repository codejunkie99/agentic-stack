import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT, FONT_MONO } from "../tokens";

const LAYERS = [
  { name: "working/",  file: "WORKSPACE.md",         desc: "Volatile · task-scoped",        color: COLORS.blue   },
  { name: "episodic/", file: "AGENT_LEARNINGS.jsonl", desc: "JSONL log · 90-day window",     color: COLORS.orange },
  { name: "semantic/", file: "LESSONS.md",            desc: "Distilled lessons · permanent", color: COLORS.green  },
  { name: "personal/", file: "PREFERENCES.md",        desc: "User conventions · permanent",  color: COLORS.purple },
];

const Card: React.FC<{ layer: typeof LAYERS[0]; delay: number }> = ({ layer, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sp = spring({ fps, frame: Math.max(0, frame - delay), config: { damping: 20, stiffness: 90 } });
  const op = interpolate(frame, [delay, delay + 18], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{
      background: COLORS.surface, borderRadius: 18, padding: "24px 28px",
      border: `1px solid ${COLORS.border}`, minWidth: 260,
      opacity: op, transform: `translateY(${(1 - sp) * 20}px)`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: layer.color }} />
        <div style={{ fontSize: 18, fontWeight: 500, color: COLORS.text, fontFamily: FONT }}>
          {layer.name}
        </div>
      </div>
      <div style={{ fontSize: 12, color: COLORS.textTertiary, fontFamily: FONT_MONO, marginBottom: 8 }}>
        {layer.file}
      </div>
      <div style={{ fontSize: 14, color: COLORS.textSecondary, fontFamily: FONT }}>
        {layer.desc}
      </div>
    </div>
  );
};

export const Memory: React.FC = () => {
  const frame = useCurrentFrame();
  const labelOp = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  const { fps } = useVideoConfig();
  const formulaSp = spring({ fps, frame: Math.max(0, frame - 165), config: { damping: 22 } });
  const formulaOp = interpolate(frame, [165, 195], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{
      background: COLORS.bg, width: "100%", height: "100%",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      fontFamily: FONT, gap: 24,
    }}>
      <div style={{ fontSize: 13, letterSpacing: 3, color: COLORS.textTertiary, opacity: labelOp }}>
        MEMORY LAYERS
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {LAYERS.map((l, i) => <Card key={l.name} layer={l} delay={26 + i * 32} />)}
      </div>
      <div style={{
        opacity: formulaOp, transform: `translateY(${(1 - formulaSp) * 12}px)`,
        background: COLORS.surface, border: `1px solid ${COLORS.border}`,
        padding: "12px 28px", borderRadius: 12,
      }}>
        <span style={{ fontSize: 13, color: COLORS.textTertiary, fontFamily: FONT_MONO }}>
          salience = age_decay × pain × importance × recurrence
        </span>
      </div>
    </div>
  );
};
