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
