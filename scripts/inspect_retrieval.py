import json
from pathlib import Path

DATA = Path("data/processed")
OUT = Path("outputs")

def load_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def main():
    queries = {row["query_id"]: row for row in load_jsonl(DATA / "queries.jsonl")}
    corpus = {row["id"]: row for row in load_jsonl(DATA / "corpus.jsonl")}
    runs = load_jsonl(OUT / "flexrag_retrieval_top10.jsonl")

    for run in runs[:5]:
        qid = run["query_id"]
        print("=" * 100)
        print("Query:", queries[qid]["question"])
        for rank, (doc_id, score) in enumerate(run["results"][:3], start=1):
            doc = corpus.get(doc_id, {})
            print(f"\nRank {rank} | doc_id={doc_id} | score={score:.4f}")
            print("Title:", doc.get("title"))
            print("Page:", doc.get("page_number"))
            print("Text preview:", (doc.get("text", "")[:400]).replace("\n", " "))

if __name__ == "__main__":
    main()