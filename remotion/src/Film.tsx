import React from 'react';
import {AbsoluteFill, Img, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {Audio, Video} from '@remotion/media';
import {cameraAt, coverRect, soundVolume, type Camera, type Sound} from './timing';

export type Shot = {id: string; path: string; from: number; to: number; media: string; source_start: number; speed: number; source_width: number; source_height: number; camera: Camera[]; fit?: 'cover' | 'contain'};
export type Line = {id: string; text: string; path: string; from: number; to: number; duration: number};
export type FilmProps = {title: string; video: {width: number; height: number; fps: number}; durationInFrames: number; shots: Shot[]; lines: Line[]; audio: Sound[]; mix: {duck_volume: number; duck_seconds: number}; assetBase: string};
const asset = (base: string, path: string) => `${base}/project/${path.split('/').map(encodeURIComponent).join('/')}`;

const Picture: React.FC<{shot: Shot; base: string}> = ({shot: s, base}) => {
  const f = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const camera = cameraAt(s.camera, f / Math.max(1, s.to - s.from - 1));
  const rect = coverRect(s.source_width, s.source_height, width, height, camera, s.fit);
  const style: React.CSSProperties = {position: 'absolute', ...rect};
  return <AbsoluteFill style={{overflow: 'hidden', backgroundColor: '#000'}}>
    {s.media === 'video'
      ? <Video src={asset(base, s.path)} trimBefore={Math.round(s.source_start * fps)} playbackRate={s.speed} muted style={style} objectFit="fill" />
      : <Img src={asset(base, s.path)} style={style} />}
  </AbsoluteFill>;
};

// Compiled edit decisions are the source of truth. No random motion or baked-in overlays.
export const Film: React.FC<FilmProps> = (p) => {
  const {fps} = useVideoConfig();
  return <AbsoluteFill style={{backgroundColor: '#000'}}>
    {p.shots.map(s => <Sequence key={s.id} name={s.id} from={s.from} durationInFrames={s.to - s.from}><Picture shot={s} base={p.assetBase} /></Sequence>)}
    {p.lines.map(l => <Sequence key={l.id} name={l.text} from={l.from} durationInFrames={l.to - l.from}><Audio src={asset(p.assetBase, l.path)} /></Sequence>)}
    {p.audio.map((s, i) => <Sequence key={i} name={s.role ?? s.path} from={s.from} durationInFrames={s.to - s.from}><Audio src={asset(p.assetBase, s.path)} trimBefore={Math.round((s.source_start ?? 0) * fps)} loop={s.loop ?? false} loopVolumeCurveBehavior="extend" volume={local => soundVolume(s, local, fps, p.lines, p.mix)} /></Sequence>)}
  </AbsoluteFill>;
};
