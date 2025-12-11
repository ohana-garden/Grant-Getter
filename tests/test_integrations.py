"""Tests for Integrations Module - Stories 5.1 & 6.x

Tests for Nanobanana image generation and Stripe payments services.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

from integrations import NanobananaClient, WinCard, ImageStyle
from integrations import (
    StripePaymentsClient,
    Subscription,
    SubscriptionTier,
    SubscriptionStatus,
    Payment,
    PaymentStatus,
    Referral,
    TIER_PRICING,
)
from integrations.stripe_payments import (
    WebhookEvent,
    create_free_subscription,
    create_premium_trial,
    get_tier_features,
    get_tier_price,
)
from integrations.nanobanana import (
    GenerationStatus,
    GenerationRequest,
    GenerationResult,
    WIN_CARD_TEMPLATES,
    STYLE_PROMPTS,
    create_scholarship_win_card,
    create_fafsa_complete_card,
    create_deadline_met_card,
    create_appeal_success_card,
)


# ============================================================================
# Nanobanana Client Tests
# ============================================================================

class TestNanobananaClient:
    """Tests for NanobananaClient."""

    def test_client_initialization_default(self):
        """Test client initializes with defaults."""
        client = NanobananaClient()

        assert client.base_url == "https://api.nanobanana.ai/v1"
        assert client._cache == {}
        assert client._history == []
        assert client._pending == {}

    def test_client_initialization_custom(self):
        """Test client initializes with custom values."""
        client = NanobananaClient(
            api_key="test-key",
            base_url="https://custom.api.ai/v1"
        )

        assert client.api_key == "test-key"
        assert client.base_url == "https://custom.api.ai/v1"

    @pytest.mark.asyncio
    async def test_generate_win_card_scholarship(self):
        """Test generating scholarship win card."""
        client = NanobananaClient(api_key="test-key")

        card = await client.generate_win_card(
            student_id="student123",
            card_type="scholarship_won",
            context={
                "scholarship_name": "Merit Award",
                "amount": "$5,000",
            }
        )

        assert card.student_id == "student123"
        assert card.title == "Scholarship Won!"
        assert "Merit Award" in card.message
        assert "$5,000" in card.message
        assert card.style == ImageStyle.CELEBRATION
        assert card.achievement_type == "scholarship_won"
        assert card.achievement_value == "$5,000"
        assert card.status == GenerationStatus.COMPLETED
        assert card.image_url is not None
        assert "nanobanana.ai" in card.image_url

    @pytest.mark.asyncio
    async def test_generate_win_card_fafsa(self):
        """Test generating FAFSA completion win card."""
        client = NanobananaClient(api_key="test-key")

        card = await client.generate_win_card(
            student_id="student456",
            card_type="fafsa_completed",
            context={}
        )

        assert card.title == "FAFSA Complete!"
        assert "FAFSA" in card.message
        assert card.style == ImageStyle.ACHIEVEMENT
        assert card.status == GenerationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_generate_win_card_application(self):
        """Test generating application submitted win card."""
        client = NanobananaClient(api_key="test-key")

        card = await client.generate_win_card(
            student_id="student789",
            card_type="application_submitted",
            context={"school_name": "UCLA"}
        )

        assert card.title == "Application Submitted!"
        assert "UCLA" in card.message
        assert card.style == ImageStyle.MILESTONE
        assert card.school_name == "UCLA"

    @pytest.mark.asyncio
    async def test_generate_win_card_deadline(self):
        """Test generating deadline met win card."""
        client = NanobananaClient(api_key="test-key")

        card = await client.generate_win_card(
            student_id="student123",
            card_type="deadline_met",
            context={"deadline_name": "Early Action"}
        )

        assert card.title == "Deadline Met!"
        assert "Early Action" in card.message
        assert card.style == ImageStyle.MILESTONE

    @pytest.mark.asyncio
    async def test_generate_win_card_aid_package(self):
        """Test generating aid package received win card."""
        client = NanobananaClient(api_key="test-key")

        card = await client.generate_win_card(
            student_id="student123",
            card_type="aid_package_received",
            context={"school_name": "Stanford"}
        )

        assert card.title == "Aid Package Received!"
        assert "Stanford" in card.message
        assert card.style == ImageStyle.SCHOLARSHIP

    @pytest.mark.asyncio
    async def test_generate_win_card_appeal_success(self):
        """Test generating appeal success win card."""
        client = NanobananaClient(api_key="test-key")

        card = await client.generate_win_card(
            student_id="student123",
            card_type="appeal_success",
            context={
                "school_name": "MIT",
                "increase": "$3,000"
            }
        )

        assert card.title == "Appeal Successful!"
        assert "MIT" in card.message
        assert "$3,000" in card.message
        assert card.style == ImageStyle.CELEBRATION
        assert card.achievement_value == "$3,000"

    @pytest.mark.asyncio
    async def test_generate_win_card_unknown_type(self):
        """Test generating win card with unknown type falls back to milestone."""
        client = NanobananaClient(api_key="test-key")

        card = await client.generate_win_card(
            student_id="student123",
            card_type="unknown_type",
            context={"milestone_description": "Custom milestone!"}
        )

        # Falls back to milestone_reached template
        assert card.title == "Milestone Reached!"
        assert card.style == ImageStyle.MILESTONE

    @pytest.mark.asyncio
    async def test_generate_comparison_card_two_schools(self):
        """Test generating comparison card for two schools."""
        client = NanobananaClient(api_key="test-key")

        schools = [
            {"name": "UCLA", "total_aid": 45000},
            {"name": "USC", "total_aid": 52000},
        ]

        card = await client.generate_comparison_card(
            student_id="student123",
            schools=schools
        )

        assert card.title == "Aid Package Comparison"
        assert "UCLA" in card.message
        assert "USC" in card.message
        assert card.style == ImageStyle.COMPARISON
        assert card.achievement_type == "comparison"
        assert card.metadata.get("schools") == schools
        assert card.status == GenerationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_generate_comparison_card_multiple_schools(self):
        """Test generating comparison card for multiple schools."""
        client = NanobananaClient(api_key="test-key")

        schools = [
            {"name": "UCLA"},
            {"name": "USC"},
            {"name": "Stanford"},
            {"name": "Berkeley"},
        ]

        card = await client.generate_comparison_card(
            student_id="student123",
            schools=schools
        )

        # Message should list all schools
        assert "UCLA" in card.message
        assert "USC" in card.message
        assert "Stanford" in card.message
        assert "Berkeley" in card.message

    @pytest.mark.asyncio
    async def test_generate_motivational_image(self):
        """Test generating motivational image."""
        client = NanobananaClient(api_key="test-key")

        card = await client.generate_motivational_image(
            student_id="student123",
            message="You're almost there! Keep pushing!"
        )

        assert card.title == "Keep Going!"
        assert card.message == "You're almost there! Keep pushing!"
        assert card.style == ImageStyle.MOTIVATIONAL
        assert card.achievement_type == "motivation"
        assert card.status == GenerationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_image_caching(self):
        """Test that images are cached and reused."""
        client = NanobananaClient(api_key="test-key")

        # Generate first card
        card1 = await client.generate_win_card(
            student_id="student1",
            card_type="fafsa_completed",
            context={}
        )

        # Clear cache stats before second generation
        initial_cache_size = len(client._cache)
        assert initial_cache_size >= 1  # At least one cached

        # Generate same type again - should use cache
        card2 = await client.generate_win_card(
            student_id="student2",  # Different student
            card_type="fafsa_completed",
            context={}
        )

        # Cache should not grow (same prompt/style)
        assert len(client._cache) == initial_cache_size

    def test_clear_cache(self):
        """Test cache clearing."""
        client = NanobananaClient(api_key="test-key")

        # Add something to cache
        client._cache["test_key"] = "test_url"
        assert len(client._cache) == 1

        # Clear cache
        client.clear_cache()
        assert len(client._cache) == 0

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        client = NanobananaClient(api_key="test-key")

        stats = client.get_cache_stats()

        assert "cached_images" in stats
        assert "total_generated" in stats
        assert "successful" in stats
        assert "failed" in stats
        assert "pending" in stats

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting client statistics."""
        client = NanobananaClient(api_key="test-key")

        # Generate a card
        await client.generate_win_card(
            student_id="student123",
            card_type="fafsa_completed",
            context={}
        )

        stats = client.get_stats()

        assert stats["api_configured"] is True
        assert "base_url" in stats
        assert stats["total_requests"] >= 1
        assert stats["successful_requests"] >= 1
        assert "average_generation_time_ms" in stats

    def test_get_stats_no_api_key(self):
        """Test stats shows API not configured when no key."""
        client = NanobananaClient(api_key=None)

        stats = client.get_stats()
        assert stats["api_configured"] is False

    @pytest.mark.asyncio
    async def test_history_limit(self):
        """Test history is limited to 100 entries."""
        client = NanobananaClient(api_key="test-key")

        # Generate many cards
        for i in range(110):
            await client.generate_win_card(
                student_id=f"student{i}",
                card_type="fafsa_completed",
                context={}
            )

        # History should be limited
        assert len(client._history) <= 100


# ============================================================================
# WinCard Tests
# ============================================================================

class TestWinCard:
    """Tests for WinCard dataclass."""

    def test_win_card_creation(self):
        """Test WinCard creation with defaults."""
        card = WinCard(
            id="card123",
            student_id="student456",
            title="Test Title",
            message="Test message",
            style=ImageStyle.CELEBRATION,
        )

        assert card.id == "card123"
        assert card.student_id == "student456"
        assert card.title == "Test Title"
        assert card.message == "Test message"
        assert card.style == ImageStyle.CELEBRATION
        assert card.image_url is None
        assert card.thumbnail_url is None
        assert card.status == GenerationStatus.PENDING
        assert isinstance(card.created_at, datetime)
        assert card.metadata == {}

    def test_win_card_with_all_fields(self):
        """Test WinCard with all fields populated."""
        card = WinCard(
            id="card123",
            student_id="student456",
            title="Scholarship Won!",
            message="You won $5,000!",
            style=ImageStyle.CELEBRATION,
            image_url="https://example.com/image.png",
            thumbnail_url="https://example.com/thumb.png",
            metadata={"source": "test"},
            achievement_type="scholarship",
            achievement_value="$5,000",
            school_name="UCLA",
            status=GenerationStatus.COMPLETED,
        )

        assert card.image_url == "https://example.com/image.png"
        assert card.thumbnail_url == "https://example.com/thumb.png"
        assert card.achievement_type == "scholarship"
        assert card.achievement_value == "$5,000"
        assert card.school_name == "UCLA"
        assert card.status == GenerationStatus.COMPLETED


# ============================================================================
# Enums Tests
# ============================================================================

class TestEnums:
    """Tests for ImageStyle and GenerationStatus enums."""

    def test_image_styles(self):
        """Test all image styles exist."""
        assert ImageStyle.CELEBRATION.value == "celebration"
        assert ImageStyle.ACHIEVEMENT.value == "achievement"
        assert ImageStyle.MILESTONE.value == "milestone"
        assert ImageStyle.SCHOLARSHIP.value == "scholarship"
        assert ImageStyle.DEADLINE.value == "deadline"
        assert ImageStyle.MOTIVATIONAL.value == "motivational"
        assert ImageStyle.COMPARISON.value == "comparison"

    def test_generation_status(self):
        """Test all generation statuses exist."""
        assert GenerationStatus.PENDING.value == "pending"
        assert GenerationStatus.GENERATING.value == "generating"
        assert GenerationStatus.COMPLETED.value == "completed"
        assert GenerationStatus.FAILED.value == "failed"


# ============================================================================
# Templates Tests
# ============================================================================

class TestTemplates:
    """Tests for win card templates."""

    def test_all_templates_exist(self):
        """Test all expected templates exist."""
        expected = [
            "scholarship_won",
            "application_submitted",
            "fafsa_completed",
            "deadline_met",
            "aid_package_received",
            "appeal_success",
            "milestone_reached",
        ]

        for template_name in expected:
            assert template_name in WIN_CARD_TEMPLATES

    def test_template_structure(self):
        """Test all templates have required fields."""
        for name, template in WIN_CARD_TEMPLATES.items():
            assert "title_template" in template, f"Missing title_template in {name}"
            assert "message_template" in template, f"Missing message_template in {name}"
            assert "style" in template, f"Missing style in {name}"
            assert isinstance(template["style"], ImageStyle)

    def test_style_prompts_exist(self):
        """Test style prompts exist for all styles."""
        for style in ImageStyle:
            assert style in STYLE_PROMPTS, f"Missing prompt for {style}"
            assert isinstance(STYLE_PROMPTS[style], str)
            assert len(STYLE_PROMPTS[style]) > 0


# ============================================================================
# Convenience Functions Tests
# ============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_create_scholarship_win_card(self):
        """Test create_scholarship_win_card convenience function."""
        client = NanobananaClient(api_key="test-key")

        card = await create_scholarship_win_card(
            client=client,
            student_id="student123",
            scholarship_name="Gates Scholarship",
            amount="$20,000"
        )

        assert card.title == "Scholarship Won!"
        assert "Gates Scholarship" in card.message
        assert "$20,000" in card.message
        assert card.status == GenerationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_create_fafsa_complete_card(self):
        """Test create_fafsa_complete_card convenience function."""
        client = NanobananaClient(api_key="test-key")

        card = await create_fafsa_complete_card(
            client=client,
            student_id="student123"
        )

        assert card.title == "FAFSA Complete!"
        assert card.style == ImageStyle.ACHIEVEMENT
        assert card.status == GenerationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_create_deadline_met_card(self):
        """Test create_deadline_met_card convenience function."""
        client = NanobananaClient(api_key="test-key")

        card = await create_deadline_met_card(
            client=client,
            student_id="student123",
            deadline_name="Regular Decision"
        )

        assert card.title == "Deadline Met!"
        assert "Regular Decision" in card.message
        assert card.style == ImageStyle.MILESTONE

    @pytest.mark.asyncio
    async def test_create_appeal_success_card(self):
        """Test create_appeal_success_card convenience function."""
        client = NanobananaClient(api_key="test-key")

        card = await create_appeal_success_card(
            client=client,
            student_id="student123",
            school_name="Harvard",
            increase="$10,000"
        )

        assert card.title == "Appeal Successful!"
        assert "Harvard" in card.message
        assert "$10,000" in card.message
        assert card.style == ImageStyle.CELEBRATION


# ============================================================================
# GenerationRequest Tests
# ============================================================================

class TestGenerationRequest:
    """Tests for GenerationRequest dataclass."""

    def test_request_creation_defaults(self):
        """Test GenerationRequest with defaults."""
        request = GenerationRequest(
            id="req123",
            prompt="Generate a celebration image",
            style=ImageStyle.CELEBRATION,
        )

        assert request.id == "req123"
        assert request.prompt == "Generate a celebration image"
        assert request.style == ImageStyle.CELEBRATION
        assert request.width == 1024
        assert request.height == 1024
        assert request.student_id is None
        assert isinstance(request.created_at, datetime)

    def test_request_creation_custom(self):
        """Test GenerationRequest with custom values."""
        request = GenerationRequest(
            id="req456",
            prompt="Test prompt",
            style=ImageStyle.MILESTONE,
            width=512,
            height=512,
            student_id="student123",
        )

        assert request.width == 512
        assert request.height == 512
        assert request.student_id == "student123"


# ============================================================================
# GenerationResult Tests
# ============================================================================

class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_result_creation_success(self):
        """Test GenerationResult for success."""
        result = GenerationResult(
            request_id="req123",
            status=GenerationStatus.COMPLETED,
            image_url="https://example.com/image.png",
            thumbnail_url="https://example.com/thumb.png",
            generation_time_ms=150.5,
        )

        assert result.request_id == "req123"
        assert result.status == GenerationStatus.COMPLETED
        assert result.image_url == "https://example.com/image.png"
        assert result.thumbnail_url == "https://example.com/thumb.png"
        assert result.generation_time_ms == 150.5
        assert result.error is None

    def test_result_creation_failure(self):
        """Test GenerationResult for failure."""
        result = GenerationResult(
            request_id="req456",
            status=GenerationStatus.FAILED,
            error="API rate limit exceeded",
        )

        assert result.status == GenerationStatus.FAILED
        assert result.image_url is None
        assert result.error == "API rate limit exceeded"


# ============================================================================
# Module Exports Tests
# ============================================================================

class TestModuleExports:
    """Tests for module exports."""

    def test_integration_exports(self):
        """Test integrations module exports expected items."""
        from integrations import __all__

        # Nanobanana exports
        assert 'NanobananaClient' in __all__
        assert 'WinCard' in __all__
        assert 'ImageStyle' in __all__

        # Stripe exports
        assert 'StripePaymentsClient' in __all__
        assert 'Subscription' in __all__
        assert 'SubscriptionTier' in __all__
        assert 'SubscriptionStatus' in __all__
        assert 'Payment' in __all__
        assert 'PaymentStatus' in __all__
        assert 'Referral' in __all__
        assert 'TIER_PRICING' in __all__


# ============================================================================
# Stripe Payments Client Tests - Story 6.x
# ============================================================================

class TestStripePaymentsClient:
    """Tests for StripePaymentsClient."""

    def test_client_initialization_default(self):
        """Test client initializes with defaults."""
        client = StripePaymentsClient()

        assert client.api_key is None
        assert client.webhook_secret is None
        assert client._subscriptions == {}
        assert client._payments == {}
        assert client._referrals == {}

    def test_client_initialization_custom(self):
        """Test client initializes with custom values."""
        client = StripePaymentsClient(
            api_key="sk_test_123",
            webhook_secret="whsec_123"
        )

        assert client.api_key == "sk_test_123"
        assert client.webhook_secret == "whsec_123"

    @pytest.mark.asyncio
    async def test_create_subscription_free(self):
        """Test creating a free subscription."""
        client = StripePaymentsClient(api_key="sk_test_123")

        subscription = await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.FREE,
        )

        assert subscription.student_id == "student123"
        assert subscription.tier == SubscriptionTier.FREE
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.is_active is True
        assert subscription.stripe_subscription_id is not None

    @pytest.mark.asyncio
    async def test_create_subscription_with_trial(self):
        """Test creating subscription with trial period."""
        client = StripePaymentsClient(api_key="sk_test_123")

        subscription = await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.PREMIUM,
            trial_days=14,
        )

        assert subscription.tier == SubscriptionTier.PREMIUM
        assert subscription.status == SubscriptionStatus.TRIALING
        assert subscription.trial_ends_at is not None
        assert subscription.is_active is True

    @pytest.mark.asyncio
    async def test_create_subscription_duplicate_fails(self):
        """Test creating duplicate subscription fails."""
        client = StripePaymentsClient(api_key="sk_test_123")

        await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.BASIC,
        )

        with pytest.raises(ValueError, match="already has an active subscription"):
            await client.create_subscription(
                student_id="student123",
                tier=SubscriptionTier.PREMIUM,
            )

    @pytest.mark.asyncio
    async def test_get_subscription(self):
        """Test getting a subscription."""
        client = StripePaymentsClient(api_key="sk_test_123")

        await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.BASIC,
        )

        subscription = await client.get_subscription("student123")

        assert subscription is not None
        assert subscription.tier == SubscriptionTier.BASIC

    @pytest.mark.asyncio
    async def test_get_subscription_not_found(self):
        """Test getting non-existent subscription."""
        client = StripePaymentsClient(api_key="sk_test_123")

        subscription = await client.get_subscription("nonexistent")

        assert subscription is None

    @pytest.mark.asyncio
    async def test_upgrade_subscription(self):
        """Test upgrading a subscription."""
        client = StripePaymentsClient(api_key="sk_test_123")

        await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.BASIC,
        )

        upgraded = await client.upgrade_subscription(
            student_id="student123",
            new_tier=SubscriptionTier.PREMIUM,
        )

        assert upgraded.tier == SubscriptionTier.PREMIUM
        assert upgraded.metadata.get("previous_tier") == "basic"

    @pytest.mark.asyncio
    async def test_upgrade_same_tier_fails(self):
        """Test upgrading to same or lower tier fails."""
        client = StripePaymentsClient(api_key="sk_test_123")

        await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.PREMIUM,
        )

        with pytest.raises(ValueError, match="Cannot upgrade"):
            await client.upgrade_subscription(
                student_id="student123",
                new_tier=SubscriptionTier.BASIC,
            )

    @pytest.mark.asyncio
    async def test_downgrade_subscription(self):
        """Test downgrading a subscription."""
        client = StripePaymentsClient(api_key="sk_test_123")

        await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.PREMIUM,
        )

        downgraded = await client.downgrade_subscription(
            student_id="student123",
            new_tier=SubscriptionTier.BASIC,
            at_period_end=False,
        )

        assert downgraded.tier == SubscriptionTier.BASIC
        assert downgraded.metadata.get("previous_tier") == "premium"

    @pytest.mark.asyncio
    async def test_downgrade_at_period_end(self):
        """Test scheduling downgrade at period end."""
        client = StripePaymentsClient(api_key="sk_test_123")

        await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.PREMIUM,
        )

        downgraded = await client.downgrade_subscription(
            student_id="student123",
            new_tier=SubscriptionTier.BASIC,
            at_period_end=True,
        )

        # Tier not changed yet
        assert downgraded.tier == SubscriptionTier.PREMIUM
        assert downgraded.metadata.get("scheduled_tier") == "basic"

    @pytest.mark.asyncio
    async def test_cancel_subscription(self):
        """Test canceling a subscription."""
        client = StripePaymentsClient(api_key="sk_test_123")

        await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.BASIC,
        )

        canceled = await client.cancel_subscription(
            student_id="student123",
            at_period_end=True,
            reason="Testing",
        )

        assert canceled.cancel_at_period_end is True
        assert canceled.metadata.get("cancel_reason") == "Testing"

    @pytest.mark.asyncio
    async def test_cancel_immediately(self):
        """Test immediate cancellation."""
        client = StripePaymentsClient(api_key="sk_test_123")

        await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.BASIC,
        )

        canceled = await client.cancel_subscription(
            student_id="student123",
            at_period_end=False,
        )

        assert canceled.status == SubscriptionStatus.CANCELED
        assert canceled.is_active is False

    @pytest.mark.asyncio
    async def test_reactivate_subscription(self):
        """Test reactivating a canceled subscription."""
        client = StripePaymentsClient(api_key="sk_test_123")

        await client.create_subscription(
            student_id="student123",
            tier=SubscriptionTier.BASIC,
        )

        await client.cancel_subscription(
            student_id="student123",
            at_period_end=False,
        )

        reactivated = await client.reactivate_subscription("student123")

        assert reactivated.status == SubscriptionStatus.ACTIVE
        assert reactivated.is_active is True


class TestPaymentProcessing:
    """Tests for payment processing."""

    @pytest.mark.asyncio
    async def test_process_payment(self):
        """Test processing a payment."""
        client = StripePaymentsClient(api_key="sk_test_123")

        payment = await client.process_payment(
            student_id="student123",
            amount=1999,  # $19.99
            description="Premium upgrade",
        )

        assert payment.student_id == "student123"
        assert payment.amount == 1999
        assert payment.status == PaymentStatus.SUCCEEDED
        assert payment.stripe_payment_intent_id is not None
        assert payment.completed_at is not None

    @pytest.mark.asyncio
    async def test_refund_payment(self):
        """Test refunding a payment."""
        client = StripePaymentsClient(api_key="sk_test_123")

        payment = await client.process_payment(
            student_id="student123",
            amount=1999,
            description="Test payment",
        )

        refunded = await client.refund_payment(
            payment_id=payment.id,
            reason="Customer request",
        )

        assert refunded.status == PaymentStatus.REFUNDED
        assert refunded.refunded_at is not None
        assert refunded.metadata.get("refund_reason") == "Customer request"

    @pytest.mark.asyncio
    async def test_partial_refund(self):
        """Test partial refund."""
        client = StripePaymentsClient(api_key="sk_test_123")

        payment = await client.process_payment(
            student_id="student123",
            amount=2000,
            description="Test payment",
        )

        refunded = await client.refund_payment(
            payment_id=payment.id,
            amount=1000,  # Partial refund
        )

        assert refunded.metadata.get("refund_amount") == 1000


class TestReferrals:
    """Tests for referral system."""

    @pytest.mark.asyncio
    async def test_create_referral_code(self):
        """Test creating a referral code."""
        client = StripePaymentsClient(api_key="sk_test_123")

        code = await client.create_referral_code("student123")

        assert code is not None
        assert len(code) >= 8
        assert "STUD" in code  # First 4 chars of student_id uppercased

    @pytest.mark.asyncio
    async def test_get_referral_code(self):
        """Test getting a student's referral code."""
        client = StripePaymentsClient(api_key="sk_test_123")

        created = await client.create_referral_code("student123")
        retrieved = await client.get_referral_code("student123")

        assert retrieved == created

    @pytest.mark.asyncio
    async def test_referral_processed_on_signup(self):
        """Test referral is processed when new student signs up."""
        client = StripePaymentsClient(api_key="sk_test_123")

        # Create referral code for existing student
        code = await client.create_referral_code("referrer123")

        # New student signs up with referral code
        await client.create_subscription(
            student_id="newstudent456",
            tier=SubscriptionTier.BASIC,
            referral_code=code,
        )

        # Check referral stats
        stats = await client.get_referral_stats("referrer123")

        assert stats["total_referrals"] >= 1
        assert stats["converted_referrals"] >= 1

    @pytest.mark.asyncio
    async def test_referral_stats_empty(self):
        """Test referral stats for student with no referrals."""
        client = StripePaymentsClient(api_key="sk_test_123")

        stats = await client.get_referral_stats("nostudent")

        assert stats["total_referrals"] == 0
        assert stats["converted_referrals"] == 0


class TestWebhooks:
    """Tests for webhook handling."""

    @pytest.mark.asyncio
    async def test_handle_payment_succeeded(self):
        """Test handling payment succeeded webhook."""
        client = StripePaymentsClient(api_key="sk_test_123")

        result = await client.handle_webhook(
            event_type="payment_intent.succeeded",
            event_data={"id": "pi_test123", "amount": 1999},
        )

        assert result["handled"] is True

    @pytest.mark.asyncio
    async def test_handle_subscription_created(self):
        """Test handling subscription created webhook."""
        client = StripePaymentsClient(api_key="sk_test_123")

        result = await client.handle_webhook(
            event_type="customer.subscription.created",
            event_data={"id": "sub_test123", "customer": "cus_test123"},
        )

        assert result["handled"] is True
        assert result["subscription_id"] == "sub_test123"

    @pytest.mark.asyncio
    async def test_handle_unknown_event(self):
        """Test handling unknown webhook event."""
        client = StripePaymentsClient(api_key="sk_test_123")

        result = await client.handle_webhook(
            event_type="unknown.event.type",
            event_data={},
        )

        assert result["handled"] is False

    def test_verify_webhook_no_secret(self):
        """Test webhook verification fails without secret."""
        client = StripePaymentsClient(api_key="sk_test_123")

        # Run coroutine synchronously
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(
            client.verify_webhook(b"payload", "sig")
        )
        loop.close()

        assert result is False


class TestSubscriptionModel:
    """Tests for Subscription dataclass."""

    def test_subscription_creation(self):
        """Test Subscription creation with defaults."""
        sub = Subscription(
            id="sub123",
            student_id="student456",
            tier=SubscriptionTier.BASIC,
            status=SubscriptionStatus.ACTIVE,
        )

        assert sub.id == "sub123"
        assert sub.student_id == "student456"
        assert sub.tier == SubscriptionTier.BASIC
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.is_active is True
        assert sub.current_period_start is not None
        assert sub.current_period_end is not None

    def test_subscription_is_active(self):
        """Test is_active property."""
        active = Subscription(
            id="sub1", student_id="s1",
            tier=SubscriptionTier.BASIC,
            status=SubscriptionStatus.ACTIVE
        )
        trialing = Subscription(
            id="sub2", student_id="s2",
            tier=SubscriptionTier.BASIC,
            status=SubscriptionStatus.TRIALING
        )
        canceled = Subscription(
            id="sub3", student_id="s3",
            tier=SubscriptionTier.BASIC,
            status=SubscriptionStatus.CANCELED
        )

        assert active.is_active is True
        assert trialing.is_active is True
        assert canceled.is_active is False

    def test_subscription_days_until_renewal(self):
        """Test days_until_renewal calculation."""
        sub = Subscription(
            id="sub123",
            student_id="student456",
            tier=SubscriptionTier.BASIC,
            status=SubscriptionStatus.ACTIVE,
            current_period_end=datetime.utcnow() + timedelta(days=15),
        )

        assert 14 <= sub.days_until_renewal <= 16

    def test_subscription_check_limit(self):
        """Test checking feature limits."""
        sub = Subscription(
            id="sub123",
            student_id="student456",
            tier=SubscriptionTier.BASIC,
            status=SubscriptionStatus.ACTIVE,
        )

        # Basic tier has unlimited scholarship searches (-1)
        assert sub.check_limit("scholarship_searches") == -1
        # Basic tier has 10 comparisons per month
        assert sub.check_limit("comparisons_per_month") == 10


class TestPaymentModel:
    """Tests for Payment dataclass."""

    def test_payment_creation(self):
        """Test Payment creation."""
        payment = Payment(
            id="pay123",
            student_id="student456",
            amount=1999,
            description="Test payment",
        )

        assert payment.id == "pay123"
        assert payment.amount == 1999
        assert payment.currency == "usd"
        assert payment.status == PaymentStatus.PENDING


class TestReferralModel:
    """Tests for Referral dataclass."""

    def test_referral_creation(self):
        """Test Referral creation."""
        referral = Referral(
            id="ref123",
            referrer_id="referrer456",
            referred_id="referred789",
            referral_code="CODE123",
        )

        assert referral.id == "ref123"
        assert referral.referrer_id == "referrer456"
        assert referral.status == "pending"
        assert referral.reward_paid is False


class TestTierPricing:
    """Tests for tier pricing configuration."""

    def test_all_tiers_have_pricing(self):
        """Test all subscription tiers have pricing."""
        for tier in SubscriptionTier:
            assert tier in TIER_PRICING

    def test_pricing_structure(self):
        """Test pricing structure is correct."""
        for tier, pricing in TIER_PRICING.items():
            assert "monthly_price" in pricing
            assert "annual_price" in pricing
            assert "features" in pricing
            assert "limits" in pricing
            assert isinstance(pricing["features"], list)
            assert isinstance(pricing["limits"], dict)

    def test_free_tier_is_free(self):
        """Test free tier has zero price."""
        free = TIER_PRICING[SubscriptionTier.FREE]
        assert free["monthly_price"] == 0
        assert free["annual_price"] == 0

    def test_annual_savings(self):
        """Test annual pricing provides savings."""
        for tier in [SubscriptionTier.BASIC, SubscriptionTier.PREMIUM, SubscriptionTier.FAMILY]:
            pricing = TIER_PRICING[tier]
            monthly = pricing["monthly_price"] * 12
            annual = pricing["annual_price"]
            # Annual should be cheaper than 12 months
            assert annual < monthly


class TestConvenienceFunctionsStripe:
    """Tests for Stripe convenience functions."""

    @pytest.mark.asyncio
    async def test_create_free_subscription(self):
        """Test create_free_subscription convenience function."""
        client = StripePaymentsClient(api_key="sk_test_123")

        sub = await create_free_subscription(client, "student123")

        assert sub.tier == SubscriptionTier.FREE
        assert sub.is_active is True

    @pytest.mark.asyncio
    async def test_create_premium_trial(self):
        """Test create_premium_trial convenience function."""
        client = StripePaymentsClient(api_key="sk_test_123")

        sub = await create_premium_trial(
            client, "student123",
            trial_days=7,
        )

        assert sub.tier == SubscriptionTier.PREMIUM
        assert sub.status == SubscriptionStatus.TRIALING

    def test_get_tier_features(self):
        """Test get_tier_features function."""
        features = get_tier_features(SubscriptionTier.PREMIUM)

        assert isinstance(features, list)
        assert len(features) > 0

    def test_get_tier_price_monthly(self):
        """Test get_tier_price for monthly."""
        price = get_tier_price(SubscriptionTier.BASIC, annual=False)

        assert price == 999  # $9.99

    def test_get_tier_price_annual(self):
        """Test get_tier_price for annual."""
        price = get_tier_price(SubscriptionTier.BASIC, annual=True)

        assert price == 9999  # $99.99


class TestRevenueStats:
    """Tests for revenue statistics."""

    @pytest.mark.asyncio
    async def test_get_revenue_stats(self):
        """Test getting revenue statistics."""
        client = StripePaymentsClient(api_key="sk_test_123")

        # Create some activity
        await client.create_subscription(
            student_id="student1",
            tier=SubscriptionTier.BASIC,
        )
        await client.process_payment(
            student_id="student1",
            amount=999,
            description="Basic subscription",
        )

        stats = client.get_revenue_stats()

        assert "total_revenue_cents" in stats
        assert "total_revenue_dollars" in stats
        assert "active_subscriptions" in stats
        assert "subscriptions_by_tier" in stats
        assert stats["total_revenue_cents"] >= 999

    def test_get_stats(self):
        """Test getting client stats."""
        client = StripePaymentsClient(
            api_key="sk_test_123",
            webhook_secret="whsec_123",
        )

        stats = client.get_stats()

        assert stats["api_configured"] is True
        assert stats["webhook_configured"] is True
