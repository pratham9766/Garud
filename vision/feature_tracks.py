"""Compact multi-view feature track construction."""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2


@dataclass(frozen=True)
class FeatureObservation:
    """One image feature assigned to a track."""

    image_name: str
    feature_id: int


@dataclass
class FeatureTrack:
    """A terrain point observed in two or more images."""

    track_id: int
    observations: set[FeatureObservation] = field(default_factory=set)


@dataclass(frozen=True)
class FeatureTrackBuildResult:
    """Track construction result plus consistency diagnostics."""

    tracks: tuple[FeatureTrack, ...]
    rejected_conflict_tracks: int
    rejected_short_tracks: int


class _DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[FeatureObservation, FeatureObservation] = {}

    def find(self, item: FeatureObservation) -> FeatureObservation:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, a: FeatureObservation, b: FeatureObservation) -> None:
        root_a = self.find(a)
        root_b = self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a


def build_feature_tracks(
    pair_matches: dict[tuple[str, str], tuple[cv2.DMatch, ...]],
    min_track_length: int = 2,
) -> tuple[FeatureTrack, ...]:
    """Build compact feature tracks from verified pairwise matches."""
    return build_feature_tracks_with_diagnostics(pair_matches, min_track_length).tracks


def build_feature_tracks_with_diagnostics(
    pair_matches: dict[tuple[str, str], tuple[cv2.DMatch, ...]],
    min_track_length: int = 2,
) -> FeatureTrackBuildResult:
    """Build compact, internally consistent feature tracks from verified matches."""
    dsu = _DisjointSet()
    for (source, target), matches in pair_matches.items():
        for match in matches:
            dsu.union(
                FeatureObservation(source, int(match.queryIdx)),
                FeatureObservation(target, int(match.trainIdx)),
            )

    groups: dict[FeatureObservation, set[FeatureObservation]] = {}
    for item in list(dsu.parent):
        groups.setdefault(dsu.find(item), set()).add(item)

    tracks: list[FeatureTrack] = []
    rejected_conflicts = 0
    rejected_short = 0
    for observations in groups.values():
        by_image: dict[str, FeatureObservation] = {}
        conflict = False
        for obs in observations:
            existing = by_image.get(obs.image_name)
            if existing is not None and existing.feature_id != obs.feature_id:
                conflict = True
                break
            by_image[obs.image_name] = obs
        if conflict:
            rejected_conflicts += 1
            continue
        if len(by_image) < min_track_length:
            rejected_short += 1
            continue
        tracks.append(FeatureTrack(track_id=len(tracks), observations=set(by_image.values())))
    return FeatureTrackBuildResult(
        tracks=tuple(tracks),
        rejected_conflict_tracks=rejected_conflicts,
        rejected_short_tracks=rejected_short,
    )
