from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from typing import Any

from common import read_json, write_json

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
