# Wake / kill phrase models — recording + training

Until custom models exist here, the daemon uses openwakeword's bundled
**"Hey Jarvis"** model as the fallback wake phrase, and the spoken OFFLINE kill is
unarmed (the ⌥⌘J hotkey and menu-bar cut always work, with zero network).

Two phrases get their own model:

| Phrase | Env var (.env) | Output file (suggested) |
|---|---|---|
| "Hey Friday" | `WAKE_MODEL_PATH` | `voice/wakeword/wake.onnx` |
| "Stand Down" | `KILL_MODEL_PATH` | `voice/wakeword/standdown.onnx` |

## 1. Record your 50 samples per phrase (~15 min each)

```bash
uv run python -m scripts.record_wakeword                    # wake phrase
uv run python -m scripts.record_wakeword --phrase standdown # kill phrase
```

Guided takes: 15 near, 15 far, 10 quiet, 10 loud → `voice/wakeword/samples/<phrase>/`.
Re-running resumes; delete a .wav to redo it.

## 2. Train the model (openWakeWord)

openWakeWord trains phrase models on synthetic speech; your recordings are for
validation and the optional verifier below. In the upstream repo
(github.com/dscripka/openWakeWord) follow **"Training New Models"** — the
automatic-training notebook (Colab, free tier is enough):

1. Set the target phrase text (e.g. `hey friday`).
2. Run all cells; it generates synthetic data and trains.
3. Export/download the **.onnx** model (this project runs the onnx backend —
   openwakeword 0.4.0 pin, macOS has no tflite wheels).
4. Drop it at `voice/wakeword/wake.onnx` (and `standdown.onnx` for the kill phrase).

## 3. (Optional, cuts false wakes) personal verifier

openwakeword 0.4.0 can train a small verifier on YOUR voice from the recorded
samples. In this repo the workflow is already scaffolded:

```bash
uv run python -m scripts.record_voice_verifier
uv run python -m scripts.train_voice_verifier
```

Then set these in `.env`:

```bash
WAKE_VERIFIER_PATH=voice/wakeword/owner.joblib
WAKE_REQUIRE_VERIFIER=true
```

This strict lock applies to the wake phrase only right now.

## 4. Arm it

In `.env`:

```
WAKE_MODEL_PATH=voice/wakeword/wake.onnx
KILL_MODEL_PATH=voice/wakeword/standdown.onnx
```

Restart the daemon (`uv run python -m client.killswitch`). Tune `WAKE_THRESHOLD`
(default 0.6): raise toward 0.7–0.8 if it false-wakes, lower if it misses you
across the room. Acceptance target: wakes across the room, <2 false wakes/day.
