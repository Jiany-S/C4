import hashlib
import json
import pytest
from scripts.verify_evidence import verify_manifest


def test_windows_manifest_paths_verify_on_any_platform(tmp_path):
    folder = tmp_path / 'trials'
    folder.mkdir()
    data = b'{"answer":"actual result"}\r\n'
    (folder / 'trial.json').write_bytes(data)
    (tmp_path / 'manifest.json').write_text(json.dumps({'sha256': {
        'trials\\trial.json': hashlib.sha256(data).hexdigest()}}))
    assert verify_manifest(tmp_path) == 1
    (folder / 'trial.json').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        verify_manifest(tmp_path)


def test_manifest_cannot_escape_evidence_directory(tmp_path):
    (tmp_path / 'manifest.json').write_text(json.dumps({'sha256': {'../outside.json':'bad'}}))
    with pytest.raises(ValueError, match='leaves'):
        verify_manifest(tmp_path)
