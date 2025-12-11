"""SMS/RCS Messaging Integration - Story 4.1

Twilio-based SMS and RCS messaging for student communication.
Supports both traditional SMS and rich RCS messages.
"""

import os
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Awaitable
from enum import Enum
import uuid
import hashlib
import hmac

logger = logging.getLogger(__name__)


class MessageChannel(Enum):
    """Available messaging channels."""
    SMS = "sms"
    RCS = "rcs"
    MMS = "mms"


class MessageStatus(Enum):
    """Message delivery status."""
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


class MessageDirection(Enum):
    """Message direction."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class RCSCapability(Enum):
    """RCS capabilities."""
    TEXT = "text"
    RICH_CARD = "rich_card"
    CAROUSEL = "carousel"
    SUGGESTED_REPLIES = "suggested_replies"
    SUGGESTED_ACTIONS = "suggested_actions"
    FILE_TRANSFER = "file_transfer"


@dataclass
class PhoneNumber:
    """A phone number with metadata."""
    number: str  # E.164 format (+1234567890)
    country_code: str = "US"
    is_mobile: bool = True
    carrier: Optional[str] = None
    rcs_enabled: bool = False
    verified: bool = False
    opted_in: bool = True
    opted_out_at: Optional[datetime] = None

    @property
    def formatted(self) -> str:
        """Get formatted phone number."""
        if len(self.number) == 12 and self.number.startswith("+1"):
            return f"({self.number[2:5]}) {self.number[5:8]}-{self.number[8:]}"
        return self.number


@dataclass
class SMSMessage:
    """An SMS/RCS message."""
    id: str
    student_id: str
    phone_number: str
    content: str
    channel: MessageChannel = MessageChannel.SMS
    direction: MessageDirection = MessageDirection.OUTBOUND
    status: MessageStatus = MessageStatus.QUEUED
    twilio_sid: Optional[str] = None
    media_urls: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RCSCard:
    """An RCS rich card."""
    title: str
    description: str
    image_url: Optional[str] = None
    suggestions: List[Dict[str, str]] = field(default_factory=list)
    orientation: str = "VERTICAL"  # VERTICAL or HORIZONTAL

    def add_reply(self, text: str, postback_data: str = None):
        """Add a suggested reply."""
        self.suggestions.append({
            "type": "reply",
            "text": text,
            "postback_data": postback_data or text,
        })

    def add_action(self, text: str, action_type: str, action_data: str):
        """Add a suggested action."""
        self.suggestions.append({
            "type": "action",
            "text": text,
            "action_type": action_type,  # "dial", "open_url", "share_location"
            "action_data": action_data,
        })


@dataclass
class Conversation:
    """A messaging conversation with a student."""
    id: str
    student_id: str
    phone_number: str
    channel: MessageChannel = MessageChannel.SMS
    messages: List[SMSMessage] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_message_at: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def message_count(self) -> int:
        """Get number of messages."""
        return len(self.messages)

    @property
    def rcs_capable(self) -> bool:
        """Check if conversation is RCS capable."""
        return self.channel == MessageChannel.RCS


# Message templates for common scenarios
MESSAGE_TEMPLATES = {
    "deadline_reminder_7day": {
        "sms": "{name}, reminder: {deadline_name} is due in 7 days on {date}. Reply HELP for assistance.",
        "rcs": {
            "text": "Hi {name}! Friendly reminder: {deadline_name} is due in 7 days on {date}.",
            "suggestions": ["Show details", "Set reminder", "I'll do it now"],
        },
    },
    "deadline_reminder_24hr": {
        "sms": "URGENT: {deadline_name} is due tomorrow ({date})! Don't miss it. Reply HELP for assistance.",
        "rcs": {
            "text": "URGENT: {deadline_name} is due tomorrow ({date})! Don't miss this deadline.",
            "suggestions": ["Start now", "Get help", "Already done"],
        },
    },
    "scholarship_match": {
        "sms": "{name}, we found a new scholarship match: {scholarship_name} - up to {amount}. Deadline: {deadline}. Reply INFO for details.",
        "rcs": {
            "text": "Great news, {name}! We found a scholarship that matches your profile.",
            "card": {
                "title": "{scholarship_name}",
                "description": "Up to {amount} - Deadline: {deadline}",
            },
            "suggestions": ["View details", "Apply now", "Save for later"],
        },
    },
    "aid_received": {
        "sms": "{name}, your financial aid package from {school_name} is ready to review! Check the app for details.",
        "rcs": {
            "text": "Your financial aid package from {school_name} is ready!",
            "suggestions": ["View package", "Compare schools", "Get help"],
        },
    },
    "appeal_update": {
        "sms": "{name}, update on your {school_name} appeal: {status}. Reply VIEW for details.",
        "rcs": {
            "text": "Update on your {school_name} financial aid appeal: {status}",
            "suggestions": ["View details", "Next steps", "Contact advisor"],
        },
    },
    "weekly_summary": {
        "sms": "{name}, your weekly summary: {upcoming_deadlines} upcoming deadlines, {new_matches} new scholarship matches. Reply VIEW for details.",
        "rcs": {
            "text": "Here's your weekly summary, {name}!",
            "card": {
                "title": "This Week",
                "description": "{upcoming_deadlines} deadlines | {new_matches} new matches",
            },
            "suggestions": ["View all", "Check deadlines", "See matches"],
        },
    },
    "opt_in_confirmation": {
        "sms": "Welcome to StudentAid! You'll receive important updates about scholarships, deadlines, and financial aid. Reply STOP to opt out.",
        "rcs": {
            "text": "Welcome to StudentAid! You'll receive important updates about scholarships, deadlines, and financial aid.",
            "suggestions": ["Get started", "Set preferences"],
        },
    },
    "opt_out_confirmation": {
        "sms": "You've been unsubscribed from StudentAid messages. Reply START to re-subscribe.",
        "rcs": {
            "text": "You've been unsubscribed from StudentAid messages. We'll miss you!",
            "suggestions": ["Re-subscribe", "Give feedback"],
        },
    },
}


class SMSRCSClient:
    """Client for SMS and RCS messaging via Twilio.

    Acceptance Criteria:
    - Students can opt-in/out of SMS
    - RCS for rich responses when possible
    - Deadline reminders sent via SMS
    - Respects messaging regulations (TCPA, etc.)
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        phone_number: Optional[str] = None,
        messaging_service_sid: Optional[str] = None,
    ):
        """Initialize SMS/RCS client.

        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            phone_number: Twilio phone number for sending
            messaging_service_sid: Twilio Messaging Service SID
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = phone_number or os.getenv("TWILIO_PHONE_NUMBER")
        self.messaging_service_sid = messaging_service_sid or os.getenv(
            "TWILIO_MESSAGING_SERVICE_SID"
        )

        # Phone number registry
        self._phone_numbers: Dict[str, PhoneNumber] = {}

        # Conversation storage
        self._conversations: Dict[str, Conversation] = {}

        # Message history
        self._messages: List[SMSMessage] = []

        # Webhook handlers
        self._webhook_handlers: Dict[str, Callable] = {}

        # Rate limiting
        self._rate_limits: Dict[str, List[datetime]] = {}
        self.rate_limit_per_minute = 60
        self.rate_limit_per_day = 1000

        # Ambassador callback for responses
        self.ambassador_callback: Optional[Callable[[str, str], Awaitable[str]]] = None

    async def register_phone(
        self,
        student_id: str,
        phone_number: str,
        verify: bool = True,
    ) -> PhoneNumber:
        """Register a phone number for a student.

        Args:
            student_id: Student ID
            phone_number: Phone number in E.164 format
            verify: Whether to verify the number

        Returns:
            PhoneNumber object
        """
        # Normalize phone number
        normalized = self._normalize_phone(phone_number)

        # Check RCS capability
        rcs_enabled = await self._check_rcs_capability(normalized)

        # Create phone number record
        phone = PhoneNumber(
            number=normalized,
            rcs_enabled=rcs_enabled,
            verified=not verify,  # Will be verified if requested
        )

        self._phone_numbers[student_id] = phone

        # Send verification if requested
        if verify:
            await self._send_verification(student_id, normalized)

        logger.info(f"Registered phone {normalized} for student {student_id}")

        return phone

    def _normalize_phone(self, phone_number: str) -> str:
        """Normalize phone number to E.164 format."""
        # Remove all non-digit characters
        digits = ''.join(c for c in phone_number if c.isdigit())

        # Add country code if missing
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        elif digits.startswith("+"):
            return phone_number

        return f"+{digits}"

    async def _check_rcs_capability(self, phone_number: str) -> bool:
        """Check if phone number is RCS capable.

        Args:
            phone_number: Phone number to check

        Returns:
            True if RCS capable
        """
        # In production, call Twilio API to check RCS capability
        # For now, simulate - assume ~30% of numbers are RCS capable
        hash_val = int(hashlib.md5(phone_number.encode()).hexdigest()[:8], 16)
        return hash_val % 10 < 3

    async def _send_verification(self, student_id: str, phone_number: str):
        """Send verification code to phone number."""
        # In production, use Twilio Verify API
        code = str(uuid.uuid4().int)[:6]

        await self.send_message(
            student_id=student_id,
            content=f"Your StudentAid verification code is: {code}",
            bypass_opt_in=True,
        )

        # Store code for verification
        phone = self._phone_numbers.get(student_id)
        if phone:
            phone.verified = False
            # In production, store code securely with expiration

    async def verify_phone(
        self,
        student_id: str,
        code: str,
    ) -> bool:
        """Verify a phone number with the provided code.

        Args:
            student_id: Student ID
            code: Verification code

        Returns:
            True if verified
        """
        phone = self._phone_numbers.get(student_id)
        if not phone:
            return False

        # In production, validate code against stored code
        # For now, accept any 6-digit code
        if len(code) == 6 and code.isdigit():
            phone.verified = True
            logger.info(f"Verified phone for student {student_id}")
            return True

        return False

    async def opt_in(self, student_id: str) -> bool:
        """Opt in a student to receive messages.

        Args:
            student_id: Student ID

        Returns:
            True if successful
        """
        phone = self._phone_numbers.get(student_id)
        if not phone:
            return False

        phone.opted_in = True
        phone.opted_out_at = None

        # Send confirmation
        await self.send_template(
            student_id=student_id,
            template_name="opt_in_confirmation",
            context={},
            bypass_opt_in=True,
        )

        logger.info(f"Student {student_id} opted in to SMS")
        return True

    async def opt_out(self, student_id: str) -> bool:
        """Opt out a student from receiving messages.

        Args:
            student_id: Student ID

        Returns:
            True if successful
        """
        phone = self._phone_numbers.get(student_id)
        if not phone:
            return False

        phone.opted_in = False
        phone.opted_out_at = datetime.utcnow()

        # Send confirmation (this is required by regulations)
        await self.send_template(
            student_id=student_id,
            template_name="opt_out_confirmation",
            context={},
            bypass_opt_in=True,
        )

        logger.info(f"Student {student_id} opted out of SMS")
        return True

    def is_opted_in(self, student_id: str) -> bool:
        """Check if student is opted in.

        Args:
            student_id: Student ID

        Returns:
            True if opted in
        """
        phone = self._phone_numbers.get(student_id)
        return phone is not None and phone.opted_in and phone.verified

    async def send_message(
        self,
        student_id: str,
        content: str,
        media_urls: List[str] = None,
        use_rcs: bool = True,
        bypass_opt_in: bool = False,
    ) -> Optional[SMSMessage]:
        """Send a message to a student.

        Args:
            student_id: Student ID
            content: Message content
            media_urls: Optional media URLs for MMS
            use_rcs: Whether to use RCS if available
            bypass_opt_in: Whether to bypass opt-in check (for confirmations)

        Returns:
            SMSMessage if sent, None if blocked
        """
        phone = self._phone_numbers.get(student_id)
        if not phone:
            logger.warning(f"No phone registered for student {student_id}")
            return None

        # Check opt-in status
        if not bypass_opt_in and not phone.opted_in:
            logger.warning(f"Student {student_id} is not opted in")
            return None

        # Check rate limits
        if not self._check_rate_limit(student_id):
            logger.warning(f"Rate limit exceeded for student {student_id}")
            return None

        # Determine channel
        channel = MessageChannel.SMS
        if use_rcs and phone.rcs_enabled:
            channel = MessageChannel.RCS
        elif media_urls:
            channel = MessageChannel.MMS

        # Create message
        message_id = str(uuid.uuid4())
        message = SMSMessage(
            id=message_id,
            student_id=student_id,
            phone_number=phone.number,
            content=content,
            channel=channel,
            direction=MessageDirection.OUTBOUND,
            media_urls=media_urls or [],
        )

        # Send via Twilio
        success = await self._send_via_twilio(message)

        if success:
            message.status = MessageStatus.SENT
            message.sent_at = datetime.utcnow()
        else:
            message.status = MessageStatus.FAILED

        # Store message
        self._messages.append(message)
        self._update_rate_limit(student_id)

        # Update conversation
        await self._update_conversation(student_id, message)

        return message

    async def _send_via_twilio(self, message: SMSMessage) -> bool:
        """Send message via Twilio API.

        Args:
            message: Message to send

        Returns:
            True if successful
        """
        if not self.account_sid or not self.auth_token:
            logger.warning("Twilio credentials not configured")
            # Simulate successful send for testing
            message.twilio_sid = f"SM{uuid.uuid4().hex[:32]}"
            return True

        try:
            # In production, call Twilio API:
            # from twilio.rest import Client
            # client = Client(self.account_sid, self.auth_token)
            # tw_message = client.messages.create(
            #     body=message.content,
            #     from_=self.phone_number,
            #     to=message.phone_number,
            #     media_url=message.media_urls if message.media_urls else None,
            # )
            # message.twilio_sid = tw_message.sid

            # Simulate for testing
            await asyncio.sleep(0.05)  # Simulate API call
            message.twilio_sid = f"SM{uuid.uuid4().hex[:32]}"

            return True

        except Exception as e:
            logger.error(f"Twilio send failed: {e}")
            message.error_message = str(e)
            return False

    async def send_template(
        self,
        student_id: str,
        template_name: str,
        context: Dict[str, Any],
        bypass_opt_in: bool = False,
    ) -> Optional[SMSMessage]:
        """Send a templated message.

        Args:
            student_id: Student ID
            template_name: Template name from MESSAGE_TEMPLATES
            context: Context for template rendering
            bypass_opt_in: Whether to bypass opt-in check

        Returns:
            SMSMessage if sent
        """
        template = MESSAGE_TEMPLATES.get(template_name)
        if not template:
            logger.error(f"Unknown template: {template_name}")
            return None

        phone = self._phone_numbers.get(student_id)
        use_rcs = phone and phone.rcs_enabled

        if use_rcs and "rcs" in template:
            # Use RCS template
            rcs_template = template["rcs"]
            content = rcs_template["text"].format(**context)

            # In production, would also handle rich cards and suggestions
            # For now, just send the text
        else:
            # Use SMS template
            content = template["sms"].format(**context)

        return await self.send_message(
            student_id=student_id,
            content=content,
            use_rcs=use_rcs,
            bypass_opt_in=bypass_opt_in,
        )

    async def send_rcs_card(
        self,
        student_id: str,
        card: RCSCard,
    ) -> Optional[SMSMessage]:
        """Send an RCS rich card.

        Args:
            student_id: Student ID
            card: RCS card to send

        Returns:
            SMSMessage if sent
        """
        phone = self._phone_numbers.get(student_id)
        if not phone or not phone.rcs_enabled:
            # Fall back to text
            content = f"{card.title}\n\n{card.description}"
            return await self.send_message(student_id=student_id, content=content)

        # In production, send RCS rich card via Twilio RCS API
        # For now, format as text
        content = f"{card.title}\n\n{card.description}"

        if card.suggestions:
            content += "\n\nOptions: "
            content += ", ".join(s["text"] for s in card.suggestions)

        return await self.send_message(
            student_id=student_id,
            content=content,
            use_rcs=True,
        )

    async def send_deadline_reminder(
        self,
        student_id: str,
        deadline_name: str,
        deadline_date: datetime,
        days_until: int,
    ) -> Optional[SMSMessage]:
        """Send a deadline reminder.

        Args:
            student_id: Student ID
            deadline_name: Name of the deadline
            deadline_date: Deadline date
            days_until: Days until deadline

        Returns:
            SMSMessage if sent
        """
        phone = self._phone_numbers.get(student_id)
        name = phone.number if phone else "Student"

        # Choose template based on urgency
        if days_until <= 1:
            template_name = "deadline_reminder_24hr"
        else:
            template_name = "deadline_reminder_7day"

        return await self.send_template(
            student_id=student_id,
            template_name=template_name,
            context={
                "name": name,
                "deadline_name": deadline_name,
                "date": deadline_date.strftime("%B %d, %Y"),
            },
        )

    async def send_scholarship_notification(
        self,
        student_id: str,
        scholarship_name: str,
        amount: str,
        deadline: str,
    ) -> Optional[SMSMessage]:
        """Send a scholarship match notification.

        Args:
            student_id: Student ID
            scholarship_name: Scholarship name
            amount: Award amount
            deadline: Application deadline

        Returns:
            SMSMessage if sent
        """
        phone = self._phone_numbers.get(student_id)
        name = phone.number if phone else "Student"

        return await self.send_template(
            student_id=student_id,
            template_name="scholarship_match",
            context={
                "name": name,
                "scholarship_name": scholarship_name,
                "amount": amount,
                "deadline": deadline,
            },
        )

    async def handle_inbound_message(
        self,
        from_number: str,
        content: str,
        twilio_sid: Optional[str] = None,
    ) -> Optional[SMSMessage]:
        """Handle an incoming message.

        Args:
            from_number: Sender phone number
            content: Message content
            twilio_sid: Twilio message SID

        Returns:
            The inbound SMSMessage
        """
        # Find student by phone number
        student_id = None
        for sid, phone in self._phone_numbers.items():
            if phone.number == self._normalize_phone(from_number):
                student_id = sid
                break

        if not student_id:
            logger.warning(f"Unknown phone number: {from_number}")
            return None

        # Create inbound message
        message = SMSMessage(
            id=str(uuid.uuid4()),
            student_id=student_id,
            phone_number=from_number,
            content=content,
            direction=MessageDirection.INBOUND,
            status=MessageStatus.DELIVERED,
            twilio_sid=twilio_sid,
            delivered_at=datetime.utcnow(),
        )

        # Store message
        self._messages.append(message)

        # Update conversation
        await self._update_conversation(student_id, message)

        # Handle special commands
        content_upper = content.strip().upper()
        if content_upper == "STOP" or content_upper == "UNSUBSCRIBE":
            await self.opt_out(student_id)
            return message
        elif content_upper == "START" or content_upper == "SUBSCRIBE":
            await self.opt_in(student_id)
            return message
        elif content_upper == "HELP":
            await self.send_message(
                student_id=student_id,
                content="StudentAid Help: Reply STOP to unsubscribe. For support, visit studentaid.example.com/help or call 1-800-555-0123.",
                bypass_opt_in=True,
            )
            return message

        # Process with ambassador if callback available
        if self.ambassador_callback:
            try:
                response = await self.ambassador_callback(student_id, content)
                await self.send_message(student_id=student_id, content=response)
            except Exception as e:
                logger.error(f"Ambassador callback failed: {e}")

        return message

    async def _update_conversation(
        self,
        student_id: str,
        message: SMSMessage,
    ):
        """Update or create conversation with message.

        Args:
            student_id: Student ID
            message: Message to add
        """
        if student_id not in self._conversations:
            phone = self._phone_numbers.get(student_id)
            self._conversations[student_id] = Conversation(
                id=str(uuid.uuid4()),
                student_id=student_id,
                phone_number=phone.number if phone else message.phone_number,
                channel=message.channel,
            )

        conv = self._conversations[student_id]
        conv.messages.append(message)
        conv.last_message_at = datetime.utcnow()

    def _check_rate_limit(self, student_id: str) -> bool:
        """Check if student is within rate limits.

        Args:
            student_id: Student ID

        Returns:
            True if within limits
        """
        now = datetime.utcnow()

        if student_id not in self._rate_limits:
            return True

        timestamps = self._rate_limits[student_id]

        # Clean old entries
        cutoff_minute = now - timedelta(minutes=1)
        cutoff_day = now - timedelta(days=1)

        timestamps = [t for t in timestamps if t > cutoff_day]
        self._rate_limits[student_id] = timestamps

        # Check limits
        recent_minute = sum(1 for t in timestamps if t > cutoff_minute)
        if recent_minute >= self.rate_limit_per_minute:
            return False

        if len(timestamps) >= self.rate_limit_per_day:
            return False

        return True

    def _update_rate_limit(self, student_id: str):
        """Update rate limit tracking.

        Args:
            student_id: Student ID
        """
        if student_id not in self._rate_limits:
            self._rate_limits[student_id] = []

        self._rate_limits[student_id].append(datetime.utcnow())

    def get_conversation(self, student_id: str) -> Optional[Conversation]:
        """Get conversation for a student.

        Args:
            student_id: Student ID

        Returns:
            Conversation or None
        """
        return self._conversations.get(student_id)

    def get_message_history(
        self,
        student_id: str,
        limit: int = 50,
    ) -> List[SMSMessage]:
        """Get message history for a student.

        Args:
            student_id: Student ID
            limit: Maximum messages to return

        Returns:
            List of messages
        """
        messages = [m for m in self._messages if m.student_id == student_id]
        return messages[-limit:]

    async def handle_delivery_status(
        self,
        twilio_sid: str,
        status: str,
        error_code: Optional[str] = None,
    ):
        """Handle delivery status webhook.

        Args:
            twilio_sid: Twilio message SID
            status: Status string
            error_code: Optional error code
        """
        # Find message by Twilio SID
        for message in self._messages:
            if message.twilio_sid == twilio_sid:
                try:
                    message.status = MessageStatus(status)
                except ValueError:
                    logger.warning(f"Unknown status: {status}")

                if status == "delivered":
                    message.delivered_at = datetime.utcnow()
                elif status in ("failed", "undelivered"):
                    message.error_code = error_code

                logger.info(f"Updated message {twilio_sid} status to {status}")
                break

    def verify_webhook_signature(
        self,
        url: str,
        params: Dict[str, str],
        signature: str,
    ) -> bool:
        """Verify Twilio webhook signature.

        Args:
            url: Webhook URL
            params: Request parameters
            signature: X-Twilio-Signature header

        Returns:
            True if valid
        """
        if not self.auth_token:
            return False

        # Build string to sign
        param_string = "".join(f"{k}{v}" for k, v in sorted(params.items()))
        data = url + param_string

        # Compute expected signature
        expected = hmac.new(
            self.auth_token.encode(),
            data.encode(),
            hashlib.sha1
        ).digest()

        import base64
        expected_b64 = base64.b64encode(expected).decode()

        return hmac.compare_digest(expected_b64, signature)

    def get_stats(self) -> Dict[str, Any]:
        """Get messaging statistics.

        Returns:
            Stats dict
        """
        total_messages = len(self._messages)
        outbound = sum(1 for m in self._messages if m.direction == MessageDirection.OUTBOUND)
        inbound = total_messages - outbound

        delivered = sum(1 for m in self._messages if m.status == MessageStatus.DELIVERED)
        failed = sum(1 for m in self._messages if m.status == MessageStatus.FAILED)

        rcs_messages = sum(1 for m in self._messages if m.channel == MessageChannel.RCS)

        opted_in = sum(1 for p in self._phone_numbers.values() if p.opted_in)
        verified = sum(1 for p in self._phone_numbers.values() if p.verified)

        return {
            "api_configured": bool(self.account_sid and self.auth_token),
            "total_messages": total_messages,
            "outbound_messages": outbound,
            "inbound_messages": inbound,
            "delivered": delivered,
            "failed": failed,
            "delivery_rate": delivered / outbound if outbound > 0 else 0,
            "rcs_messages": rcs_messages,
            "rcs_percentage": rcs_messages / total_messages if total_messages > 0 else 0,
            "registered_phones": len(self._phone_numbers),
            "opted_in": opted_in,
            "verified": verified,
            "active_conversations": len(self._conversations),
        }


# Convenience functions
async def send_reminder(
    client: SMSRCSClient,
    student_id: str,
    message: str,
) -> Optional[SMSMessage]:
    """Send a simple reminder message.

    Args:
        client: SMSRCSClient instance
        student_id: Student ID
        message: Message content

    Returns:
        SMSMessage if sent
    """
    return await client.send_message(
        student_id=student_id,
        content=message,
    )


async def send_bulk_deadline_reminders(
    client: SMSRCSClient,
    reminders: List[Dict[str, Any]],
) -> List[SMSMessage]:
    """Send bulk deadline reminders.

    Args:
        client: SMSRCSClient instance
        reminders: List of reminder dicts with student_id, deadline_name, deadline_date, days_until

    Returns:
        List of sent messages
    """
    results = []
    for reminder in reminders:
        message = await client.send_deadline_reminder(
            student_id=reminder["student_id"],
            deadline_name=reminder["deadline_name"],
            deadline_date=reminder["deadline_date"],
            days_until=reminder["days_until"],
        )
        if message:
            results.append(message)
        # Small delay to respect rate limits
        await asyncio.sleep(0.1)
    return results
