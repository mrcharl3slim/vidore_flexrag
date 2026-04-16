"""
Run retrieval over all ViDoRe queries using the CLIP image index.

For each query the text is encoded with HFClipEncoder (encode_text path) and
searched against the FAISS index of page image embeddings.

Output: outputs/clip_retrieval_top10.jsonl — same format as
flexrag_retrieval_top10.jsonl so eval_clip_retrieval.py can consume it directly.

Prerequisite: run build_clip_index.py first.

Usage:
    python scripts/run_clip_retrieval.py
"""

import json
from pathlib import Path

from flexrag.models import EncoderConfig, HFClipEncoderConfig
from flexrag.retriever.index.faiss_index import FaissIndex, FaissIndexConfig

QUERIES_PATH = Path("data/processed/queries.jsonl")
INDEX_DIR = "data/processed/clip_index"
OUT_PATH = Path("outputs/clip_retrieval_top10.jsonl")
CLIP_MODEL = "openai/clip-vit-base-patch32"
TOP_K = 10


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def save_jsonl(rows: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def clip_encoder_config() -> EncoderConfig:
    return EncoderConfig(
        encoder_type="hf_clip",
        hf_clip_config=HFClipEncoderConfig(
            model_path=CLIP_MODEL,
            device_id=[],
            normalize=True,
            convert_to_rgb=True,
            max_encode_length=77,
        ),
    )


def main():
    id_map_path = Path(INDEX_DIR) / "id_map.json"
    if not id_map_path.exists():
        raise FileNotFoundError(
            f"{id_map_path} not found — run build_clip_index.py first"
        )

    with id_map_path.open() as f:
        id_map: list[str] = json.load(f)   # id_map[faiss_row] = corpus_id

    queries = load_jsonl(QUERIES_PATH)
    print(f"Queries : {len(queries)}")
    print(f"Index   : {INDEX_DIR}  ({len(id_map)} docs)")

    encoder_cfg = clip_encoder_config()

    # FaissIndex auto-loads the saved index when index_path exists on disk.
    # We still pass encoder configs so the query encoder is available.
    index_cfg = FaissIndexConfig(
        index_type="FLAT",
        distance_function="COS",
        index_path=INDEX_DIR,
        batch_size=16,
        query_encoder_config=encoder_cfg,
        passage_encoder_config=encoder_cfg,
    )
    index = FaissIndex(index_cfg)
    print(f"Loaded index: {len(index)} vectors, dim={index.embedding_size}\n")

    runs = []
    for i, q in enumerate(queries, start=1):
        # search returns (indices, scores) each shaped (n_queries, top_k)
        indices, scores = index.search([q["question"]], top_k=TOP_K)
        row_indices = indices[0].tolist()   # FAISS row ints for this query
        row_scores = scores[0].tolist()

        ranked = []
        for row_idx, score in zip(row_indices, row_scores):
            if row_idx < 0 or row_idx >= len(id_map):
                continue  # FAISS returns -1 for unfilled slots
            corpus_id = id_map[row_idx]
            ranked.append([corpus_id, float(score)])

        runs.append({
            "query_id": str(q["query_id"]),
            "question": q["question"],
            "results": ranked,
        })

        if i % 100 == 0:
            print(f"  {i}/{len(queries)} queries done")

    save_jsonl(runs, OUT_PATH)
    print(f"\nSaved {len(runs)} query results to {OUT_PATH}")


if __name__ == "__main__":
    main()
