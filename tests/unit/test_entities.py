"""Smoke imports + construction tests for plain-dataclass entity modules."""


def test_billing_entities_construct():
    from app.billing.entities import (
        ALPHA_PACK_CREDITS,
        TOPUP_PACKS,
        CreditBalance,
        user_can_see_pack,
    )
    b = CreditBalance(user_id="u1", balance=10, total_purchased=10, total_used=0)
    assert b.balance == 10
    assert ALPHA_PACK_CREDITS == 15
    assert "mini" in TOPUP_PACKS
    assert user_can_see_pack(TOPUP_PACKS["mini"], "public") is True
    assert user_can_see_pack({"tier": "alpha"}, "public") is False
    assert user_can_see_pack({"tier": "alpha"}, "alpha") is True


def test_cv_generation_entities_construct():
    from app.cv_generation.entities import (
        CVData,
        Education,
        Experience,
        Project,
        Reference,
        SkillGroup,
    )
    cv = CVData(
        name="X",
        experience=[Experience(title="T", company="C", date="2020")],
        education=[Education(degree="BS", institution="MIT")],
        skills_grouped=[SkillGroup(category="Tech", items=["py"])],
        projects=[Project(name="P", tech=["py"])],
        references=[Reference(name="R")],
    )
    assert cv.name == "X"
    assert cv.experience[0].title == "T"
    assert cv.skills_grouped[0].items == ["py"]


def test_identity_entities_construct():
    from app.identity.entities import UserProfile
    p = UserProfile(id="u1", email="a@b.c", name="A")
    assert p.email == "a@b.c"


def test_consent_entities_construct():
    from datetime import UTC, datetime

    from app.consent.entities import CURRENT_POLICY_VERSION, ConsentRecord
    rec = ConsentRecord(
        user_id="u1",
        policy_version=CURRENT_POLICY_VERSION,
        consented_at=datetime.now(UTC),
        ip_address="1.2.3.4",
    )
    assert rec.user_id == "u1"


def test_pii_entities_construct():
    from app.pii.entities import PIIProfile, ReferenceContact
    p = PIIProfile(full_name="John Smith")
    p.references.append(ReferenceContact(name="R", email="r@example.com"))
    assert p.full_name == "John Smith"
    assert p.references[0].email == "r@example.com"


def test_cv_export_entities_module_imports():
    """cv_export/entities re-exports CVTemplate + RegionConfig from the registry."""
    from app.cv_export.entities import CVTemplate, RegionConfig
    assert CVTemplate is not None
    assert RegionConfig is not None


def test_ports_modules_import():
    """Importing port protocols should not error and should register the module."""
    import app.billing.ports  # noqa: F401
    import app.cv_export.ports  # noqa: F401
    import app.cv_generation.ports  # noqa: F401
