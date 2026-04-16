"""
Build a FlexRAG retriever using BAAI/bge-large-en-v1.5 as the dense encoder.

BGE-large scores significantly higher than contriever-msmarco on MTEB/BEIR
retrieval benchmarks. This script mirrors build_flexrag_retriever.py but
uses a separate retriever path so both can coexist.

Usage:
    python scripts/build_bge_retriever.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from flexrag.datasets import RAGCorpusDataset, RAGCorpusDatasetConfig
from flexrag.models import EncoderConfig, HFEncoderConfig
from flexrag.retriever import FlexRetriever, FlexRetrieverConfig
from flexrag.retriever.index import (
    FaissIndexConfig,
    MultiFieldIndexConfig,
    RetrieverIndexConfig,
)

RETRIEVER_PATH = "data/processed/bge_retriever"
CORPUS_PATH = ["data/processed/corpus.jsonl"]
BGE_MODEL = "BAAI/bge-large-en-v1.5"


def add_passages():
    corpus = RAGCorpusDataset(
        RAGCorpusDatasetConfig(
            file_paths=CORPUS_PATH,
            saving_fields=["title", "text", "page_number"],
            id_field="id",
        )
    )
    retriever = FlexRetriever(
        FlexRetrieverConfig(
            retriever_path=RETRIEVER_PATH,
            log_interval=1000,
            batch_size=128,
        )
    )
    retriever.add_passages(passages=corpus)
    print("Passages added.")


def add_bm25_index():
    retriever = FlexRetriever.load_from_local(RETRIEVER_PATH)
    retriever.add_index(
        index_name="bm25",
        index_config=RetrieverIndexConfig(index_type="bm25"),
        indexed_fields_config=MultiFieldIndexConfig(
            indexed_fields=["title", "text"],
            merge_method="concat",
        ),
    )
    print("BM25 index built.")


def add_dense_index():
    retriever = FlexRetriever.load_from_local(RETRIEVER_PATH)
    retriever.add_index(
        index_name="dense",
        index_config=RetrieverIndexConfig(
            index_type="faiss",
            faiss_config=FaissIndexConfig(
                index_type="FLAT",
                index_train_num=-1,
                query_encoder_config=EncoderConfig(
                    encoder_type="hf",
                    hf_config=HFEncoderConfig(
                        model_path=BGE_MODEL,
                        device_id=[],
                    ),
                ),
                passage_encoder_config=EncoderConfig(
                    encoder_type="hf",
                    hf_config=HFEncoderConfig(
                        model_path=BGE_MODEL,
                        device_id=[],
                    ),
                ),
            ),
        ),
        indexed_fields_config=MultiFieldIndexConfig(
            indexed_fields=["title", "text"],
            merge_method="concat",
        ),
    )
    print("BGE dense FAISS index built.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        {"passages": add_passages, "bm25": add_bm25_index, "dense": add_dense_index}[sys.argv[1]]()
    else:
        if os.path.exists(RETRIEVER_PATH):
            shutil.rmtree(RETRIEVER_PATH)
        for step in ["passages", "bm25", "dense"]:
            subprocess.run([sys.executable, __file__, step], check=True)
