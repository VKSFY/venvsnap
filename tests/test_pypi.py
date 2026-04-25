import httpx
import pytest
import respx
from packaging.tags import Tag

from venvsnap.pypi import (
    PypiError,
    _tags_from_filename,
    fetch_release,
    select_wheel,
)

PYPI_PAYLOAD = {
    "info": {"name": "requests", "version": "2.31.0"},
    "urls": [
        {
            "filename": "requests-2.31.0-py3-none-any.whl",
            "url": "https://files.pythonhosted.org/packages/r/requests/requests-2.31.0-py3-none-any.whl",
            "packagetype": "bdist_wheel",
            "digests": {"sha256": "deadbeef"},
            "requires_python": ">=3.7",
        },
        {
            "filename": "requests-2.31.0.tar.gz",
            "url": "https://files.pythonhosted.org/packages/r/requests/requests-2.31.0.tar.gz",
            "packagetype": "sdist",
            "digests": {"sha256": "ffffffff"},
            "requires_python": ">=3.7",
        },
    ],
}


@respx.mock
def test_fetch_release_returns_only_wheels() -> None:
    respx.get("https://pypi.org/pypi/requests/2.31.0/json").mock(
        return_value=httpx.Response(200, json=PYPI_PAYLOAD)
    )
    with httpx.Client() as client:
        artifacts = fetch_release(client, "requests", "2.31.0")
    assert len(artifacts) == 1
    assert artifacts[0].filename.endswith(".whl")
    assert artifacts[0].sha256 == "deadbeef"


@respx.mock
def test_fetch_release_404_raises() -> None:
    respx.get("https://pypi.org/pypi/nope/0.0.1/json").mock(return_value=httpx.Response(404))
    with httpx.Client() as client, pytest.raises(PypiError, match="not found"):
        fetch_release(client, "nope", "0.0.1")


@respx.mock
def test_fetch_release_500_raises() -> None:
    respx.get("https://pypi.org/pypi/x/1.0/json").mock(return_value=httpx.Response(503))
    with httpx.Client() as client, pytest.raises(PypiError, match="HTTP 503"):
        fetch_release(client, "x", "1.0")


def test_tags_from_filename_pure() -> None:
    tags = _tags_from_filename("requests-2.31.0-py3-none-any.whl")
    assert Tag("py3", "none", "any") in tags


def test_tags_from_filename_compound() -> None:
    # cp310.cp311 means two python tags
    tags = _tags_from_filename("foo-1.0-cp310.cp311-none-any.whl")
    assert Tag("cp310", "none", "any") in tags
    assert Tag("cp311", "none", "any") in tags


def test_select_wheel_prefers_higher_priority_tag() -> None:
    from venvsnap.pypi import WheelArtifact

    pure = WheelArtifact(
        filename="x-1.0-py3-none-any.whl",
        url="u",
        sha256="s",
        requires_python=None,
        tags=(Tag("py3", "none", "any"),),
    )
    native = WheelArtifact(
        filename="x-1.0-cp311-cp311-linux_x86_64.whl",
        url="u2",
        sha256="s2",
        requires_python=None,
        tags=(Tag("cp311", "cp311", "linux_x86_64"),),
    )
    compatible = [
        Tag("cp311", "cp311", "linux_x86_64"),
        Tag("py3", "none", "any"),
    ]
    chosen = select_wheel([pure, native], compatible_tags=compatible)
    assert chosen is native


def test_select_wheel_returns_none_when_no_match() -> None:
    from venvsnap.pypi import WheelArtifact

    art = WheelArtifact(
        filename="x-1.0-cp311-cp311-win_amd64.whl",
        url="u",
        sha256="s",
        requires_python=None,
        tags=(Tag("cp311", "cp311", "win_amd64"),),
    )
    chosen = select_wheel([art], compatible_tags=[Tag("cp310", "cp310", "linux_x86_64")])
    assert chosen is None
