import {Easing, interpolate} from 'remotion';

export type EditorialEvent = {
  id: string; group: string; effect: string; version: number; from: number; to: number; intensity: number;
  params: Record<string, number>; seed: string; reason: string; sync_frame: number;
  target: {shot?: string; line?: string; keyword?: string; anchor?: {x: number; y: number}; point?: {x: number; y: number}};
  media?: import('./Film').Shot; layers?: {path: string; depth?: number}[]; label?: string;
  direction?: 'left' | 'right'; previous_shot?: string;
  attack_frames?: number; release_frames?: number;
};
export type Editing = {version: number; events: EditorialEvent[]; caption_animation: 'none' | 'caption_pop'; renderer: 'cpu' | 'webgl'; caption_preset?: {frames: number; params: {start_scale: number; peak_scale: number}; intensity: number}};
export const clamp = (n: number, a = 0, b = 1) => Math.max(a, Math.min(b, n));
export const active = (e: EditorialEvent, f: number) => f >= e.from && f < e.to;
export const ease = (value: number) => 1 - (1 - clamp(value)) ** 3;
export const strength = (e: EditorialEvent) => e.intensity / 0.5;
export const progress = (e: EditorialEvent, f: number) => clamp((f - e.from) / Math.max(1, e.to - e.from - 1));
export function seeded(seed: string): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) h = Math.imul(h ^ seed.charCodeAt(i), 16777619);
  return (h >>> 0) / 4294967295;
}
const curve = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)} as const;

export function popScale(local: number, frames: number, amount = 0.5, start = 0.86, peak = 1.06) {
  if (local < 0) return 1;
  const last = Math.max(2, frames - 1);
  return interpolate(local, [0, Math.max(1, Math.round(last * 0.55)), last],
    [1 + (start - 1) * amount / 0.5, 1 + (peak - 1) * amount / 0.5, 1], curve);
}

export function pictureMotion(events: EditorialEvent[], f: number, fps: number, width: number, height: number) {
  let zoom = 1, x = 0, y = 0, rotate = 0, blur = 0;
  let anchor = {x: 0.5, y: 0.5};
  for (const e of [...events].sort((a, b) => a.from - b.from)) {
    if (e.effect === 'punch_zoom' && f >= e.from) {
      const last = Math.max(2, e.to - e.from - 1);
      zoom = interpolate(f - e.from, [0, Math.max(1, Math.round(last * 0.4)), last],
        [zoom, 1 + (e.params.peak_scale - 1) * strength(e), 1 + (e.params.settle_scale - 1) * strength(e)], curve);
      anchor = e.target.anchor ?? anchor;
    }
    if (!active(e, f)) continue;
    if (e.effect === 'impact_shake') {
      const t = progress(e, f), decay = (1 - t) ** 3;
      const phase = seeded(e.seed) * Math.PI * 2;
      const cycle = (f - e.from) / fps * e.params.frequency * Math.PI * 2;
      const amplitude = e.params.pixels * strength(e) * width / 1080 * decay;
      x += Math.cos(cycle + phase) * amplitude;
      y += Math.sin(cycle * 1.17 + phase) * amplitude * 0.65;
      rotate += Math.cos(cycle + phase) * e.params.rotation * strength(e) * decay;
    }
    if (e.effect === 'focus_reveal') blur = Math.max(blur, e.params.blur * strength(e) * (1 - ease(progress(e, f))) * width / 1080);
  }
  // Overscan derives from the actual displacement/rotation rather than a fixed margin.
  const radians = rotate * Math.PI / 180;
  const coverage = Math.max(Math.abs(Math.cos(radians)) + height / width * Math.abs(Math.sin(radians)) + 2 * Math.abs(x * Math.cos(radians) + y * Math.sin(radians)) / width,
    Math.abs(Math.cos(radians)) + width / height * Math.abs(Math.sin(radians)) + 2 * Math.abs(-x * Math.sin(radians) + y * Math.cos(radians)) / height) + (blur ? 6 * blur / width : 0);
  return {zoom, x, y, rotate, blur, coverage, anchor};
}

export function sourceFrame(local: number, shotFrom: number, events: EditorialEvent[]) {
  let held = 0;
  for (const e of events.filter(e => e.effect === 'freeze_frame').sort((a, b) => a.from - b.from)) held += clamp(shotFrom + local - e.from, 0, e.to - e.from);
  return local - held;
}

export function subjectBounds(subject: {x: number; y: number; width: number; height: number},
  rect: {left: number; top: number; width: number; height: number}, motion: ReturnType<typeof pictureMotion>, width: number, height: number) {
  const radians = motion.rotate * Math.PI / 180;
  return [subject.x, subject.x + subject.width].flatMap(x => [subject.y, subject.y + subject.height].map(y => {
    const px = (rect.left + x * rect.width - motion.anchor.x * width) * motion.zoom + motion.anchor.x * width - width / 2;
    const py = (rect.top + y * rect.height - motion.anchor.y * height) * motion.zoom + motion.anchor.y * height - height / 2;
    return {x: (px * Math.cos(radians) - py * Math.sin(radians)) * motion.coverage + width / 2 + motion.x,
      y: (px * Math.sin(radians) + py * Math.cos(radians)) * motion.coverage + height / 2 + motion.y};
  }));
}
