#!/usr/bin/env bash
# Run the full ViDoRe FlexRAG pipeline end-to-end.
#
# Requirements:
#   - venv activated (source venv/bin/activate)
#   - Ollama running with required models:
#       ollama serve
#       ollama pull qwen2.5:latest        # generation + LLM judge
#       ollama pull llava:7b              # optional: page captions
#
# Usage:
#   bash run_pipeline.sh                  # full pipeline
#   bash run_pipeline.sh --skip-text      # skip text pipeline
#   bash run_pipeline.sh --clip-only      # only CLIP pipeline + compare
#   bash run_pipeline.sh --colpali-only   # only ColPali pipeline + compare

set -euo pipefail

SKIP_TEXT=false
CLIP_ONLY=false
COLPALI_ONLY=false

for arg in "$@"; do
  case $arg in
    --skip-text)    SKIP_TEXT=true ;;
    --clip-only)    CLIP_ONLY=true; SKIP_TEXT=true ;;
    --colpali-only) COLPALI_ONLY=true; SKIP_TEXT=true; CLIP_ONLY=true ;;
  esac
done

log() { echo; echo "══════════════════════════════════════════════════════"; echo "  $1"; echo "══════════════════════════════════════════════════════"; }

# ── Ollama health check ────────────────────────────────────────────────────────

log "Checking Ollama"
if ! curl -sf http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
  echo "ERROR: Ollama is not running — start it with: ollama serve"
  exit 1
fi

if ! curl -sf http://127.0.0.1:11434/api/tags | python -c "import sys,json; models=[m['name'] for m in json.load(sys.stdin)['models']]; exit(0 if any('qwen2.5' in m for m in models) else 1)" 2>/dev/null; then
  echo "WARNING: qwen2.5:latest not found — pulling now..."
  ollama pull qwen2.5:latest
fi
echo "  Ollama OK"

# ── Data prep ─────────────────────────────────────────────────────────────────

if [ ! -f data/processed/corpus.jsonl ]; then
  log "1. Convert ViDoRe dataset"
  python scripts/convert_vidore.py
else
  echo "1. [skip] corpus.jsonl already exists"
fi

if [ ! -f data/processed/image_manifest.jsonl ]; then
  log "2. Save page images to disk"
  python scripts/save_vidore_images.py
else
  echo "2. [skip] image_manifest.jsonl already exists"
fi

# ── Text pipeline: contriever-msmarco ─────────────────────────────────────────

if [ "$SKIP_TEXT" = false ]; then

  if [ ! -d data/processed/vidore_flexrag_retriever ]; then
    log "3. Build FlexRAG text retriever (BM25 + contriever-msmarco)"
    python scripts/build_flexrag_retriever.py
  else
    echo "3. [skip] contriever retriever already built"
  fi

  if [ ! -f outputs/flexrag_retrieval_top10.jsonl ]; then
    log "4. Run contriever retrieval"
    python scripts/run_flexrag_retrieval.py
  else
    echo "4. [skip] contriever retrieval already done"
  fi

  log "5. Evaluate contriever retrieval"
  python scripts/eval_vidore_retrieval.py

  # ── Text pipeline: BGE-large ──────────────────────────────────────────────

  if [ ! -d data/processed/bge_retriever ]; then
    log "6. Build FlexRAG text retriever (BM25 + BGE-large)"
    python scripts/build_bge_retriever.py
  else
    echo "6. [skip] BGE retriever already built"
  fi

  if [ ! -f outputs/bge_retrieval_top10.jsonl ]; then
    log "7. Run BGE retrieval"
    python scripts/run_bge_retrieval.py
  else
    echo "7. [skip] BGE retrieval already done"
  fi

  log "8. Evaluate BGE retrieval"
  python scripts/eval_bge_retrieval.py

  # ── Generation pipeline ───────────────────────────────────────────────────

  # Optional: generate page captions (requires llava:7b)
  if curl -sf http://127.0.0.1:11434/api/tags | python -c "import sys,json; models=[m['name'] for m in json.load(sys.stdin)['models']]; exit(0 if any('llava' in m for m in models) else 1)" 2>/dev/null; then
    if [ ! -f outputs/page_captions.json ]; then
      log "9. Generate page captions with llava:7b"
      python scripts/caption_pages.py --model llava:7b
    else
      echo "9. [skip] page_captions.json already exists"
    fi
  else
    echo "9. [skip] llava not available (pull llava:7b to enable page captions)"
  fi

  log "10. Generate answers with qwen2.5 (top-5 contexts, 50 queries)"
  PYTHONPATH=. python scripts/run_generation.py

  log "11. Evaluate generation — lexical metrics"
  python scripts/eval_vidore_generation.py

  log "12. Evaluate generation — LLM judge"
  python scripts/eval_vidore_llm_judge.py

  log "13. Build qualitative review"
  python scripts/build_qualitative_review.py

else
  echo "3-13. [skip] text + generation pipeline (--skip-text)"
fi

# ── Multimodal: CLIP ───────────────────────────────────────────────────────────

if [ "$COLPALI_ONLY" = false ]; then

  if [ ! -f data/processed/clip_index/id_map.json ]; then
    log "14. Build CLIP image index (openai/clip-vit-base-patch32)"
    python scripts/build_clip_index.py
  else
    echo "14. [skip] CLIP index already built"
  fi

  if [ ! -f outputs/clip_retrieval_top10.jsonl ]; then
    log "15. Run CLIP retrieval"
    PYTHONPATH=. python scripts/run_clip_retrieval.py
  else
    echo "15. [skip] CLIP retrieval already done"
  fi

  log "16. Evaluate CLIP retrieval"
  python scripts/eval_clip_retrieval.py

fi

# ── Multimodal: ColPali ────────────────────────────────────────────────────────
# KMP_DUPLICATE_LIB_OK suppresses the OpenMP duplicate-library abort on macOS
# (caused by PyTorch + FAISS each bundling their own libomp.dylib).
export KMP_DUPLICATE_LIB_OK=TRUE

# Rebuild if the index is missing OR was built on a sample (id_map shorter than corpus)
CORPUS_SIZE=$(wc -l < data/processed/corpus.jsonl | tr -d ' ')
IDMAP_SIZE=0
if [ -f data/processed/colpali_index/id_map.json ]; then
  IDMAP_SIZE=$(python -c "import json; print(len(json.load(open('data/processed/colpali_index/id_map.json'))))")
fi

if [ "$IDMAP_SIZE" -lt "$CORPUS_SIZE" ]; then
  log "17. Build ColPali image index (vidore/colpali-v1.2)  [~1-3 hrs on CPU]"
  PYTHONPATH=. python scripts/build_colpali_index.py
else
  echo "17. [skip] ColPali index already built ($IDMAP_SIZE docs)"
fi

if [ ! -f outputs/colpali_retrieval_top10.jsonl ]; then
  log "18. Run ColPali retrieval"
  PYTHONPATH=. python scripts/run_colpali_retrieval.py
else
  echo "18. [skip] ColPali retrieval already done"
fi

log "19. Evaluate ColPali retrieval"
python scripts/eval_colpali_retrieval.py

# ── Final comparison ──────────────────────────────────────────────────────────

log "20. Compare all retrievers vs ViDoRe V3 leaderboard"
python scripts/compare_retrievers.py

echo
echo "Done. Key outputs:"
echo "  outputs/retrieval_metrics.json          contriever retrieval"
echo "  outputs/bge_retrieval_metrics.json      BGE-large retrieval"
echo "  outputs/clip_retrieval_metrics.json     CLIP multimodal retrieval"
echo "  outputs/colpali_retrieval_metrics.json  ColPali multimodal retrieval"
echo "  outputs/generation_metrics.json         EM, Token F1, ROUGE-L"
echo "  outputs/llm_judge_metrics.json          LLM judge accuracy"
echo "  outputs/qualitative_review_top20.md     qualitative review"
