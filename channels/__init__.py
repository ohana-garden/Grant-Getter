# Communication Channels Module
# Integrations for voice, SMS, web chat, and email

from channels.hume_voice import HumeVoiceClient, EmotionState, VoiceSession
from channels.web_chat import WebChatHandler, ChatMessage, ChatSession

__all__ = [
    'HumeVoiceClient',
    'EmotionState',
    'VoiceSession',
    'WebChatHandler',
    'ChatMessage',
    'ChatSession',
]
