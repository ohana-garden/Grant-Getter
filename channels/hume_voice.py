"""Hume Voice Integration - Story 4.2

Connects Hume.ai EVI for voice conversations with emotion detection.
Adapts ambassador responses based on detected emotions.
"""

import os
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Awaitable
from enum import Enum
import json

logger = logging.getLogger(__name__)


class EmotionCategory(Enum):
    """Primary emotion categories from Hume."""
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    CONTEMPT = "contempt"
    NEUTRAL = "neutral"
    CONFUSION = "confusion"
    ANXIETY = "anxiety"
    EXCITEMENT = "excitement"
    FRUSTRATION = "frustration"


@dataclass
class EmotionScore:
    """A single emotion detection score."""
    emotion: EmotionCategory
    score: float  # 0.0 to 1.0
    confidence: float = 1.0


@dataclass
class EmotionState:
    """Current emotional state of a user."""
    primary_emotion: EmotionCategory
    primary_score: float
    all_emotions: List[EmotionScore]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_negative(self) -> bool:
        """Check if primary emotion is negative."""
        negative_emotions = {
            EmotionCategory.SADNESS,
            EmotionCategory.ANGER,
            EmotionCategory.FEAR,
            EmotionCategory.DISGUST,
            EmotionCategory.CONTEMPT,
            EmotionCategory.ANXIETY,
            EmotionCategory.FRUSTRATION,
        }
        return self.primary_emotion in negative_emotions

    @property
    def is_positive(self) -> bool:
        """Check if primary emotion is positive."""
        positive_emotions = {
            EmotionCategory.JOY,
            EmotionCategory.EXCITEMENT,
        }
        return self.primary_emotion in positive_emotions

    @property
    def needs_support(self) -> bool:
        """Check if user needs extra support based on emotion."""
        return self.is_negative and self.primary_score > 0.6


@dataclass
class VoiceMessage:
    """A voice message in a session."""
    id: str
    role: str  # "user" or "assistant"
    text: str
    audio_data: Optional[bytes] = None
    emotion_state: Optional[EmotionState] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class VoiceSession:
    """A voice conversation session."""
    session_id: str
    student_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    messages: List[VoiceMessage] = field(default_factory=list)
    emotion_history: List[EmotionState] = field(default_factory=list)
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        end = self.ended_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    @property
    def average_emotion(self) -> Optional[EmotionCategory]:
        """Get the most common emotion in the session."""
        if not self.emotion_history:
            return None
        emotion_counts: Dict[EmotionCategory, int] = {}
        for state in self.emotion_history:
            emotion_counts[state.primary_emotion] = emotion_counts.get(state.primary_emotion, 0) + 1
        return max(emotion_counts, key=emotion_counts.get)


# Response adaptation based on emotion
EMOTION_ADAPTATIONS = {
    EmotionCategory.ANXIETY: {
        "pace": "slower",
        "tone": "calm and reassuring",
        "phrases": [
            "I understand this can feel overwhelming.",
            "Let's take this one step at a time.",
            "Don't worry, we'll figure this out together.",
        ],
    },
    EmotionCategory.FRUSTRATION: {
        "pace": "measured",
        "tone": "empathetic and solution-focused",
        "phrases": [
            "I hear your frustration.",
            "Let me help make this easier.",
            "I know this process can be challenging.",
        ],
    },
    EmotionCategory.SADNESS: {
        "pace": "gentle",
        "tone": "warm and supportive",
        "phrases": [
            "I'm here to help.",
            "It's okay to feel this way.",
            "Let's see what options we have.",
        ],
    },
    EmotionCategory.EXCITEMENT: {
        "pace": "energetic",
        "tone": "enthusiastic and encouraging",
        "phrases": [
            "That's great!",
            "I love your energy!",
            "Let's keep this momentum going!",
        ],
    },
    EmotionCategory.JOY: {
        "pace": "upbeat",
        "tone": "celebratory",
        "phrases": [
            "Wonderful!",
            "That's fantastic news!",
            "I'm so happy for you!",
        ],
    },
    EmotionCategory.CONFUSION: {
        "pace": "clear and deliberate",
        "tone": "patient and explanatory",
        "phrases": [
            "Let me explain that more clearly.",
            "Good question - here's what that means.",
            "I'll break this down step by step.",
        ],
    },
}


class HumeVoiceClient:
    """Client for Hume.ai EVI voice integration.

    Acceptance Criteria:
    - Can start voice session
    - Emotion detected in real-time
    - Ambassador adapts pace/tone based on emotion
    - Voice transcribed and stored in Graphiti
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        graphiti_client=None,
        ambassador_callback: Optional[Callable[[str, str], Awaitable[str]]] = None,
    ):
        """Initialize Hume voice client.

        Args:
            api_key: Hume API key (or from HUME_API_KEY env var)
            graphiti_client: Graphiti client for storing transcripts
            ambassador_callback: Callback to get ambassador response
        """
        self.api_key = api_key or os.getenv("HUME_API_KEY")
        self.graphiti = graphiti_client
        self.ambassador_callback = ambassador_callback

        # Active sessions
        self._sessions: Dict[str, VoiceSession] = {}

        # WebSocket connections (in production, actual Hume connections)
        self._connections: Dict[str, Any] = {}

        # Emotion detection state
        self._current_emotions: Dict[str, EmotionState] = {}

    async def start_session(
        self,
        student_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VoiceSession:
        """Start a new voice session.

        Args:
            student_id: Student ID for the session
            metadata: Optional session metadata

        Returns:
            VoiceSession object
        """
        import uuid
        session_id = str(uuid.uuid4())

        session = VoiceSession(
            session_id=session_id,
            student_id=student_id,
            metadata=metadata or {},
        )

        self._sessions[session_id] = session

        # In production, establish WebSocket connection to Hume
        await self._connect_to_hume(session_id)

        logger.info(f"Started voice session {session_id} for student {student_id}")

        return session

    async def _connect_to_hume(self, session_id: str):
        """Establish WebSocket connection to Hume API.

        Args:
            session_id: Session ID
        """
        # In production, this would:
        # 1. Connect to wss://api.hume.ai/v0/evi/chat
        # 2. Authenticate with API key
        # 3. Configure emotion detection settings

        # For now, simulate connection
        self._connections[session_id] = {
            "connected": True,
            "connected_at": datetime.utcnow(),
        }

        logger.info(f"Connected to Hume API for session {session_id}")

    async def end_session(self, session_id: str) -> Optional[VoiceSession]:
        """End a voice session.

        Args:
            session_id: Session ID to end

        Returns:
            Completed VoiceSession or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        session.is_active = False
        session.ended_at = datetime.utcnow()

        # Close WebSocket connection
        if session_id in self._connections:
            del self._connections[session_id]

        # Store transcript in Graphiti
        await self._store_transcript(session)

        logger.info(f"Ended voice session {session_id}")

        return session

    async def _store_transcript(self, session: VoiceSession):
        """Store session transcript in Graphiti.

        Args:
            session: VoiceSession to store
        """
        if not self.graphiti:
            return

        try:
            # Build transcript text
            transcript_parts = []
            for msg in session.messages:
                role = "Student" if msg.role == "user" else "Ambassador"
                emotion_note = ""
                if msg.emotion_state:
                    emotion_note = f" [{msg.emotion_state.primary_emotion.value}]"
                transcript_parts.append(f"{role}{emotion_note}: {msg.text}")

            transcript = "\n".join(transcript_parts)

            # Store as episode
            await self.graphiti.add_episode(
                name=f"voice_session_{session.session_id}",
                episode_body=transcript,
                source_description="voice_conversation",
                group_id=session.student_id,
            )

            logger.info(f"Stored transcript for session {session.session_id}")

        except Exception as e:
            logger.error(f"Failed to store transcript: {e}")

    async def process_audio(
        self,
        session_id: str,
        audio_data: bytes,
    ) -> Optional[Dict[str, Any]]:
        """Process incoming audio from user.

        Args:
            session_id: Session ID
            audio_data: Raw audio bytes

        Returns:
            Processing result with transcription and emotion
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return None

        # In production, send to Hume for processing
        # For now, simulate transcription and emotion detection

        # Simulate transcription (in production, from Hume STT)
        transcription = await self._transcribe_audio(audio_data)

        # Simulate emotion detection (in production, from Hume)
        emotion_state = await self._detect_emotion(audio_data)

        # Store emotion state
        self._current_emotions[session_id] = emotion_state
        session.emotion_history.append(emotion_state)

        # Create voice message
        import uuid
        message = VoiceMessage(
            id=str(uuid.uuid4()),
            role="user",
            text=transcription,
            audio_data=audio_data,
            emotion_state=emotion_state,
        )
        session.messages.append(message)

        # Get ambassador response
        response_text = await self._get_ambassador_response(
            session.student_id,
            transcription,
            emotion_state,
        )

        # Create response message
        response_message = VoiceMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            text=response_text,
        )
        session.messages.append(response_message)

        return {
            "transcription": transcription,
            "emotion": {
                "primary": emotion_state.primary_emotion.value,
                "score": emotion_state.primary_score,
                "needs_support": emotion_state.needs_support,
            },
            "response": response_text,
            "adaptation": self._get_adaptation(emotion_state),
        }

    async def _transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio to text.

        Args:
            audio_data: Audio bytes

        Returns:
            Transcribed text
        """
        # In production, use Hume's STT or Whisper
        # For now, return placeholder
        return "[Transcribed speech from audio]"

    async def _detect_emotion(self, audio_data: bytes) -> EmotionState:
        """Detect emotion from audio.

        Args:
            audio_data: Audio bytes

        Returns:
            EmotionState
        """
        # In production, this comes from Hume's emotion API
        # For now, return neutral state
        return EmotionState(
            primary_emotion=EmotionCategory.NEUTRAL,
            primary_score=0.7,
            all_emotions=[
                EmotionScore(EmotionCategory.NEUTRAL, 0.7),
                EmotionScore(EmotionCategory.ANXIETY, 0.2),
                EmotionScore(EmotionCategory.CONFUSION, 0.1),
            ],
        )

    async def _get_ambassador_response(
        self,
        student_id: str,
        user_message: str,
        emotion_state: EmotionState,
    ) -> str:
        """Get adapted response from ambassador.

        Args:
            student_id: Student ID
            user_message: User's message
            emotion_state: Detected emotion

        Returns:
            Adapted response text
        """
        # Get base response from ambassador
        if self.ambassador_callback:
            base_response = await self.ambassador_callback(student_id, user_message)
        else:
            base_response = "I'm here to help you with your financial aid questions."

        # Adapt response based on emotion
        adapted_response = self._adapt_response(base_response, emotion_state)

        return adapted_response

    def _adapt_response(
        self,
        base_response: str,
        emotion_state: EmotionState,
    ) -> str:
        """Adapt response based on detected emotion.

        Args:
            base_response: Original response
            emotion_state: Detected emotion

        Returns:
            Adapted response
        """
        adaptation = EMOTION_ADAPTATIONS.get(emotion_state.primary_emotion)

        if not adaptation or emotion_state.primary_score < 0.5:
            return base_response

        # Add supportive prefix if needed
        if emotion_state.needs_support and adaptation.get("phrases"):
            prefix = adaptation["phrases"][0]
            return f"{prefix} {base_response}"

        return base_response

    def _get_adaptation(self, emotion_state: EmotionState) -> Dict[str, Any]:
        """Get adaptation settings for response delivery.

        Args:
            emotion_state: Detected emotion

        Returns:
            Adaptation settings
        """
        adaptation = EMOTION_ADAPTATIONS.get(
            emotion_state.primary_emotion,
            {"pace": "normal", "tone": "friendly"}
        )

        return {
            "pace": adaptation.get("pace", "normal"),
            "tone": adaptation.get("tone", "friendly"),
            "prosody_adjustments": {
                "rate": 0.9 if emotion_state.is_negative else 1.0,
                "pitch": "medium",
                "volume": "medium",
            },
        }

    def get_current_emotion(self, session_id: str) -> Optional[EmotionState]:
        """Get current emotion state for a session.

        Args:
            session_id: Session ID

        Returns:
            Current EmotionState or None
        """
        return self._current_emotions.get(session_id)

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Get a voice session.

        Args:
            session_id: Session ID

        Returns:
            VoiceSession or None
        """
        return self._sessions.get(session_id)

    def get_active_sessions(self) -> List[VoiceSession]:
        """Get all active sessions.

        Returns:
            List of active VoiceSession objects
        """
        return [s for s in self._sessions.values() if s.is_active]

    async def send_text_response(
        self,
        session_id: str,
        text: str,
    ) -> bool:
        """Send a text response (will be converted to speech).

        Args:
            session_id: Session ID
            text: Text to speak

        Returns:
            True if successful
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return False

        # In production, send to Hume TTS
        import uuid
        message = VoiceMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            text=text,
        )
        session.messages.append(message)

        logger.info(f"Sent response in session {session_id}")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get voice client statistics.

        Returns:
            Stats dict
        """
        active = len(self.get_active_sessions())
        total = len(self._sessions)

        return {
            "active_sessions": active,
            "total_sessions": total,
            "completed_sessions": total - active,
            "api_configured": bool(self.api_key),
        }
