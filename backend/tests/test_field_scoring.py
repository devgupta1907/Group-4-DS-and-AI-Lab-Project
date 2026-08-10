from evals.field_scoring import confusion_rows
from evals.gold import apply_corrections, atomic_skill_issues
from evals.normalization import normalize_skill_values


def row_for(rows: list[dict], field: str) -> dict:
    return next(row for row in rows if row["field"] == field)


def test_verified_gold_education_corrections_do_not_change_job_titles() -> None:
    profile = {
        "education": [{
            "degree": "Advanced Technical Certificate in Automotive Technology",
            "field": "Automotive Technology",
        }],
        "job_titles": ["Automotive Technician"],
    }

    corrected = apply_corrections("automobile__7b9fa0558115d57f", profile)

    assert corrected["education"][0]["degree"] == "Advanced Technical Certificate"
    assert corrected["job_titles"] == ["Automotive Technician"]


def test_gold_skill_corrections_are_atomic_and_deduplicated() -> None:
    profile = {
        "skills": [
            "Microsoft Word, Excel, Access, PowerPoint, Outlook",
            "Microsoft Excel",
        ]
    }
    corrected = apply_corrections("accountant__44", profile)
    assert corrected["skills"] == [
        "Microsoft Word", "Microsoft Excel", "Microsoft Access",
        "Microsoft PowerPoint", "Microsoft Outlook",
    ]
    assert atomic_skill_issues(corrected["skills"]) == []


def test_atomic_skill_validator_rejects_bundles_and_proficiency_framing() -> None:
    assert atomic_skill_issues(["Python", "Proficient in bookkeeping", "Word, Excel"]) == [
        "Proficient in bookkeeping", "Word, Excel",
    ]


def test_unambiguous_microsoft_skill_aliases_compare_equally() -> None:
    assert normalize_skill_values("MS Word") == {"microsoft word"}
    assert normalize_skill_values("Excel") == {"microsoft excel"}
    assert normalize_skill_values("Access") == {"microsoft access"}
    expected_office = {
        "microsoft word", "microsoft excel", "microsoft access",
        "microsoft powerpoint", "microsoft outlook",
    }
    assert normalize_skill_values(
        "Microsoft Word, Excel, Access, PowerPoint, & Outlook expertise"
    ) == expected_office
    assert normalize_skill_values(
        "Microsoft Word, Excel, Access, PowerPoint, & Outlook"
    ) == expected_office


def test_evidence_backed_skill_grammar_variants_compare_equally() -> None:
    assert normalize_skill_values("Bank reconciliation") == {"bank reconciliation"}
    assert normalize_skill_values("Bank reconciliations") == {"bank reconciliation"}
    assert normalize_skill_values("Preparing financial statements") == {
        "financial statement preparation"
    }
    assert normalize_skill_values("Financial statement preparation") == {
        "financial statement preparation"
    }


def test_unambiguous_vendor_product_aliases_compare_equally() -> None:
    assert normalize_skill_values("Photoshop") == {"adobe photoshop"}
    assert normalize_skill_values("G Suite") == {"google workspace"}
    assert normalize_skill_values("Google Sheets") == {"google sheets"}
    # A bare generic noun is not expanded without reliable vendor context.
    assert normalize_skill_values("Sheets") == {"sheets"}


def test_aws_service_aliases_compare_equally() -> None:
    assert normalize_skill_values("Amazon Web Services") == {"aws"}
    assert normalize_skill_values("AWS Elastic Compute") == {"ec2"}
    assert normalize_skill_values("Cloud EC2") == {"ec2"}
    assert normalize_skill_values("Cloud watch") == {"cloudwatch"}
    assert normalize_skill_values("AWS CloudWatch") == {"cloudwatch"}


def test_evidence_backed_skill_boundaries_and_versions_are_normalized() -> None:
    assert normalize_skill_values("JS/jQuery") == {"javascript", "jquery"}
    assert normalize_skill_values("MS SQL 2005/2008") == {"sql server"}
    assert normalize_skill_values(
        "Background in electrical construction or electrical engineering"
    ) == {"electrical construction", "electrical engineering"}
    assert normalize_skill_values(
        "Electrical construction / electrical engineering"
    ) == {"electrical construction", "electrical engineering"}
    assert normalize_skill_values("Knowledge of construction codes") == {
        "construction codes"
    }
    assert normalize_skill_values("Enterprise information and architecture") == {
        "enterprise information architecture"
    }


def test_verified_certification_corrections_fix_boundaries_and_atomicity() -> None:
    profile = {
        "skills": [],
        "education": [],
        "certifications": [{
            "name": "Safety Certificates: Confined Space Entry, Fall Protection",
            "issuer": None,
            "year": None,
        }],
    }
    corrected = apply_corrections("mechanical_engineer__f8cab5066475ed7d", profile)
    assert [item["name"] for item in corrected["certifications"]] == [
        "Confined Space Entry", "Fall Protection",
    ]


def test_verified_project_correction_removes_inferred_technology() -> None:
    profile = {"skills": [], "education": [], "projects": []}
    corrected = apply_corrections("web_designing__42ea741f515ea544", profile)
    assert corrected["projects"][1]["name"] == "Feather"
    assert corrected["projects"][1]["technologies"] == []


def test_normalized_scoring_reuses_locality_privacy_policy() -> None:
    prediction = {"contact": {"location": "Miami, FL"}}
    reference = {"contact": {"location": "123 Elm Street, Miami, FL 33183"}}

    result = row_for(
        confusion_rows(prediction, reference, mode="normalized"), "contact.location"
    )

    assert (result["tp"], result["fp"], result["fn"]) == (1, 0, 0)
    assert result["gold_values"] == ["miami fl"]


def test_normalized_scoring_uses_controlled_degree_aliases() -> None:
    prediction = {"education": [{"degree": "B. Sc."}]}
    reference = {"education": [{"degree": "Bachelor of Science"}]}

    result = row_for(
        confusion_rows(prediction, reference, mode="normalized"), "education.degree"
    )

    assert (result["tp"], result["fp"], result["fn"]) == (1, 0, 0)


def test_education_field_labels_are_not_part_of_the_discipline() -> None:
    prediction = {"education": [{"field": "Major in Visual Art"}]}
    reference = {"education": [{"field": "Visual Art"}]}

    result = row_for(
        confusion_rows(prediction, reference, mode="normalized"),
        "education.field",
    )

    assert (result["tp"], result["fp"], result["fn"]) == (1, 0, 0)


def test_institution_trailing_location_is_removed() -> None:
    prediction = {
        "education": [
            {"institution": "Colorado State University, Fort Collins, CO"},
            {
                "institution":
                    "The Ohio State University, Fisher College of Business - Columbus, OH"
            },
        ]
    }
    reference = {
        "education": [
            {"institution": "Colorado State University"},
            {"institution": "The Ohio State University, Fisher College of Business"},
        ]
    }

    result = row_for(
        confusion_rows(prediction, reference, mode="normalized"),
        "education.institution",
    )

    assert (result["tp"], result["fp"], result["fn"]) == (2, 0, 0)


def test_institution_campus_name_is_not_removed_as_a_location() -> None:
    prediction = {
        "education": [
            {"institution": "California State University, Fullerton"},
            {"institution": "University of Michigan - Dearborn - Dearborn, MI"},
        ]
    }
    reference = {
        "education": [
            {"institution": "California State University, Fullerton"},
            {"institution": "University of Michigan - Dearborn"},
        ]
    }

    result = row_for(
        confusion_rows(prediction, reference, mode="normalized"),
        "education.institution",
    )

    assert (result["tp"], result["fp"], result["fn"]) == (2, 0, 0)


def test_verified_institution_spacing_alias_is_normalized() -> None:
    prediction = {"education": [{"institution": "Penn State WorldCampus"}]}
    reference = {"education": [{"institution": "Penn State World Campus"}]}

    result = row_for(
        confusion_rows(prediction, reference, mode="normalized"),
        "education.institution",
    )

    assert (result["tp"], result["fp"], result["fn"]) == (1, 0, 0)


def test_company_location_suffix_is_removed_but_corporate_suffix_is_kept() -> None:
    prediction = {
        "experience": [
            {
                "company": "Genesis Fitness Center / Charleston, SC",
                "location": "Charleston, SC",
            },
            {"company": "Google, Inc.", "location": "Mountain View, CA"},
        ]
    }
    reference = {
        "experience": [
            {"company": "Genesis Fitness Center", "location": "Charleston, SC"},
            {"company": "Google Inc", "location": "Mountain View, CA"},
        ]
    }

    result = row_for(
        confusion_rows(prediction, reference, mode="normalized"), "experience.company"
    )

    assert (result["tp"], result["fp"], result["fn"]) == (2, 0, 0)


def test_date_range_is_split_by_target_field() -> None:
    prediction = {
        "experience": [
            {"start_date": "04/2011 – 11/2017", "end_date": "04/2011 – 11/2017"}
        ]
    }
    reference = {
        "experience": [{"start_date": "04/2011", "end_date": "11/2017"}]
    }

    rows = confusion_rows(prediction, reference, mode="normalized")

    assert row_for(rows, "experience.start_date")["tp"] == 1
    assert row_for(rows, "experience.end_date")["tp"] == 1


def test_year_fields_ignore_extra_month_and_season_precision() -> None:
    prediction = {
        "education": [{"end_year": "Spring 2018"}],
        "certifications": [{"year": "Mar 2020"}],
    }
    reference = {
        "education": [{"end_year": "2018"}],
        "certifications": [{"year": "2020"}],
    }

    rows = confusion_rows(prediction, reference, mode="normalized")

    assert row_for(rows, "education.end_year")["tp"] == 1
    assert row_for(rows, "certifications.year")["tp"] == 1


def test_apostrophe_year_is_expanded() -> None:
    prediction = {"education": [{"end_year": "May '16"}]}
    reference = {"education": [{"end_year": "2016"}]}

    result = row_for(
        confusion_rows(prediction, reference, mode="normalized"),
        "education.end_year",
    )

    assert (result["tp"], result["fp"], result["fn"]) == (1, 0, 0)


def test_experience_date_matches_at_gold_year_precision_only() -> None:
    prediction = {"experience": [{"start_date": "05/2015"}]}
    year_reference = {"experience": [{"start_date": "2015"}]}
    month_reference = {"experience": [{"start_date": "06/2015"}]}

    year_result = row_for(
        confusion_rows(prediction, year_reference, mode="normalized"),
        "experience.start_date",
    )
    month_result = row_for(
        confusion_rows(prediction, month_reference, mode="normalized"),
        "experience.start_date",
    )

    assert (year_result["tp"], year_result["fp"], year_result["fn"]) == (1, 0, 0)
    assert year_result["matched_value_pairs"] == [
        {"predicted": "2015-05", "gold": "2015"}
    ]
    assert (month_result["tp"], month_result["fp"], month_result["fn"]) == (0, 1, 1)


def test_missing_sentinels_and_location_placeholders_are_absent() -> None:
    prediction = {
        "experience": [
            {"company": "null", "location": "City, State", "start_date": "20xx"}
        ]
    }

    rows = confusion_rows(prediction, {}, mode="normalized")

    assert row_for(rows, "experience.company")["predicted_values"] == []
    assert row_for(rows, "experience.location")["predicted_values"] == []
    assert row_for(rows, "experience.start_date")["predicted_values"] == []


def test_skill_groups_are_compared_as_atomic_values_with_controlled_aliases() -> None:
    prediction = {
        "skills": ["Programming Languages: Python, Java Script", "Cloud Formation"]
    }
    reference = {"skills": ["Python", "JavaScript", "CloudFormation"]}

    result = row_for(confusion_rows(prediction, reference, mode="normalized"), "skills")

    assert (result["tp"], result["fp"], result["fn"]) == (3, 0, 0)


def test_parenthesized_skill_enumerations_are_split() -> None:
    prediction = {"skills": ["AWS (EC2, EBS, S3, RDS)"]}
    reference = {"skills": ["EC2", "EBS", "S3", "RDS"]}

    result = row_for(confusion_rows(prediction, reference, mode="normalized"), "skills")

    assert (result["tp"], result["fp"], result["fn"]) == (4, 0, 0)


def test_experience_job_title_abbreviations_and_acronyms_are_controlled() -> None:
    prediction = {"experience": [{"job_title": "Sr. E T L Engineer"}]}
    reference = {"experience": [{"job_title": "Senior ETL Engineer"}]}

    result = row_for(
        confusion_rows(prediction, reference, mode="normalized"),
        "experience.job_title",
    )

    assert (result["tp"], result["fp"], result["fn"]) == (1, 0, 0)
