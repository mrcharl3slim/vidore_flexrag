"""
Run retrieval over ViDoRe queries using the ColPali image index.

Encodes each query text with ColPali's text encoder and searches the FAISS
index of mean-pooled ColPali image embeddings.

Output: outputs/colpali_retrieval_top10.jsonl

Prerequisite: run build_colpali_index.py first.

Usage:
    PYTHONPATH=. python scripts/run_colpali_retrieval.py
"""

import json
import os
from pathlib import Path

# Suppress OpenMP duplicate-library abort on macOS
# (PyTorch and FAISS each bundle their own libomp.dylib)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from flexrag.retriever.index.faiss_index import FaissIndex, FaissIndexConfig
from app.colpali_encoder import ColPaliEncoder, ColPaliEncoderConfig

QUERIES_PATH = Path("data/processed/queries.jsonl")
INDEX_DIR = "data/processed/colpali_index"
OUT_PATH = Path("outputs/colpali_retrieval_top10.jsonl")
COLPALI_MODEL = "vidore/colpali-v1.2"
TOP_K = 10


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def save_jsonl(rows: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    id_map_path = Path(INDEX_DIR) / "id_map.json"
    if not id_map_path.exists():
        raise FileNotFoundError(
            f"{id_map_path} not found — run build_colpali_index.py first"
        )
    with id_map_path.open() as f:
        id_map: list[str] = json.load(f)

    queries = load_jsonl(QUERIES_PATH)
    print(f"Queries : {len(queries)}")
    print(f"Index   : {INDEX_DIR}  ({len(id_map)} docs)")

    encoder = ColPaliEncoder(ColPaliEncoderConfig(
        model_path=COLPALI_MODEL,
        device="cpu",
        normalize=True,
    ))

    index_cfg = FaissIndexConfig(
        index_type="FLAT",
        distance_function="COS",
        index_path=INDEX_DIR,
        batch_size=4,
    )
    index = FaissIndex(index_cfg)
    index.query_encoder = encoder
    index.passage_encoder = encoder
    print(f"Loaded index: {len(index)} vectors, dim={index.embedding_size}\n")

    runs = []
    for i, q in enumerate(queries, start=1):
        indices, scores = index.search([q["question"]], top_k=TOP_K)
        row_indices = indices[0].tolist()
        row_scores = scores[0].tolist()

        ranked = []
        for row_idx, score in zip(row_indices, row_scores):
            if 0 <= row_idx < len(id_map):
                ranked.append([id_map[row_idx], float(score)])

        runs.append({
            "query_id": str(q["query_id"]),
            "question": q["question"],
            "results": ranked,
        })

        if i % 100 == 0:
            print(f"  {i}/{len(queries)} queries done")

    save_jsonl(runs, OUT_PATH)
    print(f"\nSaved {len(runs)} results to {OUT_PATH}")


if __name__ == "__main__":
    main()
