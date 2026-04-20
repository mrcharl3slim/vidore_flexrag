"""
LLM-as-judge evaluation for generation predictions.

Usage:
    PYTHONPATH=. python scripts/eval_vidore_llm_judge.py --retriever bge
    PYTHONPATH=. python scripts/eval_vidore_llm_judge.py --retriever colpali --out_dir outputs_full
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any

import requests

_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def ask_ollama_judge(
    question: str,
    prediction: str,
    references: List[str],
    model_name: str = "qwen2.5:latest",
    base_url: str = _OLLAMA_BASE_URL,
) -> Dict[str, Any]:
    reference_block = "\n".join(f"- {r}" for r in references if r and r.strip())

    prompt = f"""You are an evaluator for question answering.

Decide whether the predicted answer is correct based on the reference answers.

Question:
{question}

Predicted Answer:
{prediction}

Reference Answers:
{reference_block}

Instructions:
- Return a JSON object only.
- Use this schema exactly:
{{
  "verdict": "correct" or "incorrect",
  "score": 1 or 0,
  "reason": "short explanation"
}}
- Mark as correct if the predicted answer matches the meaning of any reference answer, even if wording differs.
- Mark as incorrect if the prediction is unsupported, contradictory, too vague, or misses the key idea.
- Do not include any text outside the JSON object.
"""

    resp = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={"model": model_name, "prompt": prompt, "stream": False},
        timeout=300,
    )
    resp.raise_for_status()
    raw = resp.json()["response"].strip()

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        parsed = json.loads(raw[start:end + 1])
    except Exception:
        parsed = {"verdict": "incorrect", "score": 0, "reason": f"Parse error: {raw[:200]}"}

    verdict = str(parsed.get("verdict", "incorrect")).lower()
    score = 1 if parsed.get("score", 0) == 1 or verdict == "correct" else 0

    return {
        "verdict": "correct" if score == 1 else "incorrect",
        "score": score,
        "reason": parsed.get("reason", ""),
        "raw_judge_output": raw,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retriever", default="bge",
                        choices=["contriever", "bge", "clip", "colpali"])
    parser.add_argument("--out_dir", default="outputs_full")
    parser.add_argument("--model", default="qwen2.5:latest")
    args = parser.parse_args()

    out_dir = Path(args.out_dir) / args.retriever
    predictions = load_jsonl(out_dir / "predictions.jsonl")

    judged_rows = []
    scores = []

    for i, row in enumerate(predictions, start=1):
        result = ask_ollama_judge(
            question=row.get("question", ""),
            prediction=row.get("prediction", ""),
            references=row.get("answers", []) or [],
            model_name=args.model,
        )

        judged_rows.append({
            **row,
            "judge_verdict": result["verdict"],
            "judge_score": result["score"],
            "judge_reason": result["reason"],
            "raw_judge_output": result["raw_judge_output"],
        })
        scores.append(result["score"])

        if i % 50 == 0:
            print(f"Judged {i}/{len(predictions)}")

        time.sleep(0.1)

    metrics = {
        "retriever": args.retriever,
        "num_predictions": len(predictions),
        "LLMJudgeAccuracy": round(sum(scores) / len(scores), 4) if scores else 0.0,
    }

    print(json.dumps(metrics, indent=2))

    with (out_dir / "llm_judge_metrics.json").open("w") as f:
        json.dump(metrics, f, indent=2)
    with (out_dir / "llm_judge_per_example.jsonl").open("w") as f:
        for row in judged_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Saved {out_dir / 'llm_judge_metrics.json'}")


if __name__ == "__main__":
    main()
