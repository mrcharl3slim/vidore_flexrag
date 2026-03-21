import json
from pathlib import Path
from rank_bm25 import BM25Okapi

DATA = Path("data/processed")
OUT = Path("outputs")
OUT.mkdir(parents=True, exist_ok=True)

def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def main():
    corpus = load_jsonl(DATA / "corpus.jsonl")
    queries = load_jsonl(DATA / "queries.jsonl")

    tokenized_corpus = [doc["text"].lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)

    results = []
    for q in queries:
        tokens = q["question"].lower().split()
        scores = bm25.get_scores(tokens)
        ranked = sorted(
            zip([doc["doc_id"] for doc in corpus], scores),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        results.append({
            "query_id": q["query_id"],
            "results": [[doc_id, float(score)] for doc_id, score in ranked]
        })

    with open(OUT / "retrieval_top10.jsonl", "w", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row) + "\n")

    print("Saved retrieval_top10.jsonl")

if __name__ == "__main__":
    main()
