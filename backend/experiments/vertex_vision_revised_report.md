# Vertex AI Resume Extraction Evaluation

## Purpose

This experiment evaluates whether a vision-language model can extract structured information from resume images. The evaluation records the raw model response, the final production prediction, field-level TP/FP/FN counts, schema validity, and latency for every resume.

The initial smoke tests used five resumes. Semantic value normalization was disabled so the results represent an exact-match baseline.

## Schema-adherence problem

The first Vertex AI implementation produced valid JSON, but the JSON did not consistently follow the required resume schema. This was an integration problem in the Vertex AI provider rather than a Pydantic problem.

The earlier implementation passed schema configuration through the Google Gen AI SDK. For the Gemma MaaS endpoint, this did not consistently constrain the response. Unlike the existing AI Studio Gemma path, the complete JSON Schema was also not visible in the model's user prompt. As a result, Gemma invented alternative field names and structures.

In the failed five-resume run:

- Schema-valid resumes: **0/5**
- Schema-invalid resumes: **5/5**

### Example of an invalid raw response

The following schema-relevant excerpt is taken from an actual failed response:

```json
{
  "education": [
    {
      "degree": "Bachelor | Accounting",
      "details": [
        "Graduated Magna Cum Laude",
        "Phi Kappa Phi Honor Society"
      ],
      "graduation_date": "2002",
      "institution": "Northwestern State University of Louisiana, Natchitoches, LA"
    }
  ],
  "professional_summary": "Current Account with the City of Alexandria with over 15 years of experience in the accounting industry.",
  "skills": [
    "Accounting",
    "Bookkeeping Services",
    "Financial statements"
  ],
  "work_history": [
    {
      "employer": "City of Alexandria",
      "job_title": "ACCOUNTANT",
      "location": "Alexandria, VA",
      "end_date": "08/2013 to CURRENT",
      "start_date": null
    }
  ]
}
```

The JSON was syntactically valid, but it violated the required contract:

- `contact` was missing.
- `experience` was replaced by `work_history`.
- `company` was replaced by `employer`.
- `education.field`, `education.start_year`, and `education.end_year` were missing.
- Unsupported fields such as `professional_summary`, `details`, and `graduation_date` were added.
- `job_titles` was missing.

### Expected structure

The application expected the following structure, including nullable fields and empty lists when information was unavailable:

```json
{
  "contact": {
    "name": "Jessica Claire",
    "location": "Monterey, CA",
    "links": []
  },
  "skills": [],
  "education": [
    {
      "degree": null,
      "field": null,
      "institution": "Northwestern State University of Louisiana, Natchitoches, LA",
      "start_year": null,
      "end_year": "2002"
    }
  ],
  "experience": [],
  "projects": [],
  "certifications": [],
  "job_titles": []
}
```

## Correction

The Vertex AI provider was revised in two ways:

1. Gemma MaaS requests were moved to Vertex AI's OpenAI-compatible endpoint and its Pydantic structured-response parsing interface.
2. The complete JSON Schema was also inserted directly into the Gemma user prompt, matching the successful prompting strategy used with AI Studio.

This provides two safeguards: API-level structured parsing and prompt-level schema visibility. The evaluation notebook also reloads the provider implementation and records its source fingerprint, preventing an older provider cached by Jupyter from being mistaken for a new experiment.

## Corrected result

After the correction:

- Schema-valid resumes: **5/5**
- Schema-invalid resumes: **0/5**

### Example of the latest schema-valid raw response

The following excerpt is from the corrected raw response for the same resume:

```json
{
  "certifications": [],
  "contact": {
    "links": [],
    "location": "Monterey, CA",
    "name": "Jessica Claire"
  },
  "education": [
    {
      "degree": null,
      "end_year": "2002",
      "field": null,
      "institution": "Northwestern State University of Louisiana, Natchitoches, LA",
      "start_year": null
    }
  ],
  "experience": [
    {
      "company": "City Corp | Rexburg, ID",
      "current_role": false,
      "description": "Help prepare Financial Statements and Bank Reconciliations.",
      "end_date": "08/2013",
      "job_title": "ACCOUNTANT",
      "location": "Rexburg, ID",
      "start_date": null
    }
  ],
  "job_titles": [
    "ACCOUNTANT"
  ],
  "projects": [],
  "skills": [
    "Accounting & Bookkeeping Services",
    "Financial statements",
    "Bank reconciliations"
  ]
}
```

This response contains every required root field, uses the expected nested field names, includes nullable values explicitly, and introduces no unsupported properties. It therefore passes JSON Schema validation.

## Interpretation

Schema validity and extraction accuracy are separate measurements. The correction proves that the model now returns the required structure, but it does not prove that every extracted value is correct. For example, company names, locations, dates, or skills can still be transcribed incorrectly while the response remains schema-valid. TP/FP/FN metrics and manual evidence review are therefore still required for evaluating extraction quality.

## Current conclusion

The initial schema failures were caused by the Vertex AI integration. Using the documented OpenAI-compatible structured-output interface and also placing the schema directly in the Gemma prompt corrected the issue for all five smoke-test resumes. This corrected configuration should be used for the larger evaluation run.

## Offline normalized scoring experiment

The completed baseline contained 84 successful inference results from 86 source resumes. The two remaining resumes repeatedly exceeded the 120-second inference timeout and were reported separately as operational failures. Field accuracy was therefore calculated over the common cohort of 84 successful resumes.

A second scoring experiment reused those exact 84 predictions and references. It made no additional model calls. Normalization was applied only to deterministic comparison keys; the original extracted values remained unchanged. Location was the privacy exception: exact-address and postal components were reduced to locality-level information using the production sanitizer on both prediction and reference.

The normalized comparison included Unicode normalization, case folding, whitespace normalization, controlled degree aliases, date canonicalization, and locality-only location comparison. The derived experiment retained a reference to every original inference record and inherited inference latency only as provenance. Total local normalization time for all 84 resumes was approximately 0.096 seconds.

### Aggregate result

| Metric | Raw exact match | Normalized comparison | Change |
|---|---:|---:|---:|
| Precision | 0.5230 | 0.5899 | +0.0668 |
| Recall | 0.5274 | 0.5961 | +0.0687 |
| Micro-F1 | 0.5252 | 0.5930 | +0.0677 |

Aggregate TP increased by 188, from 1,499 to 1,687. FP decreased from 1,367 to 1,173, and FN decreased from 1,343 to 1,143. The reductions are not required to equal the TP increase because canonicalization can also collapse duplicate comparison values.

### Field-level effect

| Field | Raw F1 | Normalized F1 | Change |
|---|---:|---:|---:|
| Contact location | 0.3759 | 0.8205 | +0.4446 |
| Contact name | 0.4684 | 0.8101 | +0.3418 |
| Job titles | 0.5995 | 0.7851 | +0.1857 |
| Experience job title | 0.6418 | 0.8023 | +0.1605 |
| Education institution | 0.2682 | 0.4022 | +0.1341 |
| Experience company | 0.5194 | 0.5970 | +0.0776 |
| Education field | 0.6395 | 0.7075 | +0.0680 |
| Experience location | 0.6330 | 0.6728 | +0.0398 |
| Skills | 0.4217 | 0.4512 | +0.0295 |
| Experience end date | 0.6859 | 0.7139 | +0.0280 |
| Education degree | 0.7168 | 0.7283 | +0.0116 |
| Experience start date | 0.6992 | 0.7100 | +0.0108 |

Fields not listed in the table were unchanged. No field's F1 score decreased.

### Interpretation

The largest non-location gains occurred for names and job titles, confirming that capitalization differences had substantially understated extraction quality in the raw exact-match baseline. The contact-location increase also reflects a deliberate contract correction: street and postal details are unnecessary personal information, while locality is sufficient for downstream matching.

Normalization did not repair genuine extraction problems. Projects, certification years, missing entities, incorrect companies, and materially different values remained poor. The normalized score should therefore be presented beside the raw baseline, not as evidence that the model itself improved. It measures the same model output under a fairer and more privacy-aligned comparison policy.
