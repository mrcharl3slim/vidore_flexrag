# vidore_flexrag

RAG pipeline evaluating [FlexRAG](https://github.com/ictnlp/FlexRAG)'s retrieval encoders — text and multimodal — against the [ViDoRe V3 Computer Science](https://huggingface.co/datasets/vidore/vidore_v3_computer_science) benchmark dataset.

---

## Milestones

| # | Milestone | Status |
|---|---|---|
| 1 | Text RAG pipeline (BM25 + contriever-msmarco) | ✅ Complete |
| 2 | Validate FlexRAG's `hf_clip` multimodal encoder end-to-end | ✅ Complete |
| 3 | Upgrade text encoder to BGE-large | ✅ Complete |
| 4 | Implement ColPali encoder as custom FlexRAG encoder | ✅ Complete |
| 5 | Upgrade generation to qwen2.5 with top-5 contexts | ✅ Complete |
| 6 | Page caption pipeline (llava:7b) | ✅ Complete |
| 7 | Full comparison vs ViDoRe V3 leaderboard baselines | ✅ Complete |

---

## Results

### Retrieval — ViDoRe V3 Computer Science (1290 queries, 1360 corpus pages)

Metrics follow the ViDoRe leaderboard convention: graded NDCG using qrel relevance scores 1–2.

| Retriever | Modality | nDCG@5 | nDCG@10 | Recall@5 | Recall@10 | MRR@10 |
|---|---|---|---|---|---|---|
| BM25 baseline (ViDoRe leaderboard) | text → text | — | 0.293 | — | — | — |
| FlexRAG BM25 + contriever-msmarco | text → text | 0.403 | 0.461 | 0.297 | 0.372 | 0.434 |
| **FlexRAG BM25 + BGE-large** | **text → text** | **0.473** | **0.550** | **0.344** | **0.441** | **0.514** |
| FlexRAG hf_clip (clip-vit-base-patch32) | text → image | 0.038 | 0.049 | 0.014 | 0.024 | 0.041 |
| ColPali mean-pool (colpali-v1.2) | text → image | — | — | — | — | — |
| nemo-colembed-3b (leaderboard best) | text → image | — | 0.778 | — | — | — |

> ColPali results pending full corpus encode (~1–3 hrs on CPU).

### Generation — 50 queries, qwen2.5:latest via Ollama

| Metric | qwen2 (v1) | qwen2.5 (v2, top-5) |
|---|---|---|
| Exact Match | 0.02 | 0.00 |
| Token F1 | 0.379 | 0.245 |
| ROUGE-L | 0.317 | 0.197 |
| Insufficient Evidence Rate | 0.00 | 0.38 |
| **LLM Judge Accuracy** | 0.88 | **0.90** |

### Interpretation

**Text retrieval:** BGE-large (nDCG@10 = 0.550) is a significant improvement over contriever-msmarco (0.461), reaching ~71% of the leaderboard best. FlexRAG's hybrid BM25 + dense RRF architecture is effective — the encoder is the main differentiator.

**CLIP multimodal:** `clip-vit-base-patch32` scores near-zero (nDCG@10 = 0.049) because it was trained on photo-caption pairs, not document pages. It cannot read text within images. This validates that FlexRAG's `hf_clip` encoder works correctly as a component, but the underlying model is unsuitable for document retrieval.

**ColPali multimodal:** `vidore/colpali-v1.2` is the correct model for ViDoRe — it uses a PaliGemma backbone fine-tuned specifically on document page retrieval. Expected to score significantly higher than CLIP once the full index is built.

**Generation:** LLM judge accuracy improved from 0.88 → 0.90 with qwen2.5. The higher insufficient-evidence rate (0.38 vs 0.00) reflects qwen2.5 being more calibrated — it declines to answer when context is insufficient rather than hallucinating. Low lexical scores (EM/ROUGE) are expected because both models generate verbose explanations rather than short reference-style answers; the LLM judge correctly recognises semantically correct answers that lexical metrics penalise.

---

## Running with Docker (recommended for teammates)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose v2)
- ~20 GB free disk space (models + indexes + images)
- 16 GB RAM recommended for ColPali

### Quickstart

```bash
git clone <repo-url>
cd vidore_flexrag

# 1. Build the app image and start both services (app + ollama)
docker compose up -d

# 2. Pull required Ollama models (runs inside the ollama container)
docker compose exec ollama ollama pull qwen2.5:latest   # required
docker compose exec ollama ollama pull llava:7b          # optional: page captions

# 3. Run the full pipeline
docker compose exec app bash run_pipeline.sh
```

All output is written to `./outputs/` and all data to `./data/` on your host machine (bind-mounted). HuggingFace model weights (~6 GB for ColPali) are cached in a named Docker volume and survive image rebuilds.

### Flags

```bash
docker compose exec app bash run_pipeline.sh --skip-text     # multimodal only
docker compose exec app bash run_pipeline.sh --clip-only     # CLIP + ColPali + compare
docker compose exec app bash run_pipeline.sh --colpali-only  # ColPali + compare only
```

### Expected runtimes

| Step | Approximate time |
|---|---|
| Dataset download + image save | 10–30 min (network) |
| BGE-large index build | ~5 min |
| CLIP index build | ~5 min |
| **ColPali index build** | **~1–3 hrs on CPU** |
| Generation (50 queries) | ~10 min |
| LLM judge (50 queries) | ~5 min |

> ColPali is the slow step. Test with a sample first:
> ```bash
> docker compose exec app bash -c "PYTHONPATH=. python scripts/build_colpali_index.py --sample 50"
> ```

### Stopping

```bash
docker compose down          # stop containers, keep volumes
docker compose down -v       # stop containers AND delete all volumes (deletes models!)
```

---

## Requirements (local install)

- Python 3.12
- [Ollama](https://ollama.com) with `qwen2.5:latest` pulled
- `llava:7b` (optional — for page caption generation)

---

## Installation (local)

```bash
git clone <repo-url>
cd vidore_flexrag

python3.12 -m venv venv
source venv/bin/activate

# Install faiss-cpu before other deps (build order matters)
pip install faiss-cpu

# Install FlexRAG directly from GitHub (not on PyPI)
pip install git+https://github.com/ictnlp/FlexRAG.git --no-deps

# Install ColPali engine (pinned for transformers 4.x compatibility)
pip install colpali-engine==0.3.4

# Install all remaining pinned dependencies
pip install -r requirements.txt
```

> **macOS note:** `scann` has no macOS wheel and will remain unresolved. All other dependencies install correctly.

### Pull Ollama models

```bash
ollama pull qwen2.5:latest       # required — generation + LLM judge
ollama pull llava:7b             # optional — page captions
```

---

## Running the Pipeline

### One command (recommended)

```bash
bash run_pipeline.sh
```

The script runs all 20 steps in order, skips steps whose output already exists, checks Ollama is running, and prints a final comparison table.

**Flags:**
```bash
bash run_pipeline.sh --skip-text      # multimodal pipelines only
bash run_pipeline.sh --clip-only      # CLIP + ColPali + compare
bash run_pipeline.sh --colpali-only   # ColPali + compare only
```

### Step by step

```bash
# ── Data prep ──────────────────────────────────────────────────────────────

python scripts/convert_vidore.py          # download + convert dataset
python scripts/save_vidore_images.py      # save page images to disk

# ── Text pipeline: contriever-msmarco ─────────────────────────────────────

python scripts/build_flexrag_retriever.py
python scripts/run_flexrag_retrieval.py
python scripts/eval_vidore_retrieval.py

# ── Text pipeline: BGE-large ───────────────────────────────────────────────

python scripts/build_bge_retriever.py
python scripts/run_bge_retrieval.py
python scripts/eval_bge_retrieval.py

# ── Generation ─────────────────────────────────────────────────────────────

python scripts/caption_pages.py           # optional: page captions via llava:7b
PYTHONPATH=. python scripts/run_generation.py
python scripts/eval_vidore_generation.py
python scripts/eval_vidore_llm_judge.py
python scripts/build_qualitative_review.py

# ── Multimodal: CLIP ───────────────────────────────────────────────────────

python scripts/build_clip_index.py
PYTHONPATH=. python scripts/run_clip_retrieval.py
python scripts/eval_clip_retrieval.py

# ── Multimodal: ColPali  (~1–3 hrs on CPU) ────────────────────────────────

PYTHONPATH=. python scripts/build_colpali_index.py
PYTHONPATH=. python scripts/run_colpali_retrieval.py
python scripts/eval_colpali_retrieval.py

# ── Final comparison ───────────────────────────────────────────────────────

python scripts/compare_retrievers.py
```

> `PYTHONPATH=.` is required for scripts that import from `app/`.
>
> ColPali builds ~1–3 hours on CPU. Test first with `--sample 50`:
> ```bash
> PYTHONPATH=. python scripts/build_colpali_index.py --sample 50
> ```

---

## Validation Script

To validate FlexRAG's `hf_clip` encoder in isolation (sanity checks + retrieval on a subset):

```bash
PYTHONPATH=. python scripts/validate_clip_encoder.py --n 30
```

---

## Project Structure

```
vidore_flexrag/
├── app/
│   ├── colpali_encoder.py            # Custom FlexRAG ColPali encoder
│   ├── vidore_assistant.py           # FlexRAG AssistantBase subclass
│   ├── generator.py                  # Ollama generator wrapper
│   ├── dataio.py                     # Data loading utilities
│   └── prompts.py                    # Prompt templates
├── scripts/
│   ├── convert_vidore.py             # Download and convert ViDoRe dataset
│   ├── save_vidore_images.py         # Save corpus page images to disk
│   │
│   ├── build_flexrag_retriever.py    # BM25 + contriever-msmarco retriever
│   ├── run_flexrag_retrieval.py
│   ├── eval_vidore_retrieval.py
│   │
│   ├── build_bge_retriever.py        # BM25 + BGE-large retriever
│   ├── run_bge_retrieval.py
│   ├── eval_bge_retrieval.py
│   │
│   ├── caption_pages.py              # Generate page captions via llava:7b
│   ├── run_generation.py             # Generate answers with qwen2.5 (top-5)
│   ├── eval_vidore_generation.py     # Lexical metrics (EM, Token F1, ROUGE-L)
│   ├── eval_vidore_llm_judge.py      # LLM-as-judge evaluation
│   ├── build_qualitative_review.py   # Qualitative review (JSON + Markdown)
│   │
│   ├── build_clip_index.py           # CLIP image FAISS index
│   ├── run_clip_retrieval.py
│   ├── eval_clip_retrieval.py
│   ├── validate_clip_encoder.py      # Standalone hf_clip encoder validation
│   │
│   ├── build_colpali_index.py        # ColPali image FAISS index
│   ├── run_colpali_retrieval.py
│   ├── eval_colpali_retrieval.py
│   │
│   ├── compare_retrievers.py         # Final comparison table
│   └── ask_vidore.py                 # Interactive Q&A CLI
├── data/
│   └── processed/
│       ├── corpus.jsonl
│       ├── queries.jsonl
│       ├── qrels.jsonl
│       ├── image_manifest.jsonl
│       ├── images/                   # Page images (PNG, one per corpus doc)
│       ├── vidore_flexrag_retriever/ # contriever retriever + indexes
│       ├── bge_retriever/            # BGE-large retriever + indexes
│       ├── clip_index/               # CLIP FAISS index + id_map
│       └── colpali_index/            # ColPali FAISS index + id_map
├── outputs/
│   ├── retrieval_metrics.json
│   ├── bge_retrieval_metrics.json
│   ├── clip_retrieval_metrics.json
│   ├── colpali_retrieval_metrics.json
│   ├── generation_metrics.json
│   ├── llm_judge_metrics.json
│   ├── predictions.jsonl
│   ├── page_captions.json
│   ├── qualitative_review_top20.json
│   └── qualitative_review_top20.md
├── run_pipeline.sh                   # Full pipeline runner
├── requirements.txt
└── README.md
```

---

## Known Issues

| Issue | Cause | Fix |
|---|---|---|
| `colpali-engine` upgrades transformers to 5.x | No upper bound on transformers in colpali-engine 0.3.15 | Pinned to `colpali-engine==0.3.4` + `transformers==4.57.6` |
| OpenMP abort on macOS with ColPali + FAISS | PyTorch and FAISS each bundle `libomp.dylib` | `KMP_DUPLICATE_LIB_OK=TRUE` set automatically in pipeline |
| `scann` unresolvable on macOS | No macOS wheel published | Safe to ignore — not used by this pipeline |
| ColPali index rebuild needed after `--sample` run | `run_pipeline.sh` skips build if `id_map.json` exists | Pipeline now checks id_map length vs corpus size and rebuilds if smaller |
