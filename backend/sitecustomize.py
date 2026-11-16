"""Runtime environment bootstrap for PLUTO vProctor AppSail deployment.

This module is automatically imported by Python at startup if it is present
on PYTHONPATH or in the root application directory. It ensures that imports
referencing `backend.app...` resolve transparently even when the application
is packaged with `backend` as the top-level container directory.
"""
import sys
from pathlib import Path
import types

_here = Path(__file__).resolve().parent

if "backend" not in sys.modules:
    # If there is no subdirectory named 'backend' in the current working directory,
    # alias 'backend' to the current directory's package path so `from backend.app...` works.
    if not (_here / "backend").exists() and (_here / "app").exists():
        _backend_mod = types.ModuleType("backend")
        _backend_mod.__path__ = [str(_here)]
        sys.modules["backend"] = _backend_mod
