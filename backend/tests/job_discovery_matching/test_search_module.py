from src.job_discovery_matching.internal.pipeline.nodes.search_module import (
    _is_direct_vacancy,
    _job_query,
    _looks_like_vacancy,
)


def test_adds_job_intent_to_ambiguous_query() -> None:
    assert _job_query("Senior Java Developer") == "Senior Java Developer jobs hiring"
    assert _job_query("Senior Java Developer jobs") == "Senior Java Developer jobs"


def test_rejects_informational_search_results() -> None:
    assert not _looks_like_vacancy(
        {
            "title": "Spring Boot Tutorial",
            "url": "https://example.com/tutorial/spring-boot",
            "content": "Learn Spring Boot",
        }
    )
    assert not _looks_like_vacancy(
        {
            "title": "Senior Java Developer Resume Examples",
            "url": "https://example.com/resume-example",
            "content": "Resume tips",
        }
    )


def test_accepts_direct_vacancy() -> None:
    assert _looks_like_vacancy(
        {
            "title": "Senior Software Engineer",
            "url": "https://company.example/careers/12345",
            "content": "Apply for this opening",
        }
    )


def test_distinguishes_individual_posting_from_listing_page() -> None:
    assert _is_direct_vacancy(
        {
            "title": "Senior Software Developer",
            "url": "https://company.example/careers/jobs/449492",
        }
    )
    assert not _is_direct_vacancy(
        {
            "title": "6,000+ Senior Developer jobs in India",
            "url": "https://example.com/senior-developer-jobs",
        }
    )
