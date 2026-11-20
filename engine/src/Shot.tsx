import {Video} from '@remotion/media';
import React from 'react';
import {AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Segment, Style} from './types';

// One talking-head shot: reframes landscape/any source into the canvas with a focal point,
// applies punch-in zoom, optional slow drift, and an entrance transition. Audio comes from the clip.
export const Shot: React.FC<{seg: Segment; style: Style; durationInFrames: number}> = ({seg, style, durationInFrames}) => {
  const frame = useCurrentFrame();
  const {width: W, height: H, fps} = useVideoConfig();

  const baseZoom = seg.zoom ?? 1;
  const drift = seg.drift ? interpolate(frame, [0, durationInFrames], [0, style.zoom.drift], {extrapolateRight: 'clamp'}) : 0;

  const tDur = style.transitions.accentDurationFrames;
  const t = seg.transitionIn ?? 'cut';
  const p = interpolate(frame, [0, tDur], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});

  let tx = 0;
  let extraZoom = 0;
  let opacity = 1;
  let blur = 0;
  if (t === 'whip') {
    tx = (1 - p) * W * 0.35;
    blur = (1 - p) * 28;
  } else if (t === 'zoom') {
    extraZoom = (1 - p) * 0.25;
    blur = (1 - p) * 10;
  } else if (t === 'fade') {
    opacity = p;
  }

  const zoom = baseZoom + drift + extraZoom;
  const cover = Math.max(W / seg.srcW, H / seg.srcH) * zoom;
  const vw = seg.srcW * cover;
  const vh = seg.srcH * cover;
  const fx = seg.focusX ?? 0.5;
  const fy = seg.focusY ?? 0.4;
  const left = Math.min(0, Math.max(W - vw, W / 2 - fx * vw));
  const top = Math.min(0, Math.max(H - vh, H / 2 - fy * vh));

  const flash = t === 'flash' ? interpolate(frame, [0, tDur], [0.9, 0], {extrapolateRight: 'clamp'}) : 0;

  return (
    <AbsoluteFill style={{backgroundColor: '#000', overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: left + tx, top, width: vw, height: vh, opacity, filter: blur ? `blur(${blur}px)` : undefined}}>
        <Video
          src={staticFile(seg.src)}
          trimBefore={Math.round(seg.srcIn * fps)}
          objectFit="fill"
          style={{width: '100%', height: '100%'}}
        />
      </div>
      {flash > 0 ? <AbsoluteFill style={{backgroundColor: 'white', opacity: flash}} /> : null}
    </AbsoluteFill>
  );
};
