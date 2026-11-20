import {Audio} from '@remotion/media';
import React from 'react';
import {AbsoluteFill, Sequence, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Captions} from './Captions';
import {OverlayView} from './Overlays';
import {Shot} from './Shot';
import {color, type EditProps, type Word} from './types';

export const segmentFrames = (props: EditProps) => {
  const {fps} = props.style.canvas;
  let from = 0;
  return props.timeline.segments.map((seg) => {
    const dur = Math.max(1, Math.round((seg.srcOut - seg.srcIn) * fps));
    const r = {seg, from, dur};
    from += dur;
    return r;
  });
};

// Flatten per-segment source-time words onto the output timeline (ms).
export const outputWords = (props: EditProps): Word[] => {
  const {fps} = props.style.canvas;
  const out: Word[] = [];
  for (const {seg, from, dur} of segmentFrames(props)) {
    const t0 = from / fps;
    const segEnd = (from + dur) / fps;
    for (const w of seg.words ?? []) {
      if (w.end <= seg.srcIn || w.start >= seg.srcOut) continue;
      const s = Math.max(t0, t0 + (w.start - seg.srcIn));
      const e = Math.min(segEnd, t0 + (w.end - seg.srcIn));
      out.push({text: w.text, startMs: s * 1000, endMs: e * 1000, emphasis: w.emphasis});
    }
  }
  return [...out, ...(props.timeline.extraWords ?? [])].sort((a, b) => a.startMs - b.startMs);
};

// Resolve a possibly segment-anchored time (seconds) to output seconds.
export const resolveTime = (props: EditProps, t: number, seg?: string) => {
  if (!seg) return t;
  const hit = segmentFrames(props).find((s) => s.seg.id === seg);
  return hit ? hit.from / props.style.canvas.fps + t : t;
};

const ProgressBar: React.FC<{props: EditProps}> = ({props}) => {
  const frame = useCurrentFrame();
  const {durationInFrames, width} = useVideoConfig();
  const {style} = props;
  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        height: style.progressBar.height,
        width: (frame / Math.max(1, durationInFrames - 1)) * width,
        background: color(style, 'progress'),
      }}
    />
  );
};

export const Edit: React.FC<EditProps> = (props) => {
  const {timeline, style} = props;
  const {fps} = useVideoConfig();
  const shots = segmentFrames(props);
  const words = outputWords(props);

  const speaking = (f: number) => {
    const ms = (f / fps) * 1000;
    return words.some((w) => ms >= w.startMs - 150 && ms <= w.endMs + 250);
  };

  return (
    <AbsoluteFill style={{backgroundColor: '#000'}}>
      {shots.map(({seg, from, dur}) => (
        <Sequence key={seg.id} name={seg.id} from={from} durationInFrames={dur}>
          <Shot seg={seg} style={style} durationInFrames={dur} />
        </Sequence>
      ))}

      {timeline.overlays.map((o) => {
        const from = Math.round(resolveTime(props, o.start, o.seg) * fps);
        const dur = Math.max(1, Math.round((o.end - o.start) * fps));
        return (
          <Sequence key={o.id} name={`${o.type}:${o.id}`} from={from} durationInFrames={dur}>
            <OverlayView o={o} style={style} dur={dur} />
          </Sequence>
        );
      })}

      <Captions words={words} style={style} />
      {style.progressBar.enabled ? <ProgressBar props={props} /> : null}

      {timeline.sfx.map((s, i) => (
        <Sequence key={`sfx${i}`} name={`sfx:${s.src}`} from={Math.round(resolveTime(props, s.at, s.seg) * fps)}>
          <Audio src={staticFile(s.src)} volume={s.volume ?? style.audio.sfxVolume} />
        </Sequence>
      ))}

      {timeline.music ? (
        <Audio
          src={staticFile(timeline.music.src)}
          trimBefore={Math.round((timeline.music.startOffset ?? 0) * fps)}
          loop
          volume={(f) => {
            const base = timeline.music!.volume ?? style.audio.musicVolume;
            const duck = timeline.music!.duckTo ?? style.audio.musicDuckTo;
            const fadeIn = interpolate(f, [0, fps * 0.5], [0, 1], {extrapolateRight: 'clamp'});
            return (speaking(f) ? duck : base) * fadeIn;
          }}
        />
      ) : null}
    </AbsoluteFill>
  );
};
