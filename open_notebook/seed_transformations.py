"""
Seed archival transformations on first startup.

Loads transformation definitions from configs/archival/seed_transformations.json
and creates them in the database if no transformations exist yet.
This ensures a useful out-of-the-box experience for GLAM professionals.
"""

import json
import os
from pathlib import Path

from loguru import logger

from open_notebook.domain.transformation import Transformation


async def seed_archival_transformations() -> int:
    """Load seed transformations if the database has none.

    Returns the number of transformations created (0 if skipped).
    """
    try:
        existing = await Transformation.get_all()
        if existing:
            logger.debug(
                f"Skipping seed: {len(existing)} transformations already exist"
            )
            return 0

        # Find seed file relative to repo root
        seed_path = Path(__file__).parent.parent / "configs" / "archival" / "seed_transformations.json"
        if not seed_path.exists():
            logger.warning(f"Seed file not found: {seed_path}")
            return 0

        with open(seed_path, "r", encoding="utf-8") as f:
            definitions = json.load(f)

        created = 0
        for defn in definitions:
            try:
                t = Transformation(
                    name=defn["name"],
                    title=defn["title"],
                    description=defn["description"],
                    prompt=defn["prompt"],
                    apply_default=defn.get("apply_default", False),
                )
                await t.save()
                created += 1
                logger.info(f"Seeded transformation: {defn['title']}")
            except Exception as e:
                logger.warning(f"Failed to seed transformation '{defn.get('name')}': {e}")

        logger.success(f"Seeded {created} archival transformations")
        return created

    except Exception as e:
        logger.warning(f"Seed transformations skipped: {e}")
        return 0
