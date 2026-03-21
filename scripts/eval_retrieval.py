import json
import math
from collections import defaultdict
from pathlib import Path

DATA = Path("data/processed")
OUT = Path("outputs")

def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def dcg(rels, k):
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(rels[:k]))

def ndcg_at_k(rels, k=10):
    ideal = sorted(rels, reverse=True)
    denom = dcg(ideal, k)
    return dcg(rels, k) / denom if denom > 0 else 0.0

def main():
    qrels = load_jsonl(DATA / "qrels.jsonl")
    runs = load_jsonl(OUT / "retrieval_top10.jsonl")

    relmap = defaultdict(dict)
    for row in qrels:
        relmap[row["query_id"]][row["doc_id"]] = row["relevance"]

    scores = []
    for run in runs:
        qid = run["query_id"]
        rels = [relmap[qid].get(doc_id, 0) for doc_id, _ in run["results"]]
        scores.append(ndcg_at_k(rels, 10))

    print({"nDCG@10": sum(scores) / len(scores) if scores else 0.0})

if __name__ == "__main__":
    main()
