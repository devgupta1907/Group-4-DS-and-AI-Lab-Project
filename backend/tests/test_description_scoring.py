from evals.description_scoring import score_description_entries, score_description_record


def experience(title, company, start, end, description):
    return {
        "job_title": title, "company": company, "start_date": start,
        "end_date": end, "description": description,
    }


def test_description_compares_the_same_experience_not_best_text_overlap() -> None:
    record = {
        "resume_id": "one",
        "prediction": {"experience": [
            experience("Engineer", "A", "2020", "2021", "Managed restaurant sales"),
            experience("Manager", "B", "2022", "Present", "Built Python APIs"),
        ]},
        "reference": {"experience": [
            experience("Engineer", "A", "2020", "2021", "Built Python APIs"),
            experience("Manager", "B", "2022", "Present", "Managed restaurant sales"),
        ]},
    }
    rows = score_description_entries(record)
    assert [row["predicted_experience_index"] for row in rows] == [0, 1]
    assert all(row["description_cosine"] < 0.1 for row in rows)


def test_description_alignment_does_not_require_correct_identity_fields() -> None:
    record = {
        "prediction": {"experience": [
            experience("Wrong title", "Wrong company", "Wrong", "Wrong", "Built Python APIs")
        ]},
        "reference": {"experience": [
            experience("Engineer", "A", "2020", "2021", "Built Python APIs")
        ]},
    }
    row = score_description_entries(record)[0]
    assert row["predicted_experience_index"] == 0
    assert row["identity_match_score"] == 0
    assert row["description_cosine"] > 0.999


def test_gold_entries_without_descriptions_do_not_shift_indices() -> None:
    record = {
        "prediction": {"experience": [
            experience("First", "A", "2020", "2021", None),
            experience("Second", "B", "2022", "2023", "Second description"),
        ]},
        "reference": {"experience": [
            experience("First", "A", "2020", "2021", None),
            experience("Second", "B", "2022", "2023", "Second description"),
        ]},
    }
    row = score_description_entries(record)[0]
    assert row["gold_experience_index"] == 1
    assert row["predicted_experience_index"] == 1
    assert row["description_cosine"] > 0.999


def test_missing_experience_description_receives_zero() -> None:
    result = score_description_record({
        "prediction": {"experience": []},
        "reference": {"experience": [
            experience("Engineer", "A", "2020", "2021", "Built Python APIs")
        ]},
    })
    assert result["description_coverage"] == 0.0
    assert result["description_cosine"] == 0.0


def test_gold_experience_without_description_is_not_applicable() -> None:
    result = score_description_record({
        "prediction": {"experience": []},
        "reference": {"experience": [
            experience("Engineer", "A", "2020", "2021", None)
        ]},
    })
    assert result["gold_experience_descriptions"] == 0
    assert result["description_coverage"] is None
    assert result["description_cosine"] is None
