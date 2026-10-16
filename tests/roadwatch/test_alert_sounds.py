import array
import wave

import pytest

from scripts.roadwatch.make_alert_sounds import RATE, make, write


def samples(path):
    with wave.open(str(path)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, RATE)   # like the recorded phrases
        return array.array('h', w.readframes(w.getnframes()))


def test_tones_are_short_and_the_warning_is_two_beeps_then_the_voice(tmp_path):
    write(tmp_path / 'voice.wav', [0.1] * RATE)   # a 1 s stand-in for the recorded voice
    make(tmp_path, warning_voice=tmp_path / 'voice.wav')
    chime, beeps, warning = (samples(tmp_path / f'{k}.wav') for k in ('chime', 'emergency', 'warning'))
    assert 0.25 <= len(chime) / RATE <= 0.4 and 0.35 <= len(beeps) / RATE <= 0.5
    assert len(warning) / RATE == pytest.approx(1.42, abs=0.01)                  # 0.42 s of beeps + 1 s of voice
    assert max(map(abs, chime + beeps + warning)) < 32767                         # no clipping
    assert chime[0] == 0 and beeps[0] == 0                                        # faded in: no click


def test_without_a_voice_the_warning_file_is_left_alone(tmp_path):
    (tmp_path / 'warning.wav').write_bytes(b'recorded')
    make(tmp_path)
    assert (tmp_path / 'warning.wav').read_bytes() == b'recorded' and (tmp_path / 'chime.wav').exists()
