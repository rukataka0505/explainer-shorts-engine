export type Camera = {at: number; x: number; y: number; zoom: number};
export type Sound = {path: string; from: number; to: number; source_start?: number; volume?: number; fade_in?: number; fade_out?: number; duck?: boolean; loop?: boolean; role?: string};
export function cameraAt(points: Camera[], at: number): Camera {
  if (at <= points[0].at) return points[0];
  const end = points.findIndex(p => p.at >= at);
  if (end < 0) return points[points.length - 1];
  const a = points[end - 1], b = points[end];
  const t = (at - a.at) / (b.at - a.at);
  return {at, x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, zoom: a.zoom + (b.zoom - a.zoom) * t};
}
export function coverRect(sw: number, sh: number, w: number, h: number, camera: Camera, fit = 'cover') {
  const scale = (fit === 'contain' ? Math.min(w / sw, h / sh) : Math.max(w / sw, h / sh)) * camera.zoom;
  const width = sw * scale, height = sh * scale;
  const position = (size: number, viewport: number, focus: number) => size < viewport ? (viewport - size) / 2 : -Math.max(0, Math.min(size - viewport, focus * size - viewport / 2));
  return {width, height, left: position(width, w, camera.x), top: position(height, h, camera.y)};
}
export function soundVolume(sound: Sound, local: number, fps: number, lines: {from: number; to: number}[], mix: {duck_volume: number; duck_seconds: number}) {
  const time = sound.from + local;
  const fadeIn = sound.fade_in ? Math.min(1, local / (sound.fade_in * fps)) : 1;
  const fadeOut = sound.fade_out ? Math.min(1, (sound.to - time) / (sound.fade_out * fps)) : 1;
  let duck = 1;
  if (sound.duck) for (const line of lines) {
    const distance = time < line.from ? line.from - time : time >= line.to ? time - line.to : 0;
    const ramp = Math.max(0, 1 - distance / Math.max(1, mix.duck_seconds * fps));
    duck = Math.min(duck, 1 - ramp * (1 - mix.duck_volume));
  }
  return Math.max(0, (sound.volume ?? 1) * fadeIn * fadeOut * duck);
}

const captionSegmenter = new Intl.Segmenter('ja', {granularity: 'word'});
const captionTokens = (text: string, protectedWords: string[] = []): string[] => {
  const words = [...protectedWords].filter(Boolean).sort((a, b) => b.length - a.length);
  const japanese = new Map(Array.from(captionSegmenter.segment(text), s => [s.index, s.segment]));
  const tokens: string[] = [];
  let offset = 0;
  while (offset < text.length) {
    const protectedWord = words.find(word => text.startsWith(word, offset));
    const token = protectedWord ?? text.slice(offset).match(/^(?:[A-Za-z0-9][A-Za-z0-9._+:/-]*|[ァ-ヺー]+)/u)?.[0]
      ?? japanese.get(offset) ?? String.fromCodePoint(text.codePointAt(offset)!);
    tokens.push(token); offset += token.length;
  }
  return tokens;
};

// Prefer a clause after a comma when that clause fits one row. Otherwise wrap
// at Japanese word boundaries so a small word such as よう is never torn apart.
const startsRow = (tokens: string[], index: number, used: number, limit: number) => {
  const token = tokens[index];
  if (token === '\n') return true;
  if (!used) return false;
  if (tokens[index - 1] === '、') {
    let clause = 0;
    for (const next of tokens.slice(index)) {
      if (next === '\n') break;
      clause += next.length;
      if (/^[、。！？!?]/u.test(next)) break;
    }
    if (clause <= limit && used + clause > limit) return true;
  }
  return used + token.length > limit && !/^[、。！？!?）」』]/u.test(token);
};

export const captionParts = (text: string, maxChars = 42, protectedWords: string[] = []): string[] => {
  const limit = Math.max(1, Math.floor(maxChars));
  const tokens = captionTokens(text, protectedWords);
  const parts: string[] = [];
  let current = '';
  for (const token of tokens) {
    if (current.length + token.length > limit && current && !/^[、。！？!?）」』]/u.test(token)) {parts.push(current); current = '';}
    current += token;
  }
  if (current) parts.push(current);
  return parts;
};

export const captionLines = (text: string, maxCharsPerLine = 21, protectedWords: string[] = []): string => {
  const limit = Math.max(1, Math.floor(maxCharsPerLine));
  // A page boundary may retain an authored newline for exact transcript offsets.
  // It is layout, not an additional empty subtitle row.
  const tokens = captionTokens(text.replace(/\r\n/g, '\n').replace(/^\n+|\n+$/g, ''), protectedWords);
  const lines: string[] = [''];
  for (const [index, token] of tokens.entries()) {
    if (token === '\n') {lines.push(''); continue;}
    const current = lines[lines.length - 1];
    if (startsRow(tokens, index, current.length, limit)) lines.push(token);
    else lines[lines.length - 1] += token;
  }
  return lines.join('\n');
};

// Page boundaries follow the actual wrapped rows, including protected words.
export function captionRowPages(text: string, lineChars: number, maxLines: number, protectedWords: string[] = []): string[] {
  const pages: string[] = [];
  let current = '', lineLength = 0, rows = 1;
  const tokens = captionTokens(text, protectedWords);
  for (const [index, token] of tokens.entries()) {
    const breakRow = startsRow(tokens, index, lineLength, lineChars);
    if (breakRow) {
      if (rows >= maxLines) {pages.push(current); current = ''; rows = 1;} else rows++;
      lineLength = 0;
    }
    current += token;
    if (token !== '\n') lineLength += token.length;
  }
  if (current) pages.push(current);
  return pages;
}

// Avoid a final caption containing only a trailing だ。 or いる。.
// A small width allowance keeps the phrase together; rendering still measures
// the real glyphs and reduces the font size to stay inside the safe area.
export function captionLineChars(text: string, preferred: number, maxLines: number, protectedWords: string[] = []): number {
  const pages = captionRowPages(text, preferred, maxLines, protectedWords);
  if (pages.length < 2 || pages[pages.length - 1].trim().length >= Math.max(4, preferred / 2)) return preferred;
  for (let chars = preferred + 1; chars <= Math.floor(preferred * 1.25); chars++) {
    const candidate = captionRowPages(text, chars, maxLines, protectedWords);
    if (candidate.length < pages.length || candidate[candidate.length - 1].trim().length >= Math.max(4, preferred / 2)) return chars;
  }
  return preferred;
}


export function captionPageAt(line: {text: string; duration: number; captions?: {text: string; startMs: number}[] | null}, elapsedMs: number, pageChars: number, protectedWords: string[] = [], lineChars?: number) {
  const parts = lineChars ? captionRowPages(line.text, lineChars, Math.max(1, Math.floor(pageChars / lineChars)), protectedWords) : captionParts(line.text, pageChars, protectedWords);
  let offset = 0, startMs = 0;
  for (let i = 0; i < parts.length; i++) {
    const text = parts[i], firstChar = offset;
    offset += text.length;
    let count = 0;
    const next = line.captions?.find(c => {const start = count; count += c.text.length; return start >= offset;});
    const end = i === parts.length - 1 ? Infinity : next?.startMs ?? offset / line.text.length * line.duration * 1000;
    if (elapsedMs < end) return {text, startMs, endMs: end, offset: firstChar};
    startMs = end;
  }
  return {text: '', startMs, endMs: Infinity, offset};
}
export function captionAt(line: {text: string; duration: number; captions?: {text: string; startMs: number}[] | null}, elapsedMs: number, pageChars: number): string {
  return captionPageAt(line, elapsedMs, pageChars).text;
}
