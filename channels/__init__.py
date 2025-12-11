# Communication Channels Module
# Integrations for voice, SMS, web chat, and email

from channels.hume_voice import HumeVoiceClient, EmotionState, VoiceSession
from channels.web_chat import WebChatHandler, ChatMessage, ChatSession
from channels.sms_rcs import (
    SMSRCSClient,
    SMSMessage,
    Conversation,
    PhoneNumber,
    RCSCard,
    MessageChannel,
    MessageStatus,
    MESSAGE_TEMPLATES,
)

__all__ = [
    # Hume Voice
    'HumeVoiceClient',
    'EmotionState',
    'VoiceSession',
    # Web Chat
    'WebChatHandler',
    'ChatMessage',
    'ChatSession',
    # SMS/RCS
    'SMSRCSClient',
    'SMSMessage',
    'Conversation',
    'PhoneNumber',
    'RCSCard',
    'MessageChannel',
    'MessageStatus',
    'MESSAGE_TEMPLATES',
]
