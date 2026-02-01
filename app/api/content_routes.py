"""
Content Generation API Routes

API endpoints for the content generation agent:
- Blog post generation with SEO optimization
- Social media content (Twitter/X, LinkedIn, Instagram)
- Marketing copy (product descriptions, ad copy, email campaigns)
- Content repurposing
- A/B variant generation
- Content calendar suggestions
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Annotated
from enum import Enum
import logging
import json

from app.agents.content_generator import (
    ContentGeneratorAgent,
    create_content_generator,
    ContentType,
    ContentTone,
    OutputFormat,
    CONTENT_TEMPLATES,
)
from app.auth.middleware import require_api_key, require_operator, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/content", tags=["content"])

# Global agent instance (initialized on startup)
content_agent: Optional[ContentGeneratorAgent] = None


def init_content_routes(llm_client=None, memory_manager=None):
    """Initialize the content routes with dependencies"""
    global content_agent
    content_agent = create_content_generator(
        llm_client=llm_client,
        memory_manager=memory_manager,
    )
    logger.info("Content generation routes initialized")


def get_content_agent() -> ContentGeneratorAgent:
    """Dependency to get the content agent"""
    if not content_agent:
        raise HTTPException(
            status_code=503,
            detail="Content generator not initialized"
        )
    return content_agent


# ============== Request/Response Models ==============

class ToneEnum(str, Enum):
    """Content tone options"""
    professional = "professional"
    casual = "casual"
    humorous = "humorous"
    formal = "formal"
    friendly = "friendly"
    authoritative = "authoritative"
    inspirational = "inspirational"
    educational = "educational"
    conversational = "conversational"
    urgent = "urgent"


class FormatEnum(str, Enum):
    """Output format options"""
    markdown = "markdown"
    html = "html"
    plain_text = "plain_text"
    json_format = "json"


class PlatformEnum(str, Enum):
    """Social media platforms"""
    twitter = "twitter"
    linkedin = "linkedin"
    instagram = "instagram"
    facebook = "facebook"


class BlogPostRequest(BaseModel):
    """Request to generate a blog post"""
    topic: str = Field(..., description="Main topic of the blog post")
    keywords: List[str] = Field(
        default_factory=list,
        description="SEO keywords to include"
    )
    target_audience: str = Field("", description="Target audience description")
    word_count: int = Field(1500, ge=300, le=5000, description="Target word count")
    tone: ToneEnum = Field(ToneEnum.professional, description="Writing tone")
    output_format: FormatEnum = Field(FormatEnum.markdown, description="Output format")
    include_seo: bool = Field(True, description="Include SEO metadata")


class SocialContentRequest(BaseModel):
    """Request to generate social media content"""
    platform: PlatformEnum = Field(..., description="Target platform")
    topic: str = Field(..., description="Content topic")
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (image description, etc.)"
    )
    tone: ToneEnum = Field(ToneEnum.casual, description="Writing tone")
    include_hashtags: bool = Field(True, description="Include relevant hashtags")
    hashtag_count: int = Field(5, ge=1, le=30, description="Number of hashtags")


class MarketingCopyRequest(BaseModel):
    """Request to generate marketing copy"""
    copy_type: str = Field(
        "product_description",
        description="Type: product_description, ad_copy, email_campaign"
    )
    product_info: Dict[str, Any] = Field(
        ...,
        description="Product/service information"
    )
    target_audience: str = Field("", description="Target audience description")
    tone: ToneEnum = Field(ToneEnum.professional, description="Writing tone")
    platform: str = Field("", description="Target platform for ads")


class RepurposeRequest(BaseModel):
    """Request to repurpose content"""
    source_content: str = Field(..., description="Original content to repurpose")
    source_type: str = Field(
        "blog_post",
        description="Type of source content"
    )
    target_types: List[str] = Field(
        ...,
        description="Target content types (twitter, linkedin, instagram, etc.)"
    )
    tone: ToneEnum = Field(ToneEnum.professional, description="Writing tone")


class VariantsRequest(BaseModel):
    """Request to generate A/B test variants"""
    base_content: str = Field(..., description="Original content")
    content_type: str = Field(
        "ad_copy",
        description="Type of content"
    )
    variant_count: int = Field(3, ge=2, le=10, description="Number of variants")
    variation_focus: str = Field(
        "all",
        description="Focus: headline, cta, tone, or all"
    )


class CalendarRequest(BaseModel):
    """Request to generate content calendar"""
    topics: List[str] = Field(..., description="Topics/themes to cover")
    platforms: List[str] = Field(..., description="Target platforms")
    duration_weeks: int = Field(4, ge=1, le=12, description="Planning duration in weeks")
    posts_per_week: int = Field(5, ge=1, le=14, description="Posts per week")


class HashtagRequest(BaseModel):
    """Request to generate hashtags"""
    topic: str = Field(..., description="Topic for hashtags")
    platform: str = Field("general", description="Target platform")
    count: int = Field(10, ge=1, le=30, description="Number of hashtags")
    include_niche: bool = Field(True, description="Include niche hashtags")


class StreamBlogRequest(BaseModel):
    """Request to stream blog post generation"""
    topic: str = Field(..., description="Blog topic")
    keywords: List[str] = Field(default_factory=list, description="SEO keywords")
    target_audience: str = Field("", description="Target audience")
    word_count: int = Field(1500, ge=300, le=5000, description="Word count")
    tone: ToneEnum = Field(ToneEnum.professional, description="Writing tone")


# ============== Blog Post Endpoints ==============

@router.post("/blog")
async def generate_blog_post(
    request: BlogPostRequest,
    agent: ContentGeneratorAgent = Depends(get_content_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Generate an SEO-optimized blog post.

    Features:
    - SEO metadata (title, meta description, keywords, slug)
    - Customizable tone and format
    - Reading time and word count
    - Relevant hashtags for promotion
    """
    result = await agent.generate_blog_post(
        topic=request.topic,
        keywords=request.keywords,
        target_audience=request.target_audience,
        word_count=request.word_count,
        tone=ContentTone(request.tone.value),
        output_format=OutputFormat(request.output_format.value),
        include_seo=request.include_seo,
        user_id=user.user_id if user else None,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Blog post generation failed")
        )

    return result


@router.post("/blog/stream")
async def stream_blog_post(
    request: StreamBlogRequest,
    agent: ContentGeneratorAgent = Depends(get_content_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Stream blog post generation for real-time display.

    Returns Server-Sent Events with content chunks as they're generated.
    """
    async def generate():
        try:
            async for chunk in agent.stream_blog_post(
                topic=request.topic,
                keywords=request.keywords,
                target_audience=request.target_audience,
                word_count=request.word_count,
                tone=ContentTone(request.tone.value),
                user_id=user.user_id if user else None,
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ============== Social Media Endpoints ==============

@router.post("/social")
async def generate_social_content(
    request: SocialContentRequest,
    agent: ContentGeneratorAgent = Depends(get_content_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Generate social media content for a specific platform.

    Platforms supported:
    - Twitter/X (280 character optimized)
    - LinkedIn (professional, storytelling)
    - Instagram (visual-focused, emoji-friendly)
    - Facebook (community-focused, shareable)
    """
    result = await agent.generate_social_content(
        platform=request.platform.value,
        topic=request.topic,
        context=request.context,
        tone=ContentTone(request.tone.value),
        include_hashtags=request.include_hashtags,
        hashtag_count=request.hashtag_count,
        user_id=user.user_id if user else None,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Social content generation failed")
        )

    return result


# ============== Marketing Copy Endpoints ==============

@router.post("/marketing")
async def generate_marketing_copy(
    request: MarketingCopyRequest,
    agent: ContentGeneratorAgent = Depends(get_content_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Generate marketing copy.

    Types supported:
    - product_description: E-commerce product descriptions
    - ad_copy: High-converting ad copy for various platforms
    - email_campaign: Email sequences with subject lines

    Each type includes:
    - Main copy/content
    - Alternative headlines (3 variations)
    - Call-to-action options
    """
    result = await agent.generate_marketing_copy(
        copy_type=request.copy_type,
        product_info=request.product_info,
        target_audience=request.target_audience,
        tone=ContentTone(request.tone.value),
        platform=request.platform,
        user_id=user.user_id if user else None,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Marketing copy generation failed")
        )

    return result


# ============== Content Repurposing Endpoints ==============

@router.post("/repurpose")
async def repurpose_content(
    request: RepurposeRequest,
    agent: ContentGeneratorAgent = Depends(get_content_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Repurpose content from one format to multiple others.

    Takes source content and transforms it for different platforms
    while maintaining the core message.

    Example:
    - Blog post -> Twitter thread, LinkedIn post, Instagram caption
    - Product description -> Ad copy, email campaign
    """
    # Convert string types to enums
    try:
        source_type = ContentType(request.source_type)
    except ValueError:
        source_type = ContentType.BLOG_POST

    target_types = []
    for t in request.target_types:
        try:
            target_types.append(ContentType(t))
        except ValueError:
            logger.warning(f"Unknown target type: {t}, skipping")

    if not target_types:
        raise HTTPException(
            status_code=400,
            detail="No valid target types provided"
        )

    result = await agent.repurpose_content(
        source_content=request.source_content,
        source_type=source_type,
        target_types=target_types,
        tone=ContentTone(request.tone.value),
        user_id=user.user_id if user else None,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Content repurposing failed")
        )

    return result


# ============== A/B Variant Endpoints ==============

@router.post("/variants")
async def generate_variants(
    request: VariantsRequest,
    agent: ContentGeneratorAgent = Depends(get_content_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Generate A/B test variants of content.

    Creates distinct variations for testing:
    - Headlines and hooks
    - Calls-to-action
    - Emotional appeals
    - Value propositions
    - Formatting approaches

    Each variant includes what element is being tested.
    """
    try:
        content_type = ContentType(request.content_type)
    except ValueError:
        content_type = ContentType.AD_COPY

    result = await agent.generate_variants(
        base_content=request.base_content,
        content_type=content_type,
        variant_count=request.variant_count,
        variation_focus=request.variation_focus,
        user_id=user.user_id if user else None,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Variant generation failed")
        )

    return result


# ============== Template Endpoints ==============

@router.get("/templates")
async def list_templates(
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List available content templates.

    Each template includes:
    - Name and description
    - Required and optional fields
    - Supported platforms
    - Character limits (where applicable)
    """
    return {
        "templates": CONTENT_TEMPLATES,
        "count": len(CONTENT_TEMPLATES),
    }


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """Get a specific content template"""
    template = CONTENT_TEMPLATES.get(template_id)
    if not template:
        raise HTTPException(
            status_code=404,
            detail=f"Template not found: {template_id}"
        )
    return {"template_id": template_id, **template}


# ============== Content Calendar Endpoints ==============

@router.post("/calendar")
async def generate_content_calendar(
    request: CalendarRequest,
    agent: ContentGeneratorAgent = Depends(get_content_agent),
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Generate a content calendar with scheduled posts.

    Creates a multi-week editorial calendar with:
    - Balanced content types (educational, promotional, engaging)
    - Platform-specific content
    - Optimal posting times
    - Topic distribution
    - Suggested hashtags
    """
    result = await agent.generate_content_calendar(
        topics=request.topics,
        platforms=request.platforms,
        duration_weeks=request.duration_weeks,
        posts_per_week=request.posts_per_week,
        user_id=user.user_id if user else None,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Calendar generation failed")
        )

    return result


# ============== Hashtag Endpoints ==============

@router.post("/hashtags")
async def generate_hashtags(
    request: HashtagRequest,
    agent: ContentGeneratorAgent = Depends(get_content_agent),
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Generate relevant hashtags for content.

    Returns hashtags optimized for the specified platform,
    including both popular and niche-specific options.
    """
    result = await agent.generate_hashtags(
        topic=request.topic,
        platform=request.platform,
        count=request.count,
        include_niche=request.include_niche,
        user_id=user.user_id if user else None,
    )

    if result.get("status") != "success":
        raise HTTPException(
            status_code=500,
            detail=result.get("error", "Hashtag generation failed")
        )

    return result


# ============== Utility Endpoints ==============

@router.get("/tones")
async def list_tones():
    """List available content tones"""
    return {
        "tones": [
            {"id": tone.value, "name": tone.value.replace("_", " ").title()}
            for tone in ContentTone
        ]
    }


@router.get("/formats")
async def list_formats():
    """List available output formats"""
    return {
        "formats": [
            {"id": fmt.value, "name": fmt.value.replace("_", " ").title()}
            for fmt in OutputFormat
        ]
    }


@router.get("/content-types")
async def list_content_types():
    """List available content types"""
    return {
        "content_types": [
            {"id": ct.value, "name": ct.value.replace("_", " ").title()}
            for ct in ContentType
        ]
    }


# ============== Health Check ==============

@router.get("/health")
async def health_check():
    """Health check for content module"""
    return {
        "status": "healthy" if content_agent else "not_initialized",
        "module": "content_generator",
        "capabilities": [
            "blog_post",
            "social_media",
            "marketing_copy",
            "repurpose",
            "variants",
            "calendar",
            "hashtags",
        ] if content_agent else [],
    }
