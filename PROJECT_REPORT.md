# ViDoRe FlexRAG: Multimodal Document Retrieval on ViDoRe V3
**Author:** Charles (e1610383)
**Date:** April 2026
**Repository:** https://github.com/mrcharl3slim/vidore_flexrag

---

## 1. Project Overview

This project evaluates multiple retrieval approaches — both text-based and visual — on the **ViDoRe V3 Computer Science benchmark**, a standardised document retrieval benchmark consisting of real-world PDF documents. The pipeline is built on top of **FlexRAG**, an open-source Retrieval-Augmented Generation framework, extended with custom multimodal retrieval components including CLIP and ColPali.

The central research question is:

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
| **Evaluation metric** | nDCG@10 (primary), Recall@10, MRR@10 |
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
Query text → CLIP text encoder ──→ Similarity search → Top-10 pages
                     Page images → CLIP image encoder (indexed)
```
- Model: `openai/clip-vit-base-patch32` (512-dim)
- Modality: Text query → Image corpus

#### Pipeline 4: ColPali Visual Retrieval
```
Query text → ColPali text encoder ──→ Similarity search → Top-10 pages
                  Page images → ColPali image encoder (indexed, mean-pooled)
```
- Model: `vidore/colpali-v1.2` (PaliGemma + LoRA)
- Modality: Text query → Image corpus
- **Note:** ColPali natively uses late-interaction MaxSim scoring (like ColBERT). In this pipeline, patch embeddings are **mean-pooled** into a single vector for FlexRAG FAISS compatibility — a speed-accuracy trade-off.

---

## 4. Experimental Setup

### 4.1 Infrastructure
- **Development & testing:** MacBook Pro (Apple Silicon, MPS GPU)
- **Full pipeline execution:** NUS HPC Vanda Cluster (NVIDIA A40 GPU, 36 CPUs, 240GB RAM)
- **Job scheduler:** PBS (qsub)
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
- All 1,290 queries evaluated against 1,360 corpus pages
- Metrics computed using `pytrec_eval` against ground truth qrels
- Primary metric: **nDCG@10** (normalised Discounted Cumulative Gain at rank 10)

---

## 5. Results

### 5.1 Full Dataset Results (1,290 queries, 1,360 pages)

| Retriever | Modality | nDCG@5 | nDCG@10 | Recall@5 | Recall@10 | MRR@10 |
|---|---|---|---|---|---|---|
| Contriever (BM25+Dense) | Text→Text | 0.4033 | 0.4610 | 0.2971 | 0.3719 | 0.4340 |
| BGE-large (BM25+Dense) | Text→Text | 0.4727 | **0.5499** | 0.3439 | **0.4406** | **0.5140** |
| CLIP | Text→Image | 0.0382 | 0.0490 | 0.0143 | 0.0239 | 0.0406 |
| ColPali mean-pool | Text→Image | 0.4720 | 0.5587 | 0.3090 | 0.4216 | 0.5173 |

### 5.2 Comparison with ViDoRe V3 Leaderboard (nDCG@10)

| Model | Type | nDCG@10 | Source |
|---|---|---|---|
| colnomic-7b | Visual (VLM) | 0.782 | ViDoRe V3 Leaderboard |
| nemo-colembed-3b | Visual (VLM) | 0.778 | ViDoRe V3 Leaderboard |
| nemo-colembed-1b | Visual (VLM) | 0.755 | ViDoRe V3 Leaderboard |
| colqwen2.5 | Visual (VLM) | 0.752 | ViDoRe V3 Leaderboard |
| colpali-v1.3 | Visual (VLM) | 0.725 | ViDoRe V3 Leaderboard |
| colsmol256 | Visual (VLM) | 0.574 | ViDoRe V3 Leaderboard |
| **BGE-large (ours)** | **Text hybrid** | **0.550** | **This project** |
| **Contriever (ours)** | **Text hybrid** | **0.461** | **This project** |
| **ColPali v1.2 mean-pool (ours)** | **Visual** | **0.559** | **This project** |
| **CLIP (ours)** | **Visual** | **0.049** | **This project** |

### 5.3 Small Dataset Validation Results (200 docs, 50 queries)

These results were produced on a local Mac for rapid validation before full dataset runs.

| Retriever | nDCG@10 | Recall@10 | MRR@10 |
|---|---|---|---|
| Contriever | 0.787 | 0.926 | 0.746 |
| BGE-large | 0.797 | 0.926 | 0.793 |
| CLIP | 0.052 | 0.111 | 0.030 |
| ColPali | 0.573 | 0.772 | 0.479 |

> **Note:** Small dataset scores are significantly inflated due to the reduced corpus size and fewer evaluated queries. Full dataset scores are the authoritative results.

---

## 6. Analysis & Discussion

### 6.1 Text vs Visual Retrieval
Text-based hybrid retrieval (BGE-large: 0.550 nDCG@10) significantly outperforms CLIP (0.049) on this dataset. This is expected — the ViDoRe Computer Science subset consists of Python textbooks with clean, extractable markdown text. Text retrievers can directly match query keywords against the page content.

### 6.2 BGE-large vs Contriever
BGE-large outperforms Contriever by ~19% on nDCG@10 (0.550 vs 0.461), demonstrating that the choice of dense encoder meaningfully impacts hybrid retrieval quality. BGE-large was trained with harder negatives on more diverse data, making it a stronger semantic encoder.

### 6.3 CLIP Limitations for Document Retrieval
CLIP achieves near-random performance (nDCG@10: 0.049), finding the correct page only 2.4% of the time in top-10. CLIP was designed for natural image-text matching (photos, objects) and cannot distinguish between visually similar text-dense PDF pages.

### 6.4 ColPali's Mean-Pooling Trade-off
ColPali natively uses **late-interaction MaxSim scoring** — comparing every query token against every image patch. This pipeline replaces it with **mean-pooling** for FlexRAG compatibility, which is faster but loses fine-grained patch-level matching. This explains the expected gap between our ColPali score and the leaderboard's colpali-v1.3 (0.725).

### 6.5 Text Retrievers vs Leaderboard Visual Models
On this particular subset, the best text retriever (BGE-large: 0.550) scores below the weakest leaderboard visual model (colsmol256: 0.574). This suggests that even purpose-trained visual document models have an advantage, likely due to their ability to process page layout, fonts, code blocks, and figures that text extraction may miss or distort.

---

## 7. Key Contributions

1. **Applied FlexRAG to ViDoRe V3** — FlexRAG's published benchmarks focus on Wikipedia-based QA datasets (NQ, TriviaQA, PopQA). This project is the first to apply FlexRAG to the visual document retrieval benchmark.

2. **Custom ColPali integration** — Developed `ColPaliEncoder` (`app/colpali_encoder.py`) that wraps ColPali within FlexRAG's FAISS pipeline via mean-pooling, enabling direct comparison with text retrievers.

3. **Four-way retrieval comparison** — Systematic evaluation of two text-based and two visual retrieval approaches on the same benchmark with the same evaluation protocol.

4. **HPC deployment** — Successfully deployed and ran the full pipeline on NUS HPC Vanda Cluster (A40 GPU) using PBS job scheduling and Singularity-compatible conda environments.

---

## 8. Limitations & Future Work

| Limitation | Future Work |
|---|---|
| ColPali uses mean-pooling instead of MaxSim | Implement full late-interaction scoring for accurate ColPali comparison |
| Only one ViDoRe V3 subset evaluated | Extend to multilingual subsets (French Finance, Physics) |
| No generation pipeline on HPC (Ollama unavailable) | Integrate vLLM or HuggingFace TGI for server-side generation |
| ColPali v1.2 evaluated (not latest v1.3) | Upgrade to colpali-v1.3 for leaderboard parity |
| Text extractability varies by PDF | Evaluate on image-heavy subsets (Industrial, Pharmaceuticals) where visual models should outperform text |

---

## 9. Repository Structure

```
vidore_flexrag/
├── app/
│   ├── colpali_encoder.py     # Custom ColPali encoder for FlexRAG
│   ├── dataio.py              # Data loading utilities
│   ├── generator.py           # Answer generation with Ollama
│   └── prompts.py             # Prompt templates
├── scripts/
│   ├── convert_vidore.py      # Dataset conversion (supports --small flag)
│   ├── save_vidore_images.py  # Page image extraction
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
├── run_pipeline.sh            # Local Mac pipeline runner
├── run_hopper.sh              # NUS HPC PBS job script
├── requirements.txt           # Python dependencies
├── PIPELINE_DOCUMENTATION.md # Step-by-step pipeline guide
└── PROJECT_REPORT.md          # This report
```

---

## 10. References

1. **FlexRAG:** Zhang et al. (2025). *FlexRAG: A Flexible and Comprehensive Framework for Retrieval-Augmented Generation.* ACL 2025 Demo. arXiv:2506.12494
2. **ViDoRe V3:** Jaudoin et al. (2026). *ViDoRe V3: A Challenging Benchmark for Visual Document Retrieval.* arXiv:2601.08620
3. **ColPali:** Faysse et al. (2024). *ColPali: Efficient Document Retrieval with Vision Language Models.*
4. **BGE-large:** BAAI. *BGE: BAAI General Embedding.* HuggingFace: `BAAI/bge-large-en-v1.5`
5. **Contriever:** Izacard et al. (2022). *Unsupervised Dense Information Retrieval with Contrastive Learning.*
6. **CLIP:** Radford et al. (2021). *Learning Transferable Visual Models From Natural Language Supervision.*
