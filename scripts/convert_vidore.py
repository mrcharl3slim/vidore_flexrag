from datasets import load_dataset
import json
from pathlib import Path

OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

def save_jsonl(rows, path: Path):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

def main():
    corpus_ds = load_dataset("vidore/vidore_v3_computer_science", "corpus", split="test")
    queries_ds = load_dataset("vidore/vidore_v3_computer_science", "queries", split="test")
    qrels_ds = load_dataset("vidore/vidore_v3_computer_science", "qrels", split="test")

    corpus_rows = []
    for row in corpus_ds:
        corpus_rows.append({
            "id": str(row["corpus_id"]),
            "title": str(row.get("doc_id", "")),
            "text": row.get("markdown", "") or "",
            "page_number": row.get("page_number_in_doc"),
        })

    query_rows = []
    for row in queries_ds:
        query_rows.append({
            "query_id": str(row["query_id"]),
            "question": row["query"],
            "answers": row.get("raw_answers") or ([row["answer"]] if row.get("answer") else []),
        })

    qrel_rows = []
    for row in qrels_ds:
        qrel_rows.append({
            "query_id": str(row["query_id"]),
            "doc_id": str(row["corpus_id"]),
            "relevance": int(row["score"]),
        })

    save_jsonl(corpus_rows, OUT / "corpus.jsonl")
    save_jsonl(query_rows, OUT / "queries.jsonl")
    save_jsonl(qrel_rows, OUT / "qrels.jsonl")

    print("Saved processed ViDoRe files.")

if __name__ == "__main__":
    main()
