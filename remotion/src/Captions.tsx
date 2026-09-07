import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {Subtitle, type SubtitleConfig} from './Subtitle';
import {captionAt, captionLines} from './timing';
import type {Line} from './Film';

// Keep the original engine's wrapping and outline, but use speech timestamps.
export const Captions: React.FC<{lines: Line[]; config: SubtitleConfig}> = ({lines, config}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const line = lines.find(l => frame >= l.from && frame < l.to);
  if (!line) return null;
  const part = captionAt(line, (frame - line.from) / fps * 1000, config.max_chars_per_line * config.max_lines);
  if (!part) return null;
  const text = captionLines(part, config.max_chars_per_line);
  // Protected long words stay intact and scale down to the available width.
  const longest = Math.max(...text.split('\n').map(l => Array.from(l).length));
  const font_size = Math.min(config.font_size, (1080 - config.side_margin * 2 - 32) / Math.max(1, longest));
  return <div style={{position: 'absolute', width: 1080, height: 1920, transform: `scale(${width / 1080})`, transformOrigin: 'top left', pointerEvents: 'none'}}>
    <Subtitle text={text} character={null} config={{...config, font_size}} />
  </div>;
};
