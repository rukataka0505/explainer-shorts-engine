import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import upload_youtube as youtube
from common import write_json


class PublishTests(unittest.TestCase):
    def test_publication_preserves_status_and_requires_remote_readback(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            write_json(root/'project.json', {'title':'test'})
            write_json(root/'output/youtube-upload.json', {
                'sha256':'hash','video_id':'test-id','title':'test','watch_url':'https://youtube.com/watch?v=test-id',
                'thumbnail':{'status':'set','sha256':'hash'}})
            stack.enter_context(patch('video.delivery_check'))
            stack.enter_context(patch.object(youtube,'sha256',return_value='hash'))
            stack.enter_context(patch.object(youtube,'load_client_credentials',return_value=('id','secret')))
            stack.enter_context(patch.object(youtube,'obtain_access_token',return_value='test-token'))
            remote = {'snippet':{'title':'test'}, 'processingDetails':{'processingStatus':'succeeded'},
                      'status':{'privacyStatus':'private','embeddable':False,'selfDeclaredMadeForKids':False}}
            get = stack.enter_context(patch.object(youtube,'get_video',side_effect=[remote,{**remote,'status':{**remote['status'],'privacyStatus':'public'}}]))
            put = stack.enter_context(patch.object(youtube,'http_request'))
            result = youtube.publish_video(root)
            self.assertEqual(result['privacy_status'],'public')
            payload = json.loads(put.call_args.kwargs['data'])
            self.assertFalse(payload['status']['embeddable'])
            self.assertFalse(payload['status']['selfDeclaredMadeForKids'])
            self.assertEqual(get.call_count,2)
            get.side_effect = [remote,remote]
            with self.assertRaisesRegex(ValueError,'公開状態'):
                youtube.publish_video(root)

    def test_mismatched_delivery_never_calls_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_json(root/'project.json',{'title':'test'})
            write_json(root/'output/youtube-upload.json',{'sha256':'old'})
            with patch('video.delivery_check'), patch.object(youtube,'sha256',return_value='new'), patch.object(youtube,'load_client_credentials') as credentials:
                with self.assertRaisesRegex(ValueError,'一致'):
                    youtube.publish_video(root)
                credentials.assert_not_called()


if __name__ == '__main__':
    unittest.main()
