#!/usr/bin/env bash
# Runs the storage benchmark against the REAL recorded camera frames.
#
# Each camera is benchmarked separately, at every resolution its own recording
# can supply. Nothing is upscaled: a camera is only run at resolutions at or
# below what it actually captured, because enlarging a frame invents detail the
# sensor never saw and would change the JPEG entropy the results depend on.
#
# Every camera writes to its own data folder, so the per-resolution CSVs from
# one camera cannot overwrite another's - and none of them touch data/, which
# holds the published collage results behind the submitted manuscript.
#
# Usage:
#   bash run_realcase.sh --dry-run     # print the plan, execute nothing
#   bash run_realcase.sh               # run everything
#   bash run_realcase.sh --fleet       # also run the mixed round-robin arm
set -euo pipefail

cd "$(dirname "$0")"

CORPUS="$(realpath ../code_realcase/corpus/20260817-202755)"
PYTHON="./.venv/bin/python"

DRY=""
FLEET=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY="--dry-run" ;;
    --fleet)   FLEET=1 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

# camera folder : resolutions it can serve : output folder
# Tapo and Webcam 2 recorded at 1920x1080; Webcam 1 caps at 1280x720.
CAMERAS=(
  "Tapo_IP_Cam:360p 480p 720p 1080p:data_frames_tapo"
  "Webcam_2:360p 480p 720p 1080p:data_frames_webcam2"
  "Webcam_1:360p 480p 720p:data_frames_webcam1"
)

echo "=================================================================="
echo " Real-case benchmark"
echo " corpus : $CORPUS"
echo " engines: postgres, postgres_minio, mongodb  (all three, every run)"
[ -n "$DRY" ] && echo " MODE   : DRY RUN - nothing will be executed"
echo "=================================================================="

for entry in "${CAMERAS[@]}"; do
  IFS=':' read -r camera resolutions outdir <<< "$entry"
  frames="$CORPUS/$camera"

  if [ ! -d "$frames" ]; then
    echo; echo "!! missing camera folder, skipping: $frames"; continue
  fi

  echo
  echo "------------------------------------------------------------------"
  echo " camera     : $camera"
  echo " frames     : $(find "$frames" -name 'frame_*.jpg' | wc -l)"
  echo " resolutions: $resolutions"
  echo " output     : ../$outdir/"
  echo "------------------------------------------------------------------"

  BENCHMARK_PAYLOAD_SOURCE=frames \
  BENCHMARK_FRAMES_DIR="$frames" \
  BENCHMARK_DATA_DIR="$(realpath ..)/$outdir" \
  IOTBENCH_NO_VENV=1 \
    "$PYTHON" run.py $resolutions $DRY
done

if [ "$FLEET" -eq 1 ]; then
  echo
  echo "------------------------------------------------------------------"
  echo " mixed fleet: all cameras round-robin at their native resolutions"
  echo " output     : ../data_fleet/"
  echo "------------------------------------------------------------------"
  BENCHMARK_PAYLOAD_SOURCE=fleet \
  BENCHMARK_FLEET_DIR="$CORPUS" \
  BENCHMARK_DATA_DIR="$(realpath ..)/data_fleet" \
  IOTBENCH_NO_VENV=1 \
    "$PYTHON" run.py 1080p $DRY
fi

echo
echo "=================================================================="
[ -n "$DRY" ] && echo " dry run complete - re-run without --dry-run to execute" \
              || echo " all runs complete"
echo "=================================================================="
