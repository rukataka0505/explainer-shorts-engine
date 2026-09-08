import React from 'react';
import {AbsoluteFill, CanvasImage, Freeze, Img, useCurrentFrame, useVideoConfig} from 'remotion';
import {Video} from '@remotion/media';
import {chromaticAberration} from '@remotion/effects/chromatic-aberration';
import {cameraAt, coverRect} from './timing';
import {active, ease, pictureMotion, progress, seeded, sourceFrame, strength, subjectBounds, type EditorialEvent} from './editing';
import {glitchSlices} from './PixelEffects';
import type {Shot} from './Film';

export const asset = (base: string, path: string) => `${base}/project/${path.split('/').map(encodeURIComponent).join('/')}`;

export const Picture: React.FC<{shot: Shot; base: string; events?: EditorialEvent[]; localOffset?: number; push?: number}> = ({shot: s, base, events = [], localOffset = 0, push = 1}) => {
  const local = useCurrentFrame();
  const f = local + localOffset;
  const {width, height, fps} = useVideoConfig();
  const own = events.filter(e => e.target.shot === s.id);
  const mediaFrame = sourceFrame(f, s.from, own);
  const camera = cameraAt(s.camera, mediaFrame / Math.max(1, s.to - s.from - 1));
  const rect = coverRect(s.source_width, s.source_height, width, height, camera, s.fit);
  const motion = pictureMotion(own, s.from + f, fps, width, height);
  motion.zoom *= 1 + (push - 1) * ease(f / Math.max(1, s.to - s.from - 1));
  if (s.subject && localOffset === 0 && subjectBounds(s.subject, rect, motion, width, height).some(p => p.x < 0 || p.y < 0 || p.x > width || p.y > height)) {
    throw new Error(`${s.id}: 指定した重要被写体が画面外です (frame ${s.from + f})`);
  }
  const visible = own.filter(e => active(e, s.from + f));
  const layers = own.find(e => e.layers?.length);
  const layerProgress = layers && active(layers, s.from + f) ? ease((s.from + f - layers.from) / layers.attack_frames!) * ease((layers.to - 1 - s.from - f) / layers.release_frames!) : 0;
  const pixelEffects = visible.flatMap(e => {
    if (e.effect === 'rgb_split') return [chromaticAberration({amount: e.params.offset * strength(e) * width / 1080 * (1 - progress(e, s.from + f))})];
    if (e.effect === 'glitch_burst') return [glitchSlices({offset: e.params.offset * strength(e) * width / 1080, slices: e.params.slices, seed: seeded(`${e.seed}:${s.from + f}`)}), chromaticAberration({amount: 3 * strength(e) * width / 1080})];
    return [];
  });
  const style: React.CSSProperties = {position: 'absolute', ...rect};
  const video = <Video src={asset(base, s.path)} trimBefore={Math.round((s.source_start + localOffset / fps * s.speed) * fps)} playbackRate={s.speed} muted style={style} objectFit="fill" effects={pixelEffects} />;
  return <AbsoluteFill style={{overflow: 'hidden', backgroundColor: '#000'}}>
    <AbsoluteFill style={{translate: `${motion.x}px ${motion.y}px`, rotate: `${motion.rotate}deg`, scale: motion.coverage}}>
      <AbsoluteFill style={{scale: motion.zoom, transformOrigin: `${motion.anchor.x * 100}% ${motion.anchor.y * 100}%`}}>
        <AbsoluteFill style={{filter: `blur(${motion.blur + (layers?.effect === 'subject_popout' ? layers.params.blur * strength(layers) * layerProgress * width / 1080 : 0)}px) brightness(${layers?.effect === 'subject_popout' ? 1 - layers.params.dim * strength(layers) * layerProgress : 1})`, scale: layers?.effect === 'subject_popout' ? 1 + 0.04 * layerProgress : 1}}>
          {s.media === 'video' ? own.some(e => e.effect === 'freeze_frame') ? <Freeze frame={mediaFrame - localOffset}>{video}</Freeze> : video : pixelEffects.length ? <CanvasImage src={asset(base, s.path)} style={style} effects={pixelEffects} /> : <Img src={asset(base, s.path)} style={style} />}
        </AbsoluteFill>
        {layers?.layers?.map((layer, i) => <AbsoluteFill key={`${layers.id}:${i}`} style={{
          scale: layers.effect === 'subject_popout' ? 1 + (layers.params.scale - 1) * strength(layers) * layerProgress : 1 + 0.045 * (layer.depth ?? 1) * layers.params.depth * strength(layers) * layerProgress,
          translate: layers.effect === 'parallax_push' ? `${(layer.depth ?? 1) * layers.params.depth * strength(layers) * 32 * layerProgress * width / 1080}px 0` : '0 0',
          filter: layers.effect === 'subject_popout' ? `drop-shadow(0 ${6 * width / 1080}px ${16 * layerProgress * width / 1080}px rgba(0,0,0,0.5))` : undefined,
          transformOrigin: `${(layers.target.anchor?.x ?? 0.5) * 100}% ${(layers.target.anchor?.y ?? 0.5) * 100}%`,
        }}><Img src={asset(base, layer.path)} style={style} /></AbsoluteFill>)}
      </AbsoluteFill>
    </AbsoluteFill>
  </AbsoluteFill>;
};

export const Whip: React.FC<{event: EditorialEvent; shots: Shot[]; base: string; events: EditorialEvent[]}> = ({event: e, shots, base, events}) => {
  const frame = useCurrentFrame();
  const {width} = useVideoConfig();
  const t = frame / Math.max(1, e.to - e.from - 1);
  const travel = t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
  const direction = e.direction === 'right' ? -1 : 1;
  const blur = Math.sin(Math.PI * t) ** 2 * e.params.blur * strength(e) * width / 1080;
  return <AbsoluteFill style={{overflow: 'hidden'}}>{[e.previous_shot, e.target.shot].map((id, i) => {
    const shot = shots.find(s => s.id === id)!;
    return <AbsoluteFill key={id} style={{translate: `${direction * (i - travel) * width}px 0`, filter: `blur(${blur}px)`, scale: 1 + 6 * blur / width}}>
      <Picture shot={shot} base={base} events={events} localOffset={e.from - shot.from} />
    </AbsoluteFill>;
  })}</AbsoluteFill>;
};

export const Overlay: React.FC<{event: EditorialEvent}> = ({event: e}) => {
  const f = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  if (e.effect === 'flash_cut') return <AbsoluteFill style={{backgroundColor: 'white', opacity: Math.min(1, e.params.opacity * strength(e)) * (1 - f / Math.max(1, e.to - e.from - 1)), pointerEvents: 'none'}} />;
  if (e.effect !== 'callout') return null;
  const point = e.target.point!;
  const p = ease(f / Math.max(1, Math.round(fps * 0.25)));
  const x = point.x * width, y = point.y * height;
  const scale = width / 1080;
  const labelX = Math.max(100 * scale, Math.min(width - 360 * scale, x + (point.x > 0.5 ? -320 : 60) * scale));
  const labelY = Math.max(150 * scale, Math.min(height * 0.58, y - 100 * scale));
  return <AbsoluteFill style={{pointerEvents: 'none', opacity: p}}>
    <svg width={width} height={height} style={{position: 'absolute'}}><path d={`M ${x} ${y} L ${x} ${labelY + 50 * scale} L ${labelX + 100 * scale} ${labelY + 50 * scale}`} fill="none" stroke="#fff" strokeWidth={4 * scale} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - p} /><circle cx={x} cy={y} r={8 * scale} fill="#B9FFD0" /></svg>
    <div data-callout style={{position: 'absolute', left: labelX, top: labelY, maxWidth: 300 * scale, color: '#fff', fontFamily: 'Yu Gothic UI, sans-serif', fontWeight: 800, fontSize: 42 * scale, lineHeight: 1.25,
      textShadow: `0 2px ${4 * scale}px #000`, translate: `0 ${(1 - p) * e.params.offset * strength(e) * scale}px`}}>{e.label}</div>
  </AbsoluteFill>;
};
