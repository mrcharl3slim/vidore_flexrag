import json
import re
from pathlib import Path
from typing import List, Dict, Any

from rouge_score import rouge_scorer

OUT = Path("outputs")


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
    if not refs:
        return 0.0
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
            f1 = 0.0
        else:
            precision = num_same / len(pred_tokens)
            recall = num_same / len(ref_tokens)
            f1 = 2 * precision * recall / (precision + recall)

        best_f1 = max(best_f1, f1)

    return best_f1


def rouge_l_score(prediction: str, references: List[str]) -> float:
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    best = 0.0
    for ref in references:
        if not ref or not ref.strip():
            continue
        score = scorer.score(ref, prediction)["rougeL"].fmeasure
        best = max(best, score)
    return best


def unsupported_rate(predictions: List[Dict[str, Any]]) -> float:
    flagged = 0
    total = len(predictions)
    for row in predictions:
        pred = row.get("prediction", "").strip().lower()
        if pred == "insufficient evidence." or pred == "insufficient evidence":
            flagged += 1
    return flagged / total if total else 0.0


def main() -> None:
    predictions_path = OUT / "predictions.jsonl"
    predictions = load_jsonl(predictions_path)

    em_scores = []
    f1_scores = []
    rouge_scores = []

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

        per_example.append({
            "query_id": row.get("query_id"),
            "question": row.get("question"),
            "prediction": pred,
            "answers": refs,
            "exact_match": em,
            "token_f1": f1,
            "rougeL": rouge_l,
            "context_doc_ids": row.get("context_doc_ids", []),
        })

    metrics = {
        "num_predictions": len(predictions),
        "ExactMatch": sum(em_scores) / len(em_scores) if em_scores else 0.0,
        "TokenF1": sum(f1_scores) / len(f1_scores) if f1_scores else 0.0,
        "ROUGE-L": sum(rouge_scores) / len(rouge_scores) if rouge_scores else 0.0,
        "InsufficientEvidenceRate": unsupported_rate(predictions),
    }

    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    with (OUT / "generation_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    with (OUT / "generation_per_example.jsonl").open("w", encoding="utf-8") as f:
        for row in per_example:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Saved {OUT / 'generation_metrics.json'}")
    print(f"Saved {OUT / 'generation_per_example.jsonl'}")


if __name__ == "__main__":
    main()