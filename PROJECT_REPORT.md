# ViDoRe FlexRAG: Multimodal Document Retrieval on ViDoRe V3
**Author:** Charles (e1610383)
**Date:** April 2026
**Repository:** https://github.com/mrcharl3slim/vidore_flexrag

---

## 1. Project Overview

This project implements and evaluates four retrieval pipelines — both text-based and visual — on the **ViDoRe V3 Computer Science benchmark**, a standardised document retrieval benchmark of real-world PDF documents. The pipeline is built on top of **FlexRAG** (ACL 2025), extended with custom multimodal retrieval components including CLIP and ColPali.

**Research Question:**
> *How do text-based hybrid retrieval methods compare to state-of-the-art visual document retrieval models on the ViDoRe V3 benchmark?*

---

## 2. Dataset

| Property | Value |
|---|---|
| **Name** | ViDoRe V3 Computer Science |
| **Source** | `vidore/vidore_v3_computer_science` (HuggingFace) |
| **Language** | English |
| **Documents** | 2 Python programming textbooks |
| **Corpus size** | 1,360 PDF pages |
| **Queries** | 1,290 natural language questions |
| **Primary metric** | nDCG@10 |
| **Leaderboard** | https://huggingface.co/spaces/vidore/vidore-leaderboard |

The ViDoRe V3 benchmark covers 8 public domains across 6 languages (English, French, Spanish, German, Italian, Portuguese) with 26,000 pages total. This project focuses on the English Computer Science subset.

---

## 3. System Architecture

### 3.1 Framework: FlexRAG

FlexRAG (ACL 2025 Demo) is used as the backbone retrieval framework. It provides:
- **LMDB document store** for efficient corpus management
- **FAISS dense indexing** for nearest-neighbour vector search
- **BM25 sparse indexing** for keyword-based retrieval
- **Reciprocal Rank Fusion (RRF)** for hybrid result merging

### 3.2 Retrieval Pipelines

Four retrieval pipelines were implemented and evaluated:

#### Pipeline 1: FlexRAG Hybrid BM25 + Contriever
```
Query → BM25 (keyword) ──┐
                          ├── RRF fusion → Top-10 pages
Query → Contriever dense ─┘
```
- Dense encoder: `facebook/contriever-msmarco` (768-dim)
- Modality: Text query → Text corpus

#### Pipeline 2: FlexRAG Hybrid BM25 + BGE-large
```
Query → BM25 (keyword) ──┐
                          ├── RRF fusion → Top-10 pages
Query → BGE-large dense ──┘
```
- Dense encoder: `BAAI/bge-large-en-v1.5` (1024-dim)
- Modality: Text query → Text corpus

#### Pipeline 3: CLIP Visual Retrieval
```
Query text → CLIP text encoder ──→ Cosine similarity → Top-10 pages
               Page images → CLIP image encoder (pre-indexed)
```
- Model: `openai/clip-vit-base-patch32` (512-dim)
- Modality: Text query → Image corpus

#### Pipeline 4: ColPali Visual Retrieval
```
Query text → ColPali text encoder ──→ Cosine similarity → Top-10 pages
              Page images → ColPali image encoder (mean-pooled, pre-indexed)
```
- Model: `vidore/colpali-v1.2` (PaliGemma + LoRA)
- Modality: Text query → Image corpus
- **Note:** ColPali natively uses late-interaction MaxSim scoring. Patch embeddings are **mean-pooled** into a single vector for FlexRAG FAISS compatibility.

---

## 4. Experimental Setup

### 4.1 Infrastructure
- **Development & testing:** MacBook Pro (Apple Silicon, MPS GPU)
- **Full pipeline execution:** NUS HPC Vanda Cluster (NVIDIA A40 GPU, 36 CPUs, 240GB RAM)
- **Job scheduler:** PBS (qsub), project `personal-e1610383`
- **Python environment:** Conda (Python 3.11), PyTorch 2.7.0+cu126

### 4.2 Key Dependencies
| Package | Version | Purpose |
|---|---|---|
| flexrag | 0.3.0 | Retrieval framework |
| colpali-engine | 0.3.4 | ColPali model loading |
| transformers | 4.57.6 | HuggingFace model hub |
| torch | 2.7.0+cu126 | Deep learning |
| faiss-cpu | 1.13.2 | Vector indexing |
| pytrec_eval | 0.5 | IR evaluation metrics |

### 4.3 Evaluation Protocol
- All 1,290 queries evaluated against all 1,360 corpus pages
- Metrics computed using `pytrec_eval` against ground truth qrels
- Primary metric: **nDCG@10** (normalised Discounted Cumulative Gain at rank 10)

---

## 5. Results

### 5.1 Full Dataset Results (1,290 queries, 1,360 pages)

| Retriever | Modality | nDCG@5 | nDCG@10 | Recall@5 | Recall@10 | MRR@10 |
|---|---|---|---|---|---|---|
| Contriever (BM25+Dense) | Text→Text | 0.4033 | 0.4610 | 0.2971 | 0.3719 | 0.4340 |
| BGE-large (BM25+Dense) | Text→Text | 0.4727 | 0.5499 | 0.3439 | 0.4406 | 0.5140 |
| CLIP | Text→Image | 0.0382 | 0.0490 | 0.0143 | 0.0239 | 0.0406 |
| **ColPali mean-pool** | **Text→Image** | **0.4720** | **0.5587** | **0.3090** | **0.4216** | **0.5173** |

ColPali (0.5587) narrowly outperforms BGE-large (0.5499) as the best overall retriever.

### 5.2 Comparison with ViDoRe V3 Leaderboard (nDCG@10)

| Model | Type | nDCG@10 | Source |
|---|---|---|---|
| colnomic-7b | Visual VLM | 0.782 | ViDoRe V3 Leaderboard |
| nemo-colembed-3b | Visual VLM | 0.778 | ViDoRe V3 Leaderboard |
| nemo-colembed-1b | Visual VLM | 0.755 | ViDoRe V3 Leaderboard |
| colqwen2.5 | Visual VLM | 0.752 | ViDoRe V3 Leaderboard |
| colpali-v1.3 | Visual VLM | 0.725 | ViDoRe V3 Leaderboard |
| colsmol256 | Visual VLM | 0.574 | ViDoRe V3 Leaderboard |
| **ColPali v1.2 mean-pool (ours)** | **Visual** | **0.559** | **This project** |
| **BGE-large (ours)** | **Text hybrid** | **0.550** | **This project** |
| **Contriever (ours)** | **Text hybrid** | **0.461** | **This project** |
| BM25 baseline | Text | 0.293 | ViDoRe V3 Leaderboard |
| **CLIP (ours)** | **Visual** | **0.049** | **This project** |

### 5.3 Small Dataset Validation (200 docs, 50 queries — Mac)

Produced for rapid local validation before full HPC runs.

| Retriever | nDCG@10 | Recall@10 | MRR@10 |
|---|---|---|---|
| Contriever | 0.787 | 0.926 | 0.746 |
| BGE-large | 0.797 | 0.926 | 0.793 |
| CLIP | 0.052 | 0.111 | 0.030 |
| ColPali | 0.573 | 0.772 | 0.479 |

> **Note:** Small dataset scores are inflated due to reduced corpus size. Full dataset results are authoritative.

---

## 6. Analysis & Discussion

### 6.1 ColPali Beats BGE-large (Best Overall Retriever)
ColPali mean-pool (0.559 nDCG@10) narrowly outperforms BGE-large (0.550) — a visual retriever surpasses the best text retriever despite using a lossy mean-pooling approximation. This demonstrates that ColPali's document-aware vision-language backbone (trained specifically on PDF pages) captures information that text extraction misses — page layout, code formatting, figures, and visual structure.

### 6.2 BGE-large vs Contriever (+19%)
Both use the same BM25+Dense+RRF framework — the only difference is the dense encoder. BGE-large's stronger training regime yields a consistent +19% improvement (0.550 vs 0.461), confirming that **encoder quality is the primary variable** in hybrid retrieval.

### 6.3 CLIP Failure (nDCG@10: 0.049)
CLIP achieves near-random performance, finding the correct page only 2.4% of the time in top-10. CLIP was designed for natural image-text pairs from the web, not text-dense PDF pages. All pages from the same Python textbook look visually similar, making CLIP unable to discriminate between them.

### 6.4 ColPali Mean-Pooling Gap vs Leaderboard
Our ColPali (0.559) is ~0.17 below colpali-v1.3 (0.725) on the leaderboard. This gap is primarily due to mean-pooling replacing ColPali's native late-interaction MaxSim scoring:

```
Native MaxSim:   Score(q,d) = Σᵢ max_j cosine(query_token_i, patch_j)
Mean-pool:       Score(q,d) = cosine(mean(query_tokens), mean(patches))
```

Mean-pooling loses fine-grained token-patch alignment — which parts of the query match which parts of the page — information that is critical for complex multi-topic queries.

### 6.5 Our Models vs Leaderboard Context
Both our ColPali (0.559) and BGE-large (0.550) score between colsmol256 (0.574) and the BM25 baseline (0.293) on the leaderboard. The gap to top visual models (colnomic-7b: 0.782) is large, primarily because those models use larger backbones (3B–7B parameters) with full late-interaction scoring on much higher resolution images.

---

## 7. Key Contributions

1. **First FlexRAG evaluation on ViDoRe V3** — FlexRAG's published paper benchmarks only Wikipedia QA (NQ, TriviaQA, PopQA). This project is the first to apply it to visual document retrieval.

2. **Custom ColPali-FlexRAG integration** — `ColPaliEncoder` bridges ColPali's multi-vector output with FlexRAG's single-vector FAISS pipeline via mean-pooling.

3. **Four-way systematic comparison** — identical evaluation protocol across two text and two visual retrieval approaches on the same benchmark.

4. **HPC deployment** — full pipeline executed on NUS HPC Vanda Cluster (A40 GPU) via PBS batch jobs, resolving a non-trivial 3-way Python dependency conflict.

---

## 8. Limitations & Future Work

| Limitation | Proposed Solution |
|---|---|
| ColPali uses mean-pooling instead of MaxSim | Implement native late-interaction scoring |
| Only English CS subset evaluated | Extend to multilingual subsets (French Finance, Physics) |
| No generation pipeline on HPC (Ollama unavailable) | Deploy vLLM or HuggingFace TGI |
| ColPali v1.2 evaluated (not latest v1.3) | Upgrade for leaderboard parity |
| CLIP uses smallest model (base-patch32) | Test CLIP-L/14 or SigLIP for stronger visual baseline |

---

## 9. Repository Structure

```
vidore_flexrag/
├── app/
│   ├── colpali_encoder.py          # Custom ColPali encoder for FlexRAG
│   ├── dataio.py                   # Data loading utilities
│   ├── generator.py                # Answer generation with Ollama
│   └── prompts.py                  # Prompt templates
├── scripts/
│   ├── convert_vidore.py           # Dataset conversion (--small flag)
│   ├── save_vidore_images.py       # Page image extraction
│   ├── build_flexrag_retriever.py  # Contriever index builder
│   ├── build_bge_retriever.py      # BGE-large index builder
│   ├── build_clip_index.py         # CLIP index builder
│   ├── build_colpali_index.py      # ColPali index builder
│   ├── run_flexrag_retrieval.py    # Contriever retrieval
│   ├── run_bge_retrieval.py        # BGE retrieval
│   ├── run_clip_retrieval.py       # CLIP retrieval
│   ├── run_colpali_retrieval.py    # ColPali retrieval
│   ├── eval_vidore_retrieval.py    # Contriever evaluation
│   ├── eval_bge_retrieval.py       # BGE evaluation
│   ├── eval_clip_retrieval.py      # CLIP evaluation
│   ├── eval_colpali_retrieval.py   # ColPali evaluation
│   └── compare_retrievers.py       # Final comparison table
├── run_pipeline.sh                 # Local Mac pipeline runner
├── run_hopper.sh                   # NUS HPC PBS job script
├── requirements.txt                # Python dependencies
├── PIPELINE_DOCUMENTATION.md      # Step-by-step pipeline guide
├── PROJECT_REPORT.md               # This report
└── PROJECT_REPORT_WITH_CODE.md    # Technical report with code snippets
```

---

## 10. References

1. **FlexRAG:** Zhang et al. (2025). *FlexRAG: A Flexible and Comprehensive Framework for Retrieval-Augmented Generation.* ACL 2025 Demo. arXiv:2506.12494
2. **ViDoRe V3:** Jaudoin et al. (2026). *ViDoRe V3: A Challenging Benchmark for Visual Document Retrieval.* arXiv:2601.08620
3. **ColPali:** Faysse et al. (2024). *ColPali: Efficient Document Retrieval with Vision Language Models.*
4. **BGE-large:** BAAI. *BGE: BAAI General Embedding.* HuggingFace: `BAAI/bge-large-en-v1.5`
5. **Contriever:** Izacard et al. (2022). *Unsupervised Dense Information Retrieval with Contrastive Learning.*
6. **CLIP:** Radford et al. (2021). *Learning Transferable Visual Models From Natural Language Supervision.*
