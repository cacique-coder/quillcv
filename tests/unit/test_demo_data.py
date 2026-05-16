"""Cover the demo-data role + region matrix so each factory exercises at least once."""

import pytest

from app.content.use_cases.demo_data import (
    ROLES,
    get_demo_data,
    get_role,
    list_roles,
)


def test_list_roles_returns_all():
    roles = list_roles()
    assert len(roles) >= 5
    assert all(r.id for r in roles)


def test_get_role_known():
    assert get_role("software-engineer") is not None


def test_get_role_unknown():
    assert get_role("not-a-real-role") is None


@pytest.mark.parametrize("role_id", list(ROLES.keys()))
@pytest.mark.parametrize("region", ["AU", "US", "UK"])
def test_demo_data_for_every_role_region(role_id, region):
    data = get_demo_data(region, role_id=role_id)
    assert "name" in data
    assert data["name"]
    assert "_role_id" not in data  # internal marker should be stripped
