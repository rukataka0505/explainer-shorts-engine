from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from edit import compile_edit, resolve_time
from production import prepare, load_project
from common import write_json

INFO = {'streams': [{'codec_type': 'video', 'width': 1920, 'height': 1080}, {'codec_type': 'audio'}], 'format': {'duration': '30'}}

class EditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'clip.mp4').write_bytes(b'fixture')
        self.lines = {'reveal': {'start': 2, 'end': 4}}
        self.project = {'shots': [
            {'path': 'clip.mp4', 'from': 0, 'to': {'line': 'reveal', 'offset': -.2}},
            {'path': 'clip.mp4', 'from': {'line': 'reveal', 'offset': -.2}, 'source_start': 5}
        ], 'audio': [{'path': 'clip.mp4', 'from': 1.5, 'to': 4.5, 'source_start': 3, 'duck': True}]}

    @patch('edit.ffprobe', return_value=INFO)
    def test_cuts_follow_retimed_narration_and_audio_remains_independent(self, _):
        shots, audio = compile_edit(self.root, self.project, self.lines, 6, 30)
        self.assertEqual(shots[0]['to'],54)
        self.assertEqual(audio[0]['from'],45)
        moved={'reveal':{'start':3, 'end':5}}
        shots,_ = compile_edit(self.root,self.project,moved,7,30)
        self.assertEqual(shots[1]['from'],84)

    @patch('edit.ffprobe', return_value=INFO)
    def test_source_speed_is_included_in_exhaustion_check(self, _):
        self.project['shots'][1].update(source_start=24, speed=2)
        with self.assertRaisesRegex(ValueError, '尺が足りません'):
            compile_edit(self.root,self.project,self.lines,6,30)

    @patch('edit.ffprobe', return_value=INFO)
    def test_visible_gap_fails_and_overlap_fails(self, _):
        for start in [1.7,1.9]:
            self.project['shots'][1]['from']=start
            with self.assertRaisesRegex(ValueError,'空白または重複'):
                compile_edit(self.root,self.project,self.lines,6,30)

    def test_missing_or_escaping_media_fails(self):
        for path in ['missing.mp4','../outside.mp4']:
            self.project['shots'][0]['path']=path
            with self.assertRaises(ValueError):
                compile_edit(self.root,self.project,self.lines,6,30)

    @patch('edit.ffprobe', return_value=INFO)
    def test_short_audio_does_not_silently_repeat(self,_):
        self.project['audio'][0]['source_start']=29
        with self.assertRaisesRegex(ValueError,'音素材の尺'):
            compile_edit(self.root,self.project,self.lines,6,30)

    def test_invalid_time_reference_is_an_error(self):
        for value in [{'line':'missing'},{'line':'reveal','edge':'middle'},float('nan'),True]:
            with self.assertRaises(ValueError):
                resolve_time(value,self.lines,6)

    @patch('production.Voicevox', side_effect=AssertionError('recorded narration must work offline'))
    @patch('production.ffprobe', return_value={'streams':[{'codec_type':'audio'}], 'format':{'duration':'1.015'}})
    @patch('edit.ffprobe', return_value=INFO)
    def test_recorded_narration_uses_frame_rounded_end_without_clipping(self,*_):
        project={'title':'Test', 'beats':[{'id':'beat','lines':[{'id':'line','text':'Recorded','path':'clip.mp4','gap':0}]}], 'shots':[{'path':'clip.mp4'}]}
        write_json(self.root/'project.json',project)
        result=prepare(self.root,load_project(self.root))
        self.assertEqual(result['lines'][0]['to'],31)
        self.assertEqual(result['durationInFrames'],31)
        self.assertEqual(result['shots'][0]['to'],31)
