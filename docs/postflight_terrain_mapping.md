# GARUDA Post-Flight Terrain Mapping

This document describes the current post-flight terrain reconstruction workflow.
It applies to offline datasets and recovered mission imagery only. No dense
photogrammetry, COLMAP, or dataset processing runs inside the flight runtime.

## Current V2 Pipeline

```text
DJI / mission images
-> quality scoring
-> candidate image graph
-> SIFT feature extraction and cache
-> feature matching
-> robust pair verification
-> multi-view feature-track diagnostics
-> PyCOLMAP sparse SfM
-> global bundle adjustment
-> camera pose export
-> optional dense MVS
-> optional DSM
-> optional terrain orthorectification
```

The current renderer still distinguishes between diagnostic previews and true
orthomosaics:

- `global_pose_preview.jpg` is a sparse reconstruction and camera trajectory
  preview.
- `stitched_terrain.jpg` from dataset tests is a bounded mosaic preview.
- `orthomosaic.tif` must only be created when dense MVS, DSM generation, and
  terrain projection succeed.

## Dependencies

Runtime flight dependencies stay in `requirements.txt`.

Heavy post-flight dependencies are isolated in:

```text
requirements-postflight.txt
```

Install them only on a reconstruction workstation:

```bash
pip install -r requirements-postflight.txt
```

`pycolmap` is required for sparse SfM. COLMAP dense PatchMatch through PyCOLMAP
requires CUDA. If CUDA is unavailable, sparse SfM can still succeed, but dense
MVS, DSM, and true orthorectification are skipped.

## Dataset Mode

Run a Wietrznia-style folder of DJI images:

```bash
python -m processing.run_dataset_test \
    --images "D:\RESOURCES\Terrain dataset\images" \
    --output "output\terrain_mapping_test_v2\small_25" \
    --profile fast \
    --max-images 25 \
    --neighbors 4 \
    --feature-max-dim 1024 \
    --enable-dense \
    --dense-max-image-size 900
```

The runner does not modify source images. It writes a test-only CSV,
diagnostics, reconstruction artifacts, previews, and final comparison images
under the requested output directory.

## Required Diagnostics

The V2 runner writes:

```text
diagnostics/image_quality.csv
diagnostics/candidate_graph.csv
diagnostics/verified_matches.csv
diagnostics/image_id_map.csv
diagnostics/feature_track_stats.json
diagnostics/sfm_metrics.json
diagnostics/dense_metrics.json
diagnostics/dsm_metrics.json
diagnostics/gps_alignment.json
diagnostics/reconstruction_report.json
```

Sparse outputs:

```text
reconstruction/sparse/garuda_colmap.db
reconstruction/sparse/model/
reconstruction/sparse/camera_poses.csv
```

Dense outputs, when CUDA-supported PatchMatch succeeds:

```text
reconstruction/dense/fused.ply
elevation/dsm.tif
```

## Latest Wietrznia V2 Result

The latest checked-in result artifacts are stored under:

```text
mapping_output/terrain_mapping_test_v2/
```

Summary:

```text
Images found: 225
Small subset: 25 images
Good images: 25
Candidate edges: 53
Verified edges: 53
Feature tracks: 18,448
Mean track length: 2.99
Sparse SfM: SUCCESS
Registered images: 25 / 25
Sparse points: 9,329
Mean reprojection error after BA: 1.163 px
Dense MVS: FAILED
Dense blocker: CUDA unavailable for COLMAP PatchMatch
DSM: SKIPPED
True orthomosaic: SKIPPED
Overall: PARTIAL
```

This result proves that GARUDA now reaches a real global sparse reconstruction
and bundle adjustment from its verified feature graph. It does not yet prove a
true terrain orthomosaic because dense MVS could not run on the current machine.

## Known Limitations

- The visible Wietrznia dataset copy did not expose EXIF GPS through the current
  loader, so GPS similarity alignment was reported as unavailable.
- Dense MVS failed because PyCOLMAP PatchMatch requires CUDA.
- DSM generation is implemented for a dense PLY point cloud but was not run
  because `fused.ply` was not produced.
- Terrain-based orthorectification is still gated on dense geometry and DSM.
- The old chained-homography mosaic remains a diagnostic fallback, not final
  terrain geometry.

## Acceptance Status

| Requirement | Status |
| --- | --- |
| Real sparse SfM | PASS |
| Bundle adjustment | PASS |
| Camera poses exported | PASS |
| Sparse points produced | PASS |
| Dense MVS | BLOCKED: CUDA unavailable |
| DSM | SKIPPED: no dense cloud |
| True orthomosaic | SKIPPED: no DSM |
| Raw images untouched | PASS |
| Flight runtime unaffected | PASS |
