import json
from pathlib import Path
from typing import List, Dict, Any

DATA = Path("data/processed")
OUT = Path("outputs")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def truncate(text: str, limit: int = 700) -> str:
    text = (text or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " ..."


def main() -> None:
    corpus = {row["id"]: row for row in load_jsonl(DATA / "corpus.jsonl")}
    retrieval_runs = {row["query_id"]: row for row in load_jsonl(OUT / "flexrag_retrieval_top10.jsonl")}
    predictions = load_jsonl(OUT / "predictions.jsonl")
    judge_rows = {row["query_id"]: row for row in load_jsonl(OUT / "llm_judge_per_example.jsonl")}

    review_rows = []

    for row in predictions[:20]:
        query_id = row["query_id"]
        retrieval = retrieval_runs.get(query_id, {"results": []})
        judge = judge_rows.get(query_id, {})

        retrieved_pages = []
        for rank, item in enumerate(retrieval.get("results", [])[:3], start=1):
            doc_id, score = item
            doc = corpus.get(str(doc_id), {})
            retrieved_pages.append({
                "rank": rank,
                "doc_id": str(doc_id),
                "score": float(score),
                "title": doc.get("title", ""),
                "page_number": doc.get("page_number"),
                "text_preview": truncate(doc.get("text", ""), 700),
            })

        review_rows.append({
            "query_id": query_id,
            "question": row.get("question", ""),
            "retrieved_pages": retrieved_pages,
            "prediction": row.get("prediction", ""),
            "references": row.get("answers", []),
            "judge_verdict": judge.get("judge_verdict", ""),
            "judge_reason": judge.get("judge_reason", ""),
        })

    json_path = OUT / "qualitative_review_top20.json"
    md_path = OUT / "qualitative_review_top20.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(review_rows, f, indent=2, ensure_ascii=False)

    with md_path.open("w", encoding="utf-8") as f:
        f.write("# Qualitative Review (20 Examples)\n\n")
        for i, row in enumerate(review_rows, start=1):
            f.write(f"## Example {i}\n\n")
            f.write(f"**Query ID:** {row['query_id']}\n\n")
            f.write(f"**Question:** {row['question']}\n\n")

            f.write("**Retrieved Pages:**\n\n")
            for page in row["retrieved_pages"]:
                f.write(f"- Rank {page['rank']} | doc_id={page['doc_id']} | score={page['score']:.4f}\n")
                f.write(f"  - Title: {page['title']}\n")
                f.write(f"  - Page: {page['page_number']}\n")
                f.write(f"  - Text Preview: {page['text_preview']}\n")
            f.write("\n")

            f.write(f"**Prediction:** {row['prediction']}\n\n")
            f.write("**References:**\n")
            for ref in row["references"]:
                f.write(f"- {ref}\n")
            if not row["references"]:
                f.write("- None\n")
            f.write("\n")

            f.write(f"**Judge Verdict:** {row['judge_verdict']}\n\n")
            f.write(f"**Judge Reason:** {row['judge_reason']}\n\n")
            f.write("---\n\n")

    print(f"Saved {json_path}")
    print(f"Saved {md_path}")


if __name__ == "__main__":
    main()