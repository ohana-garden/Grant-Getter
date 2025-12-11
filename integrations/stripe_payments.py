"""Stripe Payments Integration - Story 6.x

Revenue integration for premium features, subscriptions, and referrals.
Handles payment processing, subscription management, and revenue tracking.
"""

import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid
import hmac
import hashlib

logger = logging.getLogger(__name__)


class SubscriptionTier(Enum):
    """Available subscription tiers."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    FAMILY = "family"


class SubscriptionStatus(Enum):
    """Subscription status."""
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


class PaymentStatus(Enum):
    """Payment transaction status."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class WebhookEvent(Enum):
    """Stripe webhook event types."""
    PAYMENT_SUCCEEDED = "payment_intent.succeeded"
    PAYMENT_FAILED = "payment_intent.payment_failed"
    SUBSCRIPTION_CREATED = "customer.subscription.created"
    SUBSCRIPTION_UPDATED = "customer.subscription.updated"
    SUBSCRIPTION_DELETED = "customer.subscription.deleted"
    INVOICE_PAID = "invoice.paid"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"


# Tier pricing configuration
TIER_PRICING = {
    SubscriptionTier.FREE: {
        "monthly_price": 0,
        "annual_price": 0,
        "features": [
            "Basic scholarship search",
            "3 school comparisons/month",
            "Email support",
        ],
        "limits": {
            "scholarship_searches": 10,
            "comparisons_per_month": 3,
            "document_uploads": 5,
            "specialist_queries": 3,
        }
    },
    SubscriptionTier.BASIC: {
        "monthly_price": 999,  # $9.99 in cents
        "annual_price": 9999,  # $99.99 in cents (2 months free)
        "features": [
            "Unlimited scholarship search",
            "10 school comparisons/month",
            "Appeal letter drafts",
            "Deadline reminders",
            "Email & chat support",
        ],
        "limits": {
            "scholarship_searches": -1,  # unlimited
            "comparisons_per_month": 10,
            "document_uploads": 25,
            "specialist_queries": 20,
        }
    },
    SubscriptionTier.PREMIUM: {
        "monthly_price": 1999,  # $19.99 in cents
        "annual_price": 19999,  # $199.99 in cents
        "features": [
            "Everything in Basic",
            "Unlimited comparisons",
            "Priority support",
            "1-on-1 counselor chat",
            "Win card celebrations",
            "Family member access (1)",
        ],
        "limits": {
            "scholarship_searches": -1,
            "comparisons_per_month": -1,
            "document_uploads": -1,
            "specialist_queries": -1,
            "family_members": 1,
        }
    },
    SubscriptionTier.FAMILY: {
        "monthly_price": 3999,  # $39.99 in cents
        "annual_price": 39999,  # $399.99 in cents
        "features": [
            "Everything in Premium",
            "Up to 4 family members",
            "Shared scholarship tracker",
            "Family deadline calendar",
            "Dedicated advisor",
        ],
        "limits": {
            "scholarship_searches": -1,
            "comparisons_per_month": -1,
            "document_uploads": -1,
            "specialist_queries": -1,
            "family_members": 4,
        }
    },
}


@dataclass
class Subscription:
    """A user subscription."""
    id: str
    student_id: str
    tier: SubscriptionTier
    status: SubscriptionStatus
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    current_period_start: datetime = None
    current_period_end: datetime = None
    cancel_at_period_end: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    trial_ends_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.current_period_start is None:
            self.current_period_start = datetime.utcnow()
        if self.current_period_end is None:
            self.current_period_end = self.current_period_start + timedelta(days=30)

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        return self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)

    @property
    def days_until_renewal(self) -> int:
        """Days until subscription renews."""
        if not self.current_period_end:
            return 0
        delta = self.current_period_end - datetime.utcnow()
        return max(0, delta.days)

    @property
    def pricing(self) -> Dict[str, Any]:
        """Get pricing info for this tier."""
        return TIER_PRICING.get(self.tier, TIER_PRICING[SubscriptionTier.FREE])

    def check_limit(self, limit_name: str) -> int:
        """Get the limit value for a feature.

        Returns:
            -1 for unlimited, or the numeric limit
        """
        limits = self.pricing.get("limits", {})
        return limits.get(limit_name, 0)


@dataclass
class Payment:
    """A payment transaction."""
    id: str
    student_id: str
    amount: int  # in cents
    currency: str = "usd"
    status: PaymentStatus = PaymentStatus.PENDING
    stripe_payment_intent_id: Optional[str] = None
    subscription_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Referral:
    """A referral record."""
    id: str
    referrer_id: str  # student who referred
    referred_id: str  # new student
    referral_code: str
    status: str = "pending"  # pending, converted, expired
    reward_amount: int = 0  # in cents
    reward_paid: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    converted_at: Optional[datetime] = None


class StripePaymentsClient:
    """Client for Stripe payment operations.

    Handles subscriptions, payments, and revenue tracking.

    Acceptance Criteria:
    - Students can upgrade to premium tiers
    - Payment processing via Stripe
    - Subscription management (cancel, upgrade, downgrade)
    - Referral rewards tracking
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ):
        """Initialize Stripe client.

        Args:
            api_key: Stripe API key (or from STRIPE_API_KEY env var)
            webhook_secret: Stripe webhook signing secret
        """
        self.api_key = api_key or os.getenv("STRIPE_API_KEY")
        self.webhook_secret = webhook_secret or os.getenv("STRIPE_WEBHOOK_SECRET")

        # In-memory storage (use database in production)
        self._subscriptions: Dict[str, Subscription] = {}
        self._payments: Dict[str, Payment] = {}
        self._referrals: Dict[str, Referral] = {}
        self._referral_codes: Dict[str, str] = {}  # code -> student_id

        # Revenue tracking
        self._revenue: Dict[str, int] = {
            "total": 0,
            "monthly": 0,
            "refunded": 0,
        }

    async def create_subscription(
        self,
        student_id: str,
        tier: SubscriptionTier,
        payment_method_id: Optional[str] = None,
        trial_days: int = 0,
        referral_code: Optional[str] = None,
    ) -> Subscription:
        """Create a new subscription for a student.

        Args:
            student_id: Student ID
            tier: Subscription tier
            payment_method_id: Stripe payment method ID
            trial_days: Number of trial days
            referral_code: Optional referral code

        Returns:
            Created Subscription
        """
        # Check for existing subscription
        existing = await self.get_subscription(student_id)
        if existing and existing.is_active:
            raise ValueError(f"Student {student_id} already has an active subscription")

        # Create subscription ID
        sub_id = str(uuid.uuid4())

        # Calculate trial period
        trial_ends = None
        status = SubscriptionStatus.ACTIVE
        if trial_days > 0:
            trial_ends = datetime.utcnow() + timedelta(days=trial_days)
            status = SubscriptionStatus.TRIALING

        # Create subscription
        subscription = Subscription(
            id=sub_id,
            student_id=student_id,
            tier=tier,
            status=status,
            trial_ends_at=trial_ends,
            metadata={"payment_method_id": payment_method_id},
        )

        # In production, call Stripe API here:
        # stripe.Subscription.create(...)
        subscription.stripe_subscription_id = f"sub_{uuid.uuid4().hex[:14]}"
        subscription.stripe_customer_id = f"cus_{uuid.uuid4().hex[:14]}"

        # Store subscription
        self._subscriptions[student_id] = subscription

        # Process referral if provided
        if referral_code:
            await self._process_referral(referral_code, student_id)

        logger.info(f"Created {tier.value} subscription for student {student_id}")

        return subscription

    async def get_subscription(self, student_id: str) -> Optional[Subscription]:
        """Get a student's current subscription.

        Args:
            student_id: Student ID

        Returns:
            Subscription or None
        """
        return self._subscriptions.get(student_id)

    async def upgrade_subscription(
        self,
        student_id: str,
        new_tier: SubscriptionTier,
    ) -> Subscription:
        """Upgrade a subscription to a higher tier.

        Args:
            student_id: Student ID
            new_tier: New subscription tier

        Returns:
            Updated Subscription
        """
        subscription = await self.get_subscription(student_id)
        if not subscription:
            raise ValueError(f"No subscription found for student {student_id}")

        old_tier = subscription.tier

        # Validate upgrade
        tier_order = [SubscriptionTier.FREE, SubscriptionTier.BASIC,
                      SubscriptionTier.PREMIUM, SubscriptionTier.FAMILY]
        if tier_order.index(new_tier) <= tier_order.index(old_tier):
            raise ValueError(f"Cannot upgrade from {old_tier.value} to {new_tier.value}")

        # Update tier
        subscription.tier = new_tier
        subscription.metadata["previous_tier"] = old_tier.value
        subscription.metadata["upgraded_at"] = datetime.utcnow().isoformat()

        # In production, update Stripe subscription here
        logger.info(f"Upgraded student {student_id} from {old_tier.value} to {new_tier.value}")

        return subscription

    async def downgrade_subscription(
        self,
        student_id: str,
        new_tier: SubscriptionTier,
        at_period_end: bool = True,
    ) -> Subscription:
        """Downgrade a subscription to a lower tier.

        Args:
            student_id: Student ID
            new_tier: New subscription tier
            at_period_end: Whether to apply at end of current period

        Returns:
            Updated Subscription
        """
        subscription = await self.get_subscription(student_id)
        if not subscription:
            raise ValueError(f"No subscription found for student {student_id}")

        old_tier = subscription.tier

        if at_period_end:
            # Schedule downgrade for end of period
            subscription.metadata["scheduled_tier"] = new_tier.value
            subscription.metadata["scheduled_at"] = subscription.current_period_end.isoformat()
            logger.info(f"Scheduled downgrade for student {student_id} at period end")
        else:
            # Immediate downgrade
            subscription.tier = new_tier
            subscription.metadata["previous_tier"] = old_tier.value
            subscription.metadata["downgraded_at"] = datetime.utcnow().isoformat()
            logger.info(f"Downgraded student {student_id} from {old_tier.value} to {new_tier.value}")

        return subscription

    async def cancel_subscription(
        self,
        student_id: str,
        at_period_end: bool = True,
        reason: Optional[str] = None,
    ) -> Subscription:
        """Cancel a subscription.

        Args:
            student_id: Student ID
            at_period_end: Whether to cancel at end of current period
            reason: Cancellation reason

        Returns:
            Updated Subscription
        """
        subscription = await self.get_subscription(student_id)
        if not subscription:
            raise ValueError(f"No subscription found for student {student_id}")

        if at_period_end:
            subscription.cancel_at_period_end = True
            subscription.metadata["cancel_reason"] = reason
            logger.info(f"Scheduled cancellation for student {student_id} at period end")
        else:
            subscription.status = SubscriptionStatus.CANCELED
            subscription.metadata["canceled_at"] = datetime.utcnow().isoformat()
            subscription.metadata["cancel_reason"] = reason
            logger.info(f"Immediately canceled subscription for student {student_id}")

        return subscription

    async def reactivate_subscription(
        self,
        student_id: str,
    ) -> Subscription:
        """Reactivate a canceled subscription.

        Args:
            student_id: Student ID

        Returns:
            Reactivated Subscription
        """
        subscription = await self.get_subscription(student_id)
        if not subscription:
            raise ValueError(f"No subscription found for student {student_id}")

        if subscription.status == SubscriptionStatus.CANCELED:
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.cancel_at_period_end = False
            subscription.metadata.pop("cancel_reason", None)
            subscription.current_period_start = datetime.utcnow()
            subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
            logger.info(f"Reactivated subscription for student {student_id}")
        elif subscription.cancel_at_period_end:
            subscription.cancel_at_period_end = False
            subscription.metadata.pop("cancel_reason", None)
            logger.info(f"Removed scheduled cancellation for student {student_id}")

        return subscription

    async def process_payment(
        self,
        student_id: str,
        amount: int,
        description: str,
        payment_method_id: Optional[str] = None,
    ) -> Payment:
        """Process a one-time payment.

        Args:
            student_id: Student ID
            amount: Amount in cents
            description: Payment description
            payment_method_id: Stripe payment method ID

        Returns:
            Payment record
        """
        payment_id = str(uuid.uuid4())

        payment = Payment(
            id=payment_id,
            student_id=student_id,
            amount=amount,
            description=description,
            status=PaymentStatus.PENDING,
            metadata={"payment_method_id": payment_method_id},
        )

        # In production, call Stripe API here:
        # stripe.PaymentIntent.create(...)
        payment.stripe_payment_intent_id = f"pi_{uuid.uuid4().hex[:14]}"

        # Simulate successful payment
        payment.status = PaymentStatus.SUCCEEDED
        payment.completed_at = datetime.utcnow()

        # Update revenue tracking
        self._revenue["total"] += amount
        self._revenue["monthly"] += amount

        # Store payment
        self._payments[payment_id] = payment

        logger.info(f"Processed ${amount/100:.2f} payment for student {student_id}")

        return payment

    async def refund_payment(
        self,
        payment_id: str,
        amount: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> Payment:
        """Refund a payment.

        Args:
            payment_id: Payment ID to refund
            amount: Amount to refund (None for full refund)
            reason: Refund reason

        Returns:
            Updated Payment
        """
        payment = self._payments.get(payment_id)
        if not payment:
            raise ValueError(f"Payment {payment_id} not found")

        if payment.status != PaymentStatus.SUCCEEDED:
            raise ValueError(f"Cannot refund payment with status {payment.status}")

        refund_amount = amount or payment.amount

        # Update payment status
        payment.status = PaymentStatus.REFUNDED
        payment.refunded_at = datetime.utcnow()
        payment.metadata["refund_amount"] = refund_amount
        payment.metadata["refund_reason"] = reason

        # Update revenue tracking
        self._revenue["refunded"] += refund_amount
        self._revenue["total"] -= refund_amount

        logger.info(f"Refunded ${refund_amount/100:.2f} for payment {payment_id}")

        return payment

    async def create_referral_code(
        self,
        student_id: str,
    ) -> str:
        """Create a referral code for a student.

        Args:
            student_id: Student ID

        Returns:
            Referral code string
        """
        # Generate unique code
        code_base = student_id[:4].upper()
        code = f"{code_base}{uuid.uuid4().hex[:6].upper()}"

        self._referral_codes[code] = student_id

        logger.info(f"Created referral code {code} for student {student_id}")

        return code

    async def get_referral_code(self, student_id: str) -> Optional[str]:
        """Get a student's referral code.

        Args:
            student_id: Student ID

        Returns:
            Referral code or None
        """
        for code, sid in self._referral_codes.items():
            if sid == student_id:
                return code
        return None

    async def _process_referral(
        self,
        referral_code: str,
        referred_id: str,
    ):
        """Process a referral when a new user signs up.

        Args:
            referral_code: Referral code used
            referred_id: New student ID
        """
        referrer_id = self._referral_codes.get(referral_code)
        if not referrer_id:
            logger.warning(f"Invalid referral code: {referral_code}")
            return

        referral_id = str(uuid.uuid4())

        referral = Referral(
            id=referral_id,
            referrer_id=referrer_id,
            referred_id=referred_id,
            referral_code=referral_code,
            status="converted",
            reward_amount=500,  # $5.00 reward
            converted_at=datetime.utcnow(),
        )

        self._referrals[referral_id] = referral

        logger.info(f"Processed referral from {referrer_id} for {referred_id}")

    async def get_referral_stats(
        self,
        student_id: str,
    ) -> Dict[str, Any]:
        """Get referral statistics for a student.

        Args:
            student_id: Student ID

        Returns:
            Referral stats dict
        """
        referrals = [r for r in self._referrals.values() if r.referrer_id == student_id]

        return {
            "total_referrals": len(referrals),
            "converted_referrals": sum(1 for r in referrals if r.status == "converted"),
            "pending_referrals": sum(1 for r in referrals if r.status == "pending"),
            "total_rewards": sum(r.reward_amount for r in referrals if r.reward_paid),
            "pending_rewards": sum(r.reward_amount for r in referrals if not r.reward_paid and r.status == "converted"),
        }

    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """Verify a Stripe webhook signature.

        Args:
            payload: Raw request body
            signature: Stripe-Signature header

        Returns:
            True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("No webhook secret configured")
            return False

        # Parse signature header
        try:
            # Stripe signature format: t=timestamp,v1=signature
            parts = dict(p.split("=", 1) for p in signature.split(","))
            timestamp = parts.get("t")
            expected_sig = parts.get("v1")

            if not timestamp or not expected_sig:
                return False

            # Compute expected signature
            signed_payload = f"{timestamp}.{payload.decode()}"
            computed = hmac.new(
                self.webhook_secret.encode(),
                signed_payload.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(computed, expected_sig)

        except Exception as e:
            logger.error(f"Webhook verification failed: {e}")
            return False

    async def handle_webhook(
        self,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle a Stripe webhook event.

        Args:
            event_type: Event type string
            event_data: Event data payload

        Returns:
            Processing result
        """
        logger.info(f"Processing webhook event: {event_type}")

        try:
            event = WebhookEvent(event_type)
        except ValueError:
            logger.warning(f"Unknown webhook event type: {event_type}")
            return {"handled": False, "reason": "unknown_event"}

        if event == WebhookEvent.PAYMENT_SUCCEEDED:
            return await self._handle_payment_succeeded(event_data)
        elif event == WebhookEvent.PAYMENT_FAILED:
            return await self._handle_payment_failed(event_data)
        elif event == WebhookEvent.SUBSCRIPTION_CREATED:
            return await self._handle_subscription_created(event_data)
        elif event == WebhookEvent.SUBSCRIPTION_UPDATED:
            return await self._handle_subscription_updated(event_data)
        elif event == WebhookEvent.SUBSCRIPTION_DELETED:
            return await self._handle_subscription_deleted(event_data)
        elif event == WebhookEvent.INVOICE_PAID:
            return await self._handle_invoice_paid(event_data)
        elif event == WebhookEvent.INVOICE_PAYMENT_FAILED:
            return await self._handle_invoice_failed(event_data)

        return {"handled": True}

    async def _handle_payment_succeeded(self, data: Dict) -> Dict:
        """Handle successful payment."""
        payment_intent_id = data.get("id")
        amount = data.get("amount", 0)

        # Find and update payment
        for payment in self._payments.values():
            if payment.stripe_payment_intent_id == payment_intent_id:
                payment.status = PaymentStatus.SUCCEEDED
                payment.completed_at = datetime.utcnow()
                self._revenue["total"] += amount
                break

        return {"handled": True, "payment_intent_id": payment_intent_id}

    async def _handle_payment_failed(self, data: Dict) -> Dict:
        """Handle failed payment."""
        payment_intent_id = data.get("id")
        error = data.get("last_payment_error", {}).get("message", "Unknown error")

        for payment in self._payments.values():
            if payment.stripe_payment_intent_id == payment_intent_id:
                payment.status = PaymentStatus.FAILED
                payment.metadata["error"] = error
                break

        return {"handled": True, "error": error}

    async def _handle_subscription_created(self, data: Dict) -> Dict:
        """Handle new subscription."""
        sub_id = data.get("id")
        customer_id = data.get("customer")
        status = data.get("status")

        logger.info(f"Subscription created: {sub_id} for customer {customer_id}")

        return {"handled": True, "subscription_id": sub_id}

    async def _handle_subscription_updated(self, data: Dict) -> Dict:
        """Handle subscription update."""
        sub_id = data.get("id")
        status = data.get("status")

        # Find and update subscription
        for subscription in self._subscriptions.values():
            if subscription.stripe_subscription_id == sub_id:
                try:
                    subscription.status = SubscriptionStatus(status)
                except ValueError:
                    pass
                break

        return {"handled": True, "subscription_id": sub_id}

    async def _handle_subscription_deleted(self, data: Dict) -> Dict:
        """Handle subscription cancellation."""
        sub_id = data.get("id")

        for subscription in self._subscriptions.values():
            if subscription.stripe_subscription_id == sub_id:
                subscription.status = SubscriptionStatus.CANCELED
                break

        return {"handled": True, "subscription_id": sub_id}

    async def _handle_invoice_paid(self, data: Dict) -> Dict:
        """Handle paid invoice."""
        amount = data.get("amount_paid", 0)
        customer_id = data.get("customer")

        self._revenue["total"] += amount
        self._revenue["monthly"] += amount

        return {"handled": True, "amount": amount}

    async def _handle_invoice_failed(self, data: Dict) -> Dict:
        """Handle failed invoice payment."""
        sub_id = data.get("subscription")
        customer_id = data.get("customer")

        for subscription in self._subscriptions.values():
            if subscription.stripe_subscription_id == sub_id:
                subscription.status = SubscriptionStatus.PAST_DUE
                break

        return {"handled": True, "subscription_id": sub_id}

    def get_revenue_stats(self) -> Dict[str, Any]:
        """Get revenue statistics.

        Returns:
            Revenue stats dict
        """
        total_subs = len(self._subscriptions)
        active_subs = sum(1 for s in self._subscriptions.values() if s.is_active)

        tier_counts = {}
        for tier in SubscriptionTier:
            tier_counts[tier.value] = sum(
                1 for s in self._subscriptions.values()
                if s.tier == tier and s.is_active
            )

        return {
            "total_revenue_cents": self._revenue["total"],
            "total_revenue_dollars": self._revenue["total"] / 100,
            "monthly_revenue_cents": self._revenue["monthly"],
            "refunded_cents": self._revenue["refunded"],
            "total_subscriptions": total_subs,
            "active_subscriptions": active_subs,
            "subscriptions_by_tier": tier_counts,
            "total_payments": len(self._payments),
            "total_referrals": len(self._referrals),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.

        Returns:
            Stats dict
        """
        return {
            "api_configured": bool(self.api_key),
            "webhook_configured": bool(self.webhook_secret),
            **self.get_revenue_stats(),
        }


# Convenience functions
async def create_free_subscription(
    client: StripePaymentsClient,
    student_id: str,
) -> Subscription:
    """Create a free tier subscription.

    Args:
        client: StripePaymentsClient instance
        student_id: Student ID

    Returns:
        Subscription
    """
    return await client.create_subscription(
        student_id=student_id,
        tier=SubscriptionTier.FREE,
    )


async def create_premium_trial(
    client: StripePaymentsClient,
    student_id: str,
    trial_days: int = 14,
    referral_code: Optional[str] = None,
) -> Subscription:
    """Create a premium subscription with trial.

    Args:
        client: StripePaymentsClient instance
        student_id: Student ID
        trial_days: Number of trial days
        referral_code: Optional referral code

    Returns:
        Subscription
    """
    return await client.create_subscription(
        student_id=student_id,
        tier=SubscriptionTier.PREMIUM,
        trial_days=trial_days,
        referral_code=referral_code,
    )


def get_tier_features(tier: SubscriptionTier) -> List[str]:
    """Get features list for a subscription tier.

    Args:
        tier: Subscription tier

    Returns:
        List of feature strings
    """
    pricing = TIER_PRICING.get(tier)
    if pricing:
        return pricing.get("features", [])
    return []


def get_tier_price(tier: SubscriptionTier, annual: bool = False) -> int:
    """Get price for a subscription tier.

    Args:
        tier: Subscription tier
        annual: Whether to get annual price

    Returns:
        Price in cents
    """
    pricing = TIER_PRICING.get(tier)
    if pricing:
        return pricing.get("annual_price" if annual else "monthly_price", 0)
    return 0
