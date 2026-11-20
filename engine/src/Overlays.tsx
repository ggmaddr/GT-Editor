import {Video} from '@remotion/media';
import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from './fonts';
import {color, type Overlay, type Style} from './types';

const useEnterExit = (durationInFrames: number) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame, fps, config: {damping: 13, stiffness: 200, mass: 0.7}});
  const exit = interpolate(frame, [durationInFrames - 6, durationInFrames], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return {enter, exit, frame};
};

const HookTitle: React.FC<{o: Extract<Overlay, {type: 'hookTitle'}>; style: Style; dur: number}> = ({o, style, dur}) => {
  const {enter, exit} = useEnterExit(dur);
  const {width} = useVideoConfig();
  const hl = new Set((o.highlight ?? []).map((s) => s.toLowerCase()));
  const words = o.text.split(/\s+/);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          top: `${style.titles.hookYPercent}%`,
          left: style.safeZone.left,
          width: width - style.safeZone.left - style.safeZone.right,
          transform: `translateY(-50%) scale(${0.85 + 0.15 * enter})`,
          opacity: exit * Math.min(1, enter * 1.4),
          textAlign: 'center',
          fontFamily: fontFamily(style.typography.titleFont),
          fontWeight: style.typography.titleWeight as React.CSSProperties['fontWeight'],
          fontSize: style.titles.hookFontSize,
          lineHeight: 1.0,
          textTransform: 'uppercase',
          color: color(style, 'text'),
          WebkitTextStroke: `14px ${color(style, 'stroke')}`,
          paintOrder: 'stroke fill',
          textShadow: `0 10px 30px ${color(style, 'shadow')}`,
        }}
      >
        {words.map((w, i) => (
          <span key={i} style={{color: hl.has(w.toLowerCase().replace(/[^a-z0-9']/g, '')) ? color(style, 'accent') : undefined}}>
            {w}{' '}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const Keyword: React.FC<{o: Extract<Overlay, {type: 'keyword'}>; style: Style; dur: number}> = ({o, style, dur}) => {
  const {enter, exit} = useEnterExit(dur);
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div
        style={{
          position: 'absolute',
          top: `${o.yPercent ?? 38}%`,
          transform: `translateY(-50%) scale(${enter}) rotate(${(1 - enter) * -8}deg)`,
          opacity: exit,
          fontFamily: fontFamily(style.typography.titleFont),
          fontSize: style.titles.keywordFontSize,
          textTransform: 'uppercase',
          color: color(style, 'accent'),
          WebkitTextStroke: `16px ${color(style, 'stroke')}`,
          paintOrder: 'stroke fill',
          textShadow: `0 12px 36px ${color(style, 'shadow')}`,
        }}
      >
        {o.text}
      </div>
    </AbsoluteFill>
  );
};

const BRoll: React.FC<{o: Extract<Overlay, {type: 'broll'}>; style: Style; dur: number}> = ({o, style, dur}) => {
  const {enter, exit, frame} = useEnterExit(dur);
  const {fps} = useVideoConfig();
  const kb = 1.05 + interpolate(frame, [0, dur], [0, 0.06]);
  const media = o.isImage ? (
    <Img src={staticFile(o.src)} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${kb})`}} />
  ) : (
    <Video src={staticFile(o.src)} trimBefore={Math.round((o.srcIn ?? 0) * fps)} muted objectFit="cover" style={{width: '100%', height: '100%'}} />
  );
  if (o.mode === 'card') {
    return (
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
        <div
          style={{
            width: '84%',
            aspectRatio: '4 / 3',
            marginTop: '-18%',
            borderRadius: 36,
            overflow: 'hidden',
            boxShadow: `0 30px 80px ${color(style, 'shadow')}`,
            border: `6px solid ${color(style, 'text')}`,
            transform: `scale(${0.7 + 0.3 * enter}) rotate(${(1 - enter) * 4}deg)`,
            opacity: exit,
          }}
        >
          {media}
        </div>
      </AbsoluteFill>
    );
  }
  return <AbsoluteFill style={{opacity: Math.min(1, enter * 2) * exit}}>{media}</AbsoluteFill>;
};

const LowerThird: React.FC<{o: Extract<Overlay, {type: 'lowerThird'}>; style: Style; dur: number}> = ({o, style, dur}) => {
  const {enter, exit} = useEnterExit(dur);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          left: style.safeZone.left,
          bottom: style.safeZone.bottom + 40,
          transform: `translateX(${(1 - enter) * -120}%)`,
          opacity: exit,
          background: color(style, 'panel'),
          borderLeft: `12px solid ${color(style, 'accent')}`,
          padding: '22px 34px',
          borderRadius: 18,
          fontFamily: fontFamily(style.typography.bodyFont),
          color: color(style, 'text'),
        }}
      >
        <div style={{fontSize: 52, fontWeight: 800}}>{o.text}</div>
        {o.sub ? <div style={{fontSize: 34, fontWeight: 600, opacity: 0.8}}>{o.sub}</div> : null}
      </div>
    </AbsoluteFill>
  );
};

const Clip: React.FC<{o: Extract<Overlay, {type: 'clip'}>}> = ({o}) => (
  <AbsoluteFill>
    <Video src={staticFile(o.src)} muted objectFit="cover" style={{width: '100%', height: '100%'}} />
  </AbsoluteFill>
);

export const OverlayView: React.FC<{o: Overlay; style: Style; dur: number}> = ({o, style, dur}) => {
  switch (o.type) {
    case 'hookTitle':
      return <HookTitle o={o} style={style} dur={dur} />;
    case 'keyword':
      return <Keyword o={o} style={style} dur={dur} />;
    case 'broll':
      return <BRoll o={o} style={style} dur={dur} />;
    case 'lowerThird':
      return <LowerThird o={o} style={style} dur={dur} />;
    case 'clip':
      return <Clip o={o} />;
  }
};
