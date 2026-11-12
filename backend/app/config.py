"""Central configuration and constants for PLUTO vProctor.

All thresholds, weights, model parameters, and storage paths MUST live here
to prevent magic numbers in business logic.
"""

import secrets
from pathlib import Path
from typing import Any, Dict, List, Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_EPHEMERAL_DEV_SECRET: str = secrets.token_urlsafe(48)


class Settings(BaseSettings):
    """Application-wide settings and thresholds."""

    # Project Information
    APP_NAME: str = "PLUTO vProctor"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    DEBUG: bool = True

    @field_validator("ENVIRONMENT", mode="before")
    @classmethod
    def _normalize_environment(cls, value: Any) -> str:
        """Canonicalize blank/alias environment names while rejecting unknown typos."""
        if value is None:
            return "development"
        raw = str(value).strip().lower()
        if not raw or raw == "dev":
            return "development"
        if raw in {"prod", "production"}:
            return "production"
        if raw in {"testing", "test"}:
            return "test"
        return raw

    @field_validator("DEBUG", mode="before")
    @classmethod
    def _coerce_debug_flag(cls, value: Any) -> bool:
        """Tolerate non-boolean host env values (e.g. DEBUG=WARN from IDE/Electron shells)."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "y"}:
                return True
            if normalized in {"0", "false", "no", "off", "n", ""}:
                return False
            return False
        return False

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
    API_PORT: int = Field(default=8000, ge=1, le=65535)
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Feature Flags & v2 Rollout Boundaries
    AUTH_ENABLED: bool = False
    HOSTED_ROOMS_ENABLED: bool = False
    LIVE_MEDIA_ENABLED: bool = False
    MEDIA_TRANSPORT_MODE: Literal["none", "p2p", "sfu"] = "p2p"
    SFU_URL: str = ""

    # Auth, Token & Cookie Configuration
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=90)
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    REFRESH_COOKIE_NAME: str = "pluto_refresh_token"
    CSRF_COOKIE_NAME: str = "pluto_csrf_token"
    PASSWORD_RESET_EXPIRE_MINUTES: int = Field(default=30, ge=5, le=1440)
    EMAIL_VERIFY_EXPIRE_HOURS: int = Field(default=24, ge=1, le=168)
    MAX_FAILED_LOGIN_ATTEMPTS: int = Field(default=5, ge=3, le=20)
    LOCKOUT_MINUTES: int = Field(default=15, ge=1, le=240)

    # WebRTC P2P / NAT Traversal (STUN & TURN) Configuration
    STUN_SERVERS: List[str] = ["stun:stun.l.google.com:19302"]
    TURN_SERVER_URLS: List[str] = []
    TURN_USERNAME: str = ""
    TURN_CREDENTIAL: str = ""

    # Database Configuration
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'backend' / 'app' / 'pluto.db'}"

    # LLM Settings (Ollama - Local Offline Inference)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:3b"
    LLM_NUM_CTX: int = 4096
    LLM_KEEP_ALIVE: str = "30s"
    LLM_TEMPERATURE: float = 0.2
    LLM_TIMEOUT_SECONDS: float = Field(default=45.0, gt=0.0, le=600.0)
    LLM_MAX_RETRIES: int = 1

    # Embedding Settings (CPU-only to protect 6 GB VRAM)
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"

    # Speech-to-Text Settings (ASR)
    ASR_PROVIDER: str = "auto"  # "auto", "faster_whisper", "deepgram", "assemblyai"
    DEEPGRAM_API_KEY: str = ""
    ASSEMBLYAI_API_KEY: str = ""
    WHISPER_MODEL_SIZE: str = "base.en"  # Fast, highly accurate on CPU; fallback "base"
    WHISPER_DEVICE: str = "cpu"        # "cuda" or "cpu"; default CPU while LLM is loaded
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_BEAM_SIZE: int = 1         # Greedy decoding for fast real-time transcription

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

    @field_validator("STUN_SERVERS", "TURN_SERVER_URLS", mode="before")
    @classmethod
    def _parse_url_list(cls, value: Any) -> List[str]:
        """Accept either Python lists or comma-separated strings from environment variables."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                import json
                parsed = json.loads(raw)
                return [str(v).strip() for v in parsed if str(v).strip()]
            return [part.strip() for part in raw.split(",") if part.strip()]
        return [str(value).strip()]

    @field_validator("SCORING_WEIGHTS")
    @classmethod
    def _validate_scoring_weights(cls, value: Dict[str, float]) -> Dict[str, float]:
        """Ensure scoring weights stay non-negative and sum close to 1.0."""
        if not value or any(v < 0.0 for v in value.values()):
            raise ValueError("SCORING_WEIGHTS values must be non-negative.")
        total = sum(value.values())
        if not (0.95 <= total <= 1.05):
            raise ValueError(f"SCORING_WEIGHTS must sum to ~1.0 (got {total:.3f}).")
        return value

    def get_signing_secret(self) -> str:
        """Return configured signing secret, or ephemeral secret in non-production."""
        secret = self.SECRET_KEY.strip()
        if secret:
            return secret
        if self.ENVIRONMENT.strip().lower() == "production":
            raise RuntimeError("Unsafe production config: SECRET_KEY must be configured.")
        return _EPHEMERAL_DEV_SECRET

    def validate_runtime_safety(self) -> None:
        """Fail fast when production settings enable auth/SFU without required security config."""
        if self.ENVIRONMENT.strip().lower() != "production":
            return
        if self.AUTH_ENABLED:
            secret = self.SECRET_KEY.strip()
            lowered = secret.lower()
            weak_markers = ("change-me", "changeme", "placeholder", "default", "dev-secret")
            if len(secret) < 32 or any(marker in lowered for marker in weak_markers):
                raise RuntimeError(
                    "Unsafe production config: SECRET_KEY must be at least 32 non-placeholder characters when AUTH_ENABLED=True."
                )
            if not self.COOKIE_SECURE:
                raise RuntimeError(
                    "Unsafe production config: COOKIE_SECURE must be True in production when AUTH_ENABLED=True."
                )
        if self.HOSTED_ROOMS_ENABLED and self.MEDIA_TRANSPORT_MODE == "sfu" and not self.SFU_URL.strip():
            raise RuntimeError(
                "Unsafe production config: SFU_URL is required when MEDIA_TRANSPORT_MODE='sfu'."
            )

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()
