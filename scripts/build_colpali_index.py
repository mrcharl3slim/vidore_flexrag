"""
Build a FAISS index over ViDoRe corpus page images using ColPali.

Uses the custom ColPaliEncoder (app/colpali_encoder.py) which wraps
vidore/colpali-v1.2 and mean-pools patch embeddings to a single vector
compatible with FlexRAG's FAISS index pipeline.

NOTE: ColPali is a 3B-parameter model. On CPU, encoding 1360 images
takes approximately 1-3 hours. Use --sample N to test on a subset first.

Prerequisite: run save_vidore_images.py first.

Usage:
    PYTHONPATH=. python scripts/build_colpali_index.py            # full corpus
    PYTHONPATH=. python scripts/build_colpali_index.py --sample 50  # test run
"""

import argparse
import json
from pathlib import Path

from PIL import Image as PILImage

from flexrag.retriever.index.faiss_index import FaissIndex, FaissIndexConfig
from app.colpali_encoder import ColPaliEncoder, ColPaliEncoderConfig

MANIFEST_PATH = Path("data/processed/image_manifest.jsonl")
INDEX_DIR = "data/processed/colpali_index"
COLPALI_MODEL = "vidore/colpali-v1.2"


def load_manifest(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def iter_images(manifest: list[dict]):
    for row in manifest:
        img_path = Path(row["image_path"])
        if not img_path.exists():
            raise FileNotFoundError(
                f"Image not found: {img_path} — run save_vidore_images.py first"
            )
        yield PILImage.open(img_path)


def make_encoder() -> ColPaliEncoder:
    return ColPaliEncoder(ColPaliEncoderConfig(
        model_path=COLPALI_MODEL,
        device="cpu",
        normalize=True,
    ))


def main(sample: int | None):
    manifest = load_manifest(MANIFEST_PATH)
    if sample:
        manifest = manifest[:sample]
        print(f"[sample mode] Using first {sample} images")

    print(f"Corpus : {len(manifest)} docs")
    print(f"Model  : {COLPALI_MODEL}")
    print(f"Index  : {INDEX_DIR}")
    print("NOTE   : ColPali on CPU is slow — ~1-3 hours for full corpus.")

    # EncoderConfig pydantic validator only accepts FlexRAG's built-in types.
    # Bypass it by creating FaissIndex with no encoder configs and injecting
    # our ColPaliEncoder directly onto the instance after construction.
    encoder = make_encoder()

    index_cfg = FaissIndexConfig(
        index_type="FLAT",
        distance_function="COS",
        index_path=INDEX_DIR,
        batch_size=4,
        log_interval=20,
    )

    # Remove stale index directory so FaissIndex doesn't try to load from it
    import shutil
    if Path(INDEX_DIR).exists():
        shutil.rmtree(INDEX_DIR)

    print("\nBuilding ColPali FAISS index...")
    index = FaissIndex(index_cfg)
    index.passage_encoder = encoder
    index.query_encoder = encoder
    index.build_index(iter_images(manifest))

    print(f"\nSaving index to {INDEX_DIR}/...")
    index.save_to_local(INDEX_DIR)

    id_map = [row["id"] for row in manifest]
    id_map_path = Path(INDEX_DIR) / "id_map.json"
    with id_map_path.open("w") as f:
        json.dump(id_map, f)

    print(f"Saved id_map ({len(id_map)} entries) to {id_map_path}")
    print(f"Index: {len(index)} vectors, dim={index.embedding_size}")
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None,
                        help="Only encode first N images (for testing)")
    args = parser.parse_args()
    main(args.sample)
