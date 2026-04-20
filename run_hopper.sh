#!/bin/bash
#PBS -P personal-e1610383
#PBS -j oe
#PBS -k oed
#PBS -N vidore_flexrag
#PBS -l walltime=12:00:00
#PBS -l select=1:ncpus=36:mpiprocs=1:ompthreads=36:ngpus=1

set -euo pipefail

cd $PBS_O_WORKDIR

log() { echo; echo "══════════════════════════════════════════════════════"; echo "  $1"; echo "══════════════════════════════════════════════════════"; }

mkdir -p logs data/processed outputs

# ── Activate existing conda environment ───────────────────────────────────────

export PATH="$HOME/miniconda3/bin:$PATH"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate "$HOME/flexrag_env"

export PYTHONPATH="."
export KMP_DUPLICATE_LIB_OK=TRUE

python -c "import flexrag; print('flexrag OK')"
python -c "from colpali_engine.models import ColPali; print('colpali-engine OK')"

# ── Steps 1-11 skip if already done ──────────────────────────────────────────

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

if [ ! -d data/processed/vidore_flexrag_retriever ]; then
  log "3. Build contriever retriever"
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

if [ ! -f outputs/retrieval_metrics.json ]; then
  log "5. Evaluate contriever"
  python scripts/eval_vidore_retrieval.py
else
  echo "5. [skip] contriever evaluation already done"
fi

if [ ! -d data/processed/bge_retriever ]; then
  log "6. Build BGE retriever"
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

if [ ! -f outputs/bge_retrieval_metrics.json ]; then
  log "8. Evaluate BGE"
  python scripts/eval_bge_retrieval.py
else
  echo "8. [skip] BGE evaluation already done"
fi

if [ ! -f data/processed/clip_index/id_map.json ]; then
  log "9. Build CLIP index"
  python scripts/build_clip_index.py
else
  echo "9. [skip] CLIP index already built"
fi

if [ ! -f outputs/clip_retrieval_top10.jsonl ]; then
  log "10. Run CLIP retrieval"
  python scripts/run_clip_retrieval.py
else
  echo "10. [skip] CLIP retrieval already done"
fi

if [ ! -f outputs/clip_retrieval_metrics.json ]; then
  log "11. Evaluate CLIP"
  python scripts/eval_clip_retrieval.py
else
  echo "11. [skip] CLIP evaluation already done"
fi

# ── ColPali (Steps 12-14) ─────────────────────────────────────────────────────

CORPUS_SIZE=$(wc -l < data/processed/corpus.jsonl | tr -d ' ')
IDMAP_SIZE=0
if [ -f data/processed/colpali_index/id_map.json ]; then
  IDMAP_SIZE=$(python -c "import json; print(len(json.load(open('data/processed/colpali_index/id_map.json'))))")
fi

if [ "$IDMAP_SIZE" -lt "$CORPUS_SIZE" ]; then
  log "12. Build ColPali index"
  python scripts/build_colpali_index.py
else
  echo "12. [skip] ColPali index already built ($IDMAP_SIZE docs)"
fi

if [ ! -f outputs/colpali_retrieval_top10.jsonl ]; then
  log "13. Run ColPali retrieval"
  python scripts/run_colpali_retrieval.py
else
  echo "13. [skip] ColPali retrieval already done"
fi

log "14. Evaluate ColPali"
python scripts/eval_colpali_retrieval.py

# ── Final comparison ──────────────────────────────────────────────────────────

log "15. Compare all retrievers"
python scripts/compare_retrievers.py

echo
echo "Done. Key outputs:"
echo "  outputs/retrieval_metrics.json"
echo "  outputs/bge_retrieval_metrics.json"
echo "  outputs/clip_retrieval_metrics.json"
echo "  outputs/colpali_retrieval_metrics.json"
