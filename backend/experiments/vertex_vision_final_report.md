# Resume Parsing Evaluation and Improvement

## 1. Executive Summary

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
