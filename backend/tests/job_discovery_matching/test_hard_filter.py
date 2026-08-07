from src.job_discovery_matching.internal.pipeline.nodes.hard_filter import (
    _passes_experience,
    _passes_location,
)


def test_unknown_experience_never_disqualifies_a_job() -> None:
    assert _passes_experience(
        {"experience_years": None},
        "This senior role requires 8+ years of software engineering experience.",
    )


def test_resume_address_is_not_an_implicit_location_filter() -> None:
    assert _passes_location(
        {"location": "100 Montgomery St. 10th Floor", "remote_ok": False},
        {"location": "Bengaluru", "is_remote": False},
        "Bengaluru office",
        {},
    )


def test_explicit_location_preference_is_enforced() -> None:
    assert not _passes_location(
        {"location": "San Francisco", "remote_ok": False},
        {"location": "Bengaluru", "is_remote": False},
        "Bengaluru office",
        {"target_location": "Hyderabad"},
    )
