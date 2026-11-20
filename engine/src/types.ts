// Shared types for timeline.json (projects/<name>/timeline.json) and the design system.
// All times on the OUTPUT timeline are in seconds unless the field ends in Ms.

export type Transition = 'cut' | 'whip' | 'flash' | 'fade' | 'zoom';

export type Segment = {
  id: string;
  src: string; // path relative to the project public dir, e.g. "media/clip01.mp4"
  srcIn: number; // seconds in source
  srcOut: number; // seconds in source
  srcW: number;
  srcH: number;
  zoom?: number; // 1 = cover fit, >1 = punch-in
  focusX?: number; // 0..1 horizontal focal point for 9:16 reframing
  focusY?: number; // 0..1 vertical focal point
  drift?: boolean; // slow push-in across the shot
  transitionIn?: Transition;
  note?: string; // editor note (why this cut exists)
  words?: SrcWord[]; // spoken words inside [srcIn, srcOut], SOURCE seconds; captions are derived from these
};

export type SrcWord = {text: string; start: number; end: number; emphasis?: boolean};

// Overlay/SFX timing: absolute output seconds, or relative to a segment's start when `seg` is set.
export type Anchor = {seg?: string};

export type Word = {
  text: string;
  startMs: number; // output timeline
  endMs: number;
  emphasis?: boolean;
};

export type Overlay = Anchor & (
  | {id: string; type: 'hookTitle'; start: number; end: number; text: string; highlight?: string[]}
  | {id: string; type: 'keyword'; start: number; end: number; text: string; yPercent?: number}
  | {id: string; type: 'broll'; start: number; end: number; src: string; mode?: 'full' | 'card'; srcIn?: number; isImage?: boolean}
  | {id: string; type: 'lowerThird'; start: number; end: number; text: string; sub?: string}
  | {id: string; type: 'clip'; start: number; end: number; src: string} // pre-rendered motion graphic (e.g. HyperFrames), alpha supported via webm/prores
);

export type Sfx = Anchor & {at: number; src: string; volume?: number};

export type Timeline = {
  version: 1;
  title?: string;
  segments: Segment[];
  extraWords?: Word[]; // optional captions not tied to a segment (output ms)
  overlays: Overlay[];
  sfx: Sfx[];
  music?: {src: string; volume?: number; duckTo?: number; startOffset?: number} | null;
};

export type Style = {
  name: string;
  canvas: {width: number; height: number; fps: number};
  safeZone: {top: number; bottom: number; left: number; right: number};
  colors: Record<string, string>;
  typography: {
    captionFont: string;
    captionWeight: string;
    titleFont: string;
    titleWeight: string;
    bodyFont: string;
    bodyWeight: string;
  };
  captions: {
    enabled: boolean;
    yPercent: number;
    fontSize: number;
    maxWordsPerPage: number;
    pageBreakGapMs: number;
    uppercase: boolean;
    strokeWidth: number;
    activeColor: string;
    emphasisColor: string;
    activeScale: number;
    entrance: 'pop' | 'slide' | 'none';
    behindSubject: boolean;
  };
  zoom: {punchInScale: number; alternatePunchIns: boolean; drift: number; hookScale: number};
  transitions: {default: Transition; accent: Transition; accentDurationFrames: number};
  titles: {hookTitle: boolean; hookDurationSec: number; hookYPercent: number; hookFontSize: number; keywordFontSize: number};
  progressBar: {enabled: boolean; height: number};
  audio: {musicVolume: number; musicDuckTo: number; sfxVolume: number};
};

export type EditProps = {timeline: Timeline; style: Style};

export const color = (style: Style, key: string) => style.colors[key] ?? key;
