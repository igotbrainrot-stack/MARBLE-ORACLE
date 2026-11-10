"""Non-GUI integration bridge acceptance tests."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_suite_manifest_points_to_real_assets_and_code():
    manifest = json.loads((ROOT/'suite_integration/manifest.json').read_text())
    assert manifest['version'] == '2.0.6'
    assert manifest['integration_mode'] == 'separate-process-child-window'
    assert not manifest['supports_same_process_embedded_tabs']
    assert (ROOT/manifest['entrypoint']).is_file()
    for path in manifest['relative_assets'].values():
        assert (ROOT/path).exists(), path


def test_bridge_resolves_inner_and_outer_extraction_and_rejects_unknown(tmp_path):
    from oggcultist.suite_bridge import program_root
    assert program_root(ROOT) == ROOT
    assert program_root(ROOT.parent) == ROOT
    with pytest.raises(FileNotFoundError):
        program_root(tmp_path)


def test_bridge_version_command_in_isolated_child_process(tmp_path):
    from oggcultist.suite_bridge import launch
    # The --version CLI is deliberately safe even on headless Linux.
    process = launch(ROOT, python_executable=sys.executable, arguments=['--version'])
    assert process.wait(timeout=30) == 0


def test_bridge_missing_python_has_clear_error(tmp_path):
    from oggcultist.suite_bridge import source_python
    with pytest.raises(FileNotFoundError, match='does not exist'):
        source_python(ROOT, explicit=tmp_path / 'missing-python')
