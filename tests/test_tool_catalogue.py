"""Tool registry and catalogue drift checks for BR-87063fd6."""

import ast
import re
from pathlib import Path

from app.db.migrations import MIGRATIONS
from app.llm.tool_resolver import TOOL_REGISTRY


ROOT = Path(__file__).resolve().parents[1]
OPTIONAL_MAPS = {
    "crisis_mcp_tools.py": "CRISIS_MCP_TOOLS",
    "projectops_mcp_tools.py": "PROJECT_OPS_MCP_TOOLS",
    "centerdeep_mcp_tools.py": "CENTERDEEP_MCP_TOOLS",
    "stable_canvas_tools.py": "STABLE_CANVAS_TOOLS",
    "stable_knowledge_tools.py": "STABLE_KNOWLEDGE_TOOLS",
    "glittermane_mcp_tools.py": "GLITTERMANE_MCP_TOOLS",
    "ilo_redfish_tools.py": "ILO_REDFISH_TOOLS",
    "knowledge_ops_tools.py": "KNOWLEDGE_OPS_TOOLS",
    "ucbrowser_mcp_tools.py": "UC_BROWSER_MCP_TOOLS",
}


def _catalogue_names() -> set[str]:
    """Read every seeded name from the SQL migration strings."""
    names: set[str] = set()
    for _version, _description, sql in MIGRATIONS:
        sql_text = "\n".join(sql) if isinstance(sql, list) else sql
        names.update(
            re.findall(r"\(\s*'([a-z0-9_]+)'\s*,\s*'[^']+'\s*,", sql_text)
        )
    return names


def _dict_keys(path: Path, variable: str) -> set[str]:
    """Extract literal registry-map keys without importing optional services."""
    tree = ast.parse(path.read_text())
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        else:
            continue
        if variable not in targets or not isinstance(node.value, ast.Dict):
            continue
        keys.update(key.value for key in node.value.keys if isinstance(key, ast.Constant))
    return keys


def _all_source_registry_names() -> set[str]:
    """Return the union of always-on and optional names that can be executable."""
    resolver = ast.parse((ROOT / "app/llm/tool_resolver.py").read_text())
    names: set[str] = set()
    for node in ast.walk(resolver):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        elif isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        else:
            continue
        if "TOOL_REGISTRY" in targets and isinstance(node.value, ast.Dict):
            names.update(key.value for key in node.value.keys if isinstance(key, ast.Constant))
        if isinstance(node.value, ast.Dict) and any(
            key in targets for key in (
                # The Home Assistant map is an inline update in tool_resolver.
                "TOOL_REGISTRY",
            )
        ):
            names.update(key.value for key in node.value.keys if isinstance(key, ast.Constant))

    # The crisis module appends generate_pdf after its initial literal map.
    names.update(_dict_keys(ROOT / "app/llm/crisis_mcp_tools.py", "CRISIS_MCP_TOOLS"))
    names.add("generate_pdf")
    for filename, variable in OPTIONAL_MAPS.items():
        names.update(_dict_keys(ROOT / "app/llm" / filename, variable))
    names.update({
        "ha_list_entities",
        "ha_get_entity_state",
        "ha_call_service",
        "ha_search_entities",
        "ha_get_history",
        "ha_list_areas",
        "ha_get_services",
    })
    return names


def test_executable_registry_is_subset_of_catalogue():
    """A registered callable must always have a permission/cost row."""
    missing = set(TOOL_REGISTRY) - _catalogue_names()
    assert not missing, f"executable tools missing from tool_catalog seed: {sorted(missing)}"


def test_optional_registry_sources_are_catalogued_before_enablement():
    """An env-gated integration cannot become an uncatalogued execution path."""
    missing = _all_source_registry_names() - _catalogue_names()
    assert not missing, f"source-defined executable tools missing from seed: {sorted(missing)}"


def test_high_risk_new_tools_have_level_five_seed_rows():
    sql = next(sql for version, _description, sql in MIGRATIONS
               if version == "20261009_01_tool_catalogue_complete")
    assert "('bmc_flash_firmware','free',5,'ilo_redfish',false)" in sql
    assert "('bmc_power_control','free',5,'ilo_redfish',false)" in sql
    assert "('ha_call_service','free',5,'home_assistant',false)" in sql
    assert "('slack','subscription',5,'slack',true)" in sql
    assert "('ucb_fill_form','free',5,'uc_browser',false)" in sql
