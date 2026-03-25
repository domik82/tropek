"""Integration tests for SLO group CRUD and template bindings via HTTP API.

Requires TEST_DATABASE_URL and a running TimescaleDB instance.
Run: uv run pytest api/tests/db/test_slo_groups.py -m integration -v
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from app.db.session import get_session
from app.main import app
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture()
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """Yield an httpx AsyncClient bound to the FastAPI app with test DB session."""

    async def _override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _create_fixtures(
    client: AsyncClient,
    prefix: str,
    *,
    slo_kind: str = "template",
    adapter_type: str = "prometheus",
) -> None:
    """Create SLI, template SLO, and datasource fixtures with the given prefix."""
    resp = await client.post(
        "/sli-definitions",
        json={
            "name": f"{prefix}-sli",
            "adapter_type": adapter_type,
            "indicators": {"cpu": "rate(cpu_usage{process='$process_name'}[5m])"},
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        "/slo-definitions",
        json={
            "name": f"{prefix}-tpl-$__gen_process_name",
            "kind": slo_kind,
            "sli_name": f"{prefix}-sli",
            "sli_version": 1,
            "variables": {"process_name": "$__gen_process_name", "WINDOW": "5m"},
            "objectives": [{"sli": "cpu", "pass_criteria": ["<80"]}],
        },
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        "/datasources",
        json={
            "name": f"{prefix}-ds",
            "adapter_type": adapter_type,
            "adapter_url": "http://localhost:9090",
        },
    )
    assert resp.status_code == 201, resp.text


async def _create_group(
    client: AsyncClient,
    prefix: str,
    process_names: list[str],
    *,
    tags: dict[str, str] | None = None,
) -> dict:
    """Create an SLO group and return the response JSON."""
    resp = await client.post(
        "/slo-groups",
        json={
            "name": f"{prefix}-group",
            "template_slo_name": f"{prefix}-tpl-$__gen_process_name",
            "template_slo_version": 1,
            "gen_variables": {"process_name": process_names},
            "tags": tags or {"env": "test"},
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_create_group_generates_slos(async_client: AsyncClient) -> None:
    """Creating a group generates one SLO per gen_variable row."""
    await _create_fixtures(async_client, "grp1")
    data = await _create_group(async_client, "grp1", ["auth", "cache", "db"])

    assert data["name"] == "grp1-group"
    assert data["version"] == 1
    assert data["active"] is True
    assert data["generated_slo_count"] == 3

    # Verify each generated SLO exists via the list endpoint
    resp = await async_client.get(
        "/slo-definitions", params={"tag_key": "slo_group", "tag_val": "grp1-group"}
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    generated_names = {item["name"] for item in items}
    for proc in ("auth", "cache", "db"):
        assert f"grp1-tpl-{proc}" in generated_names


@pytest.mark.integration
async def test_create_group_rejects_non_template(async_client: AsyncClient) -> None:
    """A group referencing a standard SLO (not template kind) is rejected with 422."""
    await async_client.post(
        "/sli-definitions",
        json={
            "name": "grp2-sli",
            "adapter_type": "prometheus",
            "indicators": {"cpu": "rate(cpu[5m])"},
        },
    )
    await async_client.post(
        "/slo-definitions",
        json={
            "name": "grp2-std-slo",
            "kind": "standard",
            "sli_name": "grp2-sli",
            "sli_version": 1,
            "objectives": [{"sli": "cpu", "pass_criteria": ["<80"]}],
        },
    )

    resp = await async_client.post(
        "/slo-groups",
        json={
            "name": "grp2-group",
            "template_slo_name": "grp2-std-slo",
            "template_slo_version": 1,
            "gen_variables": {"process_name": ["auth"]},
        },
    )
    assert resp.status_code == 422


@pytest.mark.integration
async def test_create_group_name_collision(async_client: AsyncClient) -> None:
    """Creating a group that would generate an SLO colliding with existing name returns 409."""
    await _create_fixtures(async_client, "grp3")

    # Pre-create an SLO that will collide with a generated name
    await async_client.post(
        "/slo-definitions",
        json={
            "name": "grp3-tpl-auth",
            "sli_name": "grp3-sli",
            "sli_version": 1,
            "objectives": [{"sli": "cpu", "pass_criteria": ["<80"]}],
        },
    )

    resp = await async_client.post(
        "/slo-groups",
        json={
            "name": "grp3-group",
            "template_slo_name": "grp3-tpl-$__gen_process_name",
            "template_slo_version": 1,
            "gen_variables": {"process_name": ["auth", "cache"]},
        },
    )
    assert resp.status_code == 409


@pytest.mark.integration
async def test_update_group_add_row(async_client: AsyncClient) -> None:
    """Updating gen_variables to add a row creates a new generated SLO."""
    await _create_fixtures(async_client, "grp4")
    await _create_group(async_client, "grp4", ["auth", "cache"])

    resp = await async_client.put(
        "/slo-groups/grp4-group",
        json={"gen_variables": {"process_name": ["auth", "cache", "db"]}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["generated_slo_count"] == 3

    # New SLO should exist (check via list)
    resp = await async_client.get(
        "/slo-definitions", params={"tag_key": "slo_group", "tag_val": "grp4-group"}
    )
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["items"]}
    assert "grp4-tpl-db" in names


@pytest.mark.integration
async def test_update_group_remove_row(async_client: AsyncClient) -> None:
    """Updating gen_variables to remove a row deactivates the corresponding SLO."""
    await _create_fixtures(async_client, "grp5")
    await _create_group(async_client, "grp5", ["auth", "cache", "db"])

    resp = await async_client.put(
        "/slo-groups/grp5-group",
        json={"gen_variables": {"process_name": ["auth", "cache"]}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["generated_slo_count"] == 2

    # Removed SLO should be deactivated (not in active list)
    resp = await async_client.get(
        "/slo-definitions", params={"tag_key": "slo_group", "tag_val": "grp5-group"}
    )
    names = {item["name"] for item in resp.json()["items"]}
    assert "grp5-tpl-db" not in names


@pytest.mark.integration
async def test_extract_slo(async_client: AsyncClient) -> None:
    """Extracting a generated SLO creates a standalone copy and shrinks the group."""
    await _create_fixtures(async_client, "grp6")
    await _create_group(async_client, "grp6", ["auth", "cache", "db"])

    resp = await async_client.post(
        "/slo-groups/grp6-group/extract",
        json={"slo_name": "grp6-tpl-auth", "new_name": "grp6-standalone-auth"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["generated_slo_count"] == 2

    # Extracted standalone SLO should exist
    resp = await async_client.get("/slo-definitions/grp6-standalone-auth")
    assert resp.status_code == 200

    # Original generated SLO should be deactivated
    resp = await async_client.get(
        "/slo-definitions", params={"tag_key": "slo_group", "tag_val": "grp6-group"}
    )
    names = {item["name"] for item in resp.json()["items"]}
    assert "grp6-tpl-auth" not in names


@pytest.mark.integration
async def test_deactivate_group_cascades(async_client: AsyncClient) -> None:
    """Deleting a group deactivates it and its generated SLOs."""
    await _create_fixtures(async_client, "grp7")
    await _create_group(async_client, "grp7", ["auth", "cache"])

    resp = await async_client.delete("/slo-groups/grp7-group")
    assert resp.status_code == 204

    # Group should not be found
    resp = await async_client.get("/slo-groups/grp7-group")
    assert resp.status_code == 404

    # Generated SLOs should be deactivated
    resp = await async_client.get(
        "/slo-definitions", params={"tag_key": "slo_group", "tag_val": "grp7-group"}
    )
    assert resp.json()["items"] == []


@pytest.mark.integration
async def test_list_groups_tag_filter(async_client: AsyncClient) -> None:
    """Listing groups with tag filter returns only matching groups."""
    await _create_fixtures(async_client, "grp8a")
    await _create_fixtures(async_client, "grp8b")
    await _create_group(async_client, "grp8a", ["auth"], tags={"team": "platform"})
    await _create_group(async_client, "grp8b", ["auth"], tags={"team": "mobile"})

    resp = await async_client.get("/slo-groups", params={"tag_key": "team", "tag_val": "platform"})
    assert resp.status_code == 200
    data = resp.json()
    names = [g["name"] for g in data["items"]]
    assert "grp8a-group" in names
    assert "grp8b-group" not in names


@pytest.mark.integration
async def test_template_binding_crud(async_client: AsyncClient) -> None:
    """Template binding CRUD: create, list, delete for an asset."""
    await _create_fixtures(async_client, "grp9")
    await _create_group(async_client, "grp9", ["auth"])

    # Create asset
    await async_client.post("/asset-types", json={"name": "grp9-type"})
    await async_client.post("/assets", json={"name": "grp9-asset", "type_name": "grp9-type"})

    # Create template binding
    resp = await async_client.post(
        "/assets/grp9-asset/template-bindings",
        json={"template_group_name": "grp9-group", "data_source_name": "grp9-ds"},
    )
    assert resp.status_code == 201
    assert resp.json()["template_group_name"] == "grp9-group"

    # List
    resp = await async_client.get("/assets/grp9-asset/template-bindings")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Delete
    resp = await async_client.delete("/assets/grp9-asset/template-bindings/grp9-group")
    assert resp.status_code == 204

    # List again — empty
    resp = await async_client.get("/assets/grp9-asset/template-bindings")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.integration
async def test_template_binding_adapter_type_validation(async_client: AsyncClient) -> None:
    """Template binding rejects mismatched adapter_type between SLI and datasource."""
    await _create_fixtures(async_client, "grp10")
    await _create_group(async_client, "grp10", ["auth"])

    # Create a datasource with a different adapter_type
    await async_client.post(
        "/datasources",
        json={
            "name": "grp10-ds-dd",
            "adapter_type": "datadog",
            "adapter_url": "http://localhost:8080",
        },
    )

    await async_client.post("/asset-types", json={"name": "grp10-type"})
    await async_client.post("/assets", json={"name": "grp10-asset", "type_name": "grp10-type"})

    resp = await async_client.post(
        "/assets/grp10-asset/template-bindings",
        json={"template_group_name": "grp10-group", "data_source_name": "grp10-ds-dd"},
    )
    assert resp.status_code == 422


@pytest.mark.integration
async def test_template_binding_duplicate_rejected(async_client: AsyncClient) -> None:
    """Creating the same template binding twice fails with an error status."""
    await _create_fixtures(async_client, "grp11")
    await _create_group(async_client, "grp11", ["auth"])

    await async_client.post("/asset-types", json={"name": "grp11-type"})
    await async_client.post("/assets", json={"name": "grp11-asset", "type_name": "grp11-type"})

    resp = await async_client.post(
        "/assets/grp11-asset/template-bindings",
        json={"template_group_name": "grp11-group", "data_source_name": "grp11-ds"},
    )
    assert resp.status_code == 201

    # Second identical binding should fail with 409
    resp = await async_client.post(
        "/assets/grp11-asset/template-bindings",
        json={"template_group_name": "grp11-group", "data_source_name": "grp11-ds"},
    )
    assert resp.status_code == 409
