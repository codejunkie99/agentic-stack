import { Composition, Series } from "remotion";
import { Title }        from "./scenes/Title";
import { Architecture } from "./scenes/Architecture";
import { Memory }       from "./scenes/Memory";
import { Skills }       from "./scenes/Skills";
import { DreamCycle }   from "./scenes/DreamCycle";
import { Quickstart }   from "./scenes/Quickstart";
import { Outro }        from "./scenes/Outro";
import { FPS, W, H }   from "./tokens";

// Scene durations in frames @ 30fps
const T_TITLE  = 150;   // 5s
const T_ARCH   = 270;   // 9s
const T_MEM    = 270;   // 9s
const T_SKILLS = 270;   // 9s
const T_DREAM  = 210;   // 7s
const T_QUICK  = 240;   // 8s
const T_OUTRO  = 150;   // 5s
const TOTAL = T_TITLE + T_ARCH + T_MEM + T_SKILLS + T_DREAM + T_QUICK + T_OUTRO; // 1560 = 52s

const Demo: React.FC = () => (
  <Series>
    <Series.Sequence durationInFrames={T_TITLE} ><Title        /></Series.Sequence>
    <Series.Sequence durationInFrames={T_ARCH}  ><Architecture /></Series.Sequence>
    <Series.Sequence durationInFrames={T_MEM}   ><Memory       /></Series.Sequence>
    <Series.Sequence durationInFrames={T_SKILLS}><Skills       /></Series.Sequence>
    <Series.Sequence durationInFrames={T_DREAM} ><DreamCycle   /></Series.Sequence>
    <Series.Sequence durationInFrames={T_QUICK} ><Quickstart   /></Series.Sequence>
    <Series.Sequence durationInFrames={T_OUTRO} ><Outro        /></Series.Sequence>
  </Series>
);

export const RemotionRoot: React.FC = () => (
  <Composition
    id="AgenticStackDemo"
    component={Demo}
    durationInFrames={TOTAL}
    fps={FPS}
    width={W}
    height={H}
  />
);
