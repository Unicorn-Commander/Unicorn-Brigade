#!/usr/bin/env python3
"""
Database migration script to add code_attributions table for Agent Trace.

This script creates the code_attributions table if it doesn't exist.
Run this after adding the CodeAttribution model to app/db/models.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from app.db.database import engine, init_db
from app.db.models import Base, CodeAttribution


async def migrate():
    """Add code_attributions table"""
    print("Starting Agent Trace migration...")

    # Initialize database connection
    await init_db()

    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'code_attributions'
            );
        """))
        table_exists = result.scalar()

        if table_exists:
            print("Table 'code_attributions' already exists. Skipping migration.")
            return

        print("Creating 'code_attributions' table...")

        # Create the table
        await conn.run_sync(Base.metadata.create_all, tables=[CodeAttribution.__table__])

        print("Table 'code_attributions' created successfully!")
        print("Migration completed.")


if __name__ == "__main__":
    asyncio.run(migrate())
