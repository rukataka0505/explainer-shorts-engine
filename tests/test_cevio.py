import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from speech import synthesize_cevio
from production import load_project
from common import write_json


class FakeCevio:
    version = '9.test'
    casts = ['さとうささら', 'すずきつづみ']

    def __init__(self):
        self.calls = 0

    def identity(self, cast):
        if cast not in self.casts:
            raise ValueError('missing cast')
        return {'name': cast, 'cast': cast, 'host_version': self.version}

    def output_wave(self, text, cast, settings, path):
        self.calls += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(b'\x00\x00' * 4800)
        return {'host_version': self.version, 'cast': cast}


class CevioTests(unittest.TestCase):
    def test_cache_keys_cast_settings_and_engine_version(self):
        client = FakeCevio()
        voice = {'provider': 'cevio', 'cast': 'さとうささら'}
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)
            first, reused = synthesize_cevio(client, cache, 'テスト', voice, {'Speed': 50})
            self.assertFalse(reused)
            self.assertEqual(first['duration'], .1)
            self.assertTrue(synthesize_cevio(client, cache, 'テスト', voice, {'Speed': 50})[1])
            self.assertEqual(client.calls, 1)
            self.assertFalse(synthesize_cevio(client, cache, 'テスト', voice, {'Speed': 51})[1])
            client.version = '10.test'
            self.assertFalse(synthesize_cevio(client, cache, 'テスト', voice, {'Speed': 51})[1])

    def test_default_voice_is_sato_sasara(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_json(root / 'project.json', {
                'title': 'Test',
                'beats': [{'id': 'beat', 'lines': [{'id': 'line', 'text': 'こんにちは'}]}],
                'shots': [{'path': 'clip.mp4'}],
            })
            project = load_project(root)
            self.assertEqual(project['voices']['narrator']['provider'], 'cevio')
            self.assertEqual(project['voices']['narrator']['cast'], 'さとうささら')

    def test_elevenlabs_can_still_be_selected_without_repeating_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_json(root / 'project.json', {
                'title': 'Test',
                'voices': {'narrator': {'provider': 'elevenlabs'}},
                'beats': [{'id': 'beat', 'lines': [{'id': 'line', 'text': 'こんにちは'}]}],
                'shots': [{'path': 'clip.mp4'}],
            })
            project = load_project(root)
            self.assertEqual(project['voices']['narrator']['provider'], 'elevenlabs')
            self.assertEqual(project['voices']['narrator']['voice_id'], 'W8wofKLOWnsM57L8hIx2')


if __name__ == '__main__':
    unittest.main()
