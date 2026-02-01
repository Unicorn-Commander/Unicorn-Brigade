"""
Content Generator Agent

A comprehensive content generation agent for creating various types of content:
- Blog posts (with SEO optimization)
- Social media content (Twitter/X, LinkedIn, Instagram)
- Marketing copy (product descriptions, ad copy, email campaigns)
- Content repurposing (transform content between formats)
- A/B variant generation for testing
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import logging
import re

from app.agents.base import BaseAgent
from app.llm.ops_center_client import OpsCenterLLMClient

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    """Types of content that can be generated"""
    BLOG_POST = "blog_post"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    PRODUCT_DESCRIPTION = "product_description"
    AD_COPY = "ad_copy"
    EMAIL_CAMPAIGN = "email_campaign"
    NEWSLETTER = "newsletter"
    PRESS_RELEASE = "press_release"
    LANDING_PAGE = "landing_page"


class ContentTone(str, Enum):
    """Available content tones/styles"""
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    HUMOROUS = "humorous"
    FORMAL = "formal"
    FRIENDLY = "friendly"
    AUTHORITATIVE = "authoritative"
    INSPIRATIONAL = "inspirational"
    EDUCATIONAL = "educational"
    CONVERSATIONAL = "conversational"
    URGENT = "urgent"


class OutputFormat(str, Enum):
    """Output format options"""
    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN_TEXT = "plain_text"
    JSON = "json"


@dataclass
class SEOMetadata:
    """SEO metadata for content"""
    title: str = ""
    meta_description: str = ""
    keywords: List[str] = field(default_factory=list)
    focus_keyword: str = ""
    slug: str = ""
    reading_time_minutes: int = 0
    word_count: int = 0


@dataclass
class ContentResult:
    """Result of content generation"""
    content: str
    content_type: ContentType
    format: OutputFormat
    tone: ContentTone
    seo_metadata: Optional[SEOMetadata] = None
    hashtags: List[str] = field(default_factory=list)
    variants: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    tokens_used: Dict[str, int] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "content": self.content,
            "content_type": self.content_type.value if isinstance(self.content_type, ContentType) else self.content_type,
            "format": self.format.value if isinstance(self.format, OutputFormat) else self.format,
            "tone": self.tone.value if isinstance(self.tone, ContentTone) else self.tone,
            "seo_metadata": {
                "title": self.seo_metadata.title,
                "meta_description": self.seo_metadata.meta_description,
                "keywords": self.seo_metadata.keywords,
                "focus_keyword": self.seo_metadata.focus_keyword,
                "slug": self.seo_metadata.slug,
                "reading_time_minutes": self.seo_metadata.reading_time_minutes,
                "word_count": self.seo_metadata.word_count,
            } if self.seo_metadata else None,
            "hashtags": self.hashtags,
            "variants": self.variants,
            "suggestions": self.suggestions,
            "tokens_used": self.tokens_used,
            "generated_at": self.generated_at,
        }


@dataclass
class CalendarEntry:
    """Content calendar entry"""
    date: str
    content_type: ContentType
    topic: str
    description: str
    platform: str
    status: str = "planned"
    hashtags: List[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "date": self.date,
            "content_type": self.content_type.value if isinstance(self.content_type, ContentType) else self.content_type,
            "topic": self.topic,
            "description": self.description,
            "platform": self.platform,
            "status": self.status,
            "hashtags": self.hashtags,
            "notes": self.notes,
        }


# Content templates
CONTENT_TEMPLATES = {
    "blog_post": {
        "name": "Blog Post",
        "description": "SEO-optimized blog article with introduction, body sections, and conclusion",
        "required_fields": ["topic", "target_audience"],
        "optional_fields": ["keywords", "word_count", "include_cta"],
        "platforms": ["website", "medium", "substack"],
    },
    "twitter_thread": {
        "name": "Twitter/X Thread",
        "description": "Engaging Twitter thread with hooks and calls-to-action",
        "required_fields": ["topic"],
        "optional_fields": ["thread_length", "include_poll"],
        "platforms": ["twitter", "x"],
        "character_limit": 280,
    },
    "linkedin_post": {
        "name": "LinkedIn Post",
        "description": "Professional LinkedIn post with storytelling elements",
        "required_fields": ["topic"],
        "optional_fields": ["include_hook", "professional_angle"],
        "platforms": ["linkedin"],
        "character_limit": 3000,
    },
    "instagram_caption": {
        "name": "Instagram Caption",
        "description": "Engaging Instagram caption with emoji and hashtags",
        "required_fields": ["topic", "image_context"],
        "optional_fields": ["include_cta", "hashtag_count"],
        "platforms": ["instagram"],
        "character_limit": 2200,
    },
    "product_description": {
        "name": "Product Description",
        "description": "Compelling product description with features and benefits",
        "required_fields": ["product_name", "features"],
        "optional_fields": ["target_audience", "price_point"],
        "platforms": ["ecommerce", "amazon", "shopify"],
    },
    "ad_copy": {
        "name": "Ad Copy",
        "description": "High-converting ad copy for various platforms",
        "required_fields": ["product_service", "target_audience"],
        "optional_fields": ["platform", "ad_type", "budget_range"],
        "platforms": ["google_ads", "facebook_ads", "linkedin_ads"],
    },
    "email_campaign": {
        "name": "Email Campaign",
        "description": "Email sequence with subject lines and body content",
        "required_fields": ["campaign_goal", "target_audience"],
        "optional_fields": ["email_count", "include_personalization"],
        "platforms": ["email"],
    },
    "newsletter": {
        "name": "Newsletter",
        "description": "Engaging newsletter with sections and highlights",
        "required_fields": ["topic", "highlights"],
        "optional_fields": ["sections", "frequency"],
        "platforms": ["email"],
    },
    "press_release": {
        "name": "Press Release",
        "description": "Professional press release following AP style",
        "required_fields": ["announcement", "company_info"],
        "optional_fields": ["quotes", "contact_info"],
        "platforms": ["pr_distribution"],
    },
}


class ContentGeneratorAgent(BaseAgent):
    """
    Agent for generating various types of content with customizable
    tone, style, and format options.
    """

    def __init__(
        self,
        memory_manager=None,
        llm_client: Optional[OpsCenterLLMClient] = None,
        default_tone: ContentTone = ContentTone.PROFESSIONAL,
        default_format: OutputFormat = OutputFormat.MARKDOWN,
    ):
        super().__init__("ContentGeneratorAgent", memory_manager)
        self.llm_client = llm_client or OpsCenterLLMClient()
        self.default_tone = default_tone
        self.default_format = default_format
        logger.info("ContentGeneratorAgent initialized")

    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a content generation task"""
        task_type = task.get("type", "blog_post")

        if task_type == "blog_post":
            return await self.generate_blog_post(
                topic=task.get("topic", ""),
                keywords=task.get("keywords", []),
                target_audience=task.get("target_audience", ""),
                word_count=task.get("word_count", 1500),
                tone=ContentTone(task.get("tone", self.default_tone)),
                output_format=OutputFormat(task.get("format", self.default_format)),
                user_id=task.get("user_id"),
            )
        elif task_type == "social_media":
            return await self.generate_social_content(
                platform=task.get("platform", "twitter"),
                topic=task.get("topic", ""),
                context=task.get("context", {}),
                tone=ContentTone(task.get("tone", self.default_tone)),
                user_id=task.get("user_id"),
            )
        elif task_type == "marketing":
            return await self.generate_marketing_copy(
                copy_type=task.get("copy_type", "product_description"),
                product_info=task.get("product_info", {}),
                target_audience=task.get("target_audience", ""),
                tone=ContentTone(task.get("tone", self.default_tone)),
                user_id=task.get("user_id"),
            )
        elif task_type == "repurpose":
            return await self.repurpose_content(
                source_content=task.get("source_content", ""),
                source_type=ContentType(task.get("source_type", ContentType.BLOG_POST)),
                target_types=task.get("target_types", [ContentType.TWITTER]),
                tone=ContentTone(task.get("tone", self.default_tone)),
                user_id=task.get("user_id"),
            )
        elif task_type == "variants":
            return await self.generate_variants(
                base_content=task.get("base_content", ""),
                content_type=ContentType(task.get("content_type", ContentType.AD_COPY)),
                variant_count=task.get("variant_count", 3),
                user_id=task.get("user_id"),
            )
        else:
            return {
                "status": "error",
                "error": f"Unknown task type: {task_type}",
            }

    async def generate_blog_post(
        self,
        topic: str,
        keywords: List[str] = None,
        target_audience: str = "",
        word_count: int = 1500,
        tone: ContentTone = None,
        output_format: OutputFormat = None,
        include_seo: bool = True,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an SEO-optimized blog post.

        Args:
            topic: Main topic of the blog post
            keywords: SEO keywords to include
            target_audience: Target audience description
            word_count: Approximate word count target
            tone: Writing tone/style
            output_format: Output format (markdown, html, plain_text)
            include_seo: Whether to include SEO metadata
            user_id: User ID for billing

        Returns:
            Generated blog post with metadata
        """
        tone = tone or self.default_tone
        output_format = output_format or self.default_format
        keywords = keywords or []

        system_prompt = f"""You are an expert content writer and SEO specialist.
Generate high-quality blog content that is engaging, informative, and optimized for search engines.

Writing Guidelines:
- Use a {tone.value} tone throughout
- Target approximately {word_count} words
- Include relevant subheadings (H2, H3)
- Use short paragraphs for readability
- Include bullet points or numbered lists where appropriate
- End with a clear call-to-action

SEO Best Practices:
- Naturally incorporate keywords without stuffing
- Use keyword variations and related terms
- Include internal/external link suggestions
- Optimize for featured snippets where relevant"""

        keyword_section = f"\nTarget Keywords: {', '.join(keywords)}" if keywords else ""
        audience_section = f"\nTarget Audience: {target_audience}" if target_audience else ""

        user_prompt = f"""Write a comprehensive blog post about: {topic}
{keyword_section}
{audience_section}

Please structure the post with:
1. An engaging introduction with a hook
2. Well-organized body sections with clear subheadings
3. Practical examples or case studies where relevant
4. A conclusion with key takeaways
5. A call-to-action

Output format: {output_format.value}"""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="default",
                temperature=0.7,
                max_tokens=4000,
                user_id=user_id,
            )

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {})

            # Generate SEO metadata
            seo_metadata = None
            if include_seo:
                seo_metadata = await self._generate_seo_metadata(
                    content, topic, keywords, user_id
                )

            # Generate hashtags
            hashtags = await self._generate_hashtags(topic, keywords, 5, user_id)

            # Format content based on output format
            formatted_content = self._format_content(content, output_format)

            result = ContentResult(
                content=formatted_content,
                content_type=ContentType.BLOG_POST,
                format=output_format,
                tone=tone,
                seo_metadata=seo_metadata,
                hashtags=hashtags,
                tokens_used={
                    "input": tokens.get("prompt_tokens", 0),
                    "output": tokens.get("completion_tokens", 0),
                    "total": tokens.get("total_tokens", 0),
                },
            )

            return {
                "status": "success",
                "result": result.to_dict(),
            }

        except Exception as e:
            logger.error(f"Error generating blog post: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def generate_social_content(
        self,
        platform: str,
        topic: str,
        context: Dict[str, Any] = None,
        tone: ContentTone = None,
        include_hashtags: bool = True,
        hashtag_count: int = 5,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate social media content for a specific platform.

        Args:
            platform: Target platform (twitter, linkedin, instagram, facebook)
            topic: Content topic
            context: Additional context (image description, etc.)
            tone: Writing tone
            include_hashtags: Whether to include hashtags
            hashtag_count: Number of hashtags to generate
            user_id: User ID for billing

        Returns:
            Generated social media content with hashtags
        """
        tone = tone or self.default_tone
        context = context or {}

        platform_configs = {
            "twitter": {
                "char_limit": 280,
                "content_type": ContentType.TWITTER,
                "guidelines": "Concise, engaging, use threads for longer content",
            },
            "linkedin": {
                "char_limit": 3000,
                "content_type": ContentType.LINKEDIN,
                "guidelines": "Professional, storytelling, industry insights",
            },
            "instagram": {
                "char_limit": 2200,
                "content_type": ContentType.INSTAGRAM,
                "guidelines": "Visual-focused, emoji-friendly, engaging captions",
            },
            "facebook": {
                "char_limit": 63206,
                "content_type": ContentType.FACEBOOK,
                "guidelines": "Conversational, community-focused, shareable",
            },
        }

        config = platform_configs.get(platform.lower(), platform_configs["twitter"])

        system_prompt = f"""You are a social media expert specializing in {platform}.
Create engaging content that resonates with the platform's audience.

Platform Guidelines:
- Character limit: {config['char_limit']}
- Style: {config['guidelines']}
- Tone: {tone.value}

Best Practices:
- Start with a hook
- Include a call-to-action
- Make it shareable and engaging
- Consider the platform's algorithm preferences"""

        context_section = ""
        if context:
            context_section = f"\nAdditional Context: {json.dumps(context)}"

        user_prompt = f"""Create a {platform} post about: {topic}
{context_section}

Make it engaging and optimized for the platform."""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="default",
                temperature=0.8,
                max_tokens=1000,
                user_id=user_id,
            )

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {})

            # Generate hashtags
            hashtags = []
            if include_hashtags:
                hashtags = await self._generate_hashtags(
                    topic, [], hashtag_count, user_id
                )

            result = ContentResult(
                content=content,
                content_type=config["content_type"],
                format=OutputFormat.PLAIN_TEXT,
                tone=tone,
                hashtags=hashtags,
                tokens_used={
                    "input": tokens.get("prompt_tokens", 0),
                    "output": tokens.get("completion_tokens", 0),
                    "total": tokens.get("total_tokens", 0),
                },
            )

            return {
                "status": "success",
                "result": result.to_dict(),
            }

        except Exception as e:
            logger.error(f"Error generating social content: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def generate_marketing_copy(
        self,
        copy_type: str,
        product_info: Dict[str, Any],
        target_audience: str = "",
        tone: ContentTone = None,
        platform: str = "",
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate marketing copy (product descriptions, ad copy, email campaigns).

        Args:
            copy_type: Type of copy (product_description, ad_copy, email_campaign)
            product_info: Product/service information
            target_audience: Target audience description
            tone: Writing tone
            platform: Target platform for ads
            user_id: User ID for billing

        Returns:
            Generated marketing copy
        """
        tone = tone or self.default_tone

        copy_configs = {
            "product_description": {
                "content_type": ContentType.PRODUCT_DESCRIPTION,
                "system_prompt": """You are an expert copywriter specializing in e-commerce.
Create compelling product descriptions that highlight features, benefits, and unique selling points.
Focus on customer pain points and how the product solves them.""",
            },
            "ad_copy": {
                "content_type": ContentType.AD_COPY,
                "system_prompt": """You are a performance marketing expert.
Create high-converting ad copy with strong headlines, compelling body text, and clear CTAs.
Focus on the target audience's desires and objections.""",
            },
            "email_campaign": {
                "content_type": ContentType.EMAIL_CAMPAIGN,
                "system_prompt": """You are an email marketing specialist.
Create engaging email sequences with attention-grabbing subject lines and persuasive body copy.
Focus on building relationships and guiding readers toward action.""",
            },
        }

        config = copy_configs.get(copy_type, copy_configs["product_description"])

        system_prompt = f"""{config['system_prompt']}

Tone: {tone.value}
Target Audience: {target_audience or 'General'}"""

        platform_section = f"\nTarget Platform: {platform}" if platform else ""

        user_prompt = f"""Create {copy_type.replace('_', ' ')} for:
{json.dumps(product_info, indent=2)}

{platform_section}

Include:
1. Main copy/content
2. Alternative headlines or subject lines (3 variations)
3. Call-to-action options"""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="default",
                temperature=0.7,
                max_tokens=2000,
                user_id=user_id,
            )

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {})

            result = ContentResult(
                content=content,
                content_type=config["content_type"],
                format=OutputFormat.MARKDOWN,
                tone=tone,
                tokens_used={
                    "input": tokens.get("prompt_tokens", 0),
                    "output": tokens.get("completion_tokens", 0),
                    "total": tokens.get("total_tokens", 0),
                },
            )

            return {
                "status": "success",
                "result": result.to_dict(),
            }

        except Exception as e:
            logger.error(f"Error generating marketing copy: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def repurpose_content(
        self,
        source_content: str,
        source_type: ContentType,
        target_types: List[ContentType],
        tone: ContentTone = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Repurpose content from one format to multiple other formats.

        Args:
            source_content: Original content
            source_type: Type of the source content
            target_types: List of target content types
            tone: Writing tone for repurposed content
            user_id: User ID for billing

        Returns:
            Dictionary of repurposed content for each target type
        """
        tone = tone or self.default_tone
        results = {}

        system_prompt = f"""You are an expert content strategist who specializes in repurposing content across platforms.
Maintain the core message while adapting format, length, and style for each platform.
Tone: {tone.value}"""

        for target_type in target_types:
            target_guidelines = self._get_content_guidelines(target_type)

            user_prompt = f"""Repurpose the following {source_type.value} into a {target_type.value}:

ORIGINAL CONTENT:
{source_content}

TARGET GUIDELINES:
{target_guidelines}

Create content optimized for the target format while preserving key messages."""

            try:
                response = await self.llm_client.chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model="default",
                    temperature=0.7,
                    max_tokens=2000,
                    user_id=user_id,
                )

                content = response["choices"][0]["message"]["content"]
                tokens = response.get("usage", {})

                # Generate platform-specific hashtags
                hashtags = await self._generate_hashtags(
                    content[:200], [], 5, user_id
                )

                results[target_type.value] = ContentResult(
                    content=content,
                    content_type=target_type,
                    format=OutputFormat.PLAIN_TEXT,
                    tone=tone,
                    hashtags=hashtags,
                    tokens_used={
                        "input": tokens.get("prompt_tokens", 0),
                        "output": tokens.get("completion_tokens", 0),
                        "total": tokens.get("total_tokens", 0),
                    },
                ).to_dict()

            except Exception as e:
                logger.error(f"Error repurposing to {target_type}: {e}")
                results[target_type.value] = {"error": str(e)}

        return {
            "status": "success",
            "source_type": source_type.value,
            "repurposed_content": results,
        }

    async def generate_variants(
        self,
        base_content: str,
        content_type: ContentType,
        variant_count: int = 3,
        variation_focus: str = "all",
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate A/B test variants of content.

        Args:
            base_content: Original content to create variants of
            content_type: Type of content
            variant_count: Number of variants to generate
            variation_focus: What to vary (headline, cta, tone, all)
            user_id: User ID for billing

        Returns:
            List of content variants
        """
        system_prompt = """You are an A/B testing expert who creates compelling content variations.
Each variant should maintain the core message while testing different:
- Headlines and hooks
- Calls-to-action
- Emotional appeals
- Value propositions
- Formatting approaches

Make each variant distinctly different to maximize testing insights."""

        user_prompt = f"""Create {variant_count} distinct variants of this {content_type.value}:

ORIGINAL CONTENT:
{base_content}

VARIATION FOCUS: {variation_focus}

For each variant, explain what element is being tested and why it might perform differently.

Format your response as:
## Variant 1
[Content]
Testing: [What's being tested]

## Variant 2
[Content]
Testing: [What's being tested]

And so on..."""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="default",
                temperature=0.8,
                max_tokens=3000,
                user_id=user_id,
            )

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {})

            # Parse variants from response
            variants = self._parse_variants(content)

            return {
                "status": "success",
                "original": base_content,
                "variant_count": len(variants),
                "variants": variants,
                "tokens_used": {
                    "input": tokens.get("prompt_tokens", 0),
                    "output": tokens.get("completion_tokens", 0),
                    "total": tokens.get("total_tokens", 0),
                },
            }

        except Exception as e:
            logger.error(f"Error generating variants: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def generate_content_calendar(
        self,
        topics: List[str],
        platforms: List[str],
        duration_weeks: int = 4,
        posts_per_week: int = 5,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a content calendar with scheduled posts.

        Args:
            topics: List of topics/themes to cover
            platforms: Target platforms
            duration_weeks: Number of weeks to plan
            posts_per_week: Posts per week per platform
            user_id: User ID for billing

        Returns:
            Content calendar with scheduled entries
        """
        system_prompt = """You are a content strategist creating an editorial calendar.
Plan content that:
- Balances different content types (educational, promotional, engaging)
- Aligns topics with platform strengths
- Maintains consistent posting frequency
- Builds toward engagement and conversion goals
- Considers optimal posting times for each platform"""

        user_prompt = f"""Create a {duration_weeks}-week content calendar for:

Topics/Themes: {', '.join(topics)}
Platforms: {', '.join(platforms)}
Posts per week: {posts_per_week}

For each entry, include:
1. Date/Day
2. Platform
3. Content type
4. Topic/Title
5. Brief description
6. Suggested hashtags
7. Best posting time

Start from next Monday and organize by week."""

        try:
            response = await self.llm_client.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="default",
                temperature=0.6,
                max_tokens=4000,
                user_id=user_id,
            )

            content = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {})

            # Parse calendar entries
            calendar_entries = self._parse_calendar(content, topics, platforms)

            return {
                "status": "success",
                "duration_weeks": duration_weeks,
                "total_posts": len(calendar_entries),
                "calendar": [entry.to_dict() for entry in calendar_entries],
                "raw_plan": content,
                "tokens_used": {
                    "input": tokens.get("prompt_tokens", 0),
                    "output": tokens.get("completion_tokens", 0),
                    "total": tokens.get("total_tokens", 0),
                },
            }

        except Exception as e:
            logger.error(f"Error generating content calendar: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def generate_hashtags(
        self,
        topic: str,
        platform: str = "general",
        count: int = 10,
        include_niche: bool = True,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate relevant hashtags for content.

        Args:
            topic: Topic to generate hashtags for
            platform: Target platform
            count: Number of hashtags to generate
            include_niche: Include niche/specific hashtags
            user_id: User ID for billing

        Returns:
            List of hashtags with categories
        """
        hashtags = await self._generate_hashtags(
            topic, [], count, user_id, platform, include_niche
        )

        return {
            "status": "success",
            "topic": topic,
            "platform": platform,
            "hashtags": hashtags,
            "count": len(hashtags),
        }

    async def stream_blog_post(
        self,
        topic: str,
        keywords: List[str] = None,
        target_audience: str = "",
        word_count: int = 1500,
        tone: ContentTone = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream blog post generation for real-time display.

        Args:
            topic: Main topic
            keywords: SEO keywords
            target_audience: Target audience
            word_count: Target word count
            tone: Writing tone
            user_id: User ID for billing

        Yields:
            Chunks of generated content
        """
        tone = tone or self.default_tone
        keywords = keywords or []

        system_prompt = f"""You are an expert content writer.
Generate a high-quality blog post with:
- {tone.value} tone
- Target: {word_count} words
- Keywords: {', '.join(keywords) if keywords else 'natural keywords'}
- Audience: {target_audience or 'general'}"""

        user_prompt = f"Write a comprehensive blog post about: {topic}"

        try:
            async for chunk in self.llm_client.chat_completion_stream(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="default",
                temperature=0.7,
                max_tokens=4000,
                user_id=user_id,
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Error streaming blog post: {e}")
            yield json.dumps({"error": str(e)})

    # Helper methods

    async def _generate_seo_metadata(
        self,
        content: str,
        topic: str,
        keywords: List[str],
        user_id: Optional[str] = None,
    ) -> SEOMetadata:
        """Generate SEO metadata for content"""
        prompt = f"""Analyze this content and generate SEO metadata:

CONTENT:
{content[:2000]}

TOPIC: {topic}
TARGET KEYWORDS: {', '.join(keywords) if keywords else 'derive from content'}

Generate:
1. SEO title (60 chars max)
2. Meta description (160 chars max)
3. Focus keyword
4. 5-7 related keywords
5. URL slug

Format as JSON with keys: title, meta_description, focus_keyword, keywords, slug"""

        try:
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="default",
                temperature=0.3,
                max_tokens=500,
                user_id=user_id,
            )

            response_text = response["choices"][0]["message"]["content"]

            # Extract JSON from response
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = {}

            # Calculate word count and reading time
            word_count = len(content.split())
            reading_time = max(1, word_count // 200)

            return SEOMetadata(
                title=data.get("title", topic[:60]),
                meta_description=data.get("meta_description", "")[:160],
                keywords=data.get("keywords", keywords),
                focus_keyword=data.get("focus_keyword", keywords[0] if keywords else ""),
                slug=data.get("slug", self._generate_slug(topic)),
                reading_time_minutes=reading_time,
                word_count=word_count,
            )

        except Exception as e:
            logger.warning(f"Error generating SEO metadata: {e}")
            return SEOMetadata(
                title=topic[:60],
                slug=self._generate_slug(topic),
                word_count=len(content.split()),
                reading_time_minutes=max(1, len(content.split()) // 200),
            )

    async def _generate_hashtags(
        self,
        topic: str,
        keywords: List[str],
        count: int,
        user_id: Optional[str] = None,
        platform: str = "general",
        include_niche: bool = True,
    ) -> List[str]:
        """Generate relevant hashtags"""
        niche_instruction = "Include both popular and niche-specific hashtags." if include_niche else "Focus on popular, high-volume hashtags."

        prompt = f"""Generate {count} relevant hashtags for:
Topic: {topic}
Keywords: {', '.join(keywords) if keywords else 'derive from topic'}
Platform: {platform}

{niche_instruction}

Return ONLY hashtags, one per line, without numbers or explanations.
Example format:
#ContentMarketing
#SocialMedia"""

        try:
            response = await self.llm_client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="default",
                temperature=0.5,
                max_tokens=200,
                user_id=user_id,
            )

            response_text = response["choices"][0]["message"]["content"]

            # Parse hashtags from response
            hashtags = []
            for line in response_text.split('\n'):
                line = line.strip()
                if line.startswith('#'):
                    hashtag = line.split()[0]  # Take only the hashtag part
                    if len(hashtag) > 1:
                        hashtags.append(hashtag)

            return hashtags[:count]

        except Exception as e:
            logger.warning(f"Error generating hashtags: {e}")
            return []

    def _format_content(self, content: str, output_format: OutputFormat) -> str:
        """Format content based on output format"""
        if output_format == OutputFormat.PLAIN_TEXT:
            # Remove markdown formatting
            content = re.sub(r'#{1,6}\s+', '', content)  # Remove headers
            content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)  # Remove bold
            content = re.sub(r'\*([^*]+)\*', r'\1', content)  # Remove italic
            content = re.sub(r'`([^`]+)`', r'\1', content)  # Remove code
            content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)  # Remove links

        elif output_format == OutputFormat.HTML:
            # Convert markdown to HTML (basic conversion)
            content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
            content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
            content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
            content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', content)
            content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
            content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', content)
            content = re.sub(r'^- (.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
            content = re.sub(r'\n\n', '</p>\n<p>', content)
            content = f'<p>{content}</p>'

        return content

    def _get_content_guidelines(self, content_type: ContentType) -> str:
        """Get guidelines for a content type"""
        guidelines = {
            ContentType.TWITTER: "280 character limit, engaging hooks, conversation starters",
            ContentType.LINKEDIN: "Professional tone, industry insights, 3000 char limit",
            ContentType.INSTAGRAM: "Visual-first, emoji-friendly, engaging captions, 2200 chars",
            ContentType.FACEBOOK: "Community-focused, shareable, conversational",
            ContentType.BLOG_POST: "SEO-optimized, comprehensive, well-structured",
            ContentType.PRODUCT_DESCRIPTION: "Benefit-focused, feature highlights, persuasive",
            ContentType.AD_COPY: "Attention-grabbing, clear CTA, benefit-driven",
            ContentType.EMAIL_CAMPAIGN: "Personal, value-driven, clear next steps",
            ContentType.NEWSLETTER: "Curated value, easy to scan, consistent format",
            ContentType.PRESS_RELEASE: "Newsworthy, AP style, quotes included",
        }
        return guidelines.get(content_type, "General content guidelines apply")

    def _parse_variants(self, content: str) -> List[Dict[str, str]]:
        """Parse variants from LLM response"""
        variants = []

        # Split by variant headers
        sections = re.split(r'##\s*Variant\s*\d+', content)

        for section in sections[1:]:  # Skip first empty section
            section = section.strip()
            if not section:
                continue

            # Try to extract testing note
            testing_match = re.search(r'Testing:\s*(.+?)(?=\n\n|$)', section, re.DOTALL)
            testing_note = testing_match.group(1).strip() if testing_match else ""

            # Get content (everything before Testing:)
            content_part = re.split(r'Testing:', section)[0].strip()

            variants.append({
                "content": content_part,
                "testing_note": testing_note,
            })

        return variants

    def _parse_calendar(
        self,
        content: str,
        topics: List[str],
        platforms: List[str],
    ) -> List[CalendarEntry]:
        """Parse calendar entries from LLM response"""
        entries = []

        # This is a simplified parser - in production, you'd want more robust parsing
        lines = content.split('\n')
        current_entry = {}

        start_date = datetime.now()
        # Move to next Monday
        days_until_monday = (7 - start_date.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        start_date = start_date + timedelta(days=days_until_monday)

        entry_count = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for content entries
            if any(platform.lower() in line.lower() for platform in platforms):
                # Extract what we can from the line
                platform_found = next(
                    (p for p in platforms if p.lower() in line.lower()),
                    platforms[0]
                )

                # Calculate date
                entry_date = start_date + timedelta(days=entry_count)

                entries.append(CalendarEntry(
                    date=entry_date.strftime("%Y-%m-%d"),
                    content_type=self._platform_to_content_type(platform_found),
                    topic=topics[entry_count % len(topics)] if topics else "General",
                    description=line[:200],
                    platform=platform_found,
                ))

                entry_count += 1

                if entry_count >= 28:  # Max 4 weeks
                    break

        return entries

    def _platform_to_content_type(self, platform: str) -> ContentType:
        """Convert platform name to ContentType"""
        mapping = {
            "twitter": ContentType.TWITTER,
            "x": ContentType.TWITTER,
            "linkedin": ContentType.LINKEDIN,
            "instagram": ContentType.INSTAGRAM,
            "facebook": ContentType.FACEBOOK,
            "blog": ContentType.BLOG_POST,
            "email": ContentType.EMAIL_CAMPAIGN,
        }
        return mapping.get(platform.lower(), ContentType.BLOG_POST)

    def _generate_slug(self, title: str) -> str:
        """Generate URL slug from title"""
        slug = title.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug[:60].strip('-')

    def get_templates(self) -> Dict[str, Any]:
        """Get available content templates"""
        return CONTENT_TEMPLATES


def create_content_generator(
    llm_client: Optional[OpsCenterLLMClient] = None,
    memory_manager=None,
) -> ContentGeneratorAgent:
    """Factory function to create a ContentGeneratorAgent"""
    return ContentGeneratorAgent(
        llm_client=llm_client,
        memory_manager=memory_manager,
    )
