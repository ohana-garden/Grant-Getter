"""Tests for Integrations Module - Story 5.1

Tests for Nanobanana image generation service.
"""

import pytest
import asyncio
from datetime import datetime

from integrations import NanobananaClient, WinCard, ImageStyle
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

        assert 'NanobananaClient' in __all__
        assert 'WinCard' in __all__
        assert 'ImageStyle' in __all__
