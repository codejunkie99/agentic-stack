import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT } from "../tokens";

const STATS = [
  { value: "7", label: "harnesses" },
  { value: "6", label: "seed skills" },
  { value: "4", label: "memory layers" },
];

export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn   = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut  = interpolate(frame, [115, 150], [1, 0], { extrapolateLeft: "clamp" });
  const opacity  = fadeIn * fadeOut;

  const headSp   = spring({ fps, frame,       config: { damping: 22, stiffness: 80 } });
  const urlSp    = spring({ fps, frame: Math.max(0, frame - 35), config: { damping: 22 } });
  const statsSp  = spring({ fps, frame: Math.max(0, frame - 65), config: { damping: 22 } });

  const glow = interpolate(frame, [0, 60], [0, 0.18], { extrapolateRight: "clamp" }) * fadeOut;

  return (
    <div style={{
      background: COLORS.bg, width: "100%", height: "100%",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      fontFamily: FONT, opacity,
    }}>
      <div style={{
        position: "absolute", width: 640, height: 320, borderRadius: "50%",
        background: `radial-gradient(ellipse, rgba(10,132,255,${glow}) 0%, transparent 70%)`,
      }} />

      <div style={{ fontSize: 56, fontWeight: 300, color: COLORS.text, textAlign: "center", lineHeight: 1.15,
        transform: `translateY(${(1 - headSp) * 18}px)` }}>
        One brain,{" "}
        <span style={{ color: COLORS.blue }}>many harnesses.</span>
      </div>

      <div style={{ fontSize: 18, color: COLORS.textTertiary, marginTop: 20,
        transform: `translateY(${(1 - urlSp) * 12}px)`,
        opacity: interpolate(frame, [35, 58], [0, 1], { extrapolateRight: "clamp" }) }}>
        github.com/codejunkie99/agentic-stack
      </div>

      {/* Stat pills */}
      <div style={{
        display: "flex", gap: 14, marginTop: 36,
        opacity: interpolate(frame, [65, 88], [0, 1], { extrapolateRight: "clamp" }),
        transform: `translateY(${(1 - statsSp) * 10}px)`,
      }}>
        {STATS.map(s => (
          <div key={s.label} style={{
            background: COLORS.surface, border: `1px solid ${COLORS.border}`,
            borderRadius: 12, padding: "12px 24px", textAlign: "center",
          }}>
            <div style={{ fontSize: 28, fontWeight: 300, color: COLORS.text }}>{s.value}</div>
            <div style={{ fontSize: 12, color: COLORS.textTertiary, marginTop: 4, letterSpacing: 1 }}>{s.label}</div>
          </div>
        ))}
      </div>

      <div style={{ fontSize: 12, color: COLORS.textTertiary, letterSpacing: 3, marginTop: 28,
        opacity: interpolate(frame, [90, 110], [0, 1], { extrapolateRight: "clamp" }) }}>
        v0.3.0 · MIT
      </div>
    </div>
  );
};
