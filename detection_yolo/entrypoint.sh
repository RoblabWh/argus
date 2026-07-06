#!/bin/bash
# Warm the model cache (best-effort, never blocks startup), then run the worker.
python predownload.py || echo "[entrypoint] predownload failed (non-fatal), continuing"
exec celery -A tasks_detection_yolo worker -Q detection_yolo --loglevel="${LOG_LEVEL:-info}"
