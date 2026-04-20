"""
Build qualitative review examples from generation + judge outputs.

Usage:
    PYTHONPATH=. python scripts/build_qualitative_review.py --retriever bge
    PYTHONPATH=. python scripts/build_qualitative_review.py --retriever colpali --out_dir outputs_full --n_examples 8
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

DATA = Path("data/processed")

RETRIEVER_FILES = {
    "contriever": "flexrag_retrieval_top10.jsonl",
    "bge":        "bge_retrieval_top10.jsonl",
    "clip":       "clip_retrieval_top10.jsonl",
    "colpali":    "colpali_retrieval_top10.jsonl",
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def truncate(text: str, limit: int = 700) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text[:limit].rstrip() + " ..." if len(text) > limit else text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retriever", default="bge",
                        choices=["contriever", "bge", "clip", "colpali"])
    parser.add_argument("--out_dir", default="outputs_full")
    parser.add_argument("--in_dir", default="outputs_hopper/outputs",
                        help="Directory containing retrieval top10 files")
    parser.add_argument("--n_examples", type=int, default=8)
    args = parser.parse_args()

    out_dir = Path(args.out_dir) / args.retriever
    in_dir = Path(args.in_dir)

    corpus = {row["id"]: row for row in load_jsonl(DATA / "corpus.jsonl")}
    retrieval_runs = {
        str(row["query_id"]): row
        for row in load_jsonl(in_dir / RETRIEVER_FILES[args.retriever])
    }
    predictions = load_jsonl(out_dir / "predictions.jsonl")
    judge_rows = {
        str(row["query_id"]): row
        for row in load_jsonl(out_dir / "llm_judge_per_example.jsonl")
    }

    review_rows = []

    for row in predictions[:args.n_examples]:
        query_id = str(row["query_id"])
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

    json_path = out_dir / f"qualitative_review_{args.retriever}.json"
    md_path = out_dir / f"qualitative_review_{args.retriever}.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(review_rows, f, indent=2, ensure_ascii=False)

    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# Qualitative Review — {args.retriever} ({args.n_examples} Examples)\n\n")
        for i, row in enumerate(review_rows, start=1):
            f.write(f"## Example {i}\n\n")
            f.write(f"**Question:** {row['question']}\n\n")
            f.write("**Retrieved Pages:**\n\n")
            for page in row["retrieved_pages"]:
                f.write(f"- Rank {page['rank']} | doc={page['doc_id']} | score={page['score']:.4f}\n")
                f.write(f"  - Page {page['page_number']}: {page['text_preview']}\n")
            f.write(f"\n**Prediction:** {row['prediction']}\n\n")
            f.write("**References:**\n")
            for ref in row["references"]:
                f.write(f"- {ref}\n")
            f.write(f"\n**Judge:** {row['judge_verdict']} — {row['judge_reason']}\n\n---\n\n")

    print(f"Saved {json_path}")
    print(f"Saved {md_path}")


if __name__ == "__main__":
    main()
