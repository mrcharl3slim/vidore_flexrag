import json
import time
from pathlib import Path
from typing import List, Dict, Any

import requests

OUT = Path("outputs")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def ask_ollama_judge(
    question: str,
    prediction: str,
    references: List[str],
    model_name: str = "qwen2:latest",
    base_url: str = "http://127.0.0.1:11434",
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
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        },
        timeout=300,
    )
    resp.raise_for_status()
    raw = resp.json()["response"].strip()

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        parsed = json.loads(raw[start:end + 1])
    except Exception:
        parsed = {
            "verdict": "incorrect",
            "score": 0,
            "reason": f"Failed to parse judge output: {raw[:300]}",
        }

    verdict = str(parsed.get("verdict", "incorrect")).lower()
    score = 1 if parsed.get("score", 0) == 1 or verdict == "correct" else 0

    return {
        "verdict": "correct" if score == 1 else "incorrect",
        "score": score,
        "reason": parsed.get("reason", ""),
        "raw_judge_output": raw,
    }


def main() -> None:
    predictions_path = OUT / "predictions.jsonl"
    predictions = load_jsonl(predictions_path)

    judged_rows = []
    scores = []

    for i, row in enumerate(predictions, start=1):
        question = row.get("question", "")
        prediction = row.get("prediction", "")
        answers = row.get("answers", []) or []

        result = ask_ollama_judge(
            question=question,
            prediction=prediction,
            references=answers,
        )

        judged_row = {
            "query_id": row.get("query_id"),
            "question": question,
            "prediction": prediction,
            "answers": answers,
            "context_doc_ids": row.get("context_doc_ids", []),
            "judge_verdict": result["verdict"],
            "judge_score": result["score"],
            "judge_reason": result["reason"],
            "raw_judge_output": result["raw_judge_output"],
        }
        judged_rows.append(judged_row)
        scores.append(result["score"])

        if i % 10 == 0:
            print(f"Judged {i}/{len(predictions)} predictions")

        time.sleep(0.2)

    metrics = {
        "num_predictions": len(predictions),
        "LLMJudgeAccuracy": sum(scores) / len(scores) if scores else 0.0,
    }

    print(json.dumps(metrics, indent=2, ensure_ascii=False))

    with (OUT / "llm_judge_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    with (OUT / "llm_judge_per_example.jsonl").open("w", encoding="utf-8") as f:
        for row in judged_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Saved {OUT / 'llm_judge_metrics.json'}")
    print(f"Saved {OUT / 'llm_judge_per_example.jsonl'}")


if __name__ == "__main__":
    main()