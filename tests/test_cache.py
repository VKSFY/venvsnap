import hashlib
from pathlib import Path

import pytest

from venvsnap.cache import Cache


def test_store_and_retrieve(tmp_path: Path) -> None:
    cache = Cache(root=tmp_path)
    payload = b"wheel-bytes"
    sha = hashlib.sha256(payload).hexdigest()

    assert not cache.has(sha, "demo-1.0-py3-none-any.whl")
    path = cache.store(payload, sha, "demo-1.0-py3-none-any.whl")
    assert path.exists()
    assert path.read_bytes() == payload
    assert cache.has(sha, "demo-1.0-py3-none-any.whl")


def test_store_rejects_bad_hash(tmp_path: Path) -> None:
    cache = Cache(root=tmp_path)
    with pytest.raises(ValueError, match="hash mismatch"):
        cache.store(b"hello", "0" * 64, "bad-1.0.whl")


def test_buckets_by_two_char_prefix(tmp_path: Path) -> None:
    cache = Cache(root=tmp_path)
    payload = b"x"
    sha = hashlib.sha256(payload).hexdigest()
    path = cache.wheel_path(sha, "x.whl")
    assert path.parent.parent.name == sha[:2]


def test_stats_counts_and_sizes(tmp_path: Path) -> None:
    cache = Cache(root=tmp_path)
    for i in range(3):
        payload = f"wheel-{i}".encode()
        sha = hashlib.sha256(payload).hexdigest()
        cache.store(payload, sha, f"pkg{i}-1.0-py3-none-any.whl")
    stats = cache.stats()
    assert stats.wheel_count == 3
    assert stats.total_bytes == sum(len(f"wheel-{i}".encode()) for i in range(3))


def test_stats_empty_when_no_wheels(tmp_path: Path) -> None:
    cache = Cache(root=tmp_path)
    stats = cache.stats()
    assert stats.wheel_count == 0
    assert stats.total_bytes == 0


def test_clean_removes_all(tmp_path: Path) -> None:
    cache = Cache(root=tmp_path)
    payload = b"x"
    sha = hashlib.sha256(payload).hexdigest()
    cache.store(payload, sha, "x.whl")
    assert cache.stats().wheel_count == 1

    removed = cache.clean()
    assert removed.wheel_count == 1
    assert cache.stats().wheel_count == 0
