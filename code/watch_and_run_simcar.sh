#!/usr/bin/env bash
# Polls the SIMCAR/SEMA-MT host at a respectful interval; once reachable, runs a
# 3-record test batch and, if that confirms real PDFs come back, launches the
# full run. Bounded to MAX_ATTEMPTS cycles so it does not spin forever.
set -uo pipefail

PYTHON="/c/Users/Amintas/anaconda3/python.exe"
SCRIPT="code/download_simcar_documents.py"
INPUT="data/pre/car_proxy/car_atp_joined_20260818.csv"
OUTPUT="G:/simcar_archive/validated_car_pdfs"
LOG="$OUTPUT/watcher.log"
INTERVAL_SECONDS=300
MAX_ATTEMPTS=30   # 30 * 5min = 2.5h ceiling before giving up and reporting

mkdir -p "$OUTPUT"
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$LOG"; }

log "watcher_start interval=${INTERVAL_SECONDS}s max_attempts=${MAX_ATTEMPTS}"

attempt=0
while [ "$attempt" -lt "$MAX_ATTEMPTS" ]; do
  attempt=$((attempt + 1))
  log "attempt ${attempt}/${MAX_ATTEMPTS}: testing reachability with a 3-record probe"
  "$PYTHON" "$SCRIPT" --input "$INPUT" --output "$OUTPUT" --limit 3 --timeout 20 >>"$LOG" 2>&1
  code=$?
  if [ "$code" -eq 75 ]; then
    log "attempt ${attempt}: portal still unreachable, sleeping ${INTERVAL_SECONDS}s"
    sleep "$INTERVAL_SECONDS"
    continue
  fi
  log "attempt ${attempt}: portal reachable (probe exit=${code}); launching full batch"
  "$PYTHON" "$SCRIPT" --input "$INPUT" --output "$OUTPUT" --limit 0 --timeout 45 --workers 6 >>"$LOG" 2>&1
  full_code=$?
  log "full_batch_finished exit=${full_code}"
  exit "$full_code"
done

log "giving_up after ${MAX_ATTEMPTS} attempts: portal did not become reachable"
exit 75
