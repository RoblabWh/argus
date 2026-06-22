"""DINOv3 appearance re-identification for ARGUS YOLO detections.

See ``by_dinov3_ARGUS.md`` for the algorithm description ("A4" approach).

Public entry point: :func:`reid.by_dinov3.run_reid`.

The package is split so the appearance (``embeddings``) and ground-position
(``spatial``) components can be reused independently — e.g. a future approach
combining DINOv3 appearance with 3D-pointcloud distance can reuse
``embeddings`` while swapping out ``spatial``.
"""
