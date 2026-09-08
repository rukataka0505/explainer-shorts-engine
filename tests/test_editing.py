from pathlib import Path
import copy
import math
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from editing import REGISTRY, decisions, compile_effects, sync_frame, speech_edits, subtitle_config, validate_matte
from edit import compile_edit
from temporal import ramp_segments

INFO = {'streams': [{'codec_type': 'video', 'width': 1920, 'height': 1080}, {'codec_type': 'audio'}], 'format': {'duration': '30'}}


class EditingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'clip.mp4').write_bytes(b'fixture')
        self.project = {'title': 'Test', 'beats': [{'id': 'beat', 'lines': [{'id': 'line', 'text': '音から守る。'}]}],
                        'shots': [{'id': 'shot', 'path': 'clip.mp4'}], 'editing': {'version': 1, 'events': []}}
        self.records = [{'id': 'line', 'text': '音から守る。', 'from': 30, 'to': 150}]
        self.shots = [{'id': 'shot', 'path': 'clip.mp4', 'from': 0, 'to': 180, 'media': 'video', 'source_start': 2, 'speed': 1}]

    def event(self, **kwargs):
        return {'id': 'accent', 'effect': 'punch_zoom', 'at': {'line': 'line', 'offset': .2},
                'target': {'shot': 'shot'}, 'reason': '説明の焦点を示す', **kwargs}

    def compile(self):
        return compile_effects(self.root, self.project, self.records, self.shots, 6, 30)

    def test_legacy_project_has_no_automatic_effects(self):
        self.project.pop('editing')
        self.assertEqual(decisions(self.project), [])

    def test_version_unknown_effect_and_invalid_parameters_fail(self):
        bad = [self.event(effect='zoom_typo'), self.event(intensity=True), self.event(intensity=float('nan')),
               self.event(intensity=1.1), self.event(params={'peak_scale': 12}), self.event(params={'speeed': 2}),
               self.event(reason=''), self.event(version=2), self.event(target={'shot': 'missing'})]
        for e in bad:
            with self.subTest(e=e), self.assertRaises(ValueError):
                self.project['editing']['events'] = [e]
                decisions(self.project)

    def test_zero_intensity_is_identity(self):
        self.project['editing']['events'] = [self.event(intensity=0)]
        self.assertEqual(self.compile()[0], [])

    def test_narration_retiming_moves_picture_and_sound_together(self):
        self.project['editing'].update(sounds={'hit': {'path': 'clip.mp4', 'duration': .5, 'marker': .1}})
        self.project['editing']['events'] = [self.event(audio={'sfx': 'hit', 'sync': 'impact'})]
        with patch('editing.media_info', return_value=INFO):
            first, sounds, _ = self.compile()
            self.records[0]['from'] = 60
            later, moved, _ = self.compile()
        self.assertEqual(later[0]['from'] - first[0]['from'], 30)
        self.assertEqual(moved[0]['from'] - sounds[0]['from'], 30)
        self.assertEqual(sounds[0]['from'] + 3, first[0]['sync_frame'])

    def test_patterns_make_one_sound_and_keep_semantic_reason(self):
        e = self.event(pattern='emphasize_claim', target={'line': 'line', 'shot': 'shot', 'keyword': '音'}, audio={'sfx': 'hit'})
        e.pop('effect')
        self.project['editing']['events'] = [e]
        expanded = decisions(self.project)
        self.assertEqual([x['effect'] for x in expanded], ['punch_zoom', 'keyword_highlight'])
        self.assertEqual(sum('audio' in x for x in expanded), 1)
        self.assertTrue(all(x['reason'] == e['reason'] for x in expanded))

    def test_invalid_keyword_cannot_invent_subtitle_copy(self):
        self.project['editing']['events'] = [self.event(effect='keyword_highlight', target={'line': 'line', 'keyword': '最強'})]
        with self.assertRaisesRegex(ValueError, '原稿'):
            decisions(self.project)

    def test_variation_is_repeatable_and_bounded(self):
        self.project['editing']['events'] = [self.event(variation=1, seed='fixed')]
        a = decisions(self.project)
        self.assertEqual(a, decisions(copy.deepcopy(self.project)))
        self.assertLessEqual(abs(a[0]['duration'] - .2), .2 * .08)

    def test_target_boundary_and_duplicate_effects_fail(self):
        for events in [[self.event(at=5.9)], [self.event(), self.event(id='other')]]:
            self.project['editing']['events'] = events
            with self.assertRaises(ValueError):
                self.compile()

    def test_tightening_requires_a_whole_line_and_rejects_double_trim(self):
        e = self.event(effect='jump_cut_tighten', target={'line': 'line'})
        e.pop('at')
        self.project['editing']['events'] = [e]
        self.assertEqual(speech_edits(self.project)['line']['params']['gap'], .12)
        self.project['editing']['events'].append({**e, 'id': 'double'})
        with self.assertRaises(ValueError):
            speech_edits(self.project)

    def test_density_is_advice_and_not_a_fake_quality_gate(self):
        self.project['editing']['events'] = [self.event(at=2), self.event(id='second', at=2.5)]
        effects, _, warnings = self.compile()
        self.assertEqual(len(effects), 2)
        self.assertTrue(any('近接' in w for w in warnings))

    def test_speed_ramp_is_monotonic_and_accounts_for_extra_source(self):
        e = {'local_from': 30, 'local_to': 60, 'intensity': .5, 'params': {'peak': 3}}
        segments, consumed = ramp_segments(90, 30, [e])
        self.assertAlmostEqual(consumed, 4, places=6)
        self.assertEqual(segments[0]['speed'], 1)
        self.assertEqual(segments[-1]['speed'], 1)
        self.assertTrue(all(s['source_to'] > s['source_from'] for s in segments))
        self.assertTrue(all(abs(a['source_to'] - b['source_from']) < 1e-9 for a, b in zip(segments, segments[1:])))

    def test_gpu_is_explicit_and_mattes_are_required(self):
        for name in ['rgb_split', 'glitch_burst', 'subject_popout', 'parallax_push']:
            self.project['editing']['events'] = [self.event(effect=name)]
            with self.assertRaises(ValueError):
                self.compile()

    def test_whip_preserves_duration_and_checks_real_handles(self):
        self.project['shots'].append({'id': 'next', 'path': 'clip.mp4'})
        self.shots[0]['to'] = 90
        self.shots.append({**self.shots[0], 'id': 'next', 'from': 90, 'to': 180, 'source_start': 3})
        self.project['editing']['events'] = [self.event(effect='whip_transition', at={'shot': 'next'}, target={'shot': 'next'})]
        with patch('editing.media_info', return_value=INFO):
            effects, _, _ = self.compile()
            self.assertEqual((effects[0]['from'], effects[0]['to']), (87, 93))
            self.assertEqual(self.shots[-1]['to'], 180)
            self.shots[-1]['source_start'] = 0
            with self.assertRaisesRegex(ValueError, '余白'):
                self.compile()

    def test_registry_contains_all_sixteen_primitives(self):
        self.assertEqual(len(REGISTRY['effects']), 16)
        self.assertEqual(len(REGISTRY['patterns']), 8)

    def test_word_anchor_uses_actual_alignment_and_refuses_estimation(self):
        self.project['editing']['events'] = [self.event(at={'line': 'line', 'word': '音'})]
        with self.assertRaisesRegex(ValueError, '時刻'):
            self.compile()
        self.records[0]['captions'] = [{'text': '音', 'startMs': 450, 'endMs': 800}, {'text': 'から守る。', 'startMs': 800, 'endMs': 3000}]
        effects, _, _ = self.compile()
        self.assertEqual(effects[0]['from'], 44)

    def test_caption_alignment_does_not_change_beat_origin(self):
        from common import write_json
        from production import prepare
        (self.root / 'voice.wav').write_bytes(b'fixture')
        write_json(self.root / 'words.json', [{'text': '音', 'startMs': 200, 'endMs': 600}, {'text': 'から守る。', 'startMs': 800, 'endMs': 1800}])
        p = self.project
        p['beats'] = [{'id': 'intro', 'duration': 1}, {'id': 'body', 'duration': 2.5, 'lines': [
            {'id': 'line', 'text': '音から守る。', 'path': 'voice.wav', 'caption_path': 'words.json', 'gap': .2}]}]
        with patch('production.ffprobe', return_value={'streams':[{'codec_type':'audio'}], 'format':{'duration':'2'}}), patch('edit.ffprobe', return_value=INFO):
            result = prepare(self.root, p)
        self.assertEqual(result['durationInFrames'], 105)
        self.assertEqual(result['lines'][0]['from'], 30)
        self.assertEqual(result['beats'][1]['from'], 30)

    def test_rgba_container_without_actual_transparency_is_rejected(self):
        import cv2
        import numpy as np
        image = np.full((4, 4, 4), 255, dtype=np.uint8)
        path = self.root / 'matte.png'
        cv2.imencode('.png', image)[1].tofile(path)
        with self.assertRaisesRegex(ValueError, '透過領域'):
            validate_matte(self.root, 'matte.png')
        image[0, 0, 3] = 0
        cv2.imencode('.png', image)[1].tofile(path)
        validate_matte(self.root, 'matte.png')

    def test_layer_landing_is_reachable_even_with_short_durations(self):
        for length in (9, 24, 33):
            e = {'effect': 'subject_popout', 'stage': 'layers', 'from': 30, 'to': 30 + length}
            self.assertTrue(30 < sync_frame(e, 30, 'landing') < e['to'] - 1)

    def test_stale_review_timing_is_rejected(self):
        from production import timing_digest
        from review import verify_timing
        timing = {'lines': self.records}
        receipt = {'timing_sha256': timing_digest(timing)}
        verify_timing(receipt, timing)
        self.records[0]['from'] += 1
        with self.assertRaisesRegex(ValueError, '時間表'):
            verify_timing(receipt, timing)

    def test_empty_safe_area_and_bad_row_count_are_rejected(self):
        from common import REPO_ROOT, read_json
        style = read_json(REPO_ROOT / 'style.json')
        for subtitles in ({'max_lines': 1.5}, {'safe_area': {'left': 700, 'right': 500, 'top': 0, 'bottom': 0}}):
            with self.assertRaises(ValueError):
                subtitle_config(style, {'subtitles': subtitles})

    def test_published_schema_tracks_all_registry_parameters(self):
        from common import REPO_ROOT, read_json
        from editing_schema import schema
        self.assertEqual(schema(), read_json(REPO_ROOT / 'editing/schema.v1.json'))
        self.assertEqual(len(schema()['properties']['events']['items']['oneOf']), 24)

    def test_overloaded_raw_mix_is_rejected_before_loudness_can_hide_it(self):
        from production import normalize_loudness
        with patch('production.measure_loudness', return_value={'input_tp': '.03', 'input_i': '-13'}), patch('production.run') as process:
            with self.assertRaisesRegex(ValueError, '正規化前'):
                normalize_loudness(self.root / 'raw.mp4', self.root / 'final.mp4', 2)
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
