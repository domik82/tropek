"""Backfill SLO sli_name/sli_version from existing links and copy links to slo_bindings."""

import asyncio

from app.config import get_settings
from app.db.models import (
    AssetGroupSLOLink,
    AssetSLOLink,
    SLOBinding,
    SLODefinition,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def backfill() -> None:
    """Backfill sli_name on SLOs and copy asset/group links to slo_bindings."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # 1. Backfill sli_name on SLOs from their asset links
        slos_without_sli = (
            (await session.execute(select(SLODefinition).where(SLODefinition.sli_name.is_(None)))).scalars().all()
        )

        for slo in slos_without_sli:
            link = (
                await session.execute(select(AssetSLOLink).where(AssetSLOLink.slo_name == slo.name).limit(1))
            ).scalar_one_or_none()
            if link and link.sli_name:
                slo.sli_name = link.sli_name
                # sli_version left NULL — means "latest" at eval time

        # 2. Copy asset links to slo_bindings
        asset_links = (await session.execute(select(AssetSLOLink))).scalars().all()
        for link in asset_links:
            existing = (
                await session.execute(
                    select(SLOBinding).where(
                        SLOBinding.target_type == 'asset',
                        SLOBinding.target_id == link.asset_id,
                        SLOBinding.slo_name == link.slo_name,
                    )
                )
            ).scalar_one_or_none()
            if not existing:
                session.add(
                    SLOBinding(
                        target_type='asset',
                        target_id=link.asset_id,
                        slo_name=link.slo_name,
                        data_source_name=link.data_source_name,
                    )
                )

        # 3. Copy group links to slo_bindings
        group_links = (await session.execute(select(AssetGroupSLOLink))).scalars().all()
        for link in group_links:
            existing = (
                await session.execute(
                    select(SLOBinding).where(
                        SLOBinding.target_type == 'asset_group',
                        SLOBinding.target_id == link.group_id,
                        SLOBinding.slo_name == link.slo_name,
                    )
                )
            ).scalar_one_or_none()
            if not existing:
                session.add(
                    SLOBinding(
                        target_type='asset_group',
                        target_id=link.group_id,
                        slo_name=link.slo_name,
                        data_source_name=link.data_source_name,
                    )
                )

        await session.commit()
        print('backfill complete')


asyncio.run(backfill())
