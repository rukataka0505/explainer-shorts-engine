import sys
import unittest
import tempfile
import base64
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from speech import alignment_captions, synthesize_elevenlabs


class ElevenLabsTests(unittest.TestCase):
    def alignment(self):
        return {'characters': ['水', '。'], 'character_start_times_seconds': [0, .8], 'character_end_times_seconds': [.8, 1]}

    def test_text_and_real_timing_are_preserved(self):
        captions = alignment_captions('水。', self.alignment(), 1)
        self.assertEqual(''.join(c['text'] for c in captions), '水。')
        self.assertEqual(captions[1]['startMs'], 800)

    def test_bad_alignment_is_rejected(self):
        for text, alignment in [('火。', self.alignment()), ('水。', {**self.alignment(), 'character_start_times_seconds': [0]}), ('水。', {**self.alignment(), 'character_end_times_seconds': [.8, float('nan')]})]:
            with self.assertRaises(ValueError):
                alignment_captions(text, alignment, 1)

    @patch('common.ffprobe', return_value={'format': {'duration': '1'}})
    def test_cache_reuses_audio_but_changed_voice_or_damaged_audio_regenerates(self, _):
        client = Mock()
        client.request.return_value = {'audio_base64': base64.b64encode(b'mp3-test').decode(), 'alignment': self.alignment()}
        voice = {'voice_id': 'test', 'model_id': 'eleven_multilingual_v2'}
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)
            first, reused = synthesize_elevenlabs(client, cache, '水。', voice, {})
            self.assertFalse(reused)
            self.assertTrue(synthesize_elevenlabs(client, cache, '水。', voice, {})[1])
            self.assertEqual(client.request.call_count, 1)
            Path(first['path']).write_bytes(b'corrupt')
            self.assertFalse(synthesize_elevenlabs(client, cache, '水。', voice, {})[1])
            self.assertFalse(synthesize_elevenlabs(client, cache, '水。', {**voice, 'voice_id': 'other'}, {})[1])


if __name__ == '__main__':
    unittest.main()
