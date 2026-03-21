import json
import math
from collections import defaultdict
from pathlib import Path

DATA = Path("data/processed")
OUT = Path("outputs")

def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
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
    runs = load_jsonl(OUT / "flexrag_retrieval_top10.jsonl")

    # qrel_map[query_id][doc_id] = relevance
    qrel_map = defaultdict(dict)
    for row in qrels:
        qrel_map[str(row["query_id"])][str(row["doc_id"])] = int(row["relevance"])

    ndcgs = []
    recalls = []
    mrrs = []
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

        ndcgs.append(ndcg_at_k(graded_rels, 10))
        recalls.append(recall_at_k(binary_rels, total_relevant, 10))
        mrrs.append(mrr_at_k(binary_rels, 10))

    metrics = {
        "num_queries_evaluated": len(ndcgs),
        "num_queries_skipped": skipped,
        "nDCG@10": sum(ndcgs) / len(ndcgs) if ndcgs else 0.0,
        "Recall@10": sum(recalls) / len(recalls) if recalls else 0.0,
        "MRR@10": sum(mrrs) / len(mrrs) if mrrs else 0.0,
    }

    print(json.dumps(metrics, indent=2))

    with (OUT / "retrieval_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"Saved {OUT / 'retrieval_metrics.json'}")

if __name__ == "__main__":
    main()