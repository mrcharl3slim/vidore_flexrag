"""
Download ViDoRe page images and save them to disk.

Reads the already-converted corpus.jsonl to know which corpus_ids exist,
then streams the HuggingFace dataset and saves each image as a PNG.
Also writes data/processed/image_manifest.jsonl — a per-doc record of:
    {"id": "<corpus_id>", "image_path": "data/processed/images/<corpus_id>.png"}

This only needs to run once.  Images persist on disk for use by
build_clip_index.py and any future multimodal scripts.

Usage:
    python scripts/save_vidore_images.py
"""

import json
from pathlib import Path

from datasets import load_dataset

CORPUS_PATH = Path("data/processed/corpus.jsonl")
IMAGE_DIR = Path("data/processed/images")
MANIFEST_PATH = Path("data/processed/image_manifest.jsonl")
HF_DATASET = "vidore/vidore_v3_computer_science"


def load_corpus_ids(path: Path) -> set[str]:
    ids = set()
    with path.open() as f:
        for line in f:
            ids.add(json.loads(line)["id"])
    return ids


def main():
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    corpus_ids = load_corpus_ids(CORPUS_PATH)
    print(f"Corpus size: {len(corpus_ids)} docs")

    print(f"Streaming {HF_DATASET} corpus split...")
    hf_corpus = load_dataset(HF_DATASET, "corpus", split="test")

    saved = 0
    skipped = 0
    manifest_rows = []

    for row in hf_corpus:
        cid = str(row["corpus_id"])
        if cid not in corpus_ids:
            skipped += 1
            continue

        img_path = IMAGE_DIR / f"{cid}.png"
        if not img_path.exists():
            img = row["image"]
            if img is None:
                print(f"  WARNING: no image for corpus_id={cid}")
                continue
            img.save(img_path, format="PNG")

        manifest_rows.append({"id": cid, "image_path": str(img_path)})
        saved += 1

        if saved % 200 == 0:
            print(f"  Saved {saved}/{len(corpus_ids)} images...")

    with MANIFEST_PATH.open("w") as f:
        for row in manifest_rows:
            f.write(json.dumps(row) + "\n")

    print(f"\nDone. Saved {saved} images to {IMAGE_DIR}/")
    print(f"Manifest written to {MANIFEST_PATH}")
    if skipped:
        print(f"Skipped {skipped} rows not in corpus.jsonl")


if __name__ == "__main__":
    main()
