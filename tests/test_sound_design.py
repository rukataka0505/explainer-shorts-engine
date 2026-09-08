import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from common import read_json, write_json
from sound_design import draft, warnings, inspect_plan
from sounds import import_sound


class SoundDesignTests(unittest.TestCase):
    def setUp(self):
        self.project = {'beats': [{'id': 'hook'}], 'audio': [{'id': 'field', 'path': 'water.wav'}]}

    def test_omission_is_distinct_from_pending(self):
        self.assertTrue(warnings(self.project))
        self.project['sound_design'] = draft(self.project)
        self.assertEqual(len(warnings(self.project)), 4)
        for item in self.project['sound_design']['beats'][0].values():
            if isinstance(item, dict):
                item.update(decision='omit', reason='声だけで説明する')
        self.assertEqual(warnings(self.project), [])

    def test_adopted_sound_needs_actual_reference(self):
        self.project['sound_design'] = draft(self.project)
        item = self.project['sound_design']['beats'][0]['ambience']
        item.update(decision='use', reason='現場を伝える', refs=['audio:missing'])
        self.assertTrue(any('存在しません' in x for x in warnings(self.project)))
        item['refs'] = ['audio:field']
        self.assertFalse(any('存在しません' in x for x in warnings(self.project)))

    def test_disabled_event_and_stale_beat(self):
        self.project['editing'] = {'events': [{'id': 'hit', 'intensity': 0, 'audio': {'sfx': 'click'}}]}
        self.project['sound_design'] = draft(self.project)
        self.project['sound_design']['beats'][0]['sfx'].update(decision='use', reason='強調', refs=['event:hit'])
        self.assertTrue(any('有効なSE' in x for x in warnings(self.project)))
        self.project['sound_design']['beats'][0]['beat'] = 'deleted'
        with self.assertRaises(ValueError):
            warnings(self.project)

    def test_init_preserves_authored_plan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); write_json(root / 'project.json', self.project)
            inspect_plan(root, True)
            first = (root / 'project.json').read_bytes()
            inspect_plan(root, True)
            self.assertEqual(first, (root / 'project.json').read_bytes())

    def test_import_preserves_custom_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.project['editing'] = {'sounds': {'custom': {'volume': .8}}}
            write_json(root / 'project.json', self.project)
            with patch('sounds.entries', return_value=[{'id': 'custom', 'marker': .01, 'volume': .3}]):
                with self.assertRaises(ValueError):
                    import_sound(root, 'custom')
            self.assertEqual(read_json(root / 'project.json'), self.project)
