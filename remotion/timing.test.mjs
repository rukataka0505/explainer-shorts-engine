import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
const source = fs.readFileSync(new URL('./src/timing.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext}}).outputText;
const {cameraAt, coverRect, soundVolume, captionAt, captionParts, captionLines} = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
test('portrait crop follows source focus without exposing empty pixels, including both edges', () => {
  for (const x of [0, .2, .5, .9, 1]) for (const y of [0, .5, 1]) for (const zoom of [1, 1.3, 2]) {
    const r = coverRect(3840, 2160, 1080, 1920, {x, y, zoom});
    assert.ok(r.left <= 0 && r.top <= 0);
    assert.ok(r.left + r.width >= 1080 - 1e-7 && r.top + r.height >= 1920 - 1e-7);
  }
  const centered = coverRect(3840, 2160, 1080, 1920, {x:.7, y:.5, zoom:1});
  assert.ok(Math.abs((.7 * centered.width + centered.left) - 540) < 1e-7);
});
test('camera reaches authored focus on the final visible frame and clamps outside keys', () => {
  const points = [{at:0,x:.2,y:.5,zoom:1},{at:1,x:.6,y:.4,zoom:1.2}];
  assert.equal(cameraAt(points, 1).x, .6);
  assert.equal(cameraAt(points, -1).x, .2);
  assert.equal(cameraAt(points, 2).x, .6);
  assert.ok(Math.abs(cameraAt(points, .5).x - .4) < 1e-7);
});
test('a J-cut retains source sound before the picture, ducks under narration and returns after speech', () => {
  const s = {from:60,to:210,path:'ambient.wav',volume:.5,duck:true};
  const lines=[{from:90,to:120}], mix={duck_volume:.2,duck_seconds:.2};
  assert.equal(soundVolume(s,0,30,lines,mix),.5);
  assert.ok(Math.abs(soundVolume(s,40,30,lines,mix)-.1)<1e-7);
  assert.equal(soundVolume(s,80,30,lines,mix),.5);
  assert.equal(soundVolume({...s,fade_in:1},0,30,lines,mix),0);
});

test('caption pages preserve every character, punctuation and protected words', () => {
  for (const text of ['字幕テスト、句読点も保持する。', '固有語ABC123を途中で壊さない。', '日本語とemoji🚀を保持する。']) {
    const pages = captionParts(text, 12);
    assert.equal(pages.join(''), text);
    assert.equal(pages.map(p => captionLines(p, 6).replaceAll('\n', '')).join(''), text);
  }
});
test('caption page changes follow the next spoken character, not text-length timing', () => {
  const line = {text: '字幕時刻テスト。', duration: 4, captions: Array.from('字幕時刻テスト。').map((text, i) => ({text, startMs: [0,100,200,300,2500,2600,2800,3000][i]}))};
  assert.equal(captionAt(line, 2499, 4), '字幕時刻');
  assert.equal(captionAt(line, 2500, 4), 'テスト。');
  assert.equal(captionAt({...line, captions: null}, 1999, 4), '字幕時刻');
});
