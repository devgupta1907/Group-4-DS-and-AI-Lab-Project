"""Standard IR metrics for the ranking eval. Pure math, no dependencies
beyond the stdlib `math` module."""
import math


def recall_at_k(ranked_job_ids: list[str], relevant_ids: set[str], k: int = 10) -> float:
    if not relevant_ids:
        return 0.0
    top_k = set(ranked_job_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)


def precision_at_k(ranked_job_ids: list[str], relevant_ids: set[str], k: int = 10) -> float:
    top_k = ranked_job_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for j in top_k if j in relevant_ids)
    return hits / min(k, len(top_k)) if top_k else 0.0


def spearman_rank_correlation(predicted_rank_by_id: dict[str, int], true_rank_by_id: dict[str, int]) -> float:
    """Standard Spearman's rho over the ids common to both rankings.
    +1 = identical order, -1 = exactly reversed, 0 = no correlation.
    Recommended by the golden dataset's own README alongside Precision@5
    and NDCG@10 for evaluating a full ranked-list output."""
    common = [jid for jid in true_rank_by_id if jid in predicted_rank_by_id]
    n = len(common)
    if n < 2:
        return 0.0
    d_sq_sum = sum((predicted_rank_by_id[jid] - true_rank_by_id[jid]) ** 2 for jid in common)
    return 1 - (6 * d_sq_sum) / (n * (n ** 2 - 1))


def ndcg_at_k(ranked_job_ids: list[str], relevance_by_id: dict[str, float], k: int = 10) -> float:
    def dcg(ids: list[str]) -> float:
        return sum(
            relevance_by_id.get(jid, 0) / math.log2(i + 2)
            for i, jid in enumerate(ids[:k])
        )

    actual = dcg(ranked_job_ids)
    ideal_order = sorted(relevance_by_id, key=lambda j: relevance_by_id[j], reverse=True)
    ideal = dcg(ideal_order)
    return actual / ideal if ideal > 0 else 0.0
