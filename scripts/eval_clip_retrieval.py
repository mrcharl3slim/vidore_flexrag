"""
Evaluate CLIP retrieval results against ViDoRe qrels.

Reads outputs/clip_retrieval_top10.jsonl and computes nDCG@5, nDCG@10,
Recall@5, Recall@10, MRR@10 — matching the metrics reported on the
ViDoRe leaderboard (https://huggingface.co/spaces/vidore/vidore-leaderboard).
Saves results to outputs/clip_retrieval_metrics.json.

Usage:
    python scripts/eval_clip_retrieval.py
"""

import json
import math
from collections import defaultdict
from pathlib import Path

DATA = Path("data/processed")
OUT = Path("outputs")


def load_jsonl(path: Path):
    with path.open() as f:
        return [json.loads(line) for line in f]


def dcg_at_k(relevances, k):
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances[:k]))


def ndcg_at_k(relevances, k=10):
    ideal = sorted(relevances, reverse=True)
    ideal_dcg = dcg_at_k(ideal, k)
    if ideal_dcg == 0:
        return 0.0
    return dcg_at_k(relevances, k) / ideal_dcg


def recall_at_k(binary_rels, total_relevant, k=10):
    if total_relevant == 0:
        return 0.0
    return sum(binary_rels[:k]) / total_relevant


def mrr_at_k(binary_rels, k=10):
    for idx, rel in enumerate(binary_rels[:k], start=1):
        if rel > 0:
            return 1.0 / idx
    return 0.0


def main():
    qrels = load_jsonl(DATA / "qrels.jsonl")
    runs = load_jsonl(OUT / "clip_retrieval_top10.jsonl")

    qrel_map = defaultdict(dict)
    for row in qrels:
        qrel_map[str(row["query_id"])][str(row["doc_id"])] = int(row["relevance"])

    ndcgs5, ndcgs10, recalls5, recalls10, mrrs = [], [], [], [], []
    skipped = 0

    for run in runs:
        qid = str(run["query_id"])
        if qid not in qrel_map:
            skipped += 1
            continue

        rels_for_query = qrel_map[qid]
        ranked_doc_ids = [str(doc_id) for doc_id, _score in run["results"]]

        graded_rels = [rels_for_query.get(doc_id, 0) for doc_id in ranked_doc_ids]
        binary_rels = [1 if rel > 0 else 0 for rel in graded_rels]
        total_relevant = sum(1 for v in rels_for_query.values() if v > 0)

        ndcgs5.append(ndcg_at_k(graded_rels, 5))
        ndcgs10.append(ndcg_at_k(graded_rels, 10))
        recalls5.append(recall_at_k(binary_rels, total_relevant, 5))
        recalls10.append(recall_at_k(binary_rels, total_relevant, 10))
        mrrs.append(mrr_at_k(binary_rels, 10))

    n = len(ndcgs10)
    metrics = {
        "retriever": "hf_clip (openai/clip-vit-base-patch32)",
        "modality": "text query → image corpus",
        "num_queries_evaluated": n,
        "num_queries_skipped": skipped,
        "nDCG@5":    round(sum(ndcgs5)   / n, 4) if n else 0.0,
        "nDCG@10":   round(sum(ndcgs10)  / n, 4) if n else 0.0,
        "Recall@5":  round(sum(recalls5) / n, 4) if n else 0.0,
        "Recall@10": round(sum(recalls10)/ n, 4) if n else 0.0,
        "MRR@10":    round(sum(mrrs)     / n, 4) if n else 0.0,
    }

    print(json.dumps(metrics, indent=2))

    out_path = OUT / "clip_retrieval_metrics.json"
    with out_path.open("w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
