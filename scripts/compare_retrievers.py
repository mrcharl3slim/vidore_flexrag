"""
Compare retrieval and generation results across all retrievers.

Reads all available metrics files and prints a side-by-side table
against published ViDoRe V3 leaderboard reference scores.

ViDoRe leaderboard: https://huggingface.co/spaces/vidore/vidore-leaderboard
Primary metric: nDCG@10 (graded relevance)

Usage:
    python scripts/compare_retrievers.py
"""

import json
from pathlib import Path

OUT = Path("outputs")

# Published ViDoRe V3 leaderboard reference scores for vidore_v3_computer_science.
# Source: https://huggingface.co/blog/QuentinJG/introducing-vidore-v3
VIDORE_LEADERBOARD = [
    {
        "retriever": "nemo-colembed-3b (leaderboard best)",
        "modality": "text query → image corpus",
        "nDCG@5": None, "nDCG@10": 0.778,
        "Recall@5": None, "Recall@10": None, "MRR@10": None,
        "source": "ViDoRe V3 leaderboard",
    },
    {
        "retriever": "BM25 baseline (leaderboard)",
        "modality": "text query → text corpus",
        "nDCG@5": None, "nDCG@10": 0.293,
        "Recall@5": None, "Recall@10": None, "MRR@10": None,
        "source": "ViDoRe V3 leaderboard",
    },
]

RETRIEVAL_FILES = [
    (OUT / "retrieval_metrics.json",      "retrieval"),
    (OUT / "bge_retrieval_metrics.json",  "bge_retrieval"),
    (OUT / "clip_retrieval_metrics.json", "clip_retrieval"),
    (OUT / "colpali_retrieval_metrics.json", "colpali_retrieval"),
]

GENERATION_FILES = [
    OUT / "generation_metrics.json",
    OUT / "llm_judge_metrics.json",
]


def load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def fmt(val) -> str:
    if val is None:
        return "    —  "
    return f"{val:.4f}"


def print_retrieval_table(rows: list[dict]):
    metrics = ["nDCG@5", "nDCG@10", "Recall@5", "Recall@10", "MRR@10"]
    col_w = 9
    name_w = max(len(r["retriever"]) for r in rows) + 2
    mod_w = 30

    header = f"  {'Retriever':<{name_w}}  {'Modality':<{mod_w}}  " + "  ".join(
        f"{m:>{col_w}}" for m in metrics
    )
    sep = "  " + "─" * (len(header) - 2)
    print(header)
    print(sep)

    for row in rows:
        vals = "  ".join(f"{fmt(row.get(m)):>{col_w}}" for m in metrics)
        src = f"  ← {row['source']}" if row.get("source") else ""
        print(f"  {row['retriever']:<{name_w}}  {row.get('modality',''):<{mod_w}}  {vals}{src}")


def main():
    print(f"\n{'═'*110}")
    print("  ViDoRe V3 Computer Science — Full Evaluation Report")
    print(f"  Dataset: vidore/vidore_v3_computer_science  |  1290 queries  |  1360 corpus pages")
    print(f"{'═'*110}")

    # ── Retrieval ──────────────────────────────────────────────────────────────
    print("\n── Retrieval ──\n")
    rows = []
    for path, label in RETRIEVAL_FILES:
        m = load_json(path)
        if m:
            rows.append(m)
        else:
            print(f"  [not yet run] {path.name}")

    rows.extend(VIDORE_LEADERBOARD)
    if rows:
        print_retrieval_table(rows)

    # ── Generation ────────────────────────────────────────────────────────────
    gen = load_json(OUT / "generation_metrics.json")
    judge = load_json(OUT / "llm_judge_metrics.json")

    if gen or judge:
        print("\n── Generation (qwen2.5, top-5 contexts, 50 queries) ──\n")
        print(f"  {'Metric':<30} {'Score':>8}")
        print(f"  {'─'*30} {'─'*8}")
        if gen:
            print(f"  {'Exact Match':<30} {gen.get('ExactMatch', 0):>8.4f}")
            print(f"  {'Token F1':<30} {gen.get('TokenF1', 0):>8.4f}")
            print(f"  {'ROUGE-L':<30} {gen.get('ROUGE-L', 0):>8.4f}")
            print(f"  {'Insufficient Evidence Rate':<30} {gen.get('InsufficientEvidenceRate', 0):>8.4f}")
        if judge:
            print(f"  {'LLM Judge Accuracy':<30} {judge.get('LLMJudgeAccuracy', 0):>8.4f}")

    print(f"\n{'─'*110}")
    print("  ViDoRe leaderboard (all models): https://huggingface.co/spaces/vidore/vidore-leaderboard")
    print(f"{'─'*110}\n")


if __name__ == "__main__":
    main()
