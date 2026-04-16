"""
Generate text captions for retrieved page images using an Ollama vision model.

Captions are saved to outputs/page_captions.json as:
    { "<corpus_id>": "<caption text>", ... }

These captions are used by run_generation.py as additional context alongside
the raw markdown text, helping the generator when the text extraction is poor.

Requires a vision-capable Ollama model. Recommended:
    ollama pull llava:7b

Usage:
    python scripts/caption_pages.py [--model llava:7b] [--top-n 50]
"""

import argparse
import json
import time
from pathlib import Path

import requests

DATA = Path("data/processed")
OUT = Path("outputs")
OUT.mkdir(parents=True, exist_ok=True)


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def check_vision_model(model_name: str, base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        return any(model_name.split(":")[0] in m for m in models)
    except Exception:
        return False


def caption_image(image_path: Path, model_name: str, base_url: str) -> str:
    import base64
    with image_path.open("rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    prompt = (
        "This is a page from a computer science textbook. "
        "Briefly describe the main topic, key concepts, and any visible "
        "text headings, tables, or diagrams. Be concise (2-3 sentences)."
    )
    r = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["response"].strip()


def main(model_name: str, top_n: int, base_url: str):
    if not check_vision_model(model_name, base_url):
        print(f"ERROR: Vision model '{model_name}' not found in Ollama.")
        print(f"  Pull it with: ollama pull {model_name}")
        return

    # Collect corpus_ids needed: union of top-3 results for first top_n queries
    runs_path = OUT / "flexrag_retrieval_top10.jsonl"
    if not runs_path.exists():
        print(f"ERROR: {runs_path} not found — run run_flexrag_retrieval.py first")
        return

    runs = load_jsonl(runs_path)[:top_n]
    needed_ids: set[str] = set()
    for run in runs:
        for doc_id, _ in run["results"][:5]:
            needed_ids.add(str(doc_id))

    image_dir = DATA / "images"
    existing_captions: dict[str, str] = {}
    captions_path = OUT / "page_captions.json"
    if captions_path.exists():
        with captions_path.open() as f:
            existing_captions = json.load(f)

    to_caption = [cid for cid in needed_ids if cid not in existing_captions]
    print(f"Captioning {len(to_caption)} pages with {model_name} ...")

    captions = dict(existing_captions)
    for i, cid in enumerate(to_caption, start=1):
        img_path = image_dir / f"{cid}.png"
        if not img_path.exists():
            captions[cid] = ""
            continue
        try:
            caption = caption_image(img_path, model_name, base_url)
            captions[cid] = caption
        except Exception as e:
            print(f"  WARNING: failed to caption {cid}: {e}")
            captions[cid] = ""

        if i % 10 == 0:
            print(f"  {i}/{len(to_caption)} done")
            with captions_path.open("w") as f:
                json.dump(captions, f, indent=2, ensure_ascii=False)
        time.sleep(0.1)

    with captions_path.open("w") as f:
        json.dump(captions, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(captions)} captions to {captions_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llava:7b",
                        help="Ollama vision model name (default: llava:7b)")
    parser.add_argument("--top-n", type=int, default=50,
                        help="Caption pages for first N queries (default: 50)")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    main(args.model, args.top_n, args.base_url)
