## judge_batch prompt variants

| # | config | composite_score | judge_schema_score | judge_calibration_score | latency_ms | pass_rate |
|---|---|---|---|---|---|---|
| 1 | judge_comparative.txt **← best** | 0.2750 | 0.5000 | 0.5000 | 21572.4167 | 0.0000 |
| 2 | judge_narrative.txt | 0.2060 | 0.5000 | 0.5000 | 28081.9167 | 0.0000 |
| 3 | judge_baseline.txt | -0.0668 | 0.0000 | 0.0000 | 27871.9167 | 0.0000 |
| 4 | judge_weighted_criteria.txt | -0.0811 | 0.0000 | 0.0000 | 29219.4167 | 0.0000 |
| 5 | judge_strict_rubric.txt | -0.0942 | 0.0000 | 0.0000 | 30450.2500 | 0.0000 |
| 6 | judge_chain_of_thought.txt | -0.1500 | 0.0000 | 0.0000 | 35715.5833 | 0.0000 |
