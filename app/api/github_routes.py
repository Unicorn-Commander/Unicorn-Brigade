"""
GitHub Integration Routes

Provides API endpoints for:
- Triggering PR reviews
- Listing recent reviews
- GitHub webhook handler for auto-review
"""

import logging
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, HTTPException, Header, Request, BackgroundTasks, status, Depends
from pydantic import BaseModel, Field

from app.agents.code_reviewer import (
    CodeReviewer,
    ReviewResult,
    create_code_reviewer,
    CODE_REVIEW_ENABLED,
)
# Import the module (not the value) so the fail-closed webhook check below reads
# the LIVE GITHUB_WEBHOOK_SECRET at call time, matching verify_webhook_signature.
from app.agents import code_reviewer as code_reviewer_mod
from app.auth.middleware import require_api_key, require_operator, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/github", tags=["github"])

# Global code reviewer instance
_code_reviewer: Optional[CodeReviewer] = None


def get_code_reviewer() -> CodeReviewer:
    """Get or create the code reviewer instance"""
    global _code_reviewer
    if _code_reviewer is None:
        _code_reviewer = create_code_reviewer()
    return _code_reviewer


# -------------------------------------------------------------------
# Request/Response Models
# -------------------------------------------------------------------

class ReviewRequest(BaseModel):
    """Request to trigger a PR review"""
    repo: str = Field(..., description="Repository in format 'owner/repo'")
    pr_number: int = Field(..., description="Pull request number", gt=0)
    post_comments: bool = Field(default=False, description="Whether to post comments to GitHub")


class ReviewResponse(BaseModel):
    """Response from a PR review"""
    repo: str
    pr_number: int
    title: str
    summary: str
    overall_status: str
    comments_count: int
    stats: dict
    reviewed_at: str


class ReviewListResponse(BaseModel):
    """Response for listing reviews"""
    reviews: List[ReviewResponse]
    total: int


class WebhookResponse(BaseModel):
    """Response from webhook handler"""
    status: str
    message: str
    review_triggered: bool = False
    repo: Optional[str] = None
    pr_number: Optional[int] = None


class HealthResponse(BaseModel):
    """Health check response"""
    enabled: bool
    status: str
    github_configured: bool


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def github_health_check():
    """
    Check GitHub integration health.

    Returns configuration status and connectivity.
    """
    reviewer = get_code_reviewer()

    return HealthResponse(
        enabled=CODE_REVIEW_ENABLED,
        status="operational" if CODE_REVIEW_ENABLED else "disabled",
        github_configured=bool(reviewer.github_token),
    )


@router.post("/review", response_model=ReviewResponse)
async def trigger_pr_review(
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    user: Annotated[AuthUser, Depends(require_operator)] = None,
):
    """
    Trigger a PR review.

    This endpoint analyzes a GitHub pull request and returns findings.
    Optionally posts comments directly to the PR.

    Args:
        request: Review request with repo and PR number
        background_tasks: FastAPI background tasks for async posting

    Returns:
        Review results with summary and statistics
    """
    if not CODE_REVIEW_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Code review is disabled",
        )

    reviewer = get_code_reviewer()

    if not reviewer.github_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub token not configured",
        )

    try:
        logger.info(f"Triggering review for {request.repo}#{request.pr_number}")

        # Run the review
        result = await reviewer.review_pr(request.repo, request.pr_number)

        # Optionally post comments to GitHub
        if request.post_comments and result.comments:
            background_tasks.add_task(
                _post_review_comments,
                reviewer,
                request.repo,
                request.pr_number,
                result,
            )

        return ReviewResponse(
            repo=result.repo,
            pr_number=result.pr_number,
            title=result.title,
            summary=result.summary,
            overall_status=result.overall_status,
            comments_count=len(result.comments),
            stats=result.stats,
            reviewed_at=result.reviewed_at.isoformat(),
        )

    except Exception as e:
        logger.error(f"Review failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review failed: {str(e)}",
        )


@router.get("/reviews", response_model=ReviewListResponse)
async def list_recent_reviews(
    limit: int = 10,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    List recent PR reviews.

    Returns cached review results from memory.

    Args:
        limit: Maximum number of reviews to return

    Returns:
        List of recent reviews
    """
    if not CODE_REVIEW_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Code review is disabled",
        )

    reviewer = get_code_reviewer()
    reviews = reviewer.get_recent_reviews(limit=limit)

    return ReviewListResponse(
        reviews=[
            ReviewResponse(
                repo=r.repo,
                pr_number=r.pr_number,
                title=r.title,
                summary=r.summary,
                overall_status=r.overall_status,
                comments_count=len(r.comments),
                stats=r.stats,
                reviewed_at=r.reviewed_at.isoformat(),
            )
            for r in reviews
        ],
        total=len(reviews),
    )


@router.get("/reviews/{repo:path}/{pr_number}", response_model=ReviewResponse)
async def get_review(
    repo: str,
    pr_number: int,
    user: Annotated[AuthUser, Depends(require_api_key)] = None,
):
    """
    Get a specific PR review.

    Returns cached review result or triggers a new review.

    Args:
        repo: Repository in format 'owner/repo'
        pr_number: Pull request number

    Returns:
        Review results
    """
    if not CODE_REVIEW_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Code review is disabled",
        )

    reviewer = get_code_reviewer()

    # Check cache first
    result = reviewer.get_cached_review(repo, pr_number)

    if not result:
        # Trigger new review
        try:
            result = await reviewer.review_pr(repo, pr_number)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Review failed: {str(e)}",
            )

    return ReviewResponse(
        repo=result.repo,
        pr_number=result.pr_number,
        title=result.title,
        summary=result.summary,
        overall_status=result.overall_status,
        comments_count=len(result.comments),
        stats=result.stats,
        reviewed_at=result.reviewed_at.isoformat(),
    )


@router.post("/webhook", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
):
    """
    GitHub webhook handler for auto-review.

    Automatically triggers reviews when PRs are opened or updated.

    Supported events:
    - pull_request.opened
    - pull_request.synchronize
    - pull_request.reopened

    Args:
        request: Raw request for signature verification
        background_tasks: Background tasks for async processing
        x_github_event: GitHub event type header
        x_hub_signature_256: Webhook signature header

    Returns:
        Webhook processing status
    """
    if not CODE_REVIEW_ENABLED:
        return WebhookResponse(
            status="disabled",
            message="Code review is disabled",
            review_triggered=False,
        )

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature — FAIL CLOSED. The prior logic only verified when the
    # X-Hub-Signature-256 header was present, so an attacker could bypass
    # verification entirely by simply omitting the header. When a webhook secret
    # is configured, EVERY request must carry a valid signature or it is rejected.
    reviewer = get_code_reviewer()
    if code_reviewer_mod.GITHUB_WEBHOOK_SECRET:
        if not x_hub_signature_256 or not CodeReviewer.verify_webhook_signature(
            body, x_hub_signature_256
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing webhook signature",
            )
    elif x_hub_signature_256:
        # A signature was presented but no secret is configured to verify it —
        # reject rather than silently trust an unverifiable signature.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature presented but no secret is configured",
        )

    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    event_type = x_github_event or "unknown"
    logger.info(f"Received GitHub webhook: {event_type}")

    # Check if this is a PR event we care about
    if event_type != "pull_request":
        return WebhookResponse(
            status="ignored",
            message=f"Event type '{event_type}' not handled",
            review_triggered=False,
        )

    action = payload.get("action", "")
    if action not in ["opened", "synchronize", "reopened"]:
        return WebhookResponse(
            status="ignored",
            message=f"PR action '{action}' not handled",
            review_triggered=False,
        )

    # Extract repo and PR info
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {}).get("full_name", "")
    pr_number = pr.get("number")

    if not repo or not pr_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing repository or PR number",
        )

    # Trigger review in background
    background_tasks.add_task(
        _run_webhook_review,
        reviewer,
        repo,
        pr_number,
    )

    return WebhookResponse(
        status="accepted",
        message=f"Review triggered for {repo}#{pr_number}",
        review_triggered=True,
        repo=repo,
        pr_number=pr_number,
    )


# -------------------------------------------------------------------
# Background Tasks
# -------------------------------------------------------------------

async def _post_review_comments(
    reviewer: CodeReviewer,
    repo: str,
    pr_number: int,
    result: ReviewResult,
):
    """Background task to post review comments"""
    try:
        # Map overall status to GitHub event
        event_map = {
            "approved": "APPROVE",
            "changes_requested": "REQUEST_CHANGES",
            "commented": "COMMENT",
        }
        event = event_map.get(result.overall_status, "COMMENT")

        await reviewer.post_review(
            repo=repo,
            pr_number=pr_number,
            comments=result.comments,
            summary=result.summary,
            event=event,
        )
        logger.info(f"Posted review comments to {repo}#{pr_number}")
    except Exception as e:
        logger.error(f"Failed to post review comments: {e}")


async def _run_webhook_review(
    reviewer: CodeReviewer,
    repo: str,
    pr_number: int,
):
    """Background task to run review from webhook"""
    try:
        result = await reviewer.review_pr(repo, pr_number)

        # Auto-post comments for webhook-triggered reviews
        if result.comments:
            # Map overall status to GitHub event
            event_map = {
                "approved": "APPROVE",
                "changes_requested": "REQUEST_CHANGES",
                "commented": "COMMENT",
            }
            event = event_map.get(result.overall_status, "COMMENT")

            await reviewer.post_review(
                repo=repo,
                pr_number=pr_number,
                comments=result.comments,
                summary=result.summary,
                event=event,
            )

        logger.info(f"Webhook review completed for {repo}#{pr_number}")
    except Exception as e:
        logger.error(f"Webhook review failed for {repo}#{pr_number}: {e}")


# -------------------------------------------------------------------
# Startup/Shutdown
# -------------------------------------------------------------------

async def shutdown_github_routes():
    """Cleanup on shutdown"""
    global _code_reviewer
    if _code_reviewer:
        await _code_reviewer.close()
        _code_reviewer = None
