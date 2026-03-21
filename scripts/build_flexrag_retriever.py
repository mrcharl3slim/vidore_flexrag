from flexrag.datasets import RAGCorpusDataset, RAGCorpusDatasetConfig
from flexrag.retriever import FlexRetriever, FlexRetrieverConfig
from flexrag.retriever.index import (
    MultiFieldIndexConfig,
    RetrieverIndexConfig,
    FaissIndexConfig,
)
from flexrag.models import EncoderConfig, HFEncoderConfig

RETRIEVER_PATH = "data/processed/vidore_flexrag_retriever"
CORPUS_PATH = ["data/processed/corpus.jsonl"]


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
                index_type="FLAT",  # corpus too small for IVF/PQ; FLAT is exact and safe
                index_train_num=-1,
                query_encoder_config=EncoderConfig(
                    encoder_type="hf",
                    hf_config=HFEncoderConfig(
                        model_path="facebook/contriever-msmarco",
                        device_id=[],   # CPU on Mac
                    ),
                ),
                passage_encoder_config=EncoderConfig(
                    encoder_type="hf",
                    hf_config=HFEncoderConfig(
                        model_path="facebook/contriever-msmarco",
                        device_id=[],   # CPU on Mac
                    ),
                ),
            ),
        ),
        indexed_fields_config=MultiFieldIndexConfig(
            indexed_fields=["title", "text"],
            merge_method="concat",
        ),
    )
    print("Dense FAISS index built.")


if __name__ == "__main__":
    import sys
    import subprocess
    import shutil
    import os

    # Each step must run in a fresh process — LMDB cannot be opened twice in the same process
    if len(sys.argv) > 1:
        {"passages": add_passages, "bm25": add_bm25_index, "dense": add_dense_index}[sys.argv[1]]()
    else:
        if os.path.exists(RETRIEVER_PATH):
            shutil.rmtree(RETRIEVER_PATH)
        for step in ["passages", "bm25", "dense"]:
            subprocess.run([sys.executable, __file__, step], check=True)