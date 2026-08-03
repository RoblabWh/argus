"""Stage 1 — COLMAP Structure-from-Motion for ARGUS.

Hybrid architecture: GPU-heavy steps go through the ``colmap`` CLI (subprocess);
``pycolmap`` is used only to read the resulting binaries and export a PLY.

Produces, under ``results_path``:
    reconstruction.json          poses + intrinsics, local frame (§3.3 contract)
    sparse_aligned/points.ply    sparse cloud, local frame
    dense/fused.ply              only if dense MVS was requested and succeeded
    logs/<step>.log              full stdout/stderr per CLI step

Reference: ``colmap_reconstruction_and_localization_ARGUS.md`` §3.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone

import numpy as np

from gps_utils import build_priors

logger = logging.getLogger(__name__)

# --- Stage 1 constants (§3.5) ---
MATCHING_MODE = "exhaustive"      # switch to sequential+spatial for very large sets
MAX_IMAGE_SIZE = 3200             # feature-extractor internal resize cap
# GPU is on by the DEVICE the worker was started with (nvidia override sets
# DEVICE=cuda); COLMAP_USE_GPU overrides explicitly. Falls back to CPU so the
# worker still functions (slowly) on a non-GPU host.
USE_GPU = os.getenv(
    "COLMAP_USE_GPU",
    "1" if os.getenv("DEVICE", "cpu").startswith("cuda") else "0",
)
ALIGNMENT_MAX_ERROR = 5.0         # model_aligner inlier threshold (metres)
DENSE_MAX_IMAGE_SIZE = 2000       # patch-match stereo resize
COLMAP_BIN = os.getenv("COLMAP_BIN", "colmap")

# A large set switches the matcher away from exhaustive (O(n²) pairs).
LARGE_SET_THRESHOLD = 150


class ColmapError(RuntimeError):
    pass


def _run_cli(args: list[str], log_path: str) -> None:
    """Run a ``colmap`` subprocess, teeing combined output to ``log_path``."""
    cmd = [COLMAP_BIN] + args
    logger.info("[colmap] $ %s", " ".join(cmd))
    with open(log_path, "w") as log:
        log.write("$ " + " ".join(cmd) + "\n\n")
        log.flush()
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        tail = ""
        try:
            with open(log_path) as f:
                tail = "".join(f.readlines()[-25:])
        except OSError:
            pass
        raise ColmapError(
            f"colmap {args[0]} failed (exit {proc.returncode}). Log tail:\n{tail}"
        )


def _stage_images(image_paths: dict[str, str], staging_dir: str) -> list[str]:
    """Symlink every source image into a flat ``staging_dir`` keyed by basename.

    COLMAP's flat ``image_list`` of basenames needs a single images root.
    Symlinks preserve EXIF (they point at the originals) regardless of the
    report's on-disk layout. Returns the list of staged basenames.
    """
    os.makedirs(staging_dir, exist_ok=True)
    names: list[str] = []
    for name, src in image_paths.items():
        if not src or not os.path.isfile(src):
            logger.warning("[colmap] skipping missing image %s (%s)", name, src)
            continue
        dst = os.path.join(staging_dir, name)
        if os.path.lexists(dst):
            if os.path.realpath(dst) == os.path.realpath(src):
                names.append(name)
                continue
            logger.warning("[colmap] basename collision for %s — skipping", name)
            continue
        os.symlink(os.path.abspath(src), dst)
        names.append(name)
    return names


def _find_primary_model(sparse_dir: str) -> str | None:
    """Pick the sub-model with the most registered images (§3.2 step 5)."""
    import pycolmap

    best, best_n = None, -1
    if not os.path.isdir(sparse_dir):
        return None
    for entry in sorted(os.listdir(sparse_dir)):
        sub = os.path.join(sparse_dir, entry)
        if not os.path.isdir(sub):
            continue
        try:
            rec = pycolmap.Reconstruction(sub)
            n = rec.num_reg_images()
        except Exception:  # noqa: BLE001 - not a valid model dir
            continue
        if n > best_n:
            best, best_n = sub, n
    return best


def _pose_world_from_cam(img):
    """Return (R_world_cam (3x3), camera_center (3,)) for a registered image.

    Works across pycolmap versions: `cam_from_world` may be a method or a
    property; the camera centre is taken from `projection_center()` when
    available (most direct) and otherwise from −Rᵀ·t.
    """
    cfw_attr = getattr(img, "cam_from_world", None)
    cfw = cfw_attr() if callable(cfw_attr) else cfw_attr
    R_cw = np.asarray(cfw.rotation.matrix())
    t_cw = np.asarray(cfw.translation)
    R_wc = R_cw.T
    proj = getattr(img, "projection_center", None)
    if callable(proj):
        center = np.asarray(proj())
    else:
        center = -R_wc @ t_cw  # camera centre, LOCAL frame
    return R_wc, center


def _summarize_reconstruction(aligned_dir, geo_offset, epsg, priors_local, mode):
    """Read aligned binaries with pycolmap → the §3.3 reconstruction.json dict."""
    import pycolmap

    rec = pycolmap.Reconstruction(aligned_dir)
    images_summary: dict = {}
    residuals: list = []
    # Registration via reg_image_ids() — the bundled pycolmap's Image has no
    # `has_pose` property, but Reconstruction exposes the registered ids
    # (sibling of num_reg_images(), which is already used in _find_primary_model).
    reg_ids = set(rec.reg_image_ids())
    for image_id, img in rec.images.items():
        if image_id not in reg_ids:
            images_summary[img.name] = {"image_id": int(image_id), "registered": False}
            continue
        cam = rec.cameras[img.camera_id]
        R_wc, center = _pose_world_from_cam(img)
        images_summary[img.name] = {
            "image_id": int(image_id),
            "camera_center_utm": [float(x) for x in center],  # name historical; value LOCAL
            "R_world_cam_3x3": [[float(v) for v in row] for row in R_wc],
            "camera": {
                "model": cam.model.name,
                "params": list(cam.params),
                "width": cam.width,
                "height": cam.height,
            },
            "width": int(cam.width),
            "height": int(cam.height),
            "registered": True,
        }
        prior = priors_local.get(img.name)
        if prior is not None:
            ep, np_, altp = prior
            residuals.append(
                float(np.linalg.norm([center[0] - ep, center[1] - np_, center[2] - altp]))
            )

    registered = sum(1 for v in images_summary.values() if v.get("registered"))
    return {
        "source": "colmap",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "utm_epsg": epsg,
        "geo_offset": geo_offset,  # metres; LOCAL = UTM − geo_offset
        "reconstruction_mode": mode,
        "geo_reg_residual_m": float(np.median(residuals)) if residuals else float("nan"),
        "registered_images": registered,
        "total_images": len(images_summary),
        "images": images_summary,
    }


def _run_dense_mvs(images_root, aligned_dir, dense_dir, log_dir) -> str | None:
    """Optional dense MVS (§3.4). Returns fused.ply path or None on failure.

    Fails regularly on low-overlap nadir flights; the caller falls back to the
    sparse cloud. The relaxed filters are deliberate concessions to low overlap.
    """
    try:
        _run_cli(
            ["image_undistorter", "--image_path", images_root,
             "--input_path", aligned_dir, "--output_path", dense_dir,
             "--output_type", "COLMAP", "--max_image_size", str(DENSE_MAX_IMAGE_SIZE)],
            os.path.join(log_dir, "image_undistorter.log"),
        )
        _run_cli(
            ["patch_match_stereo", "--workspace_path", dense_dir,
             "--PatchMatchStereo.geom_consistency", "true",
             "--PatchMatchStereo.filter", "true",
             "--PatchMatchStereo.filter_min_num_consistent", "1",
             "--PatchMatchStereo.filter_min_triangulation_angle", "1.0"],
            os.path.join(log_dir, "patch_match_stereo.log"),
        )
        fused = os.path.join(dense_dir, "fused.ply")
        _run_cli(
            ["stereo_fusion", "--workspace_path", dense_dir, "--output_path", fused],
            os.path.join(log_dir, "stereo_fusion.log"),
        )
        if os.path.isfile(fused) and os.path.getsize(fused) > 0:
            return fused
    except ColmapError as e:
        logger.warning("[colmap] dense MVS failed, falling back to sparse: %s", e)
    return None


def build_reconstruction(image_paths: dict[str, str], results_path: str,
                         options: dict | None = None, progress_cb=None) -> dict:
    """Run the full Stage-1 SfM pipeline.

    Args:
        image_paths: ``{basename: absolute_path}`` for the reconstruction set
            (the labeled / non-thermal images, EXIF intact).
        results_path: output dir (``reports_data/{id}/colmap``); created if absent.
        options: ``{"dense": bool}``.
        progress_cb: optional ``callable(message: str, percent: int)``.

    Returns the reconstruction.json dict (also written to disk).
    """
    options = options or {}

    def _p(msg, pct):
        logger.info("[colmap] %s (%d%%)", msg, pct)
        if progress_cb:
            try:
                progress_cb(msg, pct)
            except Exception:  # noqa: BLE001 - progress is best-effort
                pass

    os.makedirs(results_path, exist_ok=True)
    log_dir = os.path.join(results_path, "logs")
    db_dir = os.path.join(results_path, "colmap_db")
    sparse_dir = os.path.join(results_path, "sparse")
    aligned_dir = os.path.join(results_path, "sparse_aligned")
    staging_dir = os.path.join(results_path, "images_staging")
    # Clean prior outputs so re-runs are deterministic.
    for d in (log_dir, db_dir, sparse_dir, aligned_dir, staging_dir):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d, exist_ok=True)

    db_path = os.path.join(db_dir, "database.db")

    # (1) priors + image list ------------------------------------------------
    _p("Reading EXIF GPS priors…", 2)
    names = _stage_images(image_paths, staging_dir)
    if len(names) < 3:
        raise ColmapError(f"Too few usable images for SfM ({len(names)}).")
    images_root = staging_dir

    priors_local, geo_offset, epsg = build_priors(
        {n: os.path.join(staging_dir, n) for n in names}
    )
    if not priors_local:
        raise ColmapError("No image carried EXIF GPS — cannot geo-register.")

    image_list_path = os.path.join(results_path, "image_list.txt")
    with open(image_list_path, "w") as f:
        f.write("\n".join(names) + "\n")
    priors_path = os.path.join(results_path, "priors.txt")
    with open(priors_path, "w") as f:
        for name, (e, n, alt) in priors_local.items():
            f.write(f"{name} {e:.6f} {n:.6f} {alt:.6f}\n")

    # (2) feature extraction -------------------------------------------------
    _p("Extracting features…", 10)
    _run_cli(
        ["feature_extractor", "--database_path", db_path, "--image_path", images_root,
         "--image_list_path", image_list_path,
         "--ImageReader.camera_model", "PINHOLE",
         "--ImageReader.single_camera", "1",
         "--FeatureExtraction.max_image_size", str(MAX_IMAGE_SIZE),
         "--FeatureExtraction.use_gpu", USE_GPU],
        os.path.join(log_dir, "feature_extractor.log"),
    )

    # (3) matching -----------------------------------------------------------
    _p("Matching features…", 30)
    use_sequential = MATCHING_MODE == "sequential" or len(names) > LARGE_SET_THRESHOLD
    if use_sequential:
        _run_cli(["sequential_matcher", "--database_path", db_path,
                  "--FeatureMatching.use_gpu", USE_GPU],
                 os.path.join(log_dir, "sequential_matcher.log"))
        _run_cli(["spatial_matcher", "--database_path", db_path,
                  "--FeatureMatching.use_gpu", USE_GPU],
                 os.path.join(log_dir, "spatial_matcher.log"))
    else:
        _run_cli(["exhaustive_matcher", "--database_path", db_path,
                  "--FeatureMatching.use_gpu", USE_GPU],
                 os.path.join(log_dir, "exhaustive_matcher.log"))

    # (4) incremental SfM ----------------------------------------------------
    _p("Reconstructing (mapper)…", 50)
    _run_cli(["mapper", "--database_path", db_path, "--image_path", images_root,
              "--output_path", sparse_dir],
             os.path.join(log_dir, "mapper.log"))

    # (5) primary sub-model --------------------------------------------------
    primary = _find_primary_model(sparse_dir)
    if primary is None:
        raise ColmapError("Mapper produced no reconstruction sub-model.")

    # (6) geo-register onto priors ------------------------------------------
    _p("Geo-registering…", 70)
    _run_cli(["model_aligner", "--input_path", primary, "--output_path", aligned_dir,
              "--ref_images_path", priors_path, "--ref_is_gps", "0",
              "--alignment_type", "custom",
              "--alignment_max_error", str(ALIGNMENT_MAX_ERROR)],
             os.path.join(log_dir, "model_aligner.log"))

    # (7) summarize ----------------------------------------------------------
    _p("Summarizing reconstruction…", 80)
    mode = "sparse"
    summary = _summarize_reconstruction(aligned_dir, geo_offset, epsg, priors_local, mode)

    # (8) export sparse PLY --------------------------------------------------
    import pycolmap

    rec = pycolmap.Reconstruction(aligned_dir)
    out_ply = os.path.join(aligned_dir, "points.ply")
    rec.export_PLY(out_ply)

    # (9) optional dense MVS -------------------------------------------------
    # The cloud named by `points_ply` is the one downstream localization reads,
    # so a successful dense run has to claim it — otherwise patch-match stereo
    # is paid for and never used.
    points_ply = out_ply
    if options.get("dense"):
        _p("Dense reconstruction (MVS)…", 88)
        dense_dir = os.path.join(results_path, "dense")
        shutil.rmtree(dense_dir, ignore_errors=True)
        os.makedirs(dense_dir, exist_ok=True)
        fused = _run_dense_mvs(images_root, aligned_dir, dense_dir, log_dir)
        if fused:
            summary["reconstruction_mode"] = "dense"
            points_ply = fused

    summary["points_ply"] = os.path.relpath(points_ply, results_path)
    with open(os.path.join(results_path, "reconstruction.json"), "w") as f:
        json.dump(summary, f, indent=2)

    _p(
        f"Done — {summary['registered_images']}/{summary['total_images']} images registered",
        100,
    )
    logger.info(
        "[colmap] %d/%d registered, residual=%.2fm, mode=%s",
        summary["registered_images"], summary["total_images"],
        summary["geo_reg_residual_m"], summary["reconstruction_mode"],
    )
    return summary
