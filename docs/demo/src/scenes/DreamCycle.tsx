import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT, FONT_MONO } from "../tokens";

const STEPS = [
  { action: "find patterns",  from: "episodic/",      to: "semantic/",   color: COLORS.green  },
  { action: "decay stale",    from: "episodic/",      to: "archive/",    color: COLORS.orange },
  { action: "git snapshot",   from: ".agent/memory/", to: "autobiography", color: COLORS.blue },
];

const FlowRow: React.FC<{ step: typeof STEPS[0]; delay: number }> = ({ step, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sp = spring({ fps, frame: Math.max(0, frame - delay), config: { damping: 20, stiffness: 90 } });
  const op = interpolate(frame, [delay, delay + 20], [0, 1], { extrapolateRight: "clamp" });
  const lineW = interpolate(sp, [0, 1], [0, 80]);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, opacity: op }}>
      {/* from */}
      <div style={{
        background: COLORS.surface, border: `1px solid ${COLORS.border}`,
        borderRadius: 10, padding: "10px 20px", minWidth: 150, textAlign: "center",
        fontSize: 14, color: COLORS.textSecondary, fontFamily: FONT_MONO,
      }}>
        {step.from}
      </div>
      {/* animated line + arrow */}
      <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
        <div style={{ width: lineW, height: 1, background: step.color }} />
        <div style={{ fontSize: 14, color: step.color, transform: `translateX(${(1 - sp) * -6}px)` }}>›</div>
      </div>
      {/* action badge */}
      <div style={{
        background: `${step.color}18`, border: `1px solid ${step.color}44`,
        borderRadius: 8, padding: "8px 16px", fontSize: 14, color: step.color, fontFamily: FONT,
        transform: `translateX(${(1 - sp) * 20}px)`,
      }}>
        {step.action}
      </div>
      <div style={{ color: COLORS.textTertiary, fontSize: 14 }}>→</div>
      {/* to */}
      <div style={{
        fontSize: 14, color: COLORS.textSecondary, fontFamily: FONT_MONO,
        opacity: interpolate(frame, [delay + 20, delay + 38], [0, 1], { extrapolateRight: "clamp" }),
      }}>
        {step.to}
      </div>
    </div>
  );
};

export const DreamCycle: React.FC = () => {
  const frame = useCurrentFrame();
  const labelOp = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  const { fps } = useVideoConfig();
  const cronSp = spring({ fps, frame: Math.max(0, frame - 175), config: { damping: 22 } });
  const cronOp = interpolate(frame, [175, 205], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{
      background: COLORS.bg, width: "100%", height: "100%",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      fontFamily: FONT, gap: 26,
    }}>
      <div style={{ fontSize: 13, letterSpacing: 3, color: COLORS.textTertiary, opacity: labelOp }}>
        NIGHTLY DREAM CYCLE
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {STEPS.map((s, i) => <FlowRow key={s.action} step={s} delay={30 + i * 55} />)}
      </div>
      <div style={{
        opacity: cronOp, transform: `translateY(${(1 - cronSp) * 10}px)`,
        background: COLORS.surface, border: `1px solid ${COLORS.border}`,
        padding: "12px 28px", borderRadius: 12,
        fontSize: 13, color: COLORS.textTertiary, fontFamily: FONT_MONO,
      }}>
        0 3 * * *  python3 /path/to/.agent/memory/auto_dream.py
      </div>
    </div>
  );
};
