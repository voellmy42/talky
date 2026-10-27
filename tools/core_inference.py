"""Serialize local GPU work across dictation, model loading and meetings."""
import threading

GPU_LOCK = threading.RLock()
