# ViDoRe FlexRAG: Multimodal Document Retrieval
## Technical Report with Code Evidence

**Author:** Charles (e1610383)
**Date:** April 2026
**Repository:** https://github.com/mrcharl3slim/vidore_flexrag

---

## 1. Project Overview

This project implements and evaluates four retrieval pipelines on the **ViDoRe V3 Computer Science benchmark** — a standardised document retrieval benchmark of 1,360 PDF pages and 1,290 natural language queries. The pipeline is built on **FlexRAG** (ACL 2025), extended with custom multimodal components.

**Research Question:**
> *How do text-based hybrid retrieval methods compare to state-of-the-art visual document retrieval models on ViDoRe V3?*

---

## 2. Dataset Preparation

### Code: `scripts/convert_vidore.py`

```python
from datasets import load_dataset
import json, argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--small", action="store_true",
                        help="Use a small subset (200 corpus, 50 queries)")
    args = parser.parse_args()

    corpus_ds  = load_dataset("vidore/vidore_v3_computer_science", "corpus",  split="test")
    queries_ds = load_dataset("vidore/vidore_v3_computer_science", "queries", split="test")
    qrels_ds   = load_dataset("vidore/vidore_v3_computer_science", "qrels",   split="test")

    if args.small:
        corpus_ds  = corpus_ds.select(range(min(200, len(corpus_ds))))
        queries_ds = queries_ds.select(range(min(50,  len(queries_ds))))

    valid_corpus_ids = {str(row["corpus_id"]) for row in corpus_ds}
    valid_query_ids  = {str(row["query_id"])  for row in queries_ds}

    corpus_rows = []
    for row in corpus_ds:
        corpus_rows.append({
            "id":          str(row["corpus_id"]),
            "title":       str(row.get("doc_id", "")),
            "text":        row.get("markdown", "") or "",
            "page_number": row.get("page_number_in_doc"),
        })

    qrel_rows = []
    for row in qrels_ds:
        qid, did = str(row["query_id"]), str(row["corpus_id"])
        if qid in valid_query_ids and did in valid_corpus_ids:
            qrel_rows.append({"query_id": qid, "doc_id": did,
                              "relevance": int(row["score"])})
```

**Explanation:**
- Downloads the ViDoRe V3 Computer Science dataset from HuggingFace
- Converts it into 3 JSONL files: `corpus.jsonl`, `queries.jsonl`, `qrels.jsonl`
- The `--small` flag enables fast local testing with a 200-doc, 50-query subset
- Qrels are filtered to only include query-document pairs within the selected subset

**Dataset statistics:**

| Split | Full Dataset | Small Subset |
|---|---|---|
| Corpus pages | 1,360 | 200 |
| Queries | 1,290 | 50 |
| Qrels | ~1,290 | ~50 |

---

## 3. Pipeline 1: FlexRAG Hybrid BM25 + Contriever

### Architecture

```
Query ──→ BM25 (keyword sparse) ──────────────┐
                                               ├──→ RRF Fusion ──→ Top-10 Pages
Query ──→ Contriever Dense (768-dim) ──→ FAISS┘
```

### Code: `scripts/build_flexrag_retriever.py`

```python
from flexrag.datasets import RAGCorpusDataset, RAGCorpusDatasetConfig
from flexrag.retriever import FlexRetriever, FlexRetrieverConfig
from flexrag.retriever.index import (
    MultiFieldIndexConfig, RetrieverIndexConfig, FaissIndexConfig,
)
from flexrag.models import EncoderConfig, HFEncoderConfig

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

def add_dense_index():
    retriever = FlexRetriever.load_from_local(RETRIEVER_PATH)
    retriever.add_index(
        index_name="dense",
        index_config=RetrieverIndexConfig(
            index_type="faiss",
            faiss_config=FaissIndexConfig(
                index_type="FLAT",   # exact search — safe for 1360 docs
                query_encoder_config=EncoderConfig(
                    encoder_type="hf",
                    hf_config=HFEncoderConfig(
                        model_path="facebook/contriever-msmarco",
                        device_id=[],
                    ),
                ),
                passage_encoder_config=EncoderConfig(
                    encoder_type="hf",
                    hf_config=HFEncoderConfig(
                        model_path="facebook/contriever-msmarco",
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
```

**Explanation:**
- **BM25 index:** keyword-based sparse retrieval over concatenated title + text fields
- **Dense FAISS index:** encodes each page into a 768-dim vector using `facebook/contriever-msmarco`
- **FLAT index type:** exact nearest-neighbour search (safe for 1,360 documents)
- Both indexes are built separately due to LMDB single-process constraint

### Code: `scripts/run_flexrag_retrieval.py`

```python
from flexrag.retriever import FlexRetriever, FlexRetrieverConfig

def main():
    queries = load_jsonl(DATA / "queries.jsonl")
    retriever = FlexRetriever(
        FlexRetrieverConfig(
            retriever_path=RETRIEVER_PATH,
            used_indexes=["bm25", "dense"],  # RRF fusion of both
        )
    )

    runs = []
    for i, q in enumerate(queries, start=1):
        results = retriever.search(q["question"], top_k=10)[0]

        ranked = []
        for r in results:
            doc_id = str(r.context_id)
            score  = float(getattr(r, "score", 0.0))
            ranked.append([doc_id, score])

        runs.append({
            "query_id": str(q["query_id"]),
            "question": q["question"],
            "results":  ranked,
        })
```

**Explanation:**
- `used_indexes=["bm25", "dense"]` activates **Reciprocal Rank Fusion (RRF)** automatically
- For each query, top-10 results from BM25 and dense are merged into a single ranked list
- Results saved to `outputs/flexrag_retrieval_top10.jsonl`

---

## 4. Pipeline 2: FlexRAG Hybrid BM25 + BGE-large

Identical architecture to Pipeline 1, with one change — the dense encoder is swapped from `facebook/contriever-msmarco` to `BAAI/bge-large-en-v1.5`:

```python
# In build_bge_retriever.py
hf_config=HFEncoderConfig(
    model_path="BAAI/bge-large-en-v1.5",  # stronger encoder
    device_id=[],
),
```

**Why BGE-large?**
- Trained on more diverse data with harder negatives
- 1024-dim embeddings (vs 768-dim for Contriever)
- Consistently top-ranked on the MTEB text embedding leaderboard

---

## 5. Pipeline 3: CLIP Visual Retrieval

### Architecture

```
Query text ──→ CLIP Text Encoder (512-dim) ──┐
                                              ├──→ Cosine Similarity ──→ Top-10 Pages
Page images ──→ CLIP Image Encoder (512-dim) ─┘
                        (pre-indexed in FAISS)
```

### Code: `scripts/build_clip_index.py`

```python
from flexrag.models import EncoderConfig, HFClipEncoderConfig
from flexrag.retriever.index.faiss_index import FaissIndex, FaissIndexConfig

CLIP_MODEL = "openai/clip-vit-base-patch32"

def clip_encoder_config() -> EncoderConfig:
    return EncoderConfig(
        encoder_type="hf_clip",
        hf_clip_config=HFClipEncoderConfig(
            model_path=CLIP_MODEL,
            device_id=[],
            normalize=True,
            convert_to_rgb=True,
            max_encode_length=77,   # CLIP text encoder hard limit
        ),
    )

index_cfg = FaissIndexConfig(
    index_type="FLAT",
    distance_function="COS",    # cosine similarity
    index_path=INDEX_DIR,
    batch_size=16,              # images are large; small batches
    query_encoder_config=encoder_cfg,
    passage_encoder_config=encoder_cfg,
)

index = FaissIndex(index_cfg)
index.build_index(iter_images(manifest))   # encodes all 1360 page images
```

**Explanation:**
- Uses the **same CLIP model** for both text queries and page images — they share the same 512-dim embedding space
- Page images are pre-encoded and stored in FAISS; queries are encoded at search time
- No BM25, no RRF — pure visual similarity search

---

## 6. Pipeline 4: ColPali Visual Retrieval

### Architecture

```
Query text ──→ ColPali Text Encoder ──→ Mean Pool ──→ Single Vector ──┐
                                                                        ├──→ FAISS ──→ Top-10
Page images ──→ ColPali Image Encoder ──→ Mean Pool ──→ Single Vector ──┘
               (PaliGemma + LoRA, patch-level embeddings)
```

### Code: `app/colpali_encoder.py`

```python
from colpali_engine.models import ColPali, ColPaliProcessor
from flexrag.models.model_base import EncoderBase, EncoderBaseConfig

class ColPaliEncoder(EncoderBase):
    """FlexRAG encoder wrapping ColPali with mean-pooled single-vector output."""

    def __init__(self, cfg: ColPaliEncoderConfig):
        super().__init__(cfg)
        self.model = ColPali.from_pretrained(
            cfg.model_path,          # vidore/colpali-v1.2
            torch_dtype=torch.bfloat16,
        ).to(self.device).eval()
        self.processor = ColPaliProcessor.from_pretrained(cfg.model_path)

    @torch.no_grad()
    def encode_image(self, images: list[PILImage]) -> np.ndarray:
        inputs = self.processor.process_images(images)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        embeddings = self.model(**inputs)  # (batch, n_patches, dim)
        emb = embeddings.float().mean(dim=1)  # mean pool → (batch, dim)
        if self.normalize:
            emb = F.normalize(emb, dim=-1)
        return emb.cpu().numpy()

    @torch.no_grad()
    def encode_text(self, texts: list[str]) -> np.ndarray:
        inputs = self.processor.process_queries(queries=texts)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        embeddings = self.model(**inputs)  # (batch, seq_len, dim)
        emb = embeddings.float().mean(dim=1)  # mean pool → (batch, dim)
        if self.normalize:
            emb = F.normalize(emb, dim=-1)
        return emb.cpu().numpy()
```

**Explanation — The Mean-Pooling Trade-off:**

ColPali natively produces **multi-vector embeddings** (one vector per image patch), designed for late-interaction MaxSim scoring:

```
Native ColPali:  Score(q, d) = Σ max_j sim(q_i, d_j)   [MaxSim over all patches]
Our approach:    Score(q, d) = sim(mean(q_i), mean(d_j)) [single cosine similarity]
```

Mean-pooling is a deliberate trade-off — it sacrifices fine-grained patch-level matching for compatibility with FlexRAG's FAISS single-vector pipeline, enabling direct comparison with text retrievers in the same framework.

---

## 7. Evaluation

### Code: `scripts/eval_vidore_retrieval.py`

```python
def dcg_at_k(relevances, k):
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances[:k]))

def ndcg_at_k(relevances, k=10):
    ideal = sorted(relevances, reverse=True)
    ideal_dcg = dcg_at_k(ideal, k)
    if ideal_dcg == 0:
        return 0.0
    return dcg_at_k(relevances, k) / ideal_dcg

def recall_at_k(binary_rels, total_relevant, k=10):
    if total_relevant == 0:
        return 0.0
    return sum(binary_rels[:k]) / total_relevant

def mrr_at_k(binary_rels, k=10):
    for idx, rel in enumerate(binary_rels[:k], start=1):
        if rel > 0:
            return 1.0 / idx
    return 0.0
```

**Metrics explained:**
| Metric | What it measures |
|---|---|
| **nDCG@10** | Ranking quality — rewards placing relevant pages higher. Primary metric. |
| **Recall@10** | Coverage — what fraction of relevant pages appear in top-10 |
| **MRR@10** | Position of first correct result — 1/rank of first hit |

---

## 8. Results

### 8.1 Full Dataset (1,290 queries, 1,360 pages)

| Retriever | Modality | nDCG@5 | nDCG@10 | Recall@5 | Recall@10 | MRR@10 |
|---|---|---|---|---|---|---|
| Contriever (BM25+Dense) | Text→Text | 0.4033 | 0.4610 | 0.2971 | 0.3719 | 0.4340 |
| BGE-large (BM25+Dense) | Text→Text | 0.4727 | 0.5499 | 0.3439 | 0.4406 | 0.5140 |
| CLIP | Text→Image | 0.0382 | 0.0490 | 0.0143 | 0.0239 | 0.0406 |
| **ColPali mean-pool** | **Text→Image** | **0.4720** | **0.5587** | **0.3090** | **0.4216** | **0.5173** |

ColPali (0.5587) narrowly outperforms BGE-large (0.5499) as the best overall retriever.

### 8.2 ViDoRe V3 Leaderboard Comparison (nDCG@10, Computer Science subset)

| Model | Type | nDCG@10 |
|---|---|---|
| colnomic-7b | Visual VLM | 0.782 |
| nemo-colembed-3b | Visual VLM | 0.778 |
| colqwen2.5 | Visual VLM | 0.752 |
| colpali-v1.3 | Visual VLM | 0.725 |
| colsmol256 | Visual VLM | 0.574 |
| **ColPali v1.2 mean-pool (ours)** | **Visual** | **0.559** |
| **BGE-large (ours)** | **Text hybrid** | **0.550** |
| **Contriever (ours)** | **Text hybrid** | **0.461** |
| BM25 baseline | Text | 0.293 |
| **CLIP (ours)** | **Visual** | **0.049** |

### 8.3 Small Dataset Validation (200 docs, 50 queries — Mac)

| Retriever | nDCG@10 | Recall@10 | MRR@10 |
|---|---|---|---|
| Contriever | 0.787 | 0.926 | 0.746 |
| BGE-large | 0.797 | 0.926 | 0.793 |
| CLIP | 0.052 | 0.111 | 0.030 |
| ColPali | 0.573 | 0.772 | 0.479 |

> **Note:** Small dataset scores are inflated due to reduced corpus size. Full dataset is authoritative.

---

## 9. Analysis

### 9.1 ColPali Beats BGE-large (Best Overall Retriever)
ColPali mean-pool (0.559 nDCG@10) narrowly outperforms BGE-large (0.550) — a visual retriever surpasses the best text retriever despite using a lossy mean-pooling approximation. This shows ColPali's document-aware backbone captures page layout, code formatting, and figures that text extraction misses.

### 9.2 BGE-large vs Contriever (+19% on nDCG@10)
Both use the same BM25+Dense+RRF framework — the only difference is the dense encoder. BGE-large's stronger training regime (harder negatives, more diverse data) yields consistent +19% improvement, demonstrating that **encoder quality is the key variable** in hybrid retrieval.

### 9.3 CLIP Failure (nDCG@10: 0.049)
CLIP was trained on (image, caption) pairs from the web, not document pages. All PDF pages from the same textbook look visually similar — same font, same layout — so CLIP cannot discriminate between them. General-purpose vision-language models are unsuitable for document retrieval without domain-specific training.

### 9.4 ColPali Mean-Pooling Gap vs Leaderboard
Our ColPali (0.559) is ~0.17 below colpali-v1.3 (0.725). Full late-interaction scoring computes:

```
MaxSim Score = Σᵢ max_j cosine(query_token_i, page_patch_j)
Mean-pool    = cosine(mean(query_tokens), mean(page_patches))
```

This fine-grained token-patch matching captures which part of a page is relevant to each part of the query — information lost when averaging all patch vectors into one.

---

## 10. Infrastructure & Deployment

### Local Development (Mac)
```bash
# Quick test on small subset
export KMP_DUPLICATE_LIB_OK=TRUE
python scripts/convert_vidore.py --small
bash run_pipeline.sh --skip-text   # CLIP + ColPali only
```

### HPC Deployment (NUS Vanda Cluster — A40 GPU)
```bash
# Interactive GPU session
qsub -I -P personal-e1610383 -l select=1:ngpus=1 -l walltime=02:00:00

# Environment setup
source ~/miniconda3/etc/profile.d/conda.sh
conda activate ~/flexrag_env

# Run pipeline step by step
export PYTHONPATH=.
export KMP_DUPLICATE_LIB_OK=TRUE
python3 scripts/build_colpali_index.py   # GPU-accelerated
```

**Key dependency resolution on HPC:**

| Package | Version | Reason |
|---|---|---|
| torch | 2.7.0+cu126 | Required by flexrag 0.3.0 |
| torchvision | 0.22.0+cu126 | Matches torch 2.7.0 |
| transformers | 4.57.6 | Has `AutoModelForVision2Seq` needed by flexrag |
| colpali-engine | 0.3.4 | Compatible with transformers 4.x (0.3.15+ requires 5.x) |

---

## 11. Key Contributions

1. **First FlexRAG evaluation on ViDoRe V3** — FlexRAG's published paper benchmarks only Wikipedia-based QA (NQ, TriviaQA, PopQA). This project applies it to visual document retrieval for the first time.

2. **Custom ColPali-FlexRAG integration** — `ColPaliEncoder` bridges ColPali's multi-vector output with FlexRAG's single-vector FAISS pipeline via mean-pooling.

3. **Four-way systematic comparison** — identical evaluation protocol across text-sparse, text-dense, and visual retrieval approaches.

4. **HPC deployment with dependency resolution** — resolved a non-trivial 3-way version conflict (torch ↔ transformers ↔ colpali-engine) for Python 3.11 on CUDA 12.6.

---

## 12. Limitations & Future Work

| Limitation | Proposed Solution |
|---|---|
| ColPali uses mean-pooling instead of MaxSim | Implement native late-interaction scoring |
| Only English CS subset evaluated | Extend to French Finance, Physics subsets |
| No generation pipeline on HPC (no Ollama) | Deploy vLLM or HuggingFace TGI |
| ColPali v1.2 (not latest v1.3) | Upgrade model for leaderboard parity |
| CLIP uses base-patch32 (smallest model) | Test CLIP-L/14 or SigLIP for better visual baseline |

---

## 13. References

1. **FlexRAG:** Zhang et al. (2025). *FlexRAG: A Flexible and Comprehensive Framework for RAG.* ACL 2025.
2. **ViDoRe V3:** Jaudoin et al. (2026). *ViDoRe V3: A Challenging Benchmark for Visual Document Retrieval.* arXiv:2601.08620
3. **ColPali:** Faysse et al. (2024). *ColPali: Efficient Document Retrieval with Vision Language Models.*
4. **BGE:** BAAI. *BGE: BAAI General Embedding.* `BAAI/bge-large-en-v1.5`
5. **Contriever:** Izacard et al. (2022). *Unsupervised Dense Information Retrieval with Contrastive Learning.*
6. **CLIP:** Radford et al. (2021). *Learning Transferable Visual Models From Natural Language Supervision.*
