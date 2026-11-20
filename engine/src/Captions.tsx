import React, {useMemo} from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {fontFamily} from './fonts';
import {color, type Style, type Word} from './types';

type Page = {startMs: number; endMs: number; words: Word[]};

// Groups words into short pages: break on max words, sentence punctuation, or a pause.
export const paginate = (words: Word[], maxWords: number, gapMs: number): Page[] => {
  const pages: Page[] = [];
  let cur: Word[] = [];
  const flush = () => {
    if (cur.length) pages.push({startMs: cur[0].startMs, endMs: cur[cur.length - 1].endMs, words: cur});
    cur = [];
  };
  words.forEach((w, i) => {
    const prev = words[i - 1];
    if (cur.length && (cur.length >= maxWords || (prev && w.startMs - prev.endMs > gapMs))) flush();
    cur.push(w);
    if (/[.!?]$/.test(w.text.trim())) flush();
  });
  flush();
  // hold each page until the next one starts (no flicker), max +400ms
  pages.forEach((p, i) => {
    const next = pages[i + 1];
    p.endMs = next ? Math.min(next.startMs, p.endMs + 400) : p.endMs + 400;
  });
  return pages;
};

export const Captions: React.FC<{words: Word[]; style: Style}> = ({words, style}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const c = style.captions;
  const pages = useMemo(() => paginate(words, c.maxWordsPerPage, c.pageBreakGapMs), [words, c.maxWordsPerPage, c.pageBreakGapMs]);
  const ms = (frame / fps) * 1000;
  const page = pages.find((p) => ms >= p.startMs && ms < p.endMs);
  if (!c.enabled || !page) return null;

  const pageFrame = frame - Math.round((page.startMs / 1000) * fps);
  const enter = c.entrance === 'none' ? 1 : spring({frame: pageFrame, fps, config: {damping: 14, stiffness: 220, mass: 0.6}});
  const scale = c.entrance === 'pop' ? 0.8 + 0.2 * enter : 1;
  const ty = c.entrance === 'slide' ? (1 - enter) * 40 : 0;
  const {left, right} = style.safeZone;

  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          top: `${c.yPercent}%`,
          left,
          width: width - left - right,
          transform: `translate(0, -50%) translateY(${ty}px) scale(${scale})`,
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: '0.04em 0.42em',
          fontFamily: fontFamily(style.typography.captionFont),
          fontWeight: style.typography.captionWeight as React.CSSProperties['fontWeight'],
          fontSize: c.fontSize,
          lineHeight: 1.08,
          textAlign: 'center',
          textTransform: c.uppercase ? 'uppercase' : 'none',
          opacity: Math.min(1, enter * 1.5),
        }}
      >
        {page.words.map((w, i) => {
          const active = ms >= w.startMs && ms < (page.words[i + 1]?.startMs ?? page.endMs);
          const fill = w.emphasis ? color(style, c.emphasisColor) : active ? color(style, c.activeColor) : color(style, 'text');
          return (
            <span
              key={i}
              style={{
                color: fill,
                display: 'inline-block',
                // reserve room so the scaled active word never collides with neighbours
                margin: `0 ${((c.activeScale - 1) / 2).toFixed(3)}em`,
                transform: active ? `scale(${c.activeScale})` : undefined,
                WebkitTextStroke: `${c.strokeWidth}px ${color(style, 'stroke')}`,
                paintOrder: 'stroke fill',
                textShadow: `0 6px 18px ${color(style, 'shadow')}`,
              }}
            >
              {w.text.trim()}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
