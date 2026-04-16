"""
Validate FlexRAG's HFClipEncoder (hf_clip encoder type) using ViDoRe data.

Tests:
  1. Encoder instantiation and basic API (embedding shape, dtype, embedding_size)
  2. Text→Text retrieval: query texts vs corpus passage texts
  3. Image→Text retrieval: query texts vs corpus page images (cross-modal)

Prints a results table with Recall@1 and Recall@3 for each modality.

Usage:
    PYTHONPATH=. python scripts/validate_clip_encoder.py [--n 30]
"""

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import io

import numpy as np
from datasets import load_dataset
from PIL import Image as PILImage

# FlexRAG imports
from flexrag.models import HFClipEncoderConfig
from flexrag.models.hf_model import HFClipEncoder

# ── Config ────────────────────────────────────────────────────────────────────

CLIP_MODEL = "openai/clip-vit-base-patch32"
CORPUS_PATH = Path("data/processed/corpus.jsonl")
QUERIES_PATH = Path("data/processed/queries.jsonl")
QRELS_PATH = Path("data/processed/qrels.jsonl")
HF_DATASET = "vidore/vidore_v3_computer_science"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def blank_image_file() -> PILImage.Image:
    """Return a PIL ImageFile instance (not just Image.Image) for a blank image.

    FlexRAG's HFClipEncoder._encode checks isinstance(d, PIL.ImageFile.ImageFile).
    PIL.Image.new() returns a plain Image.Image which fails that check.
    Round-tripping through BytesIO produces the correct subclass.
    """
    buf = io.BytesIO()
    PILImage.new("RGB", (224, 224), color=200).save(buf, format="PNG")
    buf.seek(0)
    return PILImage.open(buf)


def cosine_sim(q: np.ndarray, D: np.ndarray) -> np.ndarray:
    """q: (d,)  D: (N, d)  →  (N,) cosine similarities."""
    q_norm = q / (np.linalg.norm(q) + 1e-10)
    d_norm = D / (np.linalg.norm(D, axis=1, keepdims=True) + 1e-10)
    return d_norm @ q_norm


def recall_at_k(rankings: list[list[str]], relevant: list[set[str]], k: int) -> float:
    hits = sum(
        1 for ranked, rel in zip(rankings, relevant)
        if rel.intersection(ranked[:k])
    )
    return hits / len(rankings)


def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main(n: int):

    # ── 1. Load processed data ────────────────────────────────────────────────
    section("Loading processed ViDoRe data")

    corpus = load_jsonl(CORPUS_PATH)           # all docs
    queries = load_jsonl(QUERIES_PATH)[:n]     # first n queries
    qrels = load_jsonl(QRELS_PATH)

    # Build qrel lookup: query_id → set of relevant doc_ids
    relevant: dict[str, set[str]] = defaultdict(set)
    for row in qrels:
        relevant[row["query_id"]].add(row["doc_id"])

    # Keep only queries that have at least one qrel
    queries = [q for q in queries if q["query_id"] in relevant][:n]
    query_ids = [q["query_id"] for q in queries]

    # Collect the union of relevant doc_ids for our query subset
    needed_doc_ids: set[str] = set()
    for qid in query_ids:
        needed_doc_ids.update(relevant[qid])

    # Also include some non-relevant docs as distractors (up to 5× needed)
    distractor_pool = [d for d in corpus if d["id"] not in needed_doc_ids]
    distractors = distractor_pool[:len(needed_doc_ids) * 5]

    # Final corpus subset: relevant docs + distractors
    subset_docs = [d for d in corpus if d["id"] in needed_doc_ids] + distractors
    doc_ids = [d["id"] for d in subset_docs]
    doc_id_to_idx = {did: i for i, did in enumerate(doc_ids)}

    print(f"  Queries     : {len(queries)}")
    print(f"  Corpus docs : {len(subset_docs)}  ({len(needed_doc_ids)} relevant + {len(distractors)} distractors)")

    # ── 2. Instantiate encoder ────────────────────────────────────────────────
    section("Instantiating HFClipEncoder")
    print(f"  Model : {CLIP_MODEL}")

    cfg = HFClipEncoderConfig(
        model_path=CLIP_MODEL,
        device_id=[],           # CPU
        normalize=True,
        convert_to_rgb=True,
        max_encode_length=77,   # CLIP text encoder hard limit
    )
    encoder = HFClipEncoder(cfg)
    print(f"  embedding_size : {encoder.embedding_size}")

    # ── 3. Sanity checks ──────────────────────────────────────────────────────
    section("Sanity checks")

    # Text embedding shape + dtype
    sample_texts = ["What is Python?", "A brief history of computing."]
    t_embs = encoder.encode(sample_texts)
    print(f"  encode(['...', '...']) → shape={t_embs.shape}, dtype={t_embs.dtype}")
    assert t_embs.shape == (2, encoder.embedding_size), "Unexpected text embedding shape"
    assert t_embs.dtype == np.float32, "Expected float32"

    # Norm check (normalize=True → unit vectors)
    norms = np.linalg.norm(t_embs, axis=1)
    print(f"  L2 norms (expect ≈1.0): {norms}")
    assert np.allclose(norms, 1.0, atol=1e-5), "Embeddings not normalized"

    # Image embedding shape
    dummy_img = blank_image_file()
    i_embs = encoder.encode([dummy_img])
    print(f"  encode([PIL.Image]) → shape={i_embs.shape}, dtype={i_embs.dtype}")
    assert i_embs.shape == (1, encoder.embedding_size), "Unexpected image embedding shape"

    print("  All sanity checks passed.")

    # ── 4. Text→Text retrieval ────────────────────────────────────────────────
    section("Test 1: Text→Text retrieval")

    passage_texts = [
        f"{d['title']} {d['text']}".strip() for d in subset_docs
    ]
    query_texts = [q["question"] for q in queries]

    print(f"  Encoding {len(passage_texts)} passages...")
    t0 = time.time()
    passage_embs = encoder.encode(passage_texts)   # (N, d)
    print(f"  Done in {time.time() - t0:.1f}s")

    print(f"  Encoding {len(query_texts)} queries...")
    t0 = time.time()
    query_embs = encoder.encode(query_texts)        # (Q, d)
    print(f"  Done in {time.time() - t0:.1f}s")

    tt_rankings: list[list[str]] = []
    for q_emb in query_embs:
        sims = cosine_sim(q_emb, passage_embs)
        ranked_indices = np.argsort(-sims)
        tt_rankings.append([doc_ids[i] for i in ranked_indices])

    rel_sets = [relevant[qid] for qid in query_ids]
    tt_r1 = recall_at_k(tt_rankings, rel_sets, k=1)
    tt_r3 = recall_at_k(tt_rankings, rel_sets, k=3)
    tt_r10 = recall_at_k(tt_rankings, rel_sets, k=10)

    # ── 5. Image→Text retrieval ───────────────────────────────────────────────
    section("Test 2: Image→Text (cross-modal) retrieval")
    print(f"  Fetching page images from HuggingFace ({HF_DATASET})...")

    # Load the corpus split which contains the page images
    hf_corpus = load_dataset(HF_DATASET, "corpus", split="test")

    # Build lookup: corpus_id → PIL image
    needed_ids_int = set()
    str_to_int_map: dict[str, int] = {}
    for row in hf_corpus:
        cid = str(row["corpus_id"])
        if cid in needed_doc_ids:
            str_to_int_map[cid] = row["corpus_id"]
            needed_ids_int.add(row["corpus_id"])

    corpus_id_to_image: dict[str, PILImage.Image] = {}
    for row in hf_corpus:
        cid = str(row["corpus_id"])
        if cid in needed_doc_ids:
            img = row.get("image") or row.get("page_image")
            if img is not None:
                corpus_id_to_image[cid] = img

    n_images_found = len(corpus_id_to_image)
    print(f"  Found images for {n_images_found}/{len(needed_doc_ids)} relevant docs")

    if n_images_found == 0:
        print("  WARNING: No images found in dataset — skipping image→text test.")
        img_r1 = img_r3 = img_r10 = float("nan")
    else:
        # Build an image-based corpus subset (only docs for which we have an image)
        img_doc_ids: list[str] = []
        img_list: list[PILImage.Image] = []

        for d in subset_docs:
            did = d["id"]
            if did in corpus_id_to_image:
                img_doc_ids.append(did)
                img_list.append(corpus_id_to_image[did])
            else:
                # Fallback: blank image so we keep distractor slots
                img_doc_ids.append(did)
                img_list.append(blank_image_file())

        print(f"  Encoding {len(img_list)} images...")
        t0 = time.time()
        image_embs = encoder.encode(img_list)   # (N, d)
        print(f"  Done in {time.time() - t0:.1f}s")

        # Query embeddings already computed above; reuse query_embs
        img_rankings: list[list[str]] = []
        for q_emb in query_embs:
            sims = cosine_sim(q_emb, image_embs)
            ranked_indices = np.argsort(-sims)
            img_rankings.append([img_doc_ids[i] for i in ranked_indices])

        img_r1 = recall_at_k(img_rankings, rel_sets, k=1)
        img_r3 = recall_at_k(img_rankings, rel_sets, k=3)
        img_r10 = recall_at_k(img_rankings, rel_sets, k=10)

    # ── 6. Results ────────────────────────────────────────────────────────────
    section("Results")
    print(f"  Model  : {CLIP_MODEL}")
    print(f"  Queries: {len(queries)}   Corpus: {len(subset_docs)} docs\n")
    print(f"  {'Modality':<28} {'R@1':>6} {'R@3':>6} {'R@10':>6}")
    print(f"  {'-'*28} {'------':>6} {'------':>6} {'------':>6}")
    print(f"  {'Text query → Text corpus':<28} {tt_r1:>6.3f} {tt_r3:>6.3f} {tt_r10:>6.3f}")
    img_r1_str  = f"{img_r1:>6.3f}"  if not np.isnan(img_r1)  else "   n/a"
    img_r3_str  = f"{img_r3:>6.3f}"  if not np.isnan(img_r3)  else "   n/a"
    img_r10_str = f"{img_r10:>6.3f}" if not np.isnan(img_r10) else "   n/a"
    print(f"  {'Text query → Image corpus':<28} {img_r1_str} {img_r3_str} {img_r10_str}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--n", type=int, default=30,
        help="Number of queries to evaluate (default: 30)"
    )
    args = parser.parse_args()
    main(args.n)
