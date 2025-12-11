"""Tests for Communication Channels - Stories 4.2 & 4.3"""

import pytest
from datetime import datetime

from channels import (
    HumeVoiceClient,
    EmotionState,
    VoiceSession,
    WebChatHandler,
    ChatMessage,
    ChatSession,
)
from channels.hume_voice import (
    EmotionCategory,
    EmotionScore,
    VoiceMessage,
    EMOTION_ADAPTATIONS,
)
from channels.web_chat import (
    MessageType,
    ConnectionState,
    message_to_dict,
    dict_to_message,
)


# ===========================================================================
# Hume Voice Tests (Story 4.2)
# ===========================================================================

class TestEmotionState:
    """Tests for EmotionState dataclass."""

    def test_emotion_state_creation(self):
        """Test creating an emotion state."""
        state = EmotionState(
            primary_emotion=EmotionCategory.ANXIETY,
            primary_score=0.8,
            all_emotions=[
                EmotionScore(EmotionCategory.ANXIETY, 0.8),
                EmotionScore(EmotionCategory.NEUTRAL, 0.2),
            ],
        )

        assert state.primary_emotion == EmotionCategory.ANXIETY
        assert state.primary_score == 0.8
        assert len(state.all_emotions) == 2

    def test_is_negative(self):
        """Test negative emotion detection."""
        negative_emotions = [
            EmotionCategory.SADNESS,
            EmotionCategory.ANGER,
            EmotionCategory.FEAR,
            EmotionCategory.ANXIETY,
            EmotionCategory.FRUSTRATION,
        ]

        for emotion in negative_emotions:
            state = EmotionState(
                primary_emotion=emotion,
                primary_score=0.7,
                all_emotions=[EmotionScore(emotion, 0.7)],
            )
            assert state.is_negative is True, f"{emotion} should be negative"

    def test_is_positive(self):
        """Test positive emotion detection."""
        positive_emotions = [
            EmotionCategory.JOY,
            EmotionCategory.EXCITEMENT,
        ]

        for emotion in positive_emotions:
            state = EmotionState(
                primary_emotion=emotion,
                primary_score=0.7,
                all_emotions=[EmotionScore(emotion, 0.7)],
            )
            assert state.is_positive is True, f"{emotion} should be positive"

    def test_needs_support(self):
        """Test needs_support detection."""
        # High anxiety needs support
        anxious = EmotionState(
            primary_emotion=EmotionCategory.ANXIETY,
            primary_score=0.8,
            all_emotions=[EmotionScore(EmotionCategory.ANXIETY, 0.8)],
        )
        assert anxious.needs_support is True

        # Low anxiety doesn't need support
        mild = EmotionState(
            primary_emotion=EmotionCategory.ANXIETY,
            primary_score=0.4,
            all_emotions=[EmotionScore(EmotionCategory.ANXIETY, 0.4)],
        )
        assert mild.needs_support is False

        # Positive emotions don't need support
        happy = EmotionState(
            primary_emotion=EmotionCategory.JOY,
            primary_score=0.9,
            all_emotions=[EmotionScore(EmotionCategory.JOY, 0.9)],
        )
        assert happy.needs_support is False


class TestVoiceSession:
    """Tests for VoiceSession dataclass."""

    def test_session_creation(self):
        """Test creating a voice session."""
        session = VoiceSession(
            session_id="test-123",
            student_id="student-456",
        )

        assert session.session_id == "test-123"
        assert session.student_id == "student-456"
        assert session.is_active is True
        assert session.ended_at is None

    def test_duration_seconds(self):
        """Test session duration calculation."""
        session = VoiceSession(
            session_id="test-123",
            student_id="student-456",
        )

        # Duration should be greater than 0
        import time
        time.sleep(0.01)
        assert session.duration_seconds > 0

    def test_average_emotion_empty(self):
        """Test average emotion with no history."""
        session = VoiceSession(
            session_id="test-123",
            student_id="student-456",
        )
        assert session.average_emotion is None

    def test_average_emotion_with_history(self):
        """Test average emotion calculation."""
        session = VoiceSession(
            session_id="test-123",
            student_id="student-456",
        )

        # Add emotion history
        for _ in range(3):
            session.emotion_history.append(
                EmotionState(
                    primary_emotion=EmotionCategory.NEUTRAL,
                    primary_score=0.7,
                    all_emotions=[EmotionScore(EmotionCategory.NEUTRAL, 0.7)],
                )
            )
        session.emotion_history.append(
            EmotionState(
                primary_emotion=EmotionCategory.JOY,
                primary_score=0.8,
                all_emotions=[EmotionScore(EmotionCategory.JOY, 0.8)],
            )
        )

        assert session.average_emotion == EmotionCategory.NEUTRAL


class TestHumeVoiceClient:
    """Tests for HumeVoiceClient."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return HumeVoiceClient(api_key="test-key")

    @pytest.mark.asyncio
    async def test_start_session(self, client):
        """Test starting a voice session."""
        session = await client.start_session("student-123")

        assert session.student_id == "student-123"
        assert session.is_active is True
        assert session.session_id in client._sessions

    @pytest.mark.asyncio
    async def test_end_session(self, client):
        """Test ending a voice session."""
        session = await client.start_session("student-123")
        session_id = session.session_id

        ended = await client.end_session(session_id)

        assert ended is not None
        assert ended.is_active is False
        assert ended.ended_at is not None

    @pytest.mark.asyncio
    async def test_end_nonexistent_session(self, client):
        """Test ending a nonexistent session."""
        result = await client.end_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_process_audio(self, client):
        """Test processing audio."""
        session = await client.start_session("student-123")

        result = await client.process_audio(session.session_id, b"fake audio data")

        assert result is not None
        assert "transcription" in result
        assert "emotion" in result
        assert "response" in result
        assert "adaptation" in result

    @pytest.mark.asyncio
    async def test_process_audio_inactive_session(self, client):
        """Test processing audio on inactive session."""
        session = await client.start_session("student-123")
        await client.end_session(session.session_id)

        result = await client.process_audio(session.session_id, b"fake audio")
        assert result is None

    @pytest.mark.asyncio
    async def test_send_text_response(self, client):
        """Test sending text response."""
        session = await client.start_session("student-123")

        success = await client.send_text_response(
            session.session_id,
            "Hello, how can I help?"
        )

        assert success is True
        assert len(session.messages) == 1
        assert session.messages[0].text == "Hello, how can I help?"

    @pytest.mark.asyncio
    async def test_send_text_inactive_session(self, client):
        """Test sending text to inactive session."""
        session = await client.start_session("student-123")
        await client.end_session(session.session_id)

        success = await client.send_text_response(session.session_id, "Hello")
        assert success is False

    def test_get_session(self, client):
        """Test getting a session."""
        import asyncio
        session = asyncio.get_event_loop().run_until_complete(
            client.start_session("student-123")
        )

        retrieved = client.get_session(session.session_id)
        assert retrieved == session

        nonexistent = client.get_session("nonexistent")
        assert nonexistent is None

    def test_get_active_sessions(self, client):
        """Test getting active sessions."""
        import asyncio
        loop = asyncio.get_event_loop()

        # Start two sessions
        s1 = loop.run_until_complete(client.start_session("student-1"))
        s2 = loop.run_until_complete(client.start_session("student-2"))

        active = client.get_active_sessions()
        assert len(active) == 2

        # End one
        loop.run_until_complete(client.end_session(s1.session_id))

        active = client.get_active_sessions()
        assert len(active) == 1

    def test_get_stats(self, client):
        """Test getting statistics."""
        stats = client.get_stats()

        assert "active_sessions" in stats
        assert "total_sessions" in stats
        assert "api_configured" in stats
        assert stats["api_configured"] is True

    def test_adapt_response_with_support(self, client):
        """Test response adaptation for users needing support."""
        base = "Here's information about FAFSA deadlines."

        # High anxiety should get supportive prefix
        anxious = EmotionState(
            primary_emotion=EmotionCategory.ANXIETY,
            primary_score=0.8,
            all_emotions=[EmotionScore(EmotionCategory.ANXIETY, 0.8)],
        )

        adapted = client._adapt_response(base, anxious)
        assert adapted != base
        assert "overwhelming" in adapted.lower() or base in adapted

    def test_adapt_response_neutral(self, client):
        """Test response adaptation for neutral emotion."""
        base = "Here's information about FAFSA deadlines."

        neutral = EmotionState(
            primary_emotion=EmotionCategory.NEUTRAL,
            primary_score=0.7,
            all_emotions=[EmotionScore(EmotionCategory.NEUTRAL, 0.7)],
        )

        adapted = client._adapt_response(base, neutral)
        assert adapted == base

    def test_get_adaptation_settings(self, client):
        """Test getting adaptation settings."""
        anxious = EmotionState(
            primary_emotion=EmotionCategory.ANXIETY,
            primary_score=0.8,
            all_emotions=[EmotionScore(EmotionCategory.ANXIETY, 0.8)],
        )

        adaptation = client._get_adaptation(anxious)

        assert "pace" in adaptation
        assert "tone" in adaptation
        assert "prosody_adjustments" in adaptation
        assert adaptation["prosody_adjustments"]["rate"] == 0.9  # Slower for negative


class TestEmotionAdaptations:
    """Tests for emotion adaptation configurations."""

    def test_all_negative_emotions_have_adaptations(self):
        """Test that negative emotions have adaptations."""
        negative_emotions = [
            EmotionCategory.ANXIETY,
            EmotionCategory.FRUSTRATION,
            EmotionCategory.SADNESS,
        ]

        for emotion in negative_emotions:
            assert emotion in EMOTION_ADAPTATIONS, f"Missing adaptation for {emotion}"
            adaptation = EMOTION_ADAPTATIONS[emotion]
            assert "pace" in adaptation
            assert "tone" in adaptation
            assert "phrases" in adaptation
            assert len(adaptation["phrases"]) > 0


# ===========================================================================
# Web Chat Tests (Story 4.3)
# ===========================================================================

class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_message_creation(self):
        """Test creating a chat message."""
        msg = ChatMessage(
            id="msg-123",
            session_id="session-456",
            role="user",
            content="Hello!",
        )

        assert msg.id == "msg-123"
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.message_type == MessageType.TEXT

    def test_image_message(self):
        """Test creating an image message."""
        msg = ChatMessage(
            id="msg-123",
            session_id="session-456",
            role="assistant",
            content="Here's an image",
            message_type=MessageType.IMAGE,
            image_url="https://example.com/image.png",
        )

        assert msg.message_type == MessageType.IMAGE
        assert msg.image_url is not None


class TestChatSession:
    """Tests for ChatSession dataclass."""

    def test_session_creation(self):
        """Test creating a chat session."""
        session = ChatSession(
            session_id="session-123",
            student_id="student-456",
        )

        assert session.session_id == "session-123"
        assert session.student_id == "student-456"
        assert session.is_active is True
        assert session.connection_state == ConnectionState.DISCONNECTED

    def test_message_count(self):
        """Test message count property."""
        session = ChatSession(
            session_id="session-123",
            student_id="student-456",
        )

        assert session.message_count == 0

        session.messages.append(
            ChatMessage(
                id="msg-1",
                session_id="session-123",
                role="user",
                content="Hello",
            )
        )

        assert session.message_count == 1

    def test_duration_seconds(self):
        """Test duration calculation."""
        session = ChatSession(
            session_id="session-123",
            student_id="student-456",
        )

        import time
        time.sleep(0.01)
        assert session.duration_seconds > 0


class TestWebChatHandler:
    """Tests for WebChatHandler."""

    @pytest.fixture
    def handler(self):
        """Create a test handler."""
        return WebChatHandler()

    @pytest.mark.asyncio
    async def test_create_session(self, handler):
        """Test creating a chat session."""
        session = await handler.create_session("student-123")

        assert session.student_id == "student-123"
        assert session.is_active is True
        assert len(session.messages) == 1  # Welcome message
        assert session.messages[0].role == "assistant"

    @pytest.mark.asyncio
    async def test_connect_disconnect(self, handler):
        """Test WebSocket connect and disconnect."""
        session = await handler.create_session("student-123")

        # Connect
        connected = await handler.connect(session.session_id)
        assert connected is True
        assert session.connection_state == ConnectionState.CONNECTED

        # Disconnect
        await handler.disconnect(session.session_id)
        assert session.connection_state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connect_nonexistent_session(self, handler):
        """Test connecting to nonexistent session."""
        result = await handler.connect("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message(self, handler):
        """Test sending a message."""
        session = await handler.create_session("student-123")
        initial_count = len(session.messages)

        message = await handler.send_message(
            session.session_id,
            "Hello!",
            role="user",
        )

        assert message is not None
        assert message.content == "Hello!"
        assert message.role == "user"
        # Should have user message and assistant response
        assert len(session.messages) > initial_count

    @pytest.mark.asyncio
    async def test_send_message_inactive_session(self, handler):
        """Test sending message to inactive session."""
        session = await handler.create_session("student-123")
        session.is_active = False

        message = await handler.send_message(session.session_id, "Hello")
        assert message is None

    @pytest.mark.asyncio
    async def test_send_image(self, handler):
        """Test sending an image message."""
        session = await handler.create_session("student-123")

        message = await handler.send_image(
            session.session_id,
            "https://example.com/image.png",
            caption="Check this out!",
        )

        assert message is not None
        assert message.message_type == MessageType.IMAGE
        assert message.image_url == "https://example.com/image.png"
        assert message.content == "Check this out!"

    @pytest.mark.asyncio
    async def test_send_system_message(self, handler):
        """Test sending a system message."""
        session = await handler.create_session("student-123")

        message = await handler.send_system_message(
            session.session_id,
            "Session timeout warning",
        )

        assert message is not None
        assert message.message_type == MessageType.SYSTEM
        assert message.role == "system"

    @pytest.mark.asyncio
    async def test_end_session(self, handler):
        """Test ending a session."""
        session = await handler.create_session("student-123")
        session_id = session.session_id

        ended = await handler.end_session(session_id)

        assert ended is not None
        assert ended.is_active is False
        assert ended.ended_at is not None

    @pytest.mark.asyncio
    async def test_end_nonexistent_session(self, handler):
        """Test ending nonexistent session."""
        result = await handler.end_session("nonexistent")
        assert result is None

    def test_get_session(self, handler):
        """Test getting a session."""
        import asyncio
        session = asyncio.get_event_loop().run_until_complete(
            handler.create_session("student-123")
        )

        retrieved = handler.get_session(session.session_id)
        assert retrieved == session

        nonexistent = handler.get_session("nonexistent")
        assert nonexistent is None

    def test_get_session_history(self, handler):
        """Test getting session history."""
        import asyncio
        loop = asyncio.get_event_loop()

        session = loop.run_until_complete(handler.create_session("student-123"))
        loop.run_until_complete(
            handler.send_message(session.session_id, "Message 1", "user")
        )

        history = handler.get_session_history(session.session_id)
        assert len(history) >= 2  # Welcome + user + response

        # Test limit
        history_limited = handler.get_session_history(session.session_id, limit=1)
        assert len(history_limited) == 1

    def test_get_session_history_nonexistent(self, handler):
        """Test getting history for nonexistent session."""
        history = handler.get_session_history("nonexistent")
        assert history == []

    def test_get_active_sessions(self, handler):
        """Test getting active sessions."""
        import asyncio
        loop = asyncio.get_event_loop()

        s1 = loop.run_until_complete(handler.create_session("student-1"))
        s2 = loop.run_until_complete(handler.create_session("student-2"))

        active = handler.get_active_sessions()
        assert len(active) == 2

        loop.run_until_complete(handler.end_session(s1.session_id))

        active = handler.get_active_sessions()
        assert len(active) == 1

    def test_get_stats(self, handler):
        """Test getting statistics."""
        stats = handler.get_stats()

        assert "active_sessions" in stats
        assert "total_sessions" in stats
        assert "connected_websockets" in stats
        assert "total_messages" in stats


class TestMessageSerialization:
    """Tests for message serialization utilities."""

    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        msg = ChatMessage(
            id="msg-123",
            session_id="session-456",
            role="user",
            content="Hello!",
        )

        data = message_to_dict(msg)

        assert data["id"] == "msg-123"
        assert data["session_id"] == "session-456"
        assert data["role"] == "user"
        assert data["content"] == "Hello!"
        assert data["type"] == "text"
        assert "timestamp" in data

    def test_dict_to_message(self):
        """Test converting dictionary to message."""
        data = {
            "id": "msg-123",
            "session_id": "session-456",
            "role": "user",
            "content": "Hello!",
            "type": "text",
        }

        msg = dict_to_message(data)

        assert msg.id == "msg-123"
        assert msg.session_id == "session-456"
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.message_type == MessageType.TEXT

    def test_dict_to_message_with_image(self):
        """Test converting image message dictionary."""
        data = {
            "session_id": "session-456",
            "role": "assistant",
            "content": "Here's an image",
            "type": "image",
            "image_url": "https://example.com/image.png",
        }

        msg = dict_to_message(data)

        assert msg.message_type == MessageType.IMAGE
        assert msg.image_url == "https://example.com/image.png"


class TestAmbassadorCallback:
    """Tests for ambassador callback integration."""

    @pytest.mark.asyncio
    async def test_voice_client_with_callback(self):
        """Test voice client with ambassador callback."""
        response_called = False

        async def mock_callback(student_id: str, message: str) -> str:
            nonlocal response_called
            response_called = True
            return f"Response to: {message}"

        client = HumeVoiceClient(
            api_key="test-key",
            ambassador_callback=mock_callback,
        )

        session = await client.start_session("student-123")
        result = await client.process_audio(session.session_id, b"audio")

        assert response_called is True
        assert "Response to:" in result["response"]

    @pytest.mark.asyncio
    async def test_chat_handler_with_callback(self):
        """Test chat handler with ambassador callback."""
        response_called = False

        async def mock_callback(student_id: str, message: str) -> str:
            nonlocal response_called
            response_called = True
            return f"Response to: {message}"

        handler = WebChatHandler(ambassador_callback=mock_callback)

        session = await handler.create_session("student-123")
        await handler.send_message(session.session_id, "Hello", "user")

        assert response_called is True


class TestChannelStats:
    """Tests for channel statistics."""

    @pytest.mark.asyncio
    async def test_voice_stats_update(self):
        """Test voice stats update with sessions."""
        client = HumeVoiceClient(api_key="test-key")

        stats1 = client.get_stats()
        assert stats1["total_sessions"] == 0

        await client.start_session("student-1")
        await client.start_session("student-2")

        stats2 = client.get_stats()
        assert stats2["total_sessions"] == 2
        assert stats2["active_sessions"] == 2

    @pytest.mark.asyncio
    async def test_chat_stats_update(self):
        """Test chat stats update with sessions."""
        handler = WebChatHandler()

        stats1 = handler.get_stats()
        assert stats1["total_sessions"] == 0

        s1 = await handler.create_session("student-1")
        s2 = await handler.create_session("student-2")

        stats2 = handler.get_stats()
        assert stats2["total_sessions"] == 2

        await handler.connect(s1.session_id)

        stats3 = handler.get_stats()
        assert stats3["connected_websockets"] == 1
