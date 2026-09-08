import React from 'react';

type SpeakerStyle = {
  text_color: string;
  inner_outline_color: string;
  outer_outline_color: string;
};

export type SubtitleConfig = {
  font_family: string;
  font_size: number;
  font_weight: number;
  line_height: number;
  bottom: number;
  side_margin: number;
  min_height: number;
  max_chars_per_line: number;
  max_lines: number;
  inner_outline_width: number;
  outer_outline_width: number;
  default_style: SpeakerStyle;
  speaker_styles: Record<string, SpeakerStyle>;
  safe_area?: {left: number; right: number; top: number; bottom: number};
};

export const Subtitle: React.FC<{text: string; character: string | null; config: SubtitleConfig; scale?: number; highlights?: {word: string; scale: number}[]}> = ({text, character, config, scale = 1, highlights = []}) => {
  const palette = (character && config.speaker_styles[character]) || config.default_style;
  const hasInnerOutline = palette.inner_outline_color.toLowerCase() !== palette.text_color.toLowerCase();
  const innerOutlineWidth = hasInnerOutline ? config.inner_outline_width : 0;
  const common: React.CSSProperties = {
    position: 'absolute', inset: 0, display: 'flex', justifyContent: 'center', alignItems: 'center',
    textAlign: 'center', fontFamily: config.font_family, fontSize: config.font_size,
    fontWeight: config.font_weight, lineHeight: config.line_height, color: palette.text_color,
    whiteSpace: 'pre', wordBreak: 'normal', lineBreak: 'strict', paintOrder: 'stroke fill',
  };
  const outerExtent = innerOutlineWidth + config.outer_outline_width;
  const contents = (paint: boolean) => text.split('\n').map((line, row) => {
    const pieces: React.ReactNode[] = [];
    let offset = 0;
    while (offset < line.length) {
      const matches = highlights.map(h => ({...h, at: line.indexOf(h.word, offset)})).filter(h => h.at >= 0).sort((a, b) => a.at - b.at);
      const match = matches[0];
      if (!match) {pieces.push(line.slice(offset)); break;}
      pieces.push(line.slice(offset, match.at));
      pieces.push(<span key={match.at} style={{display: 'inline-block', scale: match.scale, color: paint ? '#FFF0A3' : undefined, transformOrigin: 'center'}}>{match.word}</span>);
      offset = match.at + match.word.length;
    }
    return <React.Fragment key={row}>{row > 0 && <br />}{pieces}</React.Fragment>;
  });
  return <div style={{position: 'absolute', left: config.side_margin, right: config.side_margin, bottom: config.bottom, minHeight: config.min_height, scale, transformOrigin: 'center'}}>
    <div aria-hidden style={{...common, WebkitTextStroke: `${outerExtent * 2}px ${palette.outer_outline_color}`}}><span>{contents(false)}</span></div>
    <div style={{...common, WebkitTextStroke: hasInnerOutline ? `${innerOutlineWidth * 2}px ${palette.inner_outline_color}` : undefined}}><span data-caption-body>{contents(true)}</span></div>
  </div>;
};
