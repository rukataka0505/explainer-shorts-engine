import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from speech import synthesize
from production import load_project


class FakeEngine:
    provider = 'aivisspeech'
    version = '1.0'
    model_version = '1.0'
    calls = 0

    def identity(self, style):
        return {'uuid': 'speaker', 'name': 'にせ', 'model_version': self.model_version}

    def post(self, endpoint, params, payload=None):
        self.calls += 1
        if endpoint == 'audio_query':
            return json.dumps({'tempoDynamicsScale': 1, 'speedScale': 1}).encode()
        stream = io.BytesIO()
        with wave.open(stream, 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(b'\x01\x00' * 2400)
        return stream.getvalue()


class AivisTests(unittest.TestCase):
    def test_cache_isolated_by_provider_and_model_and_repairs_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            client = FakeEngine()
            record, reused = synthesize(client, cache, '水。', 1937616896, {'tempoDynamicsScale': .8})
            self.assertFalse(reused)
            self.assertEqual(record['query']['tempoDynamicsScale'], .8)
            self.assertTrue(synthesize(client, cache, '水。', 1937616896, {'tempoDynamicsScale': .8})[1])
            self.assertEqual(client.calls, 2)
            Path(record['path']).write_bytes(b'broken')
            self.assertFalse(synthesize(client, cache, '水。', 1937616896, {'tempoDynamicsScale': .8})[1])
            client.model_version = '2.0'
            self.assertFalse(synthesize(client, cache, '水。', 1937616896, {'tempoDynamicsScale': .8})[1])
            client.provider = 'voicevox'
            self.assertFalse(synthesize(client, cache, '水。', 1937616896, {'tempoDynamicsScale': .8})[1])

    def test_elevenlabs_defaults_survive_new_default_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = {'title':'test','voices':{'narrator':{'provider':'elevenlabs'}},
                       'beats':[{'id':'b','duration':1}], 'shots':[{'path':'unused.mp4'}]}
            (root/'project.json').write_text(json.dumps(project))
            voice = load_project(root)['voices']['narrator']
            self.assertEqual(voice['model_id'], 'eleven_multilingual_v2')
            self.assertNotIn('style_id', voice)

    def test_unknown_query_setting_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                synthesize(FakeEngine(), Path(directory), '水。', 1937616896, {'typo': 1})


if __name__ == '__main__':
    unittest.main()
