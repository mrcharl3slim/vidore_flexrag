"""
Build a FAISS index over ViDoRe corpus page images using FlexRAG's hf_clip encoder.

Encodes each page image with openai/clip-vit-base-patch32 (passage encoder) and
saves the resulting FAISS index plus an id_map to data/processed/clip_index/.

id_map.json maps FAISS row integers → corpus_id strings so run_clip_retrieval.py
can convert search results back to doc ids.

Prerequisite: run save_vidore_images.py first.

Usage:
    python scripts/build_clip_index.py
"""

import json
from pathlib import Path

from PIL import Image as PILImage

from flexrag.models import EncoderConfig, HFClipEncoderConfig
from flexrag.retriever.index.faiss_index import FaissIndex, FaissIndexConfig

MANIFEST_PATH = Path("data/processed/image_manifest.jsonl")
INDEX_DIR = "data/processed/clip_index"
CLIP_MODEL = "openai/clip-vit-base-patch32"


def load_manifest(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def iter_images(manifest: list[dict]):
    """Yield PIL ImageFile objects in manifest order."""
    for row in manifest:
        img_path = Path(row["image_path"])
        if not img_path.exists():
            raise FileNotFoundError(
                f"Image not found: {img_path}  — run save_vidore_images.py first"
            )
        # Open as PIL ImageFile (not Image.new) so isinstance(img, ImageFile) passes
        yield PILImage.open(img_path)


def clip_encoder_config() -> EncoderConfig:
    return EncoderConfig(
        encoder_type="hf_clip",
        hf_clip_config=HFClipEncoderConfig(
            model_path=CLIP_MODEL,
            device_id=[],           # CPU
            normalize=True,
            convert_to_rgb=True,
            max_encode_length=77,   # CLIP text encoder hard limit
        ),
    )


def main():
    manifest = load_manifest(MANIFEST_PATH)
    print(f"Corpus: {len(manifest)} docs")
    print(f"Model : {CLIP_MODEL}")
    print(f"Index : {INDEX_DIR}")

    encoder_cfg = clip_encoder_config()

    index_cfg = FaissIndexConfig(
        index_type="FLAT",          # exact search; 1360 docs is tiny
        distance_function="COS",    # cosine similarity (CLIP embeddings are normalized)
        index_path=INDEX_DIR,
        batch_size=16,              # images are large; keep batches small
        log_interval=100,
        query_encoder_config=encoder_cfg,
        passage_encoder_config=encoder_cfg,
    )

    print("\nBuilding FAISS index (encoding images)...")
    index = FaissIndex(index_cfg)
    index.build_index(iter_images(manifest))

    print(f"\nSaving FAISS index to {INDEX_DIR}/...")
    index.save_to_local(INDEX_DIR)

    # Save id_map: list of corpus_ids in FAISS row order
    id_map = [row["id"] for row in manifest]
    id_map_path = Path(INDEX_DIR) / "id_map.json"
    with id_map_path.open("w") as f:
        json.dump(id_map, f)

    print(f"Saved id_map ({len(id_map)} entries) to {id_map_path}")
    print(f"\nIndex contains {len(index)} vectors of dim {index.embedding_size}.")
    print("Done.")


if __name__ == "__main__":
    main()
