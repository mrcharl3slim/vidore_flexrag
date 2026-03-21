"""
Build a FlexRAG FlexRetriever with a FAISS dense index over corpus.jsonl.
Saves the retriever to data/index/ for use by run_retrieval.py.
"""

import json
from pathlib import Path

from flexrag.retriever import FlexRetriever, FlexRetrieverConfig
from flexrag.retriever.index import RETRIEVER_INDEX, FaissIndexConfig
from flexrag.retriever.index.index_base import EncoderConfig
from flexrag.retriever.index.multi_field_index import MultiFieldIndexConfig
from flexrag.models import SentenceTransformerEncoderConfig
from flexrag.utils.dataclasses import Context

DATA = Path("data/processed")
INDEX_PATH = "data/index"

def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def main():
    corpus = load_jsonl(DATA / "corpus.jsonl")
    print(f"Loaded {len(corpus)} documents")

    # Initialise an empty FlexRetriever (NaiveDatabase in memory)
    retriever = FlexRetriever(FlexRetrieverConfig())

    # Add corpus passages
    passages = [
        Context(context_id=doc["doc_id"], data={"text": doc["text"]})
        for doc in corpus
    ]
    retriever.add_passages(passages)
    print(f"Added {len(retriever)} passages to retriever")

    # Dense encoder config (all-MiniLM-L6-v2 — small, fast, CPU-friendly)
    encoder_cfg = EncoderConfig(
        encoder_type="sentence_transformer",
        sentence_transformer_config=SentenceTransformerEncoderConfig(
            model_path="sentence-transformers/all-MiniLM-L6-v2",
            normalize=True,
        ),
    )

    # FAISS FLAT index (exact search; corpus is small enough)
    RetrieverIndexConfig = RETRIEVER_INDEX.make_config()
    index_cfg = RetrieverIndexConfig(
        index_type="faiss",
        faiss_config=FaissIndexConfig(
            index_type="FLAT",
            distance_function="COS",
            passage_encoder_config=encoder_cfg,
            query_encoder_config=encoder_cfg,
        ),
    )

    # Index the "text" field
    field_cfg = MultiFieldIndexConfig(indexed_fields=["text"])

    print("Building FAISS index (this may take a minute)...")
    retriever.add_index("dense", index_cfg, field_cfg)

    # Persist to disk
    retriever.save_to_local(INDEX_PATH)
    print(f"Retriever saved to {INDEX_PATH}")

if __name__ == "__main__":
    main()
