#!/usr/bin/env bash
# Downloads the face detection and recognition models into models/.
# They are not kept in git: together they are 38 MB, and they are published
# files that can be fetched again at any time.
set -euo pipefail

cd "$(dirname "$0")"
mkdir -p models

BASE=https://github.com/opencv/opencv_zoo/raw/main/models

echo "Downloading YuNet face detector (228 KB) ..."
curl -sSL -o models/face_detection_yunet_2023mar.onnx \
  "$BASE/face_detection_yunet/face_detection_yunet_2023mar.onnx"

echo "Downloading SFace face recogniser (37 MB) ..."
curl -sSL -o models/face_recognition_sface_2021dec.onnx \
  "$BASE/face_recognition_sface/face_recognition_sface_2021dec.onnx"

echo "Done. Models are in models/"
