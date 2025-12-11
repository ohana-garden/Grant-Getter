"""Web Chat Interface - Story 4.3

Simple web chat for testing and fallback communication.
Supports WebSocket for real-time messaging.
"""

import os
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Awaitable, Set
from enum import Enum
import json
import uuid

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of chat messages."""
    TEXT = "text"
    IMAGE = "image"
    TYPING = "typing"
    SYSTEM = "system"
    ERROR = "error"


class ConnectionState(Enum):
    """WebSocket connection states."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class ChatMessage:
    """A chat message."""
    id: str
    session_id: str
    role: str  # "user", "assistant", "system"
    content: str
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    image_url: Optional[str] = None


@dataclass
class ChatSession:
    """A web chat session."""
    session_id: str
    student_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    messages: List[ChatMessage] = field(default_factory=list)
    is_active: bool = True
    connection_state: ConnectionState = ConnectionState.DISCONNECTED
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def message_count(self) -> int:
        """Get number of messages in session."""
        return len(self.messages)

    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        end = self.ended_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()


class WebChatHandler:
    """Handler for web chat sessions.

    Acceptance Criteria:
    - Can chat with ambassador via web
    - Messages persist in Graphiti
    - Can display Nanobanana-generated images
    """

    def __init__(
        self,
        graphiti_client=None,
        ambassador_callback: Optional[Callable[[str, str], Awaitable[str]]] = None,
    ):
        """Initialize web chat handler.

        Args:
            graphiti_client: Graphiti client for persistence
            ambassador_callback: Callback to get ambassador response
        """
        self.graphiti = graphiti_client
        self.ambassador_callback = ambassador_callback

        # Active sessions
        self._sessions: Dict[str, ChatSession] = {}

        # WebSocket connections (session_id -> connection)
        self._connections: Dict[str, Any] = {}

        # Typing indicators
        self._typing_users: Set[str] = set()

    async def create_session(
        self,
        student_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            student_id: Student ID
            metadata: Optional session metadata

        Returns:
            ChatSession object
        """
        session_id = str(uuid.uuid4())

        session = ChatSession(
            session_id=session_id,
            student_id=student_id,
            metadata=metadata or {},
        )

        self._sessions[session_id] = session

        # Send welcome message
        welcome = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content="Hi! I'm your Student Ambassador. How can I help you with your financial aid journey today?",
            message_type=MessageType.TEXT,
        )
        session.messages.append(welcome)

        logger.info(f"Created chat session {session_id} for student {student_id}")

        return session

    async def connect(self, session_id: str, websocket: Any = None) -> bool:
        """Connect a WebSocket to a session.

        Args:
            session_id: Session ID
            websocket: WebSocket connection object

        Returns:
            True if connected successfully
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        self._connections[session_id] = websocket
        session.connection_state = ConnectionState.CONNECTED

        logger.info(f"WebSocket connected for session {session_id}")

        return True

    async def disconnect(self, session_id: str):
        """Disconnect WebSocket from session.

        Args:
            session_id: Session ID
        """
        session = self._sessions.get(session_id)
        if session:
            session.connection_state = ConnectionState.DISCONNECTED

        if session_id in self._connections:
            del self._connections[session_id]

        logger.info(f"WebSocket disconnected for session {session_id}")

    async def send_message(
        self,
        session_id: str,
        content: str,
        role: str = "user",
    ) -> Optional[ChatMessage]:
        """Send a message in a chat session.

        Args:
            session_id: Session ID
            content: Message content
            role: Message role (user/assistant/system)

        Returns:
            Created ChatMessage or None
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return None

        # Create message
        message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            message_type=MessageType.TEXT,
        )
        session.messages.append(message)

        # Store in Graphiti
        await self._store_message(session, message)

        # Broadcast to connected clients
        await self._broadcast_message(session_id, message)

        # If user message, get ambassador response
        if role == "user":
            await self._send_typing_indicator(session_id, True)
            response = await self._get_ambassador_response(session, content)
            await self._send_typing_indicator(session_id, False)

            if response:
                response_msg = ChatMessage(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    role="assistant",
                    content=response,
                    message_type=MessageType.TEXT,
                )
                session.messages.append(response_msg)
                await self._store_message(session, response_msg)
                await self._broadcast_message(session_id, response_msg)

        return message

    async def _store_message(self, session: ChatSession, message: ChatMessage):
        """Store message in Graphiti.

        Args:
            session: Chat session
            message: Message to store
        """
        if not self.graphiti:
            return

        try:
            await self.graphiti.add_episode(
                name=f"chat_message_{message.id}",
                episode_body=f"{message.role}: {message.content}",
                source_description="web_chat",
                group_id=session.student_id,
            )
        except Exception as e:
            logger.warning(f"Failed to store message: {e}")

    async def _get_ambassador_response(
        self,
        session: ChatSession,
        user_message: str,
    ) -> str:
        """Get response from ambassador.

        Args:
            session: Chat session
            user_message: User's message

        Returns:
            Ambassador response
        """
        if self.ambassador_callback:
            try:
                return await self.ambassador_callback(session.student_id, user_message)
            except Exception as e:
                logger.error(f"Ambassador callback failed: {e}")

        # Fallback response
        return "I'm processing your request. How else can I help you?"

    async def _broadcast_message(self, session_id: str, message: ChatMessage):
        """Broadcast message to connected WebSocket.

        Args:
            session_id: Session ID
            message: Message to broadcast
        """
        connection = self._connections.get(session_id)
        if not connection:
            return

        # In production, send via WebSocket
        # await connection.send_json(message_to_dict(message))
        logger.debug(f"Broadcast message in session {session_id}")

    async def _send_typing_indicator(self, session_id: str, is_typing: bool):
        """Send typing indicator.

        Args:
            session_id: Session ID
            is_typing: Whether typing or not
        """
        if is_typing:
            self._typing_users.add(session_id)
        else:
            self._typing_users.discard(session_id)

        connection = self._connections.get(session_id)
        if connection:
            # In production, send typing indicator
            logger.debug(f"Typing indicator: {is_typing} for session {session_id}")

    async def send_image(
        self,
        session_id: str,
        image_url: str,
        caption: str = "",
    ) -> Optional[ChatMessage]:
        """Send an image in the chat (e.g., from Nanobanana).

        Args:
            session_id: Session ID
            image_url: URL of the image
            caption: Optional caption

        Returns:
            Created ChatMessage or None
        """
        session = self._sessions.get(session_id)
        if not session or not session.is_active:
            return None

        message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content=caption,
            message_type=MessageType.IMAGE,
            image_url=image_url,
        )
        session.messages.append(message)

        await self._broadcast_message(session_id, message)

        logger.info(f"Sent image in session {session_id}")

        return message

    async def send_system_message(
        self,
        session_id: str,
        content: str,
    ) -> Optional[ChatMessage]:
        """Send a system message.

        Args:
            session_id: Session ID
            content: System message content

        Returns:
            Created ChatMessage or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        message = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role="system",
            content=content,
            message_type=MessageType.SYSTEM,
        )
        session.messages.append(message)

        await self._broadcast_message(session_id, message)

        return message

    async def end_session(self, session_id: str) -> Optional[ChatSession]:
        """End a chat session.

        Args:
            session_id: Session ID

        Returns:
            Ended ChatSession or None
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        session.is_active = False
        session.ended_at = datetime.utcnow()

        # Disconnect WebSocket
        await self.disconnect(session_id)

        # Store full conversation in Graphiti
        await self._store_full_conversation(session)

        logger.info(f"Ended chat session {session_id}")

        return session

    async def _store_full_conversation(self, session: ChatSession):
        """Store full conversation transcript in Graphiti.

        Args:
            session: Chat session to store
        """
        if not self.graphiti:
            return

        try:
            transcript = "\n".join([
                f"{msg.role}: {msg.content}"
                for msg in session.messages
                if msg.message_type == MessageType.TEXT
            ])

            await self.graphiti.add_conversation(
                student_id=session.student_id,
                messages=[
                    {"role": msg.role, "content": msg.content}
                    for msg in session.messages
                    if msg.message_type == MessageType.TEXT
                ],
                channel="web_chat",
                session_time=session.started_at,
            )
        except Exception as e:
            logger.warning(f"Failed to store conversation: {e}")

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a chat session.

        Args:
            session_id: Session ID

        Returns:
            ChatSession or None
        """
        return self._sessions.get(session_id)

    def get_session_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[ChatMessage]:
        """Get message history for a session.

        Args:
            session_id: Session ID
            limit: Maximum messages to return

        Returns:
            List of ChatMessage objects
        """
        session = self._sessions.get(session_id)
        if not session:
            return []

        return session.messages[-limit:]

    def get_active_sessions(self) -> List[ChatSession]:
        """Get all active chat sessions.

        Returns:
            List of active ChatSession objects
        """
        return [s for s in self._sessions.values() if s.is_active]

    def get_stats(self) -> Dict[str, Any]:
        """Get chat handler statistics.

        Returns:
            Stats dict
        """
        active = len(self.get_active_sessions())
        total = len(self._sessions)
        connected = len(self._connections)

        total_messages = sum(s.message_count for s in self._sessions.values())

        return {
            "active_sessions": active,
            "total_sessions": total,
            "connected_websockets": connected,
            "total_messages": total_messages,
        }


# Utility functions for WebSocket message serialization
def message_to_dict(message: ChatMessage) -> Dict[str, Any]:
    """Convert ChatMessage to dictionary for WebSocket.

    Args:
        message: ChatMessage object

    Returns:
        Dictionary representation
    """
    return {
        "id": message.id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "type": message.message_type.value,
        "timestamp": message.timestamp.isoformat(),
        "image_url": message.image_url,
    }


def dict_to_message(data: Dict[str, Any]) -> ChatMessage:
    """Convert dictionary to ChatMessage.

    Args:
        data: Dictionary data

    Returns:
        ChatMessage object
    """
    return ChatMessage(
        id=data.get("id", str(uuid.uuid4())),
        session_id=data.get("session_id", ""),
        role=data.get("role", "user"),
        content=data.get("content", ""),
        message_type=MessageType(data.get("type", "text")),
        image_url=data.get("image_url"),
    )
