# Garuda V1 Pose-Assisted Mapping Architecture

Garuda V1 no longer depends on perfect mechanical camera stabilization. The
gimbal only keeps the camera approximately downward and damps extreme roll or
pitch. Image orientation is recovered after flight from synchronized IMU,
GPS, barometer, and camera metadata.

## Core Principle

The IMU is a prior, not a final correction. Raw images remain recoverable, and
OpenCV feature matching plus RANSAC must verify or reject every visual
relationship before mosaicking.

```text
Stored mission data
-> Mission validation
-> Image quality scoring
-> Lens undistortion
-> IMU pose prior
-> Candidate graph from GPS/time/yaw
-> SIFT or ORB features
-> FLANN/BF matching
-> Lowe ratio test
-> RANSAC refinement
-> Multi-view feature tracks
-> PyCOLMAP sparse SfM
-> Global bundle adjustment
-> Camera pose and sparse point export
-> Optional dense MVS / DSM / orthorectification
-> Report
```

## Pose Normalization

For each captured image, the system stores timestamp, GPS, barometer altitude,
roll, pitch, yaw, angular velocity, and camera calibration. During processing,
the camera model and IMU attitude produce a homography:

```text
H_prior = K * R_imu^-1 * K^-1
```

This homography may be used to create an expanded-canvas working image, but it
must not replace the raw image. Feature coordinates and final geometric
estimates should remain traceable to the undistorted source image.

## Image Graph

Images are graph nodes. Candidate edges are created from sensor constraints
before expensive visual matching:

- GPS distance
- capture time separation
- yaw difference
- relative IMU pose prior

This allows Image A to match Image C even when Image B is poor, blurred, or
partially overlapping.

## V1 Boundaries

Implemented foundation:

- synchronized capture metadata fields
- angular velocity logging
- camera model records
- image quality scoring
- IMU pose-prior homographies
- expanded-canvas pose-normalization helper
- SIFT-first feature detector with ORB fallback
- FLANN/BF feature matching
- RANSAC homography estimation
- graph-based candidate relationships

## V2 Sparse Reconstruction

The V2 post-flight path imports GARUDA's verified feature graph into a COLMAP
database through PyCOLMAP. It explicitly preserves mappings between filenames,
GARUDA image order, COLMAP image IDs, feature indices, and match indices. When
features are extracted on resized images, keypoints are scaled back into
original image coordinates before insertion into COLMAP.

Sparse reconstruction then runs through PyCOLMAP incremental mapping and global
bundle adjustment. The current Wietrznia test registered all 25 selected images,
produced 9,329 sparse 3D points, and reported a mean post-BA reprojection error
of about 1.16 px.

Still future work:

- GPU-backed dense MVS on a CUDA-capable reconstruction machine
- DSM generation from the dense point cloud in a completed dense run
- terrain-based orthorectification using optimized poses plus DSM
- exposure compensation, seam optimization, and multiband blending for the final orthomosaic
- semantic landing-zone detection
