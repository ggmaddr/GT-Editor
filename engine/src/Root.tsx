import React from 'react';
import {Composition} from 'remotion';
import {Edit, segmentFrames} from './Edit';
import type {EditProps} from './types';
import defaultStyle from '../../styles/design-system.json';

// Props are injected by scripts/render.py (--props). These defaults only make Studio open.
const defaultProps: EditProps = {
  style: defaultStyle as unknown as EditProps['style'],
  timeline: {version: 1, segments: [], overlays: [], sfx: [], music: null},
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Edit"
    component={Edit}
    defaultProps={defaultProps}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={30}
    calculateMetadata={({props}) => {
      const {width, height, fps} = props.style.canvas;
      const shots = segmentFrames(props);
      const last = shots[shots.length - 1];
      return {width, height, fps, durationInFrames: last ? last.from + last.dur : fps};
    }}
  />
);
