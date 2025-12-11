"""Nanobanana Integration - Story 5.1

Image generation service for creating celebratory win cards and graphics.
Used when students achieve milestones like scholarships won, applications submitted, etc.
"""

import os
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid
import hashlib

logger = logging.getLogger(__name__)


class ImageStyle(Enum):
    """Available image styles."""
    CELEBRATION = "celebration"  # Confetti, bright colors
    ACHIEVEMENT = "achievement"  # Trophy, medal, badge style
    MILESTONE = "milestone"  # Progress, journey theme
    SCHOLARSHIP = "scholarship"  # Academic, professional
    DEADLINE = "deadline"  # Calendar, clock theme
    MOTIVATIONAL = "motivational"  # Inspiring, uplifting
    COMPARISON = "comparison"  # Side-by-side, chart style


class GenerationStatus(Enum):
    """Status of image generation."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WinCard:
    """A celebratory win card for a student achievement."""
    id: str
    student_id: str
    title: str
    message: str
    style: ImageStyle
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: GenerationStatus = GenerationStatus.PENDING

    # Achievement details
    achievement_type: Optional[str] = None  # "scholarship", "deadline", "application"
    achievement_value: Optional[str] = None  # "$5,000", "FAFSA", etc.
    school_name: Optional[str] = None


@dataclass
class GenerationRequest:
    """A request to generate an image."""
    id: str
    prompt: str
    style: ImageStyle
    width: int = 1024
    height: int = 1024
    student_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GenerationResult:
    """Result of image generation."""
    request_id: str
    status: GenerationStatus
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    generation_time_ms: float = 0.0
    error: Optional[str] = None


# Win card templates by type
WIN_CARD_TEMPLATES = {
    "scholarship_won": {
        "title_template": "Scholarship Won!",
        "message_template": "Congratulations! You've been awarded the {scholarship_name} worth {amount}!",
        "style": ImageStyle.CELEBRATION,
    },
    "application_submitted": {
        "title_template": "Application Submitted!",
        "message_template": "Great job! You've submitted your application to {school_name}.",
        "style": ImageStyle.MILESTONE,
    },
    "fafsa_completed": {
        "title_template": "FAFSA Complete!",
        "message_template": "You've completed your FAFSA application. One step closer to your goals!",
        "style": ImageStyle.ACHIEVEMENT,
    },
    "deadline_met": {
        "title_template": "Deadline Met!",
        "message_template": "You submitted before the {deadline_name} deadline. Stay on track!",
        "style": ImageStyle.MILESTONE,
    },
    "aid_package_received": {
        "title_template": "Aid Package Received!",
        "message_template": "Your financial aid package from {school_name} is ready to review.",
        "style": ImageStyle.SCHOLARSHIP,
    },
    "appeal_success": {
        "title_template": "Appeal Successful!",
        "message_template": "Great news! Your appeal to {school_name} resulted in {increase} more aid!",
        "style": ImageStyle.CELEBRATION,
    },
    "milestone_reached": {
        "title_template": "Milestone Reached!",
        "message_template": "{milestone_description}",
        "style": ImageStyle.MILESTONE,
    },
}


# Style-specific prompts for image generation
STYLE_PROMPTS = {
    ImageStyle.CELEBRATION: "vibrant celebration, confetti, sparkles, bright colors, joyful",
    ImageStyle.ACHIEVEMENT: "golden trophy, medal, achievement badge, success, professional",
    ImageStyle.MILESTONE: "journey path, progress markers, achievement steps, forward motion",
    ImageStyle.SCHOLARSHIP: "academic cap, diploma, books, university campus, scholarly",
    ImageStyle.DEADLINE: "calendar check mark, clock, completion badge, organized",
    ImageStyle.MOTIVATIONAL: "sunrise, path forward, inspiring landscape, hopeful",
    ImageStyle.COMPARISON: "balanced scales, side-by-side comparison, clear charts",
}


class NanobananaClient:
    """Client for Nanobanana image generation service.

    Acceptance Criteria:
    - Ambassador can request win card images
    - Win cards display in web chat
    - Images are cached for reuse
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """Initialize Nanobanana client.

        Args:
            api_key: Nanobanana API key (or from NANOBANANA_API_KEY env var)
            base_url: Base URL for the API
        """
        self.api_key = api_key or os.getenv("NANOBANANA_API_KEY")
        self.base_url = base_url or os.getenv(
            "NANOBANANA_BASE_URL",
            "https://api.nanobanana.ai/v1"
        )

        # Image cache (in production, use Redis or similar)
        self._cache: Dict[str, str] = {}

        # Generation history
        self._history: List[GenerationResult] = []

        # Pending requests
        self._pending: Dict[str, GenerationRequest] = {}

    async def generate_win_card(
        self,
        student_id: str,
        card_type: str,
        context: Dict[str, Any],
    ) -> WinCard:
        """Generate a win card for a student achievement.

        Args:
            student_id: Student ID
            card_type: Type of win card (see WIN_CARD_TEMPLATES)
            context: Context for template rendering

        Returns:
            WinCard object
        """
        template = WIN_CARD_TEMPLATES.get(card_type)
        if not template:
            template = WIN_CARD_TEMPLATES["milestone_reached"]

        # Generate unique ID
        card_id = str(uuid.uuid4())

        # Render title and message
        title = template["title_template"]
        try:
            message = template["message_template"].format(**context)
        except KeyError:
            message = template["message_template"]

        # Create win card
        win_card = WinCard(
            id=card_id,
            student_id=student_id,
            title=title,
            message=message,
            style=template["style"],
            achievement_type=card_type,
            achievement_value=context.get("amount") or context.get("increase"),
            school_name=context.get("school_name"),
        )

        # Generate the image
        result = await self._generate_image(
            prompt=self._build_prompt(win_card),
            style=win_card.style,
            student_id=student_id,
        )

        if result.status == GenerationStatus.COMPLETED:
            win_card.image_url = result.image_url
            win_card.thumbnail_url = result.thumbnail_url
            win_card.status = GenerationStatus.COMPLETED
        else:
            win_card.status = GenerationStatus.FAILED

        logger.info(f"Generated win card {card_id} for student {student_id}")

        return win_card

    def _build_prompt(self, win_card: WinCard) -> str:
        """Build the image generation prompt.

        Args:
            win_card: WinCard to generate image for

        Returns:
            Prompt string
        """
        style_prompt = STYLE_PROMPTS.get(win_card.style, "celebration, achievement")

        prompt_parts = [
            f"Create a celebratory card image for: {win_card.title}",
            f"Style: {style_prompt}",
            "Modern, clean design with text overlay space",
            "Suitable for social media sharing",
        ]

        if win_card.achievement_value:
            prompt_parts.append(f"Highlight: {win_card.achievement_value}")

        if win_card.school_name:
            prompt_parts.append(f"Theme: {win_card.school_name}")

        return ". ".join(prompt_parts)

    async def _generate_image(
        self,
        prompt: str,
        style: ImageStyle,
        student_id: Optional[str] = None,
    ) -> GenerationResult:
        """Generate an image from a prompt.

        Args:
            prompt: Generation prompt
            style: Image style
            student_id: Optional student ID for caching

        Returns:
            GenerationResult
        """
        request_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        # Check cache
        cache_key = self._get_cache_key(prompt, style)
        if cache_key in self._cache:
            return GenerationResult(
                request_id=request_id,
                status=GenerationStatus.COMPLETED,
                image_url=self._cache[cache_key],
                generation_time_ms=0,
            )

        # Create request
        request = GenerationRequest(
            id=request_id,
            prompt=prompt,
            style=style,
            student_id=student_id,
        )
        self._pending[request_id] = request

        try:
            # In production, this would call the actual Nanobanana API
            # For now, generate a placeholder URL
            image_url = await self._call_api(request)

            # Calculate generation time
            end_time = datetime.utcnow()
            generation_time = (end_time - start_time).total_seconds() * 1000

            # Cache the result
            self._cache[cache_key] = image_url

            result = GenerationResult(
                request_id=request_id,
                status=GenerationStatus.COMPLETED,
                image_url=image_url,
                thumbnail_url=image_url.replace("/full/", "/thumb/") if "/full/" in image_url else image_url,
                generation_time_ms=generation_time,
            )

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            result = GenerationResult(
                request_id=request_id,
                status=GenerationStatus.FAILED,
                error=str(e),
            )

        # Clean up pending
        self._pending.pop(request_id, None)

        # Store in history
        self._history.append(result)
        if len(self._history) > 100:
            self._history = self._history[-100:]

        return result

    async def _call_api(self, request: GenerationRequest) -> str:
        """Call the Nanobanana API.

        Args:
            request: Generation request

        Returns:
            Generated image URL
        """
        # In production, this would:
        # 1. POST to self.base_url + "/generate"
        # 2. Wait for generation to complete
        # 3. Return the image URL

        # For now, simulate with a placeholder URL
        # The URL includes a hash of the prompt for uniqueness
        prompt_hash = hashlib.md5(request.prompt.encode()).hexdigest()[:8]

        # Simulate generation delay
        await asyncio.sleep(0.1)

        return f"https://images.nanobanana.ai/full/{request.id}_{prompt_hash}.png"

    def _get_cache_key(self, prompt: str, style: ImageStyle) -> str:
        """Generate a cache key for prompt + style combination."""
        combined = f"{prompt}:{style.value}"
        return hashlib.sha256(combined.encode()).hexdigest()

    async def generate_comparison_card(
        self,
        student_id: str,
        schools: List[Dict[str, Any]],
    ) -> WinCard:
        """Generate a comparison card for multiple school offers.

        Args:
            student_id: Student ID
            schools: List of school offer data

        Returns:
            WinCard with comparison image
        """
        card_id = str(uuid.uuid4())

        # Build comparison message
        if len(schools) == 2:
            message = f"Comparing offers from {schools[0].get('name', 'School A')} and {schools[1].get('name', 'School B')}"
        else:
            school_names = [s.get('name', f'School {i+1}') for i, s in enumerate(schools[:4])]
            message = f"Comparing offers from {', '.join(school_names)}"

        win_card = WinCard(
            id=card_id,
            student_id=student_id,
            title="Aid Package Comparison",
            message=message,
            style=ImageStyle.COMPARISON,
            achievement_type="comparison",
            metadata={'schools': schools},
        )

        # Generate comparison image
        prompt = f"Create a clean comparison infographic for {len(schools)} college financial aid packages. Modern design with clear data visualization."

        result = await self._generate_image(
            prompt=prompt,
            style=ImageStyle.COMPARISON,
            student_id=student_id,
        )

        if result.status == GenerationStatus.COMPLETED:
            win_card.image_url = result.image_url
            win_card.thumbnail_url = result.thumbnail_url
            win_card.status = GenerationStatus.COMPLETED
        else:
            win_card.status = GenerationStatus.FAILED

        return win_card

    async def generate_motivational_image(
        self,
        student_id: str,
        message: str,
    ) -> WinCard:
        """Generate a motivational image.

        Args:
            student_id: Student ID
            message: Motivational message

        Returns:
            WinCard with motivational image
        """
        card_id = str(uuid.uuid4())

        win_card = WinCard(
            id=card_id,
            student_id=student_id,
            title="Keep Going!",
            message=message,
            style=ImageStyle.MOTIVATIONAL,
            achievement_type="motivation",
        )

        prompt = f"Create an inspiring motivational image. Message: {message}. Uplifting, hopeful, encouraging."

        result = await self._generate_image(
            prompt=prompt,
            style=ImageStyle.MOTIVATIONAL,
            student_id=student_id,
        )

        if result.status == GenerationStatus.COMPLETED:
            win_card.image_url = result.image_url
            win_card.thumbnail_url = result.thumbnail_url
            win_card.status = GenerationStatus.COMPLETED
        else:
            win_card.status = GenerationStatus.FAILED

        return win_card

    def get_card(self, card_id: str) -> Optional[WinCard]:
        """Get a generated win card by ID.

        Args:
            card_id: Card ID

        Returns:
            WinCard or None
        """
        # In production, retrieve from storage
        # For now, check history
        for result in self._history:
            if result.request_id == card_id:
                # Reconstruct basic card from result
                return WinCard(
                    id=card_id,
                    student_id="",
                    title="",
                    message="",
                    style=ImageStyle.CELEBRATION,
                    image_url=result.image_url,
                    status=result.status,
                )
        return None

    def clear_cache(self):
        """Clear the image cache."""
        self._cache.clear()
        logger.info("Image cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache stats dict
        """
        return {
            "cached_images": len(self._cache),
            "total_generated": len(self._history),
            "successful": sum(1 for r in self._history if r.status == GenerationStatus.COMPLETED),
            "failed": sum(1 for r in self._history if r.status == GenerationStatus.FAILED),
            "pending": len(self._pending),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.

        Returns:
            Stats dict
        """
        avg_time = 0.0
        successful = [r for r in self._history if r.status == GenerationStatus.COMPLETED]
        if successful:
            avg_time = sum(r.generation_time_ms for r in successful) / len(successful)

        return {
            "api_configured": bool(self.api_key),
            "base_url": self.base_url,
            "total_requests": len(self._history),
            "successful_requests": len(successful),
            "failed_requests": len(self._history) - len(successful),
            "cached_images": len(self._cache),
            "average_generation_time_ms": round(avg_time, 2),
        }


# Convenience functions for common win card types
async def create_scholarship_win_card(
    client: NanobananaClient,
    student_id: str,
    scholarship_name: str,
    amount: str,
) -> WinCard:
    """Create a win card for scholarship award.

    Args:
        client: NanobananaClient instance
        student_id: Student ID
        scholarship_name: Name of scholarship
        amount: Award amount (e.g., "$5,000")

    Returns:
        WinCard
    """
    return await client.generate_win_card(
        student_id=student_id,
        card_type="scholarship_won",
        context={
            "scholarship_name": scholarship_name,
            "amount": amount,
        },
    )


async def create_fafsa_complete_card(
    client: NanobananaClient,
    student_id: str,
) -> WinCard:
    """Create a win card for FAFSA completion.

    Args:
        client: NanobananaClient instance
        student_id: Student ID

    Returns:
        WinCard
    """
    return await client.generate_win_card(
        student_id=student_id,
        card_type="fafsa_completed",
        context={},
    )


async def create_deadline_met_card(
    client: NanobananaClient,
    student_id: str,
    deadline_name: str,
) -> WinCard:
    """Create a win card for meeting a deadline.

    Args:
        client: NanobananaClient instance
        student_id: Student ID
        deadline_name: Name of deadline met

    Returns:
        WinCard
    """
    return await client.generate_win_card(
        student_id=student_id,
        card_type="deadline_met",
        context={"deadline_name": deadline_name},
    )


async def create_appeal_success_card(
    client: NanobananaClient,
    student_id: str,
    school_name: str,
    increase: str,
) -> WinCard:
    """Create a win card for successful appeal.

    Args:
        client: NanobananaClient instance
        student_id: Student ID
        school_name: Name of school
        increase: Aid increase amount

    Returns:
        WinCard
    """
    return await client.generate_win_card(
        student_id=student_id,
        card_type="appeal_success",
        context={
            "school_name": school_name,
            "increase": increase,
        },
    )
