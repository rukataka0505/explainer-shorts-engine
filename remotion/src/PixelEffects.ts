import {createEffect, type InteractivitySchema} from 'remotion';

// A small factory on Remotion's official Canvas API, not a second renderer.
type SliceParams = {offset: number; slices: number; seed: number};
const schema = {
  offset: {type: 'number', min: 0, max: 160, default: 12, step: 1, description: 'Pixel displacement', hiddenFromList: false},
  slices: {type: 'number', min: 4, max: 16, default: 8, step: 1, description: 'Horizontal bands', hiddenFromList: false},
  seed: {type: 'number', min: 0, max: 1, default: 0, step: 0.01, description: 'Deterministic frame seed', hiddenFromList: false},
} as const satisfies InteractivitySchema;
export const glitchSlices = createEffect<SliceParams, null>({
  type: 'dev.shorts.glitchSlices', label: 'glitchSlices()', documentationLink: null,
  backend: '2d', schema, calculateKey: p => JSON.stringify(p), setup: () => null, cleanup: () => undefined,
  validateParams: p => {
    if (!Number.isInteger(p.slices) || p.slices < 4 || p.slices > 16 || !Number.isFinite(p.offset) || p.offset < 0 || p.offset > 160 || !Number.isFinite(p.seed) || p.seed < 0 || p.seed > 1) throw new Error('Invalid glitch parameters');
  },
  apply: ({source, target, width, height, params}) => {
    const ctx = target.getContext('2d');
    if (!ctx) throw new Error('Canvas2D unavailable');
    ctx.save();
    ctx.clearRect(0, 0, width, height);
    for (let i = 0; i < params.slices; i++) {
      const y = Math.floor(i * height / params.slices), bottom = Math.floor((i + 1) * height / params.slices);
      const dx = Math.round(Math.sin((i + 1) * 78.233 + params.seed * 437.13) * params.offset);
      ctx.drawImage(source, 0, y, width, bottom - y, dx, y, width, bottom - y);
      if (dx > 0) ctx.drawImage(source, 0, y, 1, bottom - y, 0, y, dx, bottom - y);
      if (dx < 0) ctx.drawImage(source, width - 1, y, 1, bottom - y, width + dx, y, -dx, bottom - y);
    }
    ctx.restore();
  },
});
