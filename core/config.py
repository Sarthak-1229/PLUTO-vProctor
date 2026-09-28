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


# ============================================================
# Classical AIML retrofit (MDM project) — CPU-only scikit-learn.
# ============================================================
# The named-algorithm layer (see docs/AIML_ALGORITHMS.md). Each flag is a soft
# switch: the runtime hook also checks that the relevant artifact exists under
# MODELS_DIR and silently falls back to the Elo/FSM/lexical/LLM baseline when it
# doesn't — so the app runs identically before and after experiments/train_all.py.
# All models are tiny CPU scikit-learn estimators; nothing here touches the GPU.
MODELS_DIR = "data/models"
AIML_GRADER_ENABLED = True    # ML answer-correctness grader blended into Tier-1
AIML_SEARCH_ENABLED = True    # A*/BFS/IDS question-graph selection in the adaptive engine
AIML_CSP_ENABLED = True       # CSP + GA/local-search pool assembly at /start
AIML_TOPICS_ENABLED = True    # TF-IDF/kNN + clustering topic structure
AIML_CALIBRATION_ENABLED = True  # regression difficulty check + probability ability band in the report
