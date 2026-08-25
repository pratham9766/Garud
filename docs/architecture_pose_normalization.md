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
-> Warping and blending
-> Orthomosaic and report
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

Still future work:

- full orthomosaic blending pipeline
- bundle adjustment
- structure from motion
- 3D reconstruction
- semantic landing-zone detection

