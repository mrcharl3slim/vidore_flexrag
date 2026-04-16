"""
Run retrieval using the BGE-large FlexRAG retriever (BM25 + BGE dense, RRF).

Output: outputs/bge_retrieval_top10.jsonl

Prerequisite: run build_bge_retriever.py first.

Usage:
    python scripts/run_bge_retrieval.py
"""

import json
from pathlib import Path

from flexrag.retriever import FlexRetriever, FlexRetrieverConfig

DATA = Path("data/processed")
OUT = Path("outputs")
OUT.mkdir(parents=True, exist_ok=True)

RETRIEVER_PATH = "data/processed/bge_retriever"
TOP_K = 10


def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def save_jsonl(rows, path: Path):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    queries = load_jsonl(DATA / "queries.jsonl")
    retriever = FlexRetriever(
        FlexRetrieverConfig(
            retriever_path=RETRIEVER_PATH,
            used_indexes=["bm25", "dense"],
        )
    )

    runs = []
    for i, q in enumerate(queries, start=1):
        results = retriever.search(q["question"], top_k=TOP_K)[0]
        ranked = [[str(r.context_id), float(getattr(r, "score", 0.0))] for r in results]
        runs.append({
            "query_id": str(q["query_id"]),
            "question": q["question"],
            "results": ranked,
        })
        if i % 100 == 0:
            print(f"  {i}/{len(queries)} queries done")

    save_jsonl(runs, OUT / "bge_retrieval_top10.jsonl")
    print(f"Saved {OUT / 'bge_retrieval_top10.jsonl'}")


if __name__ == "__main__":
    main()
