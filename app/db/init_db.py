"""
Database initialization script.
Creates tables and seeds initial agent data from JSON.

Usage:
    python -m app.db.init_db
"""
import asyncio
import json
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from app.db.database import engine, migration_engine, Base, async_session, admin_session
from app.db.models import Agent
from app.llm.ops_center_client import DEFAULT_MODEL
from app.agent_avatars import canonical_avatar_path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def create_tables():
    """Create all tables.

    DDL runs on the OWNER/admin engine (migration_engine) — the RLS-subject app
    role can't create tables or the brigade_app parent. In single-role dev
    migration_engine is the same engine as `engine`, so this is unchanged there.
    """
    async with migration_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All database tables created successfully")


async def seed_agents():
    """Seed agents from JSON file if table is empty."""
    seed_filename = os.getenv("BRIGADE_SEED_AGENTS_FILE", "seed_agents.json")
    seed_path = seed_filename
    if not os.path.isabs(seed_path):
        seed_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", seed_filename
        )

    if not os.path.exists(seed_path):
        logger.warning(f"Seed file not found: {seed_path}")
        return

    # BR-1.4: seed the GLOBAL roster (NULL org_id) on the OWNER/admin session.
    # agents now has FORCE RLS with WITH CHECK (org_id = current_org_id()); the
    # RLS-subject app role can never insert a NULL-org (shared) row, so the seed
    # loader must use the owner session, which is not subject to RLS. In
    # single-role dev admin_session is the same engine as async_session.
    async with admin_session() as session:
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(Agent.id)))
        count = result.scalar() or 0

        if count > 0:
            logger.info(f"Agents table already has {count} records, skipping seed")
            return

        with open(seed_path, "r") as f:
            agents_data = json.load(f)

        for data in agents_data:
            agent = Agent(
                id=data["id"],
                name=data["name"],
                display_name=data.get("displayName"),
                title=data.get("title"),
                rank=data.get("rank"),
                avatar=data.get("avatar", "🦄"),
                avatar_url=(
                    data.get("avatarUrl")
                    or canonical_avatar_path(data["id"])
                ),
                bio=data.get("bio"),
                persona=data.get("persona"),
                system_prompt=data.get("systemPrompt"),
                domain=data.get("domain", "general"),
                subdomain=data.get("subdomain"),
                status=data.get("status", "active"),
                type=data.get("type", "individual"),
                agent_type=data.get("agentType", "analysis"),
                capabilities=data.get("capabilities", []),
                model=data.get("model") or DEFAULT_MODEL,
                temperature=data.get("temperature", 0.7),
                max_tokens=data.get("maxTokens", 2000),
                tools=data.get("tools", []),
                billing_tier=data.get("billingTier", "standard"),
                rate_multiplier=data.get("rateMultiplier", 1.0),
                base_price_per_call=data.get("basePricePerCall"),
                affiliation=data.get("affiliation"),
                access_policy=data.get("accessPolicy"),
            )
            session.add(agent)

        await session.commit()
        logger.info(f"Seeded {len(agents_data)} agents from {seed_path}")


async def main():
    """Initialize database: create tables and seed data."""
    logger.info("Initializing Unicorn Brigade database...")
    await create_tables()
    await seed_agents()
    await engine.dispose()
    logger.info("Database initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
