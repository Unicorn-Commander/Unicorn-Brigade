"""Private features (app/private_features.py).

The crisis investigation feature and the production core seed are private to
Magic Unicorn's deployment. The public GitHub mirror strips their files, so the
public build has to start without them. The detection is by file, so a broken
module that IS installed still fails loudly, and a partial install is an error.
"""
from __future__ import annotations

import pytest

from app.private_features import CRISIS_FEATURE_FILES, crisis_feature_present


def _files(tmp_path, n=3):
    return tuple(tmp_path / f"part_{i}.py" for i in range(n))


def test_every_file_present_means_installed(tmp_path):
    files = _files(tmp_path)
    for f in files:
        f.write_text("")
    assert crisis_feature_present(files) is True


def test_no_file_present_means_not_installed(tmp_path):
    assert crisis_feature_present(_files(tmp_path)) is False


def test_a_partial_install_fails_loudly(tmp_path):
    files = _files(tmp_path)
    files[0].write_text("")
    with pytest.raises(RuntimeError, match="only partly installed"):
        crisis_feature_present(files)


def test_this_build_is_all_or_nothing():
    present = [f.is_file() for f in CRISIS_FEATURE_FILES]
    assert all(present) or not any(present)


def test_the_tool_registry_matches_the_install():
    from app.llm.tool_resolver import TOOL_REGISTRY

    assert ("search_evidence" in TOOL_REGISTRY) == crisis_feature_present()
