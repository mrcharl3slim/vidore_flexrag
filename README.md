# vidore_flexrag

RAG pipeline using the ViDoRe benchmark dataset with FlexRAG.

## Requirements

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (recommended)
- Or: Python 3.11–3.13 (3.12 recommended) + [Ollama](https://ollama.com)

## Quickstart with Docker

```bash
git clone <repo-url>
cd vidore_flexrag

# Build and start the app + ollama containers
docker compose up -d --build

# Pull the generation model into the ollama container
docker compose exec ollama ollama pull qwen2:latest

# Open a shell in the app container
docker compose exec app bash

# Then run the pipeline inside the container:
python scripts/convert_vidore.py
python scripts/build_flexrag_retriever.py
python scripts/run_flexrag_retrieval.py
python scripts/eval_vidore_retrieval.py
python scripts/run_generation.py
python scripts/eval_vidore_generation.py
python scripts/eval_vidore_llm_judge.py
python scripts/build_qualitative_review.py
```

> Data and outputs are mounted as volumes — they persist on your host machine under `data/` and `outputs/`.

## Manual Installation (without Docker)

### 1. Clone the repository

```bash
git clone <repo-url>
cd vidore_flexrag
```

### 2. Create a virtual environment

```bash
python3.12 -m venv venv
source venv/bin/activate
```

### 3. Install faiss-cpu first

```bash
pip install faiss-cpu
```

### 4. Install FlexRAG from GitHub (no-deps)

FlexRAG is not available on PyPI — install directly from GitHub before other dependencies:

```bash
pip install git+https://github.com/ictnlp/FlexRAG.git --no-deps
```

### 5. Install all remaining dependencies

```bash
pip install -r requirements.txt
```

> This installs all pinned dependencies including `torch==2.7.0` and `transformers<5.0.0`.
>
> **Note:** `scann` (a FlexRAG dependency) has no macOS wheel and will remain unresolved on macOS. All other dependencies install correctly.

### 6. Pull the generation model (Ollama required)

```bash
ollama pull qwen2:latest
```

## Running the Pipeline

```bash
# 1. Download and convert the ViDoRe dataset
python scripts/convert_vidore.py

# 2. Build the FlexRAG retriever (BM25 index)
python scripts/build_flexrag_retriever.py

# 3. Run FlexRAG BM25 retrieval over all queries
python scripts/run_flexrag_retrieval.py

# 4. Evaluate retrieval
python scripts/eval_vidore_retrieval.py

# 5. Run generation (top-3 contexts, first 50 queries)
PYTHONPATH=. python scripts/run_generation.py

# 6. Evaluate generation (lexical metrics)
python scripts/eval_vidore_generation.py

# 7. Evaluate generation (LLM judge)
python scripts/eval_vidore_llm_judge.py

# 8. Build qualitative review
python scripts/build_qualitative_review.py

# 9. Interactive Q&A smoke test
PYTHONPATH=. python scripts/ask_vidore.py
```

> `PYTHONPATH=.` is required so scripts can import from `app/`.

## Results

### Retrieval — ViDoRe Computer Science (1290 queries)

| Retriever | nDCG@10 | Recall@10 | MRR@10 |
|---|---|---|---|
| Baseline BM25 (`rank-bm25`) | 0.293 | — | — |
| FlexRAG BM25 (`bm25s`, concat title+text) | 0.372 | 0.343 | 0.333 |
| **FlexRAG Hybrid BM25 + Dense RRF** (`contriever-msmarco`) | **0.461** | **0.372** | **0.434** |

### Generation (50 queries, qwen2:latest via Ollama)

| Metric | Score |
|---|---|
| Exact Match | 0.02 |
| Token F1 | 0.379 |
| ROUGE-L | 0.317 |
| Insufficient Evidence Rate | 0.0 |

> Low EM is expected — qwen2 generates verbose explanations rather than short reference-style answers.

### LLM Judge (qwen2 self-judged, 50 queries)

| Metric | Score |
|---|---|
| LLM Judge Accuracy | 0.84 |

> High judge accuracy vs low EM/ROUGE confirms the model answers correctly but in its own words, which lexical metrics penalise.

## Project Structure

```
vidore_flexrag/
├── data/
│   ├── raw/                          # Raw downloaded datasets
│   └── processed/
│       ├── corpus.jsonl              # Converted ViDoRe corpus
│       ├── queries.jsonl             # Converted queries
│       ├── qrels.jsonl               # Relevance judgements
│       └── vidore_flexrag_retriever/ # Persisted FlexRAG retriever + indexes
├── scripts/
│   ├── convert_vidore.py             # Download and convert ViDoRe dataset
│   ├── build_flexrag_retriever.py    # Build FlexRAG retriever with BM25 index
│   ├── run_flexrag_retrieval.py      # Run retrieval over all queries
│   ├── eval_vidore_retrieval.py      # Evaluate with nDCG, Recall, MRR
│   ├── run_generation.py             # Generate answers with Ollama
│   ├── eval_vidore_generation.py     # Lexical generation metrics (EM, F1, ROUGE-L)
│   ├── eval_vidore_llm_judge.py      # LLM-as-judge evaluation
│   ├── build_qualitative_review.py   # Qualitative review of judge results
│   ├── ask_vidore.py                 # Interactive Q&A CLI
│   └── test_flexrag_retriever.py     # Quick retriever smoke test
├── app/
│   ├── vidore_assistant.py           # FlexRAG AssistantBase subclass
│   ├── generator.py                  # Ollama generator wrapper
│   ├── dataio.py                     # Data loading utilities
│   └── prompts.py                    # Prompt templates
├── outputs/
│   ├── flexrag_retrieval_top10.jsonl  # Retrieval results
│   ├── retrieval_metrics.json         # nDCG, Recall, MRR scores
│   ├── predictions.jsonl              # Generated answers
│   ├── generation_metrics.json        # EM, Token F1, ROUGE-L scores
│   ├── generation_per_example.jsonl   # Per-query generation scores
│   ├── llm_judge_metrics.json         # LLM judge accuracy
│   ├── llm_judge_per_example.jsonl    # Per-query judge verdicts
│   ├── qualitative_review_top20.json  # Qualitative review (JSON)
│   └── qualitative_review_top20.md   # Qualitative review (Markdown)
├── requirements.txt
└── README.md
```
