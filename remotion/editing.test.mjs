import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import ts from 'typescript';

function load(file) {
  const source = fs.readFileSync(new URL(file, import.meta.url), 'utf8');
  const js = ts.transpileModule(source, {compilerOptions: {target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS}}).outputText;
  const module = {exports: {}};
  Function('require', 'module', 'exports', js)(createRequire(import.meta.url), module, module.exports);
  return module.exports;
}
const {pictureMotion, popScale, sourceFrame, seeded, subjectBounds} = load('./src/editing.ts');
const {captionParts, captionLines, captionPageAt, captionRowPages, captionLineChars} = load('./src/timing.ts');
const effect = (name, overrides = {}) => ({id: name, group: name, effect: name, from: 30, to: 36, intensity: .5, seed: 'fixed', target: {shot: 'shot'},
  params: {peak_scale: 1.12, settle_scale: 1.05, pixels: 14, rotation: .7, frequency: 10}, ...overrides});

test('Japanese captions keep short words intact and use a comma before a clause that fits', () => {
  const text = '発射台に、滝のような水。';
  assert.equal(captionLines(text, 8), '発射台に、\n滝のような水。');
  assert.ok(!captionLines('滝のような水。', 4).includes('よ\nう'));
  const long = text + '実は、ロケットを音から守っている。';
  const pages = captionRowPages(long, 8, 2, ['音']);
  assert.equal(pages.join(''), long);
  for (const page of pages) assert.ok(captionLines(page, 8, ['音']).split('\n').length <= 2);
});

test('caption width adapts modestly instead of stranding a short verb ending on its own page', () => {
  for (const text of ['発射の音は、機体を傷めるほど強烈だ。', '本番に備え、水の流れを確かめている。']) {
    const chars = captionLineChars(text, 8, 2);
    const pages = captionRowPages(text, chars, 2);
    assert.ok(chars >= 8 && chars <= 10);
    assert.equal(pages.join(''), text);
    assert.ok(pages.length === 1 || pages[pages.length - 1].length >= 4);
    for (const page of pages) assert.ok(captionLines(page, chars).split('\n').length <= 2);
  }
});

test('punch has exact overshoot, settles without a reset at its end, and respects the subject anchor', () => {
  const e = effect('punch_zoom', {target: {shot: 'shot', anchor: {x: .3, y: .4}}});
  const at = f => pictureMotion([e], f, 30, 1080, 1920);
  assert.equal(at(29).zoom, 1);
  assert.equal(at(30).zoom, 1);
  assert.equal(at(32).zoom, 1.12);
  assert.equal(at(35).zoom, 1.05);
  assert.equal(at(55).zoom, 1.05);
  assert.deepEqual(at(35).anchor, {x: .3, y: .4});
});
test('shake is seeded, converges and scales with resolution without exposing corners', () => {
  const e = effect('impact_shake');
  const at = (f, w = 1080, h = 1920) => pictureMotion([e], f, 30, w, h);
  assert.deepEqual(at(31), at(31));
  assert.notEqual(seeded('fixed'), seeded('other'));
  assert.equal(at(35).x, 0);
  assert.equal(at(35).rotate, 0);
  assert.ok(Math.abs(at(30, 2160, 3840).x - at(30).x * 2) < 1e-9);
  for (let f = 30; f < 36; f++) {
    const m = at(f), angle = -m.rotate * Math.PI / 180;
    for (const x of [-540, 540]) for (const y of [-960, 960]) {
      const px = ((x - m.x) * Math.cos(angle) - (y - m.y) * Math.sin(angle)) / m.coverage;
      const py = ((x - m.x) * Math.sin(angle) + (y - m.y) * Math.cos(angle)) / m.coverage;
      assert.ok(Math.abs(px) <= 540 + 1e-6 && Math.abs(py) <= 960 + 1e-6, JSON.stringify(m));
    }
  }
});
test('freeze holds the selected frame then resumes forward without replaying or skipping', () => {
  const e = effect('freeze_frame', {from: 40, to: 55});
  assert.deepEqual([39,40,45,54,55,56].map(f => sourceFrame(f, 0, [e])), [39,40,40,40,40,41]);
  const e2 = effect('freeze_frame', {from: 70, to: 80});
  assert.equal(sourceFrame(81, 0, [e, e2]), 56);
});
test('caption pop lands at one; disabled intensity never scales text', () => {
  assert.equal(popScale(0, 5), .86);
  assert.equal(popScale(2, 5), 1.06);
  assert.equal(popScale(4, 5), 1);
  assert.equal(popScale(400, 5), 1);
  assert.equal(popScale(0, 5, 0), 1);
});
test('protected keywords survive Japanese wrapping and paging, preserving original text', () => {
  const text = '映っているのは、発射台の放水試験。';
  const pages = captionParts(text, 12, ['放水試験']);
  assert.equal(pages.join(''), text);
  assert.equal(pages.map(p => captionLines(p, 6, ['放水試験']).replaceAll('\n', '')).join(''), text);
  assert.ok(pages.some(p => p.includes('放水試験')));
  const line = {text: '前半後半', duration: 2, captions: [{text:'前',startMs:0},{text:'半',startMs:100},{text:'後',startMs:1500},{text:'半',startMs:1600}]};
  assert.equal(captionPageAt(line, 1500, 2).startMs, 1500);
});
test('declared subject bounds detect cropping at punch peaks', () => {
  const motion = pictureMotion([effect('punch_zoom')], 32, 30, 1080, 1920);
  const rect = {left:0, top:0, width:1080, height:1920};
  assert.ok(subjectBounds({x:.4,y:.3,width:.2,height:.3}, rect, motion, 1080,1920).every(p => p.x >= 0 && p.y >= 0 && p.x <= 1080 && p.y <= 1920));
  assert.ok(subjectBounds({x:0,y:0,width:1,height:1}, rect, motion, 1080,1920).some(p => p.x < 0 || p.y < 0));
});
test('pages never overflow two rows even when a protected word forces an early wrap', () => {
  const text = 'この宇宙望遠鏡はジェイムズ・ウェッブ宇宙望遠鏡です。';
  const words = ['宇宙望遠鏡'];
  const pages = captionRowPages(text, 8, 2, words);
  assert.equal(pages.join(''), text);
  assert.ok(pages.every(p => captionLines(p, 8, words).split('\n').length <= 2));
});

test('authored newline boundaries preserve text without creating a third empty row', () => {
  const text = '最初の行\n次の行\n次のページ\n最後の行';
  const pages = captionRowPages(text, 8, 2);
  assert.equal(pages.join(''), text);
  assert.ok(pages.every(p => captionLines(p, 8).split('\n').length <= 2));
});
