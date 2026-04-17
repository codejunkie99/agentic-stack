import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT, FONT_MONO } from "../tokens";

const HARNESSES = ["Claude Code", "Cursor", "Windsurf", "OpenCode", "OpenClaw", "Hermes", "Python"];
const BRAIN_LAYERS = [
  { path: "memory/",    color: COLORS.orange },
  { path: "skills/",    color: COLORS.blue   },
  { path: "protocols/", color: COLORS.green  },
  { path: "tools/",     color: COLORS.purple },
];

const Pill: React.FC<{ label: string; delay: number }> = ({ label, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sp = spring({ fps, frame: Math.max(0, frame - delay), config: { damping: 20, stiffness: 100 } });
  const op = interpolate(frame, [delay, delay + 15], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{
      background: COLORS.surface, border: `1px solid ${COLORS.border}`,
      borderRadius: 10, padding: "9px 22px", color: COLORS.text, fontSize: 15,
      fontFamily: FONT, fontWeight: 400,
      opacity: op, transform: `translateX(${(1 - sp) * -36}px)`,
    }}>
      {label}
    </div>
  );
};

export const Architecture: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const brainSp = spring({ fps, frame: Math.max(0, frame - 20), config: { damping: 20, stiffness: 80 } });

  return (
    <div style={{
      background: COLORS.bg, width: "100%", height: "100%",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: FONT, gap: 48,
    }}>
      {/* Harness column */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {HARNESSES.map((h, i) => <Pill key={h} label={h} delay={i * 13} />)}
      </div>

      {/* Arrow column */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {HARNESSES.map((_, i) => {
          const op = interpolate(frame, [i * 13 + 22, i * 13 + 38], [0, 1], { extrapolateRight: "clamp" });
          return (
            <div key={i} style={{ color: COLORS.blue, fontSize: 16, opacity: op, lineHeight: "38px", letterSpacing: 2 }}>
              ——›
            </div>
          );
        })}
      </div>

      {/* Brain box */}
      <div style={{
        background: COLORS.surface, border: `1px solid ${COLORS.borderBright}`,
        borderRadius: 20, padding: "36px 48px", textAlign: "left", minWidth: 220,
        opacity: brainSp, transform: `scale(${interpolate(brainSp, [0, 1], [0.92, 1])})`,
        boxShadow: `0 0 60px rgba(10,132,255,${0.12 * brainSp})`,
      }}>
        <div style={{ fontSize: 13, color: COLORS.textTertiary, letterSpacing: 2, marginBottom: 18 }}>
          PORTABLE BRAIN
        </div>
        <div style={{ fontSize: 22, fontWeight: 300, color: COLORS.text, fontFamily: FONT_MONO, marginBottom: 22 }}>
          .agent/
        </div>
        {BRAIN_LAYERS.map((l, i) => {
          const op = interpolate(frame, [60 + i * 18, 80 + i * 18], [0, 1], { extrapolateRight: "clamp" });
          return (
            <div key={l.path} style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, opacity: op }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: l.color, flexShrink: 0 }} />
              <div style={{ fontSize: 15, color: COLORS.textSecondary, fontFamily: FONT_MONO }}>{l.path}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
