"""Interview extension package for PLUTO vProctor.

Adds a mock-interview / interview-practice mode on top of the existing PLUTO
FastAPI app. Everything here runs on CPU or in the browser; the resident
qwen2.5:7b (Ollama) stays the sole GPU tenant.
"""
