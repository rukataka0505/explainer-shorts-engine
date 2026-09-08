import React from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {Audio} from '@remotion/media';
import {Captions} from './Captions';
import type {SubtitleConfig} from './Subtitle';
import type {Caption} from '@remotion/captions';
import {soundVolume, type Camera, type Sound} from './timing';
import {Picture, Whip, Overlay, asset} from './Picture';
import {strength, type Editing} from './editing';

export type Shot = {id: string; path: string; from: number; to: number; media: string; source_start: number; speed: number; source_width: number; source_height: number; camera: Camera[]; fit?: 'cover' | 'contain'; subject?: {x: number; y: number; width: number; height: number}};
export type Line = {id: string; text: string; path: string; from: number; to: number; duration: number; captions?: Caption[] | null};
export type FilmProps = {title: string; video: {width: number; height: number; fps: number}; durationInFrames: number; shots: Shot[]; lines: Line[]; audio: Sound[]; mix: {duck_volume: number; duck_seconds: number; headroom_db?: number}; assetBase: string; subtitles?: SubtitleConfig; editing?: Editing};

// Compiled edit decisions are the source of truth. No random motion or baked-in overlays.
export const Film: React.FC<FilmProps> = (p) => {
  const {fps} = useVideoConfig();
  const events = p.editing?.events ?? [];
  const mixGain = 10 ** ((p.mix.headroom_db ?? -6) / 20);
  return <AbsoluteFill style={{backgroundColor: '#000'}}>
    {p.shots.map(s => <Sequence key={s.id} name={s.id} from={s.from} durationInFrames={s.to - s.from}><Picture shot={s} base={p.assetBase} events={events} /></Sequence>)}
    {events.filter(e => e.effect === 'broll_cutaway').map(e => <Sequence key={e.id} name={e.reason} from={e.from} durationInFrames={e.to - e.from}><Picture shot={e.media!} base={p.assetBase} push={1 + (e.params.push - 1) * strength(e)} /></Sequence>)}
    {events.filter(e => e.effect === 'whip_transition').map(e => <Sequence key={e.id} name={e.reason} from={e.from} durationInFrames={e.to - e.from}><Whip event={e} shots={p.shots} base={p.assetBase} events={events} /></Sequence>)}
    {events.filter(e => e.effect === 'flash_cut' || e.effect === 'callout').map(e => <Sequence key={e.id} name={e.reason} from={e.from} durationInFrames={e.to - e.from}><Overlay event={e} /></Sequence>)}
    {p.lines.map(l => <Sequence key={l.id} name={l.text} from={l.from} durationInFrames={l.to - l.from}><Audio src={asset(p.assetBase, l.path)} volume={mixGain} /></Sequence>)}
    {p.subtitles && <Captions lines={p.lines} config={p.subtitles} editing={p.editing} />}
    {p.audio.map((s, i) => <Sequence key={i} name={s.role ?? s.path} from={s.from} durationInFrames={s.to - s.from}><Audio src={asset(p.assetBase, s.path)} trimBefore={Math.round((s.source_start ?? 0) * fps)} loop={s.loop ?? false} loopVolumeCurveBehavior="extend" volume={local => soundVolume(s, local, fps, p.lines, p.mix) * mixGain} /></Sequence>)}
  </AbsoluteFill>;
};
