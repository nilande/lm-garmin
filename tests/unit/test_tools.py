import hashlib
import io
import zipfile

import pytest

from lm_garmin import tools


def test_pinned_tools_have_sha256():
    for t in tools.TOOLS.values():
        assert len(t.sha256) == 64
        assert t.url.startswith("https://")
        assert t.jar.endswith(f"/{t.name}.jar")


def _fake_zip(tool_dir: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{tool_dir}/fake.jar", b"jar")
    return buf.getvalue()


def test_fetch_uses_verified_archive(tmp_path, monkeypatch):
    payload = _fake_zip("fake-r1")
    t = tools.Tool(
        "fake", "r1", "https://example.invalid/x.zip", hashlib.sha256(payload).hexdigest()
    )
    (tmp_path / "fake-r1.zip").write_bytes(payload)
    monkeypatch.setattr(tools.urllib.request, "urlopen", lambda *_: pytest.fail("no download"))
    assert tools.fetch(t, tmp_path) == tmp_path / "fake-r1/fake.jar"


def test_fetch_rejects_bad_checksum(tmp_path, monkeypatch):
    payload = _fake_zip("fake-r1")
    t = tools.Tool("fake", "r1", "https://example.invalid/x.zip", "0" * 64)
    monkeypatch.setattr(tools.urllib.request, "urlopen", lambda *_: io.BytesIO(payload))
    with pytest.raises(RuntimeError, match="checksum"):
        tools.fetch(t, tmp_path)
