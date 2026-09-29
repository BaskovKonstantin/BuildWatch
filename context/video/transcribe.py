import os
import sys
import time
from pathlib import Path

import nvidia.cublas
import nvidia.cudnn

for pkg in (nvidia.cublas, nvidia.cudnn):
    bin_dir = Path(list(pkg.__path__)[0]) / "bin"
    os.add_dll_directory(str(bin_dir))
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ['PATH']}"

from faster_whisper import WhisperModel  # noqa: E402  needs CUDA DLL dirs registered first

HERE = Path(__file__).parent
OUT = HERE / "dgp_transcript.txt"


def load() -> WhisperModel:
    try:
        return WhisperModel("medium", device="cuda", compute_type="float16")
    except Exception as exc:
        print(f"cuda unavailable ({exc}); using cpu small", flush=True)
        return WhisperModel("small", device="cpu", compute_type="int8")


model = load()
start = time.time()
segments, _ = model.transcribe(
    str(HERE / "dgp.wav"), language="ru", vad_filter=True,
    initial_prompt="Департамент градостроительной политики, стройплощадка, техника, камеры, ЛЦТ, BuildWatch",
)
with OUT.open("w", encoding="utf-8") as f:
    for seg in segments:
        line = f"[{int(seg.start // 60):02d}:{int(seg.start % 60):02d}] {seg.text.strip()}"
        f.write(line + "\n")
        f.flush()
        print(line, flush=True)
print(f"DONE in {time.time() - start:.0f}s", flush=True)
sys.exit(0)
