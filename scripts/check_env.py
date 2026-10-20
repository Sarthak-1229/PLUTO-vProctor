"""Environment and dependency verification script for PLUTO vProctor.

Verifies:
- Ollama service accessibility and presence of 'qwen2.5:3b'
- ffmpeg executable presence in PATH
- Dataset integrity in datasets/data and datasets/data1 (file list + sizes)
- Python environment version
"""

import sys
import shutil
from pathlib import Path
import urllib.request
import urllib.error
import json

ROOT_DIR = Path(__file__).resolve().parent.parent


def check_python():
    print("=" * 60)
    print("1. Python Environment Check")
    print("=" * 60)
    v = sys.version_info
    print(f"Python executable: {sys.executable}")
    print(f"Python version   : {v.major}.{v.minor}.{v.micro}")
    if v.major == 3 and v.minor >= 10:
        print("[PASS] Python version meets requirement (>= 3.10).")
        return True
    else:
        print("[FAIL] Python 3.10+ required.")
        return False


def check_datasets():
    print("\n" + "=" * 60)
    print("2. Datasets Verification Check")
    print("=" * 60)
    datasets_root = ROOT_DIR / "datasets"
    folders = ["data", "data1"]
    all_ok = True

    for folder_name in folders:
        folder_path = datasets_root / folder_name
        print(f"\nChecking: datasets/{folder_name}/")
        if not folder_path.exists() or not folder_path.is_dir():
            print(f"  [FAIL] Directory {folder_path} does not exist!")
            all_ok = False
            continue

        files = sorted(list(folder_path.glob("*.jsonl")) + list(folder_path.glob("*.json")))
        if not files:
            print(f"  [WARN] No .jsonl or .json files found in {folder_path}")
            all_ok = False
            continue

        for f in files:
            size_bytes = f.stat().st_size
            size_kb = size_bytes / 1024.0
            print(f"  - {f.name:15s} : {size_bytes:8d} bytes ({size_kb:6.1f} KB)")

    if all_ok:
        print("\n[PASS] All expected dataset folders and splits exist.")
    return all_ok


def check_ffmpeg():
    print("\n" + "=" * 60)
    print("3. ffmpeg Multimedia Dependency Check")
    print("=" * 60)
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"[PASS] ffmpeg found at: {ffmpeg_path}")
        return True
    else:
        print("[WARN] ffmpeg is NOT found in system PATH.")
        print("       Install via 'winget install Gyan.FFmpeg' or download from https://ffmpeg.org")
        print("       and ensure ffmpeg/bin is added to your environment PATH.")
        return False


def check_ollama(ollama_url="http://localhost:11434", target_model="qwen2.5:3b"):
    print("\n" + "=" * 60)
    print("4. Ollama & Local LLM Check")
    print("=" * 60)
    print(f"Connecting to Ollama at {ollama_url}...")

    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags", headers={"User-Agent": "PLUTO-vProctor-Check"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in body.get("models", [])]
                print(f"[PASS] Ollama service is reachable. Available models ({len(models)}):")
                for m in models:
                    print(f"       - {m}")

                has_target = any(target_model in m for m in models)
                if has_target:
                    print(f"[PASS] Target model '{target_model}' is installed and ready.")
                    return True
                else:
                    print(f"\n[WARN] Target model '{target_model}' was NOT found in Ollama!")
                    print(f"       Run this command to pull it:")
                    print(f"       >>> ollama pull {target_model}")
                    return False
    except urllib.error.URLError as e:
        print(f"[WARN] Could not connect to Ollama service at {ollama_url}: {e.reason}")
        print("       Make sure Ollama is started:")
        print("       1. Start Ollama from Windows Start menu or run 'ollama serve'")
        print(f"       2. Run 'ollama pull {target_model}'")
        return False
    except Exception as e:
        print(f"[WARN] Error querying Ollama: {e}")
        return False


def main():
    print("Running PLUTO vProctor Environment Diagnostics...")
    py_ok = check_python()
    ds_ok = check_datasets()
    ff_ok = check_ffmpeg()
    ol_ok = check_ollama()

    print("\n" + "=" * 60)
    print("Diagnostics Summary")
    print("=" * 60)
    print(f"Python 3.10+      : {'PASS' if py_ok else 'FAIL'}")
    print(f"Datasets (data, 1): {'PASS' if ds_ok else 'FAIL'}")
    print(f"ffmpeg in PATH    : {'PASS' if ff_ok else 'ACTION REQUIRED'}")
    print(f"Ollama & Qwen 3B  : {'PASS' if ol_ok else 'ACTION REQUIRED'}")
    print("=" * 60)

    # Return 0 if dataset and python are ready (Ollama and ffmpeg are external services)
    if py_ok and ds_ok:
        print("\nCore project skeleton & dataset environment verified.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
