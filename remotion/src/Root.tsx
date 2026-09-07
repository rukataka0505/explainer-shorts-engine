import React from 'react';
import {Composition} from 'remotion';
import {Film, type FilmProps} from './Film';
export const RemotionRoot: React.FC = () => <Composition id="Film" component={Film} width={1080} height={1920} fps={30} durationInFrames={30} defaultProps={{title: '', video: {width: 1080, height: 1920, fps: 30}, durationInFrames: 30, shots: [], lines: [], audio: [], mix: {duck_volume: 0.22, duck_seconds: 0.16}, assetBase: ''} as FilmProps} calculateMetadata={({props}) => ({...props.video, durationInFrames: props.durationInFrames})} />;
