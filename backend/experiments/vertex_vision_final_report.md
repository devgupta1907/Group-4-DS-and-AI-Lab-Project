# Resume Parsing Evaluation and Improvement

## 1. Final Outcome

The selected configuration used Gemini 3.5 Flash to process all 86 resume images. Its source-faithful prompt preserved complete competency phrases while splitting only explicit enumerations of named tools or technologies. The acceptance target was section-level micro-F1 of 0.75, reported to two decimal places.

| Section | F1 | Result |
|---|---:|---|
| Contact | 0.98 | Pass |
| Skills | 0.82 | Pass |
| Education | 0.92 | Pass |
| Experience | 0.98 | Pass |
| Projects | 0.88 | Pass |
| Certifications | 0.75 | Pass at reported precision |

The unrounded certification F1 was 0.7472. Precision, recall, confusion evidence, latency and cost are presented in the corresponding analytical sections.

## 2. Evaluation Methodology

### Dataset and gold-standard review

### Metrics and acceptance criterion

### Experiment tracking and reproducibility

## 3. Gemma 4 Baseline

### Baseline configuration

### Baseline results

### Baseline failure evidence

## 4. Schema-Adherence Failure and Correction

### Observed failure

### Root cause

### Vertex AI provider correction

### Before-and-after evidence

## 5. Field-Level Error Analysis

### Contact and location privacy

### Education

### Experience

### Skills

### Projects

### Certifications

## 6. Deterministic Normalization Experiments

### Evidence supporting normalization

### Implemented normalization rules

### Raw versus normalized results

### Boundaries of normalization

## 7. Prompt Experiments

### Source-faithful extraction

### Atomic versus complete-line skills

### Project-boundary instructions

### Certification-boundary instructions

### Accepted and rejected experiments

## 8. Experiment Progression

![Experiment progression against the current gold](report_assets/experiment_progression.png)

*Figure 1. Diagnostic mean of the six section-level normalized micro-F1 scores, with every saved experiment rescored against the current effective gold. The figure shows the transition from Gemma experiments to Gemini experiments and retains regressions from rejected prompts.*

## 9. Gemma 4 versus Gemini 3.5 Flash

### Extraction quality

### Latency and throughput

### Token usage and estimated cost

### Schema adherence and operational reliability

## 10. Final Results Against the Acceptance Threshold

### Section-level precision, recall and F1

### Confusion examples

### Experience-description analysis

## 11. Validity and Limitations

### Gold-review status

### Development-benchmark leakage

### Inference nondeterminism

### Cost-estimation limitations

## 12. Conclusion and Production Recommendation
