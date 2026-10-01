"""WP-B2: render the MVP phrase library once, offline, and report what the config's `audio` section needs.

    python -m scripts.roadwatch.render_phrases --model vi_VN-vais1000-medium --data-dir models/piper
    python -m scripts.roadwatch.render_phrases --check config/proposals/v0.yaml

The product never runs TTS (ADR-12): B only names a phrase_id, the live sink plays `<phrase_dir>/<phrase_id>.wav`,
and the pure arbiter knows when a phrase ends from its duration in `audio.phrases` (spec 3.6). So after every
render: listen to all phrases, copy the printed durations into the proposed config, keep the hash as evidence.

Piper is a tool on the rendering machine only (`pip install piper-tts`, then
`python -m piper.download_voices vi_VN-vais1000-medium --data-dir models/piper`); it is not a project dependency.
The voice comes from the VAIS-1000 corpus, CC BY 4.0: credit it wherever the audio is published.
The Piper call follows docs/CLI.md of OHF-Voice/piper1-gpl; it has not been run in CI (see WP-B2 in the plan).
"""

import argparse
import json
import math
import struct
import subprocess
import sys
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path

import yaml

from src.roadwatch.configread import ConfigError
from src.roadwatch.contracts.base import canonical_json, sha256_hex
from src.roadwatch.contracts.config import Audio
from src.roadwatch.runtime import check_phrases, wav_duration_ms
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


def render(out_dir: Path, synth: Callable[[str, Path], None]) -> None:
    """One `<phrase_id>.wav` per phrase, 16-bit mono PCM; the emergency phrase starts with the beep."""
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for phrase_id, text in PHRASES.items():
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
    """Measured durations for `audio.phrases` and the hash of the library (evidence for WP-B2)."""
    files = {phrase_id: phrase_dir / f"{phrase_id}.wav" for phrase_id in PHRASES}
    return {
        "phrases": {phrase_id: wav_duration_ms(path) for phrase_id, path in files.items()},
        "library_sha256": sha256_hex(canonical_json({k: file_sha256(p) for k, p in files.items()})),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=Path("models/phrases"), help="phrase_dir of the config")
    p.add_argument("--model", help="Piper voice, e.g. vi_VN-vais1000-medium")
    p.add_argument("--data-dir", type=Path, help="where the Piper voice files are")
    p.add_argument("--check", metavar="CONFIG_YAML", help="do not render: compare the library with this config")
    a = p.parse_args(argv)
    if a.check:
        audio = Audio.model_validate(yaml.safe_load(Path(a.check).read_text(encoding="utf-8"))["audio"])
        try:
            check_phrases(audio)
        except ConfigError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(json.dumps(audio_section(Path(audio.phrase_dir)), indent=2))
        return 0
    if not a.model:
        p.error("--model is required to render")
    render(a.out, piper(a.model, a.data_dir))
    print(yaml.safe_dump(audio_section(a.out), sort_keys=False, allow_unicode=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
