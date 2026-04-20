#!/bin/bash
# Full generation pipeline using Hopper retrieval outputs.
# Requires: Ollama running locally with qwen2.5 pulled.
#   ollama serve   (in a separate terminal)
#   ollama pull qwen2.5
#
# Usage: bash run_generation_full.sh [bge|colpali|contriever|clip|all]
#   Default: runs bge and colpali (best two retrievers)

set -e
RETRIEVERS="${1:-bge colpali}"
[ "$RETRIEVERS" = "all" ] && RETRIEVERS="contriever bge clip colpali"

IN_DIR="outputs_hopper/outputs"
OUT_DIR="outputs_full"

echo "=================================================="
echo " ViDoRe FlexRAG — Full Generation Pipeline"
echo " Retrievers : $RETRIEVERS"
echo " Input      : $IN_DIR"
echo " Output     : $OUT_DIR"
echo "=================================================="

for RETRIEVER in $RETRIEVERS; do
    echo ""
    echo ">>> [$RETRIEVER] Step 1/3 — Generating answers..."
    PYTHONPATH=. python scripts/run_generation.py \
        --retriever "$RETRIEVER" \
        --in_dir "$IN_DIR" \
        --out_dir "$OUT_DIR"

    echo ">>> [$RETRIEVER] Step 2/3 — Evaluating EM / F1 / ROUGE-L..."
    PYTHONPATH=. python scripts/eval_vidore_generation.py \
        --retriever "$RETRIEVER" \
        --out_dir "$OUT_DIR"

    echo ">>> [$RETRIEVER] Step 3/3 — LLM-as-judge..."
    PYTHONPATH=. python scripts/eval_vidore_llm_judge.py \
        --retriever "$RETRIEVER" \
        --out_dir "$OUT_DIR"

    echo ">>> [$RETRIEVER] Building qualitative review (8 examples)..."
    PYTHONPATH=. python scripts/build_qualitative_review.py \
        --retriever "$RETRIEVER" \
        --out_dir "$OUT_DIR" \
        --in_dir "$IN_DIR" \
        --n_examples 8

    echo ">>> [$RETRIEVER] Done."
done

echo ""
echo "=================================================="
echo " All done. Results in $OUT_DIR/"
echo "=================================================="
