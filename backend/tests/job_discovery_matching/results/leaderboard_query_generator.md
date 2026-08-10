## query_generator prompt variants

| # | config | composite_score | query_schema_score | query_diversity_score | latency_ms | pass_rate |
|---|---|---|---|---|---|---|
| 1 | query_gen_boolean_operators.txt **← best** | 0.5102 | 1.0000 | 0.8010 | 19.1429 | 1.0000 |
| 2 | query_gen_roleplay.txt | 0.4306 | 1.0000 | 0.8010 | 26.3214 | 1.0000 |
| 3 | query_gen_chain_of_thought.txt | 0.4255 | 1.0000 | 0.8010 | 26.7857 | 1.0000 |
| 4 | query_gen_few_shot.txt | 0.3986 | 1.0000 | 0.8010 | 29.2143 | 1.0000 |
| 5 | query_gen_concise.txt | 0.3800 | 1.0000 | 0.8010 | 30.8929 | 1.0000 |
| 6 | query_gen_baseline.txt | 0.3646 | 1.0000 | 0.8010 | 32.2857 | 1.0000 |
| 7 | query_gen_minimal.txt | 0.3602 | 1.0000 | 0.8010 | 32.6786 | 1.0000 |
