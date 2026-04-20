"""
Compute EM, Token F1, and ROUGE-L for a predictions.jsonl file.

Usage:
    PYTHONPATH=. python scripts/eval_vidore_generation.py --retriever bge
    PYTHONPATH=. python scripts/eval_vidore_generation.py --retriever colpali --out_dir outputs_full
"""

import argparse
import json
import re
from pathlib import Path
from typing import List, Dict, Any

from rouge_score import rouge_scorer


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", "", text)
    return text


def exact_match(prediction: str, references: List[str]) -> float:
    pred = normalize_text(prediction)
    refs = [normalize_text(r) for r in references if r and r.strip()]
    return 1.0 if pred in refs else 0.0


def token_f1(prediction: str, references: List[str]) -> float:
    pred_tokens = normalize_text(prediction).split()
    if not pred_tokens:
        return 0.0
    best_f1 = 0.0
    for ref in references:
        ref_tokens = normalize_text(ref).split()
        if not ref_tokens:
            continue
        common = {}
        for tok in pred_tokens:
            if tok in ref_tokens:
                common[tok] = min(pred_tokens.count(tok), ref_tokens.count(tok))
        num_same = sum(common.values())
        if num_same == 0:
            continue
        precision = num_same / len(pred_tokens)
        recall = num_same / len(ref_tokens)
        best_f1 = max(best_f1, 2 * precision * recall / (precision + recall))
    return best_f1


def rouge_l_score(prediction: str, references: List[str]) -> float:
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    best = 0.0
    for ref in references:
        if not ref or not ref.strip():
            continue
        best = max(best, scorer.score(ref, prediction)["rougeL"].fmeasure)
    return best


def unsupported_rate(predictions: List[Dict[str, Any]]) -> float:
    flagged = sum(
        1 for r in predictions
        if r.get("prediction", "").strip().lower() in ("insufficient evidence.", "insufficient evidence")
    )
    return flagged / len(predictions) if predictions else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retriever", default="bge",
                        choices=["contriever", "bge", "clip", "colpali"])
    parser.add_argument("--out_dir", default="outputs_full")
    args = parser.parse_args()

    predictions_path = Path(args.out_dir) / args.retriever / "predictions.jsonl"
    predictions = load_jsonl(predictions_path)

    em_scores, f1_scores, rouge_scores = [], [], []
    per_example = []

    for row in predictions:
        pred = row.get("prediction", "") or ""
        refs = row.get("answers", []) or []

        em = exact_match(pred, refs)
        f1 = token_f1(pred, refs)
        rouge_l = rouge_l_score(pred, refs)

        em_scores.append(em)
        f1_scores.append(f1)
        rouge_scores.append(rouge_l)
        per_example.append({**row, "exact_match": em, "token_f1": f1, "rougeL": rouge_l})

    metrics = {
        "retriever": args.retriever,
        "num_predictions": len(predictions),
        "ExactMatch": round(sum(em_scores) / len(em_scores), 4) if em_scores else 0.0,
        "TokenF1": round(sum(f1_scores) / len(f1_scores), 4) if f1_scores else 0.0,
        "ROUGE-L": round(sum(rouge_scores) / len(rouge_scores), 4) if rouge_scores else 0.0,
        "InsufficientEvidenceRate": round(unsupported_rate(predictions), 4),
    }

    print(json.dumps(metrics, indent=2))

    out_dir = Path(args.out_dir) / args.retriever
    with (out_dir / "generation_metrics.json").open("w") as f:
        json.dump(metrics, f, indent=2)
    with (out_dir / "generation_per_example.jsonl").open("w") as f:
        for row in per_example:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Saved {out_dir / 'generation_metrics.json'}")


if __name__ == "__main__":
    main()
