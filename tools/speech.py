from __future__ import annotations

import hashlib
import base64
import math
import json
import os
import urllib.parse
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any

from common import read_json, write_json


class ElevenLabs:
    def __init__(self):
        self.key = next((v for k, v in os.environ.items() if k.upper() == 'ELEVENLABS_API_KEY'), '')
        if not self.key:
            raise ValueError('ELEVENLABS_API_KEYを環境変数に設定してください')

    def request(self, endpoint, payload=None):
        request = urllib.request.Request('https://api.elevenlabs.io/v1/' + endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None,
            headers={'xi-api-key': self.key, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise ValueError(f'ElevenLabs HTTP {exc.code}: API権限・声・残量・設定を確認してください') from None


def alignment_captions(text, alignment, duration):
    if not isinstance(alignment, dict) or ''.join(alignment.get('characters', [])) != text:
        raise ValueError('ElevenLabsの文字時刻が音声原稿と一致しません')
    chars = alignment['characters']
    starts = alignment.get('character_start_times_seconds', [])
    ends = alignment.get('character_end_times_seconds', [])
    if not len(chars) == len(starts) == len(ends):
        raise ValueError('ElevenLabsの文字時刻が不足しています')
    previous = 0
    captions = []
    for char, start, end in zip(chars, starts, ends):
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (start, end)) or not 0 <= previous <= start <= end <= duration + .1:
            raise ValueError('ElevenLabsの文字時刻が不正です')
        captions.append({'text': char, 'startMs': start * 1000, 'endMs': min(end, duration) * 1000,
                         'timestampMs': None, 'confidence': None})
        previous = start
    return captions


def synthesize_elevenlabs(client, cache, text, voice, settings):
    from common import ffprobe
    payload = {'text': text, 'model_id': voice['model_id'], 'voice_settings': settings}
    key_data = {'provider': 'elevenlabs', 'voice_id': voice['voice_id'], 'payload': payload, 'format': 'mp3_44100_128'}
    key = hashlib.sha256(json.dumps(key_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    sound, metadata = cache / f'{key}.mp3', cache / f'{key}.json'
    try:
        record = read_json(metadata)
        if record['key'] == key_data and record['sha256'] == hashlib.sha256(sound.read_bytes()).hexdigest():
            captions = alignment_captions(text, record['alignment'], record['duration'])
            return {**record, 'captions': captions, 'path': str(sound)}, True
    except (OSError, ValueError, KeyError):
        pass
    response = client.request('text-to-speech/' + urllib.parse.quote(voice['voice_id'], safe='') + '/with-timestamps?output_format=mp3_44100_128', payload)
    cache.mkdir(parents=True, exist_ok=True)
    temporary = sound.with_suffix('.tmp.mp3')
    temporary.write_bytes(base64.b64decode(response['audio_base64'], validate=True))
    duration = float(ffprobe(temporary)['format']['duration'])
    captions = alignment_captions(text, response.get('alignment'), duration)
    temporary.replace(sound)
    record = {'key': key_data, 'duration': duration, 'name': voice.get('name', voice['voice_id']),
              'alignment': response['alignment'], 'captions': captions,
              'sha256': hashlib.sha256(sound.read_bytes()).hexdigest()}
    write_json(metadata, record)
    return {**record, 'path': str(sound)}, False

class Voicevox:
    def __init__(self) -> None:
        self.url = os.environ.get("VOICEVOX_URL", "http://127.0.0.1:50021").rstrip("/")
        self.version = self.get("version")
        self.voices = self.get("speakers")

    def get(self, endpoint: str) -> Any:
        with urllib.request.urlopen(f"{self.url}/{endpoint}", timeout=5) as response:
            return json.load(response)

    def post(self, endpoint: str, params: dict, payload: dict | None = None) -> bytes:
        request = urllib.request.Request(
            f"{self.url}/{endpoint}?{urllib.parse.urlencode(params)}",
            data=json.dumps(payload).encode() if payload is not None else b"",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.read()

    def identity(self, style_id: int) -> dict:
        for voice in self.voices:
            for style in voice["styles"]:
                if style["id"] == style_id and style.get("type", "talk") == "talk":
                    return {"uuid": voice["speaker_uuid"], "name": voice["name"]}
        raise ValueError(f"VOICEVOXに読み上げ用の声がありません: {style_id}")


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        data = wav.readframes(frames)
        if frames <= 0 or len(data) != frames * wav.getnchannels() * wav.getsampwidth():
            raise ValueError("破損したWAVです")
        return frames / wav.getframerate()


def synthesize(client: Voicevox, cache: Path, text: str, style_id: int, settings: dict) -> tuple[dict, bool]:
    identity = client.identity(style_id)
    key_data = {"text": text, "style": style_id, "voice": identity["uuid"],
                "settings": settings, "engine": client.version}
    key = hashlib.sha256(json.dumps(key_data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    wav = cache / f"{key}.wav"
    record_path = cache / f"{key}.json"
    try:
        record = read_json(record_path)
        if (record["key"] == key_data and record["sha256"] == hashlib.sha256(wav.read_bytes()).hexdigest()
                and abs(wav_duration(wav) - record["duration"]) < 1e-6
                and isinstance(record["query"], dict)):
            return {**record, **identity, "path": str(wav)}, True
    except (OSError, ValueError, KeyError, wave.Error, EOFError):
        pass
    query = json.loads(client.post("audio_query", {"text": text, "speaker": style_id}))
    for name, value in settings.items():
        if name not in query:
            raise ValueError(f"未対応のVOICEVOX設定: {name}")
        query[name] = value
    cache.mkdir(parents=True, exist_ok=True)
    temporary = wav.with_suffix(".tmp.wav")
    temporary.write_bytes(client.post("synthesis", {"speaker": style_id}, query))
    duration = wav_duration(temporary)
    temporary.replace(wav)
    record = {"key": key_data, "duration": duration, "query": query,
              "sha256": hashlib.sha256(wav.read_bytes()).hexdigest()}
    write_json(record_path, record)
    return {**record, **identity, "path": str(wav)}, False
