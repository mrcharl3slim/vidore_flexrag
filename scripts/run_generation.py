"""
Generate answers using qwen2.5 with top-5 retrieved contexts.

Usage:
    PYTHONPATH=. python scripts/run_generation.py --retriever bge
    PYTHONPATH=. python scripts/run_generation.py --retriever colpali --n_queries 1290
    PYTHONPATH=. python scripts/run_generation.py --retriever bge --in_dir outputs_hopper/outputs --out_dir outputs_full
"""

import argparse
import json
from pathlib import Path

from app.generator import OllamaGenerator

DATA = Path("data/processed")
TOP_K_CONTEXTS = 5

RETRIEVER_FILES = {
    "contriever": "flexrag_retrieval_top10.jsonl",
    "bge":        "bge_retrieval_top10.jsonl",
    "clip":       "clip_retrieval_top10.jsonl",
    "colpali":    "colpali_retrieval_top10.jsonl",
}


def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def build_prompt(question: str, contexts: list) -> str:
    joined = "\n\n".join(f"[Context {i+1}]\n{c}" for i, c in enumerate(contexts))
    return f"""Answer the question using only the provided context. Be concise and direct.

Question:
{question}

Context:
{joined}

If the answer is not supported by the context, say "Insufficient evidence."

Answer:
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retriever", choices=list(RETRIEVER_FILES), default="bge",
                        help="Which retriever's top-10 file to use")
    parser.add_argument("--in_dir", default="outputs_hopper/outputs",
                        help="Directory containing *_retrieval_top10.jsonl files")
    parser.add_argument("--out_dir", default="outputs_full",
                        help="Directory to write predictions.jsonl")
    parser.add_argument("--n_queries", type=int, default=0,
                        help="Number of queries to process (0 = all)")
    parser.add_argument("--model", default="qwen2.5:latest",
                        help="Ollama model name")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir) / args.retriever
    out_dir.mkdir(parents=True, exist_ok=True)

    corpus = {d["id"]: d for d in load_jsonl(DATA / "corpus.jsonl")}
    queries = {str(q["query_id"]): q for q in load_jsonl(DATA / "queries.jsonl")}

    retrieval_file = in_dir / RETRIEVER_FILES[args.retriever]
    runs = load_jsonl(retrieval_file)
    if args.n_queries > 0:
        runs = runs[:args.n_queries]

    print(f"Retriever : {args.retriever}")
    print(f"Input     : {retrieval_file}")
    print(f"Output    : {out_dir}")
    print(f"Queries   : {len(runs)}")

    gen = OllamaGenerator(model=args.model)
    outputs = []

    for i, row in enumerate(runs, start=1):
        qid = str(row["query_id"])
        q = queries[qid]
        top_ids = [str(doc_id) for doc_id, _ in row["results"][:TOP_K_CONTEXTS]]

        contexts = []
        for doc_id in top_ids:
            if doc_id not in corpus:
                continue
            text = corpus[doc_id].get("text", "").strip()
            if text:
                contexts.append(text)

        pred = gen.generate(build_prompt(q["question"], contexts))
        outputs.append({
            "query_id": qid,
            "question": q["question"],
            "prediction": pred,
            "answers": q["answers"],
            "context_doc_ids": top_ids,
        })

        if i % 50 == 0:
            print(f"  {i}/{len(runs)} done")

    out_path = out_dir / "predictions.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for row in outputs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
