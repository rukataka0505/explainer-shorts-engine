import React, {useLayoutEffect, useRef} from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {Subtitle, type SubtitleConfig} from './Subtitle';
import {captionPageAt, captionLines, captionLineChars} from './timing';
import type {Line} from './Film';
import {active, popScale, type Editing} from './editing';

// Keep the original engine's wrapping and outline, but use speech timestamps.
export const Captions: React.FC<{lines: Line[]; config: SubtitleConfig; editing?: Editing}> = ({lines, config, editing}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const root = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const host = root.current;
    const body = host?.querySelector<HTMLElement>('[data-caption-body]');
    if (!host || !body) return;
    const base = host.getBoundingClientRect(), ratio = base.width / 1080;
    const box = body.getBoundingClientRect();
    const stroke = (config.inner_outline_width + config.outer_outline_width) * ratio * 1.2;
    const safe = config.safe_area ?? {left: 80, right: 140, top: 100, bottom: 300};
    const rects = [box, ...Array.from(body.querySelectorAll('span')).map(n => n.getBoundingClientRect())];
    for (const r of rects) if (r.left - stroke < base.left + safe.left * ratio || r.right + stroke > base.right - safe.right * ratio || r.top - stroke < base.top + safe.top * ratio || r.bottom + stroke > base.bottom - safe.bottom * ratio) throw new Error(`字幕がsafe-area外です (frame ${frame})`);
    for (const callout of document.querySelectorAll('[data-callout]')) {
      const r = callout.getBoundingClientRect();
      if (r.left < box.right + stroke && r.right > box.left - stroke && r.top < box.bottom + stroke && r.bottom > box.top - stroke) throw new Error(`字幕とcalloutが衝突しています (frame ${frame})`);
    }
  });
  const line = lines.find(l => frame >= l.from && frame < l.to);
  if (!line) return null;
  const events = (editing?.events ?? []).filter(e => e.target.line === line.id);
  const words = events.filter(e => e.effect === 'keyword_highlight').map(e => e.target.keyword!);
  const lineChars = captionLineChars(line.text, config.max_chars_per_line, config.max_lines, words);
  const page = captionPageAt(line, (frame - line.from) / fps * 1000, lineChars * config.max_lines, words, lineChars);
  if (!page.text) return null;
  const text = captionLines(page.text, lineChars, words);
  const highlights = events.filter(e => e.effect === 'keyword_highlight' && active(e, frame)).map(e => {
    if (!text.includes(e.target.keyword!)) throw new Error(`${e.id}: 強調語が現在の字幕ページにありません (frame ${frame})`);
    return {word: e.target.keyword!, scale: popScale(frame - e.from, Math.max(3, Math.round(fps * 0.12)), e.intensity, 1, e.params.peak_scale)};
  });
  const pop = events.find(e => e.effect === 'caption_pop' && active(e, frame));
  const preset = editing?.caption_preset;
  const scale = pop ? popScale(frame - pop.from, pop.to - pop.from, pop.intensity, pop.params.start_scale, pop.params.peak_scale)
    : editing?.caption_animation === 'caption_pop' ? popScale(frame - line.from - Math.round(page.startMs / 1000 * fps), preset?.frames ?? Math.max(3, Math.round(fps * 0.14)), preset?.intensity ?? 0.35, preset?.params.start_scale ?? 0.86, preset?.params.peak_scale ?? 1.06) : 1;
  // Protected long words stay intact and scale down to the available width.
  const longest = Math.max(...text.split('\n').map(l => Array.from(l).length));
  const font_size = Math.min(config.font_size, (1080 - config.side_margin * 2 - 64) / Math.max(1, longest) / Math.max(1, scale));
  if (text.split('\n').length > config.max_lines) throw new Error(`${line.id}: 字幕がmax_linesを超えます。短いlineに分割してください`);
  return <div ref={root} style={{position: 'absolute', width: 1080, height: 1920, transform: `scale(${width / 1080})`, transformOrigin: 'top left', pointerEvents: 'none'}}>
    <Subtitle text={text} character={null} config={{...config, font_size}} scale={scale} highlights={highlights} />
  </div>;
};
