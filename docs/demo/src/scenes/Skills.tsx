import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { COLORS, FONT, FONT_MONO } from "../tokens";

const SKILLS = [
  { name: "skillforge",         trigger: "new pattern detected"          },
  { name: "memory-manager",     trigger: "reflect · review · compress"   },
  { name: "git-proxy",          trigger: "git · commit · push · branch"  },
  { name: "debug-investigator", trigger: "bug · error · broken · failing" },
  { name: "deploy-checklist",   trigger: "deploy · release · prod · ship" },
];

const Row: React.FC<{ skill: typeof SKILLS[0]; delay: number; active: boolean }> = ({ skill, delay, active }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sp = spring({ fps, frame: Math.max(0, frame - delay), config: { damping: 20, stiffness: 90 } });
  const op = interpolate(frame, [delay, delay + 16], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{
      opacity: op, transform: `translateX(${(1 - sp) * -28}px)`,
      display: "flex", alignItems: "center", gap: 0, borderRadius: 12,
      padding: "11px 20px",
      background: active ? COLORS.surfaceBright : "transparent",
      border: `1px solid ${active ? COLORS.borderBright : "transparent"}`,
    }}>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: COLORS.blue, marginRight: 16, opacity: active ? 1 : 0.3 }} />
      <div style={{ fontSize: 16, fontWeight: 500, color: COLORS.text, fontFamily: FONT, width: 220 }}>{skill.name}</div>
      <div style={{ fontSize: 13, color: COLORS.textTertiary, fontFamily: FONT }}>
        {skill.trigger}
      </div>
    </div>
  );
};

export const Skills: React.FC = () => {
  const frame = useCurrentFrame();
  const labelOp = interpolate(frame, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  const headerOp = interpolate(frame, [10, 28], [0, 1], { extrapolateRight: "clamp" });
  const { fps } = useVideoConfig();
  const footerSp = spring({ fps, frame: Math.max(0, frame - 195), config: { damping: 22 } });
  const footerOp = interpolate(frame, [195, 225], [0, 1], { extrapolateRight: "clamp" });

  return (
    <div style={{
      background: COLORS.bg, width: "100%", height: "100%",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      fontFamily: FONT, gap: 10,
    }}>
      <div style={{ fontSize: 13, letterSpacing: 3, color: COLORS.textTertiary, opacity: labelOp, marginBottom: 4 }}>SEED SKILLS</div>
      <div style={{ display: "flex", gap: 24, opacity: headerOp, fontSize: 13, marginBottom: 8 }}>
        <span style={{ color: COLORS.green, fontFamily: FONT_MONO }}>_manifest.jsonl</span>
        <span style={{ color: COLORS.textTertiary }}>always loaded</span>
        <span style={{ color: COLORS.textTertiary }}>·</span>
        <span style={{ color: COLORS.blue, fontFamily: FONT_MONO }}>SKILL.md</span>
        <span style={{ color: COLORS.textTertiary }}>on trigger match</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2, width: 680 }}>
        {SKILLS.map((s, i) => (
          <Row key={s.name} skill={s} delay={36 + i * 24} active={i === 2 && frame > 188} />
        ))}
      </div>
      <div style={{
        opacity: footerOp, transform: `translateY(${(1 - footerSp) * 10}px)`, marginTop: 10,
        background: COLORS.surface, border: `1px solid ${COLORS.border}`,
        padding: "11px 26px", borderRadius: 12, fontSize: 13, color: COLORS.textTertiary, fontFamily: FONT_MONO,
      }}>
        on_failure: 3+ failures in 14 days → flagged for self-rewrite
      </div>
    </div>
  );
};
