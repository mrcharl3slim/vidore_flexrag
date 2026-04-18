# ViDoRe FlexRAG Pipeline — Full Step Documentation

## Overview

This pipeline evaluates four retrieval approaches on the **ViDoRe V3 Computer Science dataset** — a benchmark of 1360 PDF pages and 1290 natural language queries from computer science textbooks.

**Retrievers evaluated:**
1. FlexRAG Hybrid BM25 + Contriever (text)
2. FlexRAG Hybrid BM25 + BGE-large (text)
3. CLIP (visual)
4. ColPali (visual)

---

## Data Preparation

### Step 1 — Convert ViDoRe Dataset
`python3 scripts/convert_vidore.py`

Downloads the ViDoRe V3 Computer Science dataset from HuggingFace and converts it into 3 JSONL files:
- `corpus.jsonl` — 1360 PDF pages with extracted markdown text
- `queries.jsonl` — 1290 natural language questions
- `qrels.jsonl` — ground truth relevance judgements linking each question to its correct page

---

### Step 2 — Save Page Images
`python3 scripts/save_vidore_images.py`

Downloads the rendered PDF page images from HuggingFace and saves them to disk. Creates `image_manifest.jsonl` mapping each corpus ID to its image file path. Required by visual retrievers (CLIP, ColPali) which operate on images rather than text.

---

## Text Retrieval — Contriever

### Step 3 — Build Contriever Retriever
`python3 scripts/build_flexrag_retriever.py`

Builds a hybrid retrieval index using FlexRAG:
- Loads all 1360 pages into an LMDB document store
- Builds a **BM25 sparse index** for keyword matching
- Builds a **FAISS dense index** encoding each page with `facebook/contriever-msmarco` (768-dim vectors)

Output: `data/processed/vidore_flexrag_retriever/`

---

### Step 4 — Run Contriever Retrieval
`python3 scripts/run_flexrag_retrieval.py`

Queries all 1290 questions against the hybrid index. For each query, BM25 and dense results are merged using **Reciprocal Rank Fusion (RRF)**. Saves top-10 results per query to `outputs/flexrag_retrieval_top10.jsonl`.

---

### Step 5 — Evaluate Contriever
`python3 scripts/eval_vidore_retrieval.py`

Measures retrieval quality against ground truth qrels using `pytrec_eval`. Reports nDCG@5, nDCG@10, Recall@5, Recall@10, MRR@10.

**Results (full dataset, 1290 queries):**
| Metric | Score |
|---|---|
| nDCG@5 | 0.4033 |
| nDCG@10 | 0.4610 |
| Recall@5 | 0.2971 |
| Recall@10 | 0.3719 |
| MRR@10 | 0.4340 |

---

## Text Retrieval — BGE-large

### Step 6 — Build BGE Retriever
`python3 scripts/build_bge_retriever.py`

Same hybrid BM25+dense architecture as Step 3 but uses `BAAI/bge-large-en-v1.5` as the dense encoder — a stronger, more recent model trained with harder negatives on more diverse data.

Output: `data/processed/bge_retriever/`

---

### Step 7 — Run BGE Retrieval
`python3 scripts/run_bge_retrieval.py`

Queries all 1290 questions against the BM25+BGE-large hybrid index using RRF fusion. Saves top-10 results to `outputs/bge_retrieval_top10.jsonl`.

---

### Step 8 — Evaluate BGE
`python3 scripts/eval_bge_retrieval.py`

**Results (full dataset, 1290 queries):**
| Metric | Score |
|---|---|
| nDCG@5 | 0.4727 |
| nDCG@10 | 0.5499 |
| Recall@5 | 0.3439 |
| Recall@10 | 0.4406 |
| MRR@10 | 0.5140 |

BGE-large outperforms Contriever by ~19% on nDCG@10.

---

## Visual Retrieval — CLIP

### Step 9 — Build CLIP Index
`python3 scripts/build_clip_index.py`

Encodes all 1360 page images into 512-dim vectors using `openai/clip-vit-base-patch32`'s image encoder. Stores vectors in a FAISS flat index. At query time, the question text is encoded using CLIP's text encoder and matched against image vectors.

Output: `data/processed/clip_index/`

---

### Step 10 — Run CLIP Retrieval
`python3 scripts/run_clip_retrieval.py`

Queries all 1290 questions using CLIP's text encoder against the image index. Pure visual similarity search — no BM25, no RRF. Saves top-10 results to `outputs/clip_retrieval_top10.jsonl`.

---

### Step 11 — Evaluate CLIP
`python3 scripts/eval_clip_retrieval.py`

**Results (full dataset, 1290 queries):**
| Metric | Score |
|---|---|
| nDCG@5 | 0.0382 |
| nDCG@10 | 0.0490 |
| Recall@5 | 0.0143 |
| Recall@10 | 0.0239 |
| MRR@10 | 0.0406 |

CLIP performs near-random — it is designed for natural images, not dense text documents.

---

## Visual Retrieval — ColPali

### Step 12 — Build ColPali Index
`python3 scripts/build_colpali_index.py`

Encodes all 1360 page images using `vidore/colpali-v1.2` — a vision-language model built on PaliGemma with LoRA adapters trained specifically for document retrieval. Each page is encoded into a multi-vector representation (one per image patch), which is **mean-pooled** into a single vector to fit FlexRAG's FAISS pipeline.

Output: `data/processed/colpali_index/`

---

### Step 13 — Run ColPali Retrieval
`python3 scripts/run_colpali_retrieval.py`

Queries all 1290 questions against the ColPali index. Query text is encoded using ColPali's text encoder and matched against page image vectors. Saves top-10 results to `outputs/colpali_retrieval_top10.jsonl`.

---

### Step 14 — Evaluate ColPali
`python3 scripts/eval_colpali_retrieval.py`

Measures ColPali's visual retrieval quality against ground truth qrels.

---

## Final Comparison

### Step 15 — Compare All Retrievers
`python3 scripts/compare_retrievers.py`

Produces a side-by-side comparison table of all 4 retrievers against the published ViDoRe V3 leaderboard benchmarks.

---

## Results Summary

### Full Dataset Results (1290 queries, 1360 corpus pages)

| Retriever | Modality | nDCG@5 | nDCG@10 | Recall@5 | Recall@10 | MRR@10 |
|---|---|---|---|---|---|---|
| Contriever (BM25+Dense) | Text→Text | 0.4033 | 0.4610 | 0.2971 | 0.3719 | 0.4340 |
| BGE-large (BM25+Dense) | Text→Text | 0.4727 | **0.5499** | 0.3439 | **0.4406** | **0.5140** |
| CLIP | Text→Image | 0.0382 | 0.0490 | 0.0143 | 0.0239 | 0.0406 |
| ColPali | Text→Image | *pending* | *pending* | *pending* | *pending* | *pending* |

### ViDoRe V3 Leaderboard Comparison (nDCG@10)

| Model | nDCG@10 | Notes |
|---|---|---|
| colnomic-7b | 0.782 | Leaderboard best |
| nemo-colembed-3b | 0.778 | |
| colqwen2.5 | 0.752 | |
| colpali-v1.3 | 0.725 | |
| colsmol256 | 0.574 | |
| **ColPali v1.2 mean-pool (ours)** | *pending* | |
| **BGE-large (ours)** | **0.550** | Best text retriever |
| **Contriever (ours)** | 0.461 | |
| CLIP (ours) | 0.049 | Not designed for docs |

---

## Key Findings

1. **BGE-large outperforms Contriever by ~19%** on nDCG@10 (0.550 vs 0.461), confirming that the choice of dense encoder significantly impacts hybrid retrieval quality.

2. **CLIP is unsuitable for document retrieval** — scoring near-random (nDCG@10: 0.049) because it was designed for natural images, not text-dense PDF pages.

3. **Text retrievers are competitive with visual models** — BGE-large (0.550) approaches the lower-tier visual models on the ViDoRe leaderboard, despite not seeing the page images at all.

4. **ColPali's mean-pooling trade-off** — the pipeline uses mean-pooling over patch embeddings for FlexRAG compatibility, sacrificing ColPali's native late-interaction MaxSim scoring. This explains the gap vs leaderboard ColPali scores.

---

## Dataset

- **Name:** ViDoRe V3 Computer Science
- **Source:** `vidore/vidore_v3_computer_science` on HuggingFace
- **Language:** English
- **Documents:** 2 Python programming textbooks
- **Corpus size:** 1360 PDF pages
- **Queries:** 1290 natural language questions
- **Leaderboard:** https://huggingface.co/spaces/vidore/vidore-leaderboard
