from evals.metrics import field_metrics


def scores(predicted: dict, gold: dict) -> dict[str, float]:
    return {
        row["key"]: row["score"]
        for row in field_metrics(predicted, gold)
    }


def profile(education: list[dict]) -> dict:
    return {
        "contact": {"name": None},
        "skills": [],
        "job_titles": [],
        "education": education,
        "experience": [],
        "certifications": [],
        "projects": [],
    }


def test_education_matches_degree_alias_and_location_suffix() -> None:
    predicted = profile(
        [
            {
                "degree": "B. Sc.",
                "institution": "Iowa State University, Ames, IA",
            }
        ]
    )
    gold = profile(
        [
            {
                "degree": "Bachelor of Science",
                "institution": "Iowa State University",
            }
        ]
    )

    result = scores(predicted, gold)

    assert result["education_precision"] == 1.0
    assert result["education_recall"] == 1.0
    assert result["education_f1"] == 1.0


def test_education_rejects_materially_different_degree_and_institution() -> None:
    predicted = profile(
        [{"degree": "Bachelor of Engineering", "institution": "Example Institute"}]
    )
    gold = profile(
        [{"degree": "Bachelor of Arts", "institution": "Different University"}]
    )

    result = scores(predicted, gold)

    assert result["education_f1"] == 0.0


def test_year_only_gold_accepts_more_precise_predicted_month() -> None:
    predicted = profile(
        [
            {
                "degree": "B.Sc.",
                "institution": "Example University",
                "start_year": "08/2018",
                "end_year": "05/2022",
            }
        ]
    )
    gold = profile(
        [
            {
                "degree": "Bachelor of Science",
                "institution": "Example University",
                "start_year": "2018",
                "end_year": "2022",
            }
        ]
    )

    result = scores(predicted, gold)

    assert result["education_date_accuracy"] == 1.0


def test_month_specific_gold_does_not_accept_year_only_prediction() -> None:
    predicted = profile(
        [
            {
                "degree": "B.Sc.",
                "institution": "Example University",
                "end_year": "2022",
            }
        ]
    )
    gold = profile(
        [
            {
                "degree": "Bachelor of Science",
                "institution": "Example University",
                "end_year": "05/2022",
            }
        ]
    )

    result = scores(predicted, gold)

    assert result["education_date_accuracy"] == 0.0
