"""Comprehensive secret scanner for PLUTO vProctor repository.

Scans all tracked files (excluding .venv, node_modules, .git, and cache dirs)
for potential hardcoded credentials, API keys, private keys, and passwords.
Redacts detected secret values to prevent credential leakage in logs.
"""
import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}

PATTERNS = [
    ("AWS Access Key ID", re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])")),
    ("AWS Secret Key Assignment", re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"][A-Za-z0-9/+=]{40}['\"]")),
    ("Generic Secret Assignment", re.compile(r"(?i)(api_key|secret_key|private_key|auth_token|password)\s*=\s*['\"][A-Za-z0-9_\-+=/]{16,}['\"]")),
    ("Private Key Header", re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub Personal Access Token", re.compile(r"gh[pous]_[A-Za-z0-9_]{36,}")),
    ("JWT Token String", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]

def scan_repository():
    findings = []
    scanned_count = 0

    for path in ROOT_DIR.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        if path.suffix in {".pyc", ".png", ".jpg", ".jpeg", ".ico", ".webm", ".wav", ".mp4", ".exe", ".dll", ".db"}:
            continue

        scanned_count += 1
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for rule_name, pattern in PATTERNS:
            for match in pattern.finditer(content):
                matched_str = match.group(0)
                # Filter out obvious false positives, test fixtures, and schema type definitions
                if any(fp in matched_str.lower() for fp in [
                    "dev-secret",
                    "_ephemeral_dev_secret",
                    "placeholder",
                    "dummy",
                    "changeme",
                    "change-me",
                    "your-secret",
                    "example",
                    "token_hash",
                    "password_hash",
                    "password_reset",
                    "password123",
                    "testpassword",
                    "strongpassword",
                    "secrets.token",
                ]):
                    continue
                # Line calculation
                line_no = content[:match.start()].count("\n") + 1
                # Redact matched secret
                redacted = matched_str[:8] + "..." + matched_str[-4:] if len(matched_str) > 16 else "[REDACTED]"
                findings.append({
                    "rule": rule_name,
                    "file": str(path.relative_to(ROOT_DIR)),
                    "line": line_no,
                    "redacted_sample": redacted,
                })

    print(f"Scanned {scanned_count} files across repository.")
    print(f"Found {len(findings)} potential secret pattern occurrences:")
    for f in findings:
        print(f"  [{f['rule']}] {f['file']}:{f['line']} -> {f['redacted_sample']}")

if __name__ == "__main__":
    scan_repository()
