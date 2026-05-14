"""VoiceChannel — handles full-duplex conversational interaction."""

from __future__ import annotations

import logging
from typing import Any, Optional

from openjarvis.agents._stubs import BaseAgent
from openjarvis.speech._stubs import SpeechBackend
from openjarvis.speech.tts import TTSBackend
from openjarvis.speech.voice_manager import VoiceSessionManager, WakeWordEngine

logger = logging.getLogger(__name__)

class VoiceChannel:
    """Orchestrates audio input, STT, agent routing, and TTS playback."""

    def __init__(
        self,
        agent: BaseAgent,
        stt: SpeechBackend,
        tts: TTSBackend,
        wake_word: Optional[WakeWordEngine] = None
    ):
        self.agent = agent
        self.stt = stt
        self.tts = tts
        self.wake_word = wake_word
        self.session = VoiceSessionManager()

    async def start_loop(self):
        """Main interaction loop: Listen -> Transcribe -> Run Agent -> Speak."""
        logger.info("Starting VoiceChannel loop...")
        # In a real impl, this would loop and use PyAudio or similar to stream audio
        pass

    async def _handle_audio_input(self, audio_data: bytes):
        """Process a single turn of audio interaction."""
        if self.wake_word and not self.session.is_active:
            if not self.wake_word.detect(audio_data):
                return
            self.session.start_session()

        # 1. Transcribe
        result = self.stt.transcribe(audio_data)
        if not result.text.strip():
            return

        # 2. Run Agent
        agent_result = self.agent.run(result.text)

        # 3. Synthesize and Play
        tts_result = self.tts.synthesize(agent_result.content)
        # Playback logic would go here

__all__ = ["VoiceChannel"]
