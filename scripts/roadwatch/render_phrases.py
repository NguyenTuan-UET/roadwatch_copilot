"""WP-B2: render the MVP phrase library once, offline, and report what the config's `audio` section needs.

    python -m scripts.roadwatch.render_phrases --model vi_VN-vais1000-medium --data-dir models/piper
    python -m scripts.roadwatch.render_phrases --check config/proposals/v0.yaml
    python -m scripts.roadwatch.render_phrases --check config/proposals/v0.yaml --play

The product never runs TTS (ADR-12): B only names a phrase_id, the live sink plays `<phrase_dir>/<phrase_id>.wav`,
and the pure arbiter knows when a phrase ends from its duration in `audio.phrases` (spec 3.6). So after every
render: listen to all phrases, then copy the printed durations and hash into `audio` of the proposed config.
Piper adds random noise, so two renders of the same text differ: once a config pins `phrases_sha256`, hand the WAV
files over as files; rendering again gives another library and needs the config updated.

Next to the library the render writes MANIFEST.json (engine, voice, licences, wording status, hash of each file)
and `draft/` with phrases for warnings that do not exist yet; neither is part of `audio.phrases`.

Piper is a tool on the rendering machine only (`pip install piper-tts`, then
`python -m piper.download_voices vi_VN-vais1000-medium --data-dir models/piper`); it is not a project dependency.
piper-tts is GPL-3.0-or-later (OHF-Voice/piper1-gpl). The voice comes from the VAIS-1000 corpus, CC BY 4.0
(its MODEL_CARD in rhasspy/piper-voices): credit it wherever the audio is published.
Run with piper-tts 1.8.0 on Windows on 02/10/2026; not run in CI (see WP-B2 in the plan).
"""

import argparse
import importlib.metadata
import json
import math
import struct
import subprocess
import sys
import tempfile
import time
import wave
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import yaml

from src.roadwatch.configread import ConfigError
from src.roadwatch.contracts.config import Audio
from src.roadwatch.live import default_play
from src.roadwatch.runtime import check_phrases, phrases_sha256, wav_duration_ms
from src.roadwatch.source import file_sha256

# phrase_id -> what the driver hears (OQ-B5). None may ask the driver to look at a screen.
# ponytail: wording of recovery and reminder is a proposal until the listening test (WP-D9, WP-B7).
PHRASES = {
    "emergency": "Phanh! Xe trước",  # after the beep
    "warning": "Giãn thêm khoảng cách",
    "info": "Xe trước đang gần lại",  # used from week 2 (WP-B6)
    "system_off": "Hệ thống cảnh báo tạm dừng",
    "cap_distance_off": "Cảnh báo khoảng cách tạm tắt",
    "cap_ttc_off": "Cảnh báo va chạm tạm tắt",
    "recovery": "Cảnh báo đã hoạt động lại",
    "reminder": "Cảnh báo vẫn chưa hoạt động đầy đủ",  # only when remind_interval is set (OQ-A8)
}
PHRASES_APPROVED = False  # OQ-B5: the wording above is a proposal until the PO approves it
# Draft wording for week 2-4 warnings that do not exist yet (OQ-A13, OQ-A14), rendered into `draft/` for listening
# only: no alert kind names these ids, and they are outside `audio.phrases` and its hash.
DRAFT_PHRASES = {
    "pedestrian": "Cẩn thận! Người phía trước",
    "lane_departure": "Xe đang lệch làn",
}
# ponytail: beep shape is a first guess (high, fast pulses read as urgent); tune it at the listening test.
BEEP_HZ, BEEP_PULSE_MS, BEEP_GAP_MS, BEEP_PULSES = 2000, 100, 50, 3


def beep_pcm(rate: int) -> bytes:
    """16-bit mono samples: BEEP_PULSES tone pulses separated by silence."""
    pulse = [int(20000 * math.sin(2 * math.pi * BEEP_HZ * i / rate)) for i in range(rate * BEEP_PULSE_MS // 1000)]
    gap = [0] * (rate * BEEP_GAP_MS // 1000)
    samples = (pulse + gap) * (BEEP_PULSES - 1) + pulse
    return struct.pack(f"<{len(samples)}h", *samples)


def piper(model: str, data_dir: Path | None) -> Callable[[str, Path], None]:
    def synth(text: str, wav_path: Path) -> None:
        cmd = [sys.executable, "-m", "piper", "-m", model, "-f", str(wav_path)]
        cmd += ["--data-dir", str(data_dir)] if data_dir else []
        subprocess.run([*cmd, "--", text], check=True)

    return synth


def render(out_dir: Path, synth: Callable[[str, Path], None], phrases: dict[str, str] = PHRASES) -> None:
    """One `<phrase_id>.wav` per phrase, 16-bit mono PCM; the emergency phrase starts with the beep."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for phrase_id, text in phrases.items():
            raw = Path(tmp) / f"{phrase_id}.wav"
            synth(text, raw)
            with wave.open(str(raw), "rb") as w:  # raises wave.Error on anything but PCM
                if (w.getnchannels(), w.getsampwidth()) != (1, 2):
                    raise ValueError(f"{phrase_id}: expected 16-bit mono PCM from the synthesizer")
                rate, frames = w.getframerate(), w.readframes(w.getnframes())
            with wave.open(str(out_dir / f"{phrase_id}.wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rate)
                w.writeframes((beep_pcm(rate) if phrase_id == "emergency" else b"") + frames)


def audio_section(phrase_dir: Path) -> dict:
    """What the rendered library gives the config: `audio.phrases` (durations) and `audio.phrases_sha256`."""
    return {
        "phrases": {phrase_id: wav_duration_ms(phrase_dir / f"{phrase_id}.wav") for phrase_id in PHRASES},
        "phrases_sha256": phrases_sha256(phrase_dir, PHRASES),
    }


def manifest(out_dir: Path, model: str, data_dir: Path | None) -> dict:
    """Where the audio came from; it travels with the WAV files (engine, voice, licences, wording status)."""
    try:
        meta = importlib.metadata.metadata("piper-tts")
        engine = {"version": meta["Version"], "license": meta["License"]}
    except importlib.metadata.PackageNotFoundError:
        engine = {"version": None, "license": None}
    voice_dir = Path(data_dir or ".")
    onnx, card = voice_dir / f"{model}.onnx", voice_dir / f"{model}.MODEL_CARD"

    def files(folder: Path, phrases: dict[str, str]) -> dict:
        return {
            k: {
                "text": t,
                "duration_ms": wav_duration_ms(folder / f"{k}.wav"),
                "sha256": file_sha256(folder / f"{k}.wav"),
            }
            for k, t in phrases.items()
        }

    return {
        "status": "approved" if PHRASES_APPROVED else "draft: the wording awaits the PO (spec 10.1, OQ-B5)",
        "rendered_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "engine": {"name": "piper-tts", **engine, "source": "https://github.com/OHF-voice/piper1-gpl"},
        "voice": {
            "name": model,
            "source": "https://huggingface.co/rhasspy/piper-voices",
            "model_sha256": file_sha256(onnx) if onnx.exists() else None,
            "model_card": card.read_text(encoding="utf-8") if card.exists() else None,  # dataset and its licence
        },
        "phrases": files(out_dir, PHRASES),
        "phrases_sha256": phrases_sha256(out_dir, PHRASES),
        "draft_phrases_note": "listening only: no alert uses these ids; outside audio.phrases (OQ-A13, OQ-A14)",
        "draft_phrases": files(out_dir / "draft", DRAFT_PHRASES),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=Path("models/phrases"), help="phrase_dir of the config")
    p.add_argument("--model", help="Piper voice, e.g. vi_VN-vais1000-medium")
    p.add_argument("--data-dir", type=Path, help="where the Piper voice files are")
    p.add_argument("--check", metavar="CONFIG_YAML", help="do not render: compare the library with this config")
    p.add_argument("--play", action="store_true", help="with --check: play every phrase through the live sink")
    a = p.parse_args(argv)
    if a.check:
        audio = Audio.model_validate(yaml.safe_load(Path(a.check).read_text(encoding="utf-8"))["audio"])
        try:
            check_phrases(audio)
            play = default_play(audio.phrase_dir) if a.play else None  # refuses when this OS has no backend
        except ConfigError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(json.dumps(audio_section(Path(audio.phrase_dir)), indent=2))
        for phrase_id, duration_ms in audio.phrases.items() if play else ():
            print(f"playing {phrase_id}: {PHRASES.get(phrase_id, '')}", file=sys.stderr)
            play(phrase_id)
            time.sleep(duration_ms / 1000 + 0.5)
        return 0
    if not a.model:
        p.error("--model is required to render")
    synth = piper(a.model, a.data_dir)
    render(a.out, synth)
    render(a.out / "draft", synth, DRAFT_PHRASES)
    text = json.dumps(manifest(a.out, a.model, a.data_dir), ensure_ascii=False, indent=2)
    (a.out / "MANIFEST.json").write_text(text + "\n", encoding="utf-8")
    print(yaml.safe_dump(audio_section(a.out), sort_keys=False, allow_unicode=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
