"""Central configuration and constants for PLUTO vProctor.

All thresholds, weights, model parameters, and storage paths MUST live here
to prevent magic numbers in business logic.
"""

from pathlib import Path
from typing import Dict, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings and thresholds."""

    # Project Information
    APP_NAME: str = "PLUTO vProctor"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Base Paths (Relative to project root)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATASETS_DIR: Path = BASE_DIR / "datasets"
    DATASET_DATA_DIR: Path = DATASETS_DIR / "data"
    DATASET_DATA1_DIR: Path = DATASETS_DIR / "data1"
    STORAGE_DIR: Path = BASE_DIR / "storage"
    PROCESSED_DATA_DIR: Path = BASE_DIR / "backend" / "app" / "data" / "processed"

    # Observability & Infrastructure
    LOG_LEVEL: str = "INFO"
    REDIS_URL: str = ""
    RETENTION_DAYS: int = 30

    # API Server Configuration
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database Configuration
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'backend' / 'app' / 'pluto.db'}"

    # LLM Settings (Ollama - Local Offline Inference)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:3b"
    LLM_NUM_CTX: int = 4096
    LLM_KEEP_ALIVE: str = "30s"
    LLM_TEMPERATURE: float = 0.2
    LLM_TIMEOUT_SECONDS: float = 45.0
    LLM_MAX_RETRIES: int = 1

    # Embedding Settings (CPU-only to protect 6 GB VRAM)
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"

    # Speech-to-Text Settings (ASR)
    ASR_PROVIDER: str = "auto"  # "auto", "faster_whisper", "deepgram", "assemblyai"
    DEEPGRAM_API_KEY: str = ""
    ASSEMBLYAI_API_KEY: str = ""
    WHISPER_MODEL_SIZE: str = "small"  # fallback "base"
    WHISPER_DEVICE: str = "cpu"        # "cuda" or "cpu"; default CPU while LLM is loaded
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_BEAM_SIZE: int = 3

    # Proctoring Video Thresholds (MediaPipe Face Mesh / Pose)
    MIN_FACE_DETECTION_CONFIDENCE: float = 0.5
    MIN_TRACKING_CONFIDENCE: float = 0.5
    GAZE_CENTER_TOLERANCE_X: float = 0.15   # Normalized eye offset horizontal
    GAZE_CENTER_TOLERANCE_Y: float = 0.12   # Normalized eye offset vertical
    HEAD_YAW_THRESHOLD_DEG: float = 25.0    # Degrees turning left/right
    HEAD_PITCH_THRESHOLD_DEG: float = 20.0  # Degrees tilting up/down
    HEAD_ROLL_THRESHOLD_DEG: float = 20.0   # Degrees tilting sideways
    MULTIPLE_FACES_PENALTY_PER_SEC: float = 2.0
    NO_FACE_PENALTY_PER_SEC: float = 1.0

    # Audio & Speech Pace Thresholds
    SPEECH_PACE_MIN_WPM: int = 90           # Words per minute lower bound
    SPEECH_PACE_MAX_WPM: int = 180          # Words per minute upper bound
    SPEECH_PAUSE_THRESHOLD_SEC: float = 3.5 # Unusually long pause threshold
    FILLER_WORD_PENALTY: float = 0.5        # Deduction per excessive filler word

    # Scoring Weights (Total 100)
    SCORING_WEIGHTS: Dict[str, float] = {
        "technical_depth": 0.35,     # Correctness & depth of answer vs dataset ground truth
        "communication": 0.25,       # Fluency, vocabulary, structure, pace
        "proctoring_integrity": 0.25,# Eye contact, posture, environment consistency
        "resume_relevance": 0.15,    # Match to claimed skills and experience
    }

    # Algorithm Parameters
    BM25_K1: float = 1.5
    BM25_B: float = 0.75
    MINHASH_NUM_PERMUTATIONS: int = 128
    MINHASH_JACCARD_THRESHOLD: float = 0.80
    MMR_LAMBDA: float = 0.7                  # Relevance vs diversity trade-off

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()
