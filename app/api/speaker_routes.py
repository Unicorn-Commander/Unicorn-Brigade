"""
Speaker profile routes for voice speaker identification.
Provides CRUD for speaker profiles + enrollment endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import numpy as np

from app.db.database import get_session
from app.db.repositories import SpeakerProfileRepository

logger = logging.getLogger(__name__)
router = APIRouter()


# ---- Pydantic Models ----

class SpeakerEnrollRequest(BaseModel):
    name: str
    embedding: List[float]


class SpeakerUpdateRequest(BaseModel):
    name: Optional[str] = None
    preferences: Optional[Dict] = None
    embedding: Optional[List[float]] = None


# ---- Routes ----

@router.get("/speakers")
async def list_speakers(
    session: AsyncSession = Depends(get_session),
):
    """List all speaker profiles (voice client caches these on startup)."""
    repo = SpeakerProfileRepository(session)
    profiles = await repo.list_all()
    return {"speakers": profiles}


@router.post("/speakers/enroll", status_code=201)
async def enroll_speaker(
    request: SpeakerEnrollRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create or update a speaker profile from voice enrollment.

    If a profile with the same name exists, the new embedding is averaged
    with the existing one (weighted by enrollment_count) for improved accuracy.
    """
    repo = SpeakerProfileRepository(session)
    existing = await repo.get_by_name(request.name)

    if existing:
        # Average new embedding with existing (weighted by enrollment count)
        old_count = existing.get("enrollmentCount", 1)
        old_embed = np.array(existing["embedding"], dtype=np.float32)
        new_embed = np.array(request.embedding, dtype=np.float32)
        averaged = ((old_embed * old_count) + new_embed) / (old_count + 1)
        # Re-normalize
        averaged = averaged / (np.linalg.norm(averaged) + 1e-10)

        updated = await repo.update(existing["id"], {
            "embedding": averaged.tolist(),
            "enrollment_count": old_count + 1,
        })
        if updated:
            logger.info("Re-enrolled speaker '%s' (count=%d)", request.name, old_count + 1)
            return updated
        raise HTTPException(status_code=500, detail="Failed to update profile")

    # New enrollment
    profile = await repo.create({
        "name": request.name,
        "embedding": request.embedding,
    })
    logger.info("Enrolled new speaker '%s'", request.name)
    return profile


@router.get("/speakers/{profile_id}")
async def get_speaker(
    profile_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a single speaker profile."""
    repo = SpeakerProfileRepository(session)
    profile = await repo.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Speaker profile not found")
    return profile


@router.put("/speakers/{profile_id}")
async def update_speaker(
    profile_id: str,
    request: SpeakerUpdateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update speaker name, preferences, or re-enroll with new embedding."""
    repo = SpeakerProfileRepository(session)
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    profile = await repo.update(profile_id, updates)
    if not profile:
        raise HTTPException(status_code=404, detail="Speaker profile not found")
    return profile


@router.delete("/speakers/{profile_id}")
async def delete_speaker(
    profile_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Remove a speaker profile."""
    repo = SpeakerProfileRepository(session)
    success = await repo.delete(profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Speaker profile not found")
    return {"message": "Speaker profile deleted", "id": profile_id}
