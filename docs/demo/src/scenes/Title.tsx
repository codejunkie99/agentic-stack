import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT } from "../tokens";

export const Title: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const sp    = spring({ fps, frame,       config: { damping: 22, stiffness: 90 } });
  const tagSp = spring({ fps, frame: Math.max(0, frame - 45), config: { damping: 22 } });
  const subSp = spring({ fps, frame: Math.max(0, frame - 80), config: { damping: 22 } });

  const fadeIn  = (f: number, a: number, b: number) =>
    interpolate(f, [a, b], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{
      background: COLORS.bg, width: "100%", height: "100%",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      fontFamily: FONT,
    }}>
      {/* Subtle ambient glow behind title */}
      <div style={{
        position: "absolute", width: 600, height: 300, borderRadius: "50%",
        background: "radial-gradient(ellipse, rgba(10,132,255,0.12) 0%, transparent 70%)",
        transform: `translateY(${(1 - sp) * 40}px)`,
      }} />

      <div style={{
        fontSize: 96, fontWeight: 300, color: COLORS.text, letterSpacing: -3,
        opacity: fadeIn(frame, 0, 18), transform: `translateY(${(1 - sp) * 24}px)`,
      }}>
        agentic-stack
      </div>

      <div style={{
        fontSize: 28, fontWeight: 400, color: COLORS.textSecondary,
        marginTop: 20, letterSpacing: 0.3,
        opacity: fadeIn(frame, 45, 68), transform: `translateY(${(1 - tagSp) * 14}px)`,
      }}>
        One brain, many harnesses.
      </div>

      <div style={{
        display: "flex", gap: 32, marginTop: 16,
        opacity: fadeIn(frame, 80, 105), transform: `translateY(${(1 - subSp) * 10}px)`,
      }}>
        {["memory", "skills", "protocols"].map((label) => (
          <div key={label} style={{
            fontSize: 14, color: COLORS.textTertiary, letterSpacing: 2,
            textTransform: "uppercase",
          }}>
            {label}
          </div>
        ))}
      </div>
    </div>
  );
};
