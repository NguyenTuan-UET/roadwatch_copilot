"""WP-B2: the phrase library (spec 3.6, 4.5). Piper itself is replaced by a tone writer; everything else is real."""

import json
import math
import struct
import wave
from typing import get_args

import pytest
import yaml

from scripts.roadwatch import render_phrases as rp
from src.roadwatch import configstore as cs
from src.roadwatch import live
from src.roadwatch.contracts.config import Audio
from src.roadwatch.contracts.streams import AlertKind
from src.roadwatch.runtime import check_phrases, run, wav_duration_ms
from tests.roadwatch.test_runtime import setup  # noqa: F401 - pytest fixture reuse

RATE = 22050
SPEECH_MS = 600


def _write_tone(path, ms=SPEECH_MS, rate=RATE):
    n = rate * ms // 1000
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 7))) for i in range(n)))


def fake_synth(text, wav_path):
    """Stands in for Piper: 600 ms of 16-bit mono audio whatever the text."""
    _write_tone(wav_path)


def _audio(phrase_dir) -> Audio:
    return Audio(max_cmd_age_ms=1500, phrase_dir=str(phrase_dir), **rp.audio_section(phrase_dir))


def test_every_alert_kind_b_can_emit_has_a_phrase_text():
    assert set(rp.PHRASES) == set(get_args(AlertKind))


def test_render_writes_one_pcm_wav_per_phrase_and_puts_the_beep_before_the_emergency_phrase(tmp_path):
    rp.render(tmp_path, fake_synth)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(f"{k}.wav" for k in rp.PHRASES)
    with wave.open(str(tmp_path / "emergency.wav"), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, RATE)
        frames = w.readframes(w.getnframes())
    beep = rp.beep_pcm(RATE)
    assert len(beep) / 2 / RATE * 1000 == pytest.approx(400, abs=0.1)  # 3 pulses of 100 ms, 2 gaps of 50 ms
    assert frames.startswith(beep) and max(struct.unpack_from("<200h", beep)) > 10000  # an audible tone, not silence
    assert wav_duration_ms(tmp_path / "emergency.wav") == SPEECH_MS + 400
    assert wav_duration_ms(tmp_path / "warning.wav") == SPEECH_MS  # only the emergency phrase gets the beep


def test_audio_section_gives_the_durations_and_a_hash_that_follows_the_files(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    rp.render(a, fake_synth)
    rp.render(b, fake_synth)
    section = rp.audio_section(a)
    assert section["phrases"] == {k: SPEECH_MS + (400 if k == "emergency" else 0) for k in rp.PHRASES}
    assert section["phrases_sha256"] == rp.audio_section(b)["phrases_sha256"]  # same audio, same hash
    _write_tone(b / "warning.wav", ms=700)
    assert rp.audio_section(b)["phrases_sha256"] != section["phrases_sha256"]


def test_check_phrases_accepts_the_library_the_config_describes(tmp_path):
    rp.render(tmp_path, fake_synth)
    check_phrases(_audio(tmp_path))


def test_check_phrases_refuses_a_missing_phrase_and_one_with_another_duration(tmp_path):
    rp.render(tmp_path, fake_synth)
    audio = _audio(tmp_path)
    _write_tone(tmp_path / "warning.wav", ms=900)  # re-rendered without updating the config
    with pytest.raises(cs.ConfigError, match="warning.*900 ms.*600 ms"):
        check_phrases(audio)
    (tmp_path / "warning.wav").unlink()
    with pytest.raises(cs.ConfigError, match="warning"):
        check_phrases(audio)


def test_check_phrases_refuses_a_library_whose_hash_is_not_the_configured_one(tmp_path):
    """D-16: a file swapped for another one of the same duration is caught by `audio.phrases_sha256`."""
    rp.render(tmp_path, fake_synth)
    audio = _audio(tmp_path)
    _write_tone(tmp_path / "warning.wav", rate=44100)  # still 600 ms, other samples
    with pytest.raises(cs.ConfigError, match="phrases_sha256"):
        check_phrases(audio)
    check_phrases(audio.model_copy(update={"phrases_sha256": None}))  # library not pinned: durations only


def test_check_command_compares_the_library_with_a_config_file(tmp_path, capsys):
    """What the WP-B2 reviewer runs: every phrase_id of the config has its WAV, with the configured duration."""
    lib = tmp_path / "phrases"
    rp.render(lib, fake_synth)
    cfg = tmp_path / "proposal.yaml"
    cfg.write_text(yaml.safe_dump({"audio": _audio(lib).model_dump()}), encoding="utf-8")
    assert rp.main(["--check", str(cfg)]) == 0
    assert json.loads(capsys.readouterr().out) == rp.audio_section(lib)
    (lib / "recovery.wav").unlink()
    assert rp.main(["--check", str(cfg)]) == 2 and "recovery" in capsys.readouterr().err


def test_check_command_can_play_every_phrase_through_the_live_backend(tmp_path, capsys, monkeypatch):
    """Hand-over: the keeper of the demo machine hears the library through the very sink a live run uses."""
    lib = tmp_path / "phrases"
    rp.render(lib, fake_synth)
    cfg = tmp_path / "proposal.yaml"
    cfg.write_text(yaml.safe_dump({"audio": _audio(lib).model_dump()}), encoding="utf-8")
    played, slept = [], []
    monkeypatch.setattr(rp, "default_play", lambda phrase_dir: played.append)
    monkeypatch.setattr(rp.time, "sleep", slept.append)
    assert rp.main(["--check", str(cfg), "--play"]) == 0
    assert sorted(played) == sorted(rp.PHRASES) and len(slept) == len(played) and min(slept) >= SPEECH_MS / 1000
    capsys.readouterr()


class _FakePopen:
    started: list = []

    def __init__(self, cmd):
        self.cmd, self.terminated = cmd, False
        _FakePopen.started.append(self)

    def terminate(self):
        self.terminated = True


def test_on_linux_the_speaker_is_aplay_and_a_new_phrase_cuts_the_one_being_played(monkeypatch):
    """Spec 3.6: starting a phrase preempts the previous one; winsound does it itself, aplay has to be stopped."""
    _FakePopen.started = []
    monkeypatch.setattr(live.sys, "platform", "linux")
    monkeypatch.setattr(live.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(live.subprocess, "Popen", _FakePopen)
    play = live.default_play("lib")
    play("warning")
    play("emergency")
    first, second = _FakePopen.started
    assert first.cmd[:2] == ["/usr/bin/aplay", "-q"] and first.cmd[2].endswith("warning.wav")
    assert first.terminated and not second.terminated and second.cmd[2].endswith("emergency.wav")


def test_a_machine_without_an_audio_backend_is_refused_instead_of_running_silent(monkeypatch):
    monkeypatch.setattr(live.sys, "platform", "linux")
    monkeypatch.setattr(live.shutil, "which", lambda name: None)  # Linux without alsa-utils
    with pytest.raises(cs.ConfigError, match="no audio backend.*aplay.*simulated"):
        live.default_play("lib")
    monkeypatch.setattr(live.sys, "platform", "darwin")
    with pytest.raises(cs.ConfigError, match="no audio backend on darwin"):
        live.default_play("lib")


def test_live_run_that_would_really_speak_refuses_to_start_without_its_phrase_library(setup, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.chdir(tmp_path)  # the config's phrase_dir is relative: nothing to play here
    setup.mode, setup.play = "live", None
    with pytest.raises(cs.ConfigError, match="phrase"):
        run(setup)
    assert not (setup.out_root).exists()  # refused before anything was recorded
