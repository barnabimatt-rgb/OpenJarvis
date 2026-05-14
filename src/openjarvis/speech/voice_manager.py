"""Voice Subsystem — WakeWord, STT, TTS, and Session Management."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

class WakeWordEngine:
    """Detects wake phrases like 'Jarvis' using openWakeWord."""

    def __init__(self, phrase: str = "jarvis", sensitivity: float = 0.5):
        self.phrase = phrase
        self.sensitivity = sensitivity
        self._model = None # openWakeWord model loaded lazily

    def detect(self, audio_chunk: bytes) -> bool:
        """Process a chunk of audio and return True if wake word is detected."""
        # Stub for this buildout - real impl uses openwakeword.model.Model
        return False

class VoiceSessionManager:
    """Manages the state of a continuous voice interaction session."""

    def __init__(self):
        self.is_active = False
        self.history: List[str] = []
        self.interrupted = False

    def start_session(self):
        self.is_active = True
        self.interrupted = False

    def end_session(self):
        self.is_active = False

    def handle_interruption(self):
        self.interrupted = True
        # In a real impl, this would signal the TTS engine to stop playback

@dataclass
class VoiceState:
    """Current state of the voice channel."""
    mode: str = "idle" # listening, thinking, speaking, idle
    last_transcript: str = ""
    is_muted: bool = False

__all__ = ["WakeWordEngine", "VoiceSessionManager", "VoiceState"]
