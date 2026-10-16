"""Alert sounds of docs/warning_to_do.md made from tones, no recording: chime.wav (one soft "ding"), emergency.wav (three
short high beeps) and, given a recorded voice, warning.wav = two beeps + that voice. Standard library only; 48 kHz mono
16-bit like the recorded phrases. info.wav stays a plain recording.

    python -m scripts.roadwatch.make_alert_sounds [--out models/phrases-demo] [--warning-voice qua_gan.wav]
"""
import argparse
import array
import math
import wave
from pathlib import Path

RATE = 48000


def tone(partials, dur, peak, decay=None, fade=0.005):
    """Sum of (Hz, weight) sines for dur s, peak amplitude, 5 ms fades (no click), optional exponential decay (s)."""
    total = sum(w for _, w in partials)
    out = []
    for i in range(round(dur * RATE)):
        t = i / RATE
        env = min(1.0, t / fade, (dur - t) / fade) * (math.exp(-t / decay) if decay else 1.0)
        out.append(peak * env * sum(w * math.sin(2 * math.pi * f * t) for f, w in partials) / total)
    return out


def beeps(n, hz, on, off, peak):
    out = []
    for i in range(n):
        out += tone([(hz, 1.0)], on, peak) + ([0.0] * round(off * RATE) if i < n - 1 else [])
    return out


def read(path):
    with wave.open(str(path)) as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, RATE):
            raise SystemExit(f'{path}: cần WAV mono 16-bit {RATE} Hz')
        return [x / 32767 for x in array.array('h', w.readframes(w.getnframes()))]


def write(path, samples):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(array.array('h', (round(max(-1.0, min(1.0, x)) * 32767) for x in samples)).tobytes())


def make(out, warning_voice=None):
    out = Path(out)
    write(out / 'chime.wav', tone([(880, 1.0), (1760, 0.35), (2640, 0.12)], 0.35, 0.5, decay=0.12))   # 0.35 s
    write(out / 'emergency.wav', beeps(3, 1800, 0.09, 0.06, 0.8))                                        # 0.39 s
    if warning_voice:   # 2 beeps (0.32 s), 0.1 s pause, then the voice
        write(out / 'warning.wav', beeps(2, 1000, 0.12, 0.08, 0.7) + [0.0] * round(0.1 * RATE) + read(warning_voice))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='models/phrases-demo')
    ap.add_argument('--warning-voice', help='recorded voice (mono 16-bit 48 kHz WAV) to put after the two beeps')
    a = ap.parse_args()
    make(a.out, a.warning_voice)
    print(f'wrote {a.out}/chime.wav, emergency.wav' + (', warning.wav' if a.warning_voice else ''))


if __name__ == '__main__':
    main()
