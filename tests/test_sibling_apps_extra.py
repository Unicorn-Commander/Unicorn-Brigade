"""Deployment-private sibling apps (BRIGADE_SIBLING_APPS_EXTRA).

A deployment adds its own sibling apps in a separate JSON file instead of
bind-mounting a replacement for the bundled app/data/sibling_apps.json. A
replacement would freeze the bundled list at the time it was copied. The extra
entries merge after the bundled ones, and a same-name entry replaces its
bundled counterpart.
"""
from __future__ import annotations

import json
import logging
import os

import pytest

import app.llm.sibling_app_tools as sat

EXTRA = {
    "name": "private-tools",
    "namespace": "privatetools",
    "transport": "mcp",
    "url_env": "PRIVATE_TOOLS_URL",
    "default_url": "",
    "token_env": "PRIVATE_TOOLS_TOKEN",
    "token_required": True,
    "timeout": 15,
    "tools": ["catalog_search"],
}


def _names(configs):
    return [c.name for c in configs]


def test_without_the_setting_only_the_bundled_apps_load(monkeypatch):
    monkeypatch.delenv(sat.SIBLING_APPS_EXTRA_ENV, raising=False)
    bundled = json.loads(sat.CONFIG_PATH.read_text())
    assert _names(sat._load_configs()) == [b["name"] for b in bundled]


def test_an_extra_file_adds_its_apps_after_the_bundled_ones(monkeypatch, tmp_path):
    f = tmp_path / "extra.json"
    f.write_text(json.dumps([EXTRA]))
    monkeypatch.setenv(sat.SIBLING_APPS_EXTRA_ENV, str(f))
    names = _names(sat._load_configs())
    bundled = [b["name"] for b in json.loads(sat.CONFIG_PATH.read_text())]
    assert names == bundled + ["private-tools"]
    cfg = next(c for c in sat._load_configs() if c.name == "private-tools")
    assert cfg.namespace == "privatetools" and cfg.token_required is True


def test_a_same_name_entry_replaces_the_bundled_app(monkeypatch, tmp_path, caplog):
    bundled = json.loads(sat.CONFIG_PATH.read_text())
    override = dict(bundled[0], timeout=42)
    f = tmp_path / "extra.json"
    f.write_text(json.dumps([override]))
    monkeypatch.setenv(sat.SIBLING_APPS_EXTRA_ENV, str(f))
    with caplog.at_level(logging.WARNING, logger=sat.logger.name):
        configs = sat._load_configs()
    matching = [c for c in configs if c.name == bundled[0]["name"]]
    assert len(matching) == 1 and matching[0].timeout == 42
    assert "replaces bundled app" in caplog.text


def test_several_extra_files_are_read_in_order(monkeypatch, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps([EXTRA]))
    b.write_text(json.dumps([dict(EXTRA, name="second-tools", namespace="secondtools")]))
    monkeypatch.setenv(sat.SIBLING_APPS_EXTRA_ENV, os.pathsep.join([str(a), str(b)]))
    assert _names(sat._load_configs())[-2:] == ["private-tools", "second-tools"]


def test_a_missing_extra_file_is_loud_but_keeps_the_bundled_apps(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv(sat.SIBLING_APPS_EXTRA_ENV, str(tmp_path / "missing.json"))
    with caplog.at_level(logging.ERROR, logger=sat.logger.name):
        names = _names(sat._load_configs())
    assert names == [b["name"] for b in json.loads(sat.CONFIG_PATH.read_text())]
    assert "unavailable" in caplog.text


@pytest.mark.parametrize("orgs, expected", [
    (None, None),
    ([], ()),
    (["majiks", "00000000-0000-0000-0000-000000000001"],
     ("majiks", "00000000-0000-0000-0000-000000000001")),
])
@pytest.mark.parametrize("extra", [False, True])
def test_orgs_parse_in_bundled_and_extra_configs(monkeypatch, tmp_path, orgs, expected, extra):
    config = tmp_path / "apps.json"
    config.write_text(json.dumps([dict(EXTRA, orgs=orgs)]))
    if extra:
        monkeypatch.setenv(sat.SIBLING_APPS_EXTRA_ENV, str(config))
    else:
        monkeypatch.delenv(sat.SIBLING_APPS_EXTRA_ENV, raising=False)
        monkeypatch.setattr(sat, "CONFIG_PATH", config)
    app = next(c for c in sat._load_configs() if c.name == EXTRA["name"])
    assert app.orgs == expected


def test_omitted_orgs_keep_existing_sibling_configs_global(monkeypatch):
    monkeypatch.setattr(sat, "_config_items", lambda: [EXTRA])
    assert sat._load_configs()[0].orgs is None
