import json
from pathlib import Path
from app.generator import OllamaGenerator

DATA = Path("data/processed")
OUT = Path("outputs")

def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def build_prompt(question, contexts):
    joined = "\n\n".join(f"[Context {i+1}]\n{c}" for i, c in enumerate(contexts))
    return f"""Answer the question using only the provided context.

Question:
{question}

Context:
{joined}

If the answer is not supported, say "Insufficient evidence."

Answer:
"""

def main():
    corpus = {d["doc_id"]: d for d in load_jsonl(DATA / "corpus.jsonl")}
    queries = {q["query_id"]: q for q in load_jsonl(DATA / "queries.jsonl")}
    runs = load_jsonl(OUT / "retrieval_top10.jsonl")

    gen = OllamaGenerator()
    outputs = []

    for row in runs[:50]:  # keep small first
        q = queries[row["query_id"]]
        top_ids = [doc_id for doc_id, _ in row["results"][:3]]
        contexts = [corpus[doc_id]["text"] for doc_id in top_ids if doc_id in corpus]

        pred = gen.generate(build_prompt(q["question"], contexts))
        outputs.append({
            "query_id": q["query_id"],
            "question": q["question"],
            "prediction": pred,
            "answers": q["answers"],
            "context_doc_ids": top_ids,
        })

    with open(OUT / "predictions.jsonl", "w", encoding="utf-8") as f:
        for row in outputs:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("Saved predictions.jsonl")

if __name__ == "__main__":
    main()
