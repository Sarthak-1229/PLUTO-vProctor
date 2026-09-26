"""
Updated configuration for PLUTO v2 with enhanced features.
"""

# ============================================================
# VRAM & Model Configuration
# ============================================================
VRAM_BUDGET_MB = 6000
STT_MODEL_SIZE = "small"
LLM_MODEL_NAME = "qwen2.5:7b"   # Primary LLM (~4.5GB VRAM at Q4)
REPORTS_DIR = "reports"
USE_LLM_SUMMARY = True

# STT (Speech-to-Text) is intentionally kept on CPU because qwen2.5:7b
# at Q4 quantization consumes the majority of the 6GB VRAM budget.
# Running Whisper on GPU would trigger an OOM conflict with the LLM.
FORCE_STT_CPU = True

# ============================================================
# Audio Configuration
# ============================================================
TTS_VOICE = "en-US-AriaNeural"  # Default TTS voice
AUDIO_SAMPLE_RATE = 16000       # STT sample rate
AUDIO_DURATION = 5              # Recording duration in seconds

# ============================================================
# Search & Knowledge Base
# ============================================================
MAX_SEARCH_RESULTS = 5
SEARCH_TIMEOUT = 10             # Seconds for web requests
WIKIPEDIA_API_ENABLED = True
ARXIV_ENABLED = True
OFFLINE_MODE = False            # False: auto-detect internet; True: force offline


# ============================================================
# UI Features
# ============================================================
SHOW_HISTORY = True
AUTO_PLAY_AUDIO = True
ENABLE_VOICE_INPUT = True
DARK_MODE_DEFAULT = True
