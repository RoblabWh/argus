"""Constrained union-find clustering for re-identification.

Transitive single-linkage grouping over a set of weighted edges, with one hard
invariant: a cluster (one physical object) may never contain two detections
from the same image (a detector sees each real object at most once per frame).
"""
from __future__ import annotations


class UnionFind:
    """Disjoint-set with path compression and union by rank."""

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]  # path compression (path halving, non recursive)
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> int:
        """Merge the sets of ``a`` and ``b``; return the new root."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return ra


def constrained_merge(edges, image_ids, n: int) -> list[int]:
    """Merge edges strongest-first, enforcing the no-same-image invariant.

    Args:
        edges: iterable of (local_i, local_j, weight); higher weight = merge first.
        image_ids: sequence mapping local index -> image_id.
        n: number of local nodes.

    Returns:
        ``roots`` — list of length ``n`` giving the final cluster root per node.
    """
    uf = UnionFind(n)
    cluster_images = {i: {int(image_ids[i])} for i in range(n)}

    for a, b, _ in sorted(edges, key=lambda e: -e[2]):  # highest weight first
        if image_ids[a] == image_ids[b]:
            continue  # 1) the two boxes share an image
        ra, rb = uf.find(a), uf.find(b)
        if ra == rb:
            continue  # 2) already in the same cluster
        if cluster_images[ra] & cluster_images[rb]:
            continue  # 3) clusters' image sets overlap
        new_root = uf.union(ra, rb)
        merged = cluster_images[ra] | cluster_images[rb]
        cluster_images[new_root] = merged
        old_root = rb if new_root == ra else ra
        cluster_images.pop(old_root, None)

    return [uf.find(i) for i in range(n)]
