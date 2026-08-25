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
    for observations in groups.values():
        images = {obs.image_name for obs in observations}
        if len(images) < min_track_length:
            continue
        tracks.append(FeatureTrack(track_id=len(tracks), observations=observations))
    return tuple(tracks)
