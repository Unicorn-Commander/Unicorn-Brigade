"""
Tests for the discovery-manifest validator + registration extractor.

Mirrors the contract in BRIGADE-FEDERATION-SPEC.md ("Publish a discovery
manifest at /.well-known/mcps.json"). The valid manifest below is the spec's
own example, trimmed to the fields the validator cares about. Each negative
test mutates exactly one field of a fresh copy so a failure points at the rule
under test, and asserts the field-specific error string surfaces.

Run from the repo root:
  PYTHONPATH=. python -m pytest app/federation/test_manifest_schema.py -v
"""
from app.federation.manifest_schema import extract_registration, validate_manifest


def _valid_manifest() -> dict:
    """A realistic, schema-valid manifest built from the spec example."""
    return {
        "$schema": "https://brigade.unicorncommander.ai/.well-known/mcps-schema-v1.json",
        "name": "Your-App-Name",
        "version": "1.4.2",
        "mcp_endpoint": "https://your-app.example.com/mcp",
        "tool_namespace": "your_app",
        "auth": {
            "type": "pat",
            "prefix": "yapp_pat_",
            "mint_url": "https://your-app.example.com/settings/pats",
            "federated_auth": {
                "type": "brigade_jwt",
                "trusted_issuer": "https://brigade.unicorncommander.ai",
                "jwks_url": "https://brigade.unicorncommander.ai/.well-known/jwks.json",
                "expected_audience": "your-app-name",
                "signing_algorithm": "RS256",
            },
        },
        "tools": [
            {
                "name": "search_widgets",
                "description": "Hybrid semantic + keyword search across the user's widgets.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
                "scopes_required": ["read:widgets"],
                "tier_required": "free",
                "read_only": True,
                "expected_latency_ms": 250,
            },
            {
                "name": "create_widget",
                "description": "Create a new widget with propose/confirm safety.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["title"],
                },
                "scopes_required": ["write:widgets"],
                "tier_required": "pro",
                "read_only": False,
                "expected_latency_ms": 800,
            },
        ],
        "resources": [
            {"uri_template": "widgets://list", "description": "Overview of all widgets"},
            {"uri_template": "widgets://{widget_id}", "description": "Single widget"},
        ],
        "prompts": [
            {"name": "widget_analysis", "description": "Cross-widget analysis prompt"},
        ],
        "rate_limits": {"per_user_per_minute": 60, "per_user_per_hour": 1000},
        "contact": "support@your-app.example.com",
    }


def _assert_field_error(errors: list[str], field_prefix: str) -> None:
    """Assert at least one error names the given field."""
    assert any(e.startswith(field_prefix) for e in errors), (
        f"expected an error for {field_prefix!r}, got {errors!r}"
    )


def test_valid_manifest_passes():
    ok, errors = validate_manifest(_valid_manifest())
    assert ok is True
    assert errors == []


def test_empty_tools_list_is_allowed():
    """tools may be empty but must be present."""
    doc = _valid_manifest()
    doc["tools"] = []
    ok, errors = validate_manifest(doc)
    assert ok is True, errors


def test_missing_tool_namespace_fails():
    doc = _valid_manifest()
    del doc["tool_namespace"]
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "tool_namespace:")
    assert any("missing" in e for e in errors if e.startswith("tool_namespace:"))


def test_tool_namespace_too_short_fails():
    doc = _valid_manifest()
    doc["tool_namespace"] = "abc"  # 3 chars, min is 6
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "tool_namespace:")


def test_tool_namespace_uppercase_fails():
    doc = _valid_manifest()
    doc["tool_namespace"] = "MyApp"  # uppercase not allowed
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "tool_namespace:")


def test_tool_namespace_too_long_fails():
    doc = _valid_manifest()
    doc["tool_namespace"] = "a" * 13  # 13 chars, max is 12
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "tool_namespace:")


def test_signing_algorithm_ed25519_fails():
    doc = _valid_manifest()
    doc["auth"]["federated_auth"]["signing_algorithm"] = "ed25519"
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "auth.federated_auth.signing_algorithm:")


def test_signing_algorithm_eddsa_fails():
    doc = _valid_manifest()
    doc["auth"]["federated_auth"]["signing_algorithm"] = "EdDSA"
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "auth.federated_auth.signing_algorithm:")


def test_tier_required_gold_fails():
    doc = _valid_manifest()
    doc["tools"][1]["tier_required"] = "gold"
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "tools[1].tier_required:")


def test_tool_missing_scopes_required_fails():
    doc = _valid_manifest()
    del doc["tools"][0]["scopes_required"]
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "tools[0].scopes_required:")
    # Error string names the field and that it is missing, per the spec example.
    assert "tools[0].scopes_required: required, missing" in errors


def test_missing_required_top_level_fields_fail():
    for field in ("name", "version", "mcp_endpoint"):
        doc = _valid_manifest()
        del doc[field]
        ok, errors = validate_manifest(doc)
        assert ok is False, f"{field} should be required"
        _assert_field_error(errors, f"{field}:")


def test_empty_string_top_level_field_fails():
    doc = _valid_manifest()
    doc["name"] = "   "
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "name:")


def test_missing_expected_audience_fails():
    doc = _valid_manifest()
    del doc["auth"]["federated_auth"]["expected_audience"]
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "auth.federated_auth.expected_audience:")


def test_tool_input_schema_not_dict_fails():
    doc = _valid_manifest()
    doc["tools"][0]["input_schema"] = "not-an-object"
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "tools[0].input_schema:")


def test_tool_read_only_not_bool_fails():
    doc = _valid_manifest()
    doc["tools"][0]["read_only"] = "yes"
    ok, errors = validate_manifest(doc)
    assert ok is False
    _assert_field_error(errors, "tools[0].read_only:")


def test_multiple_errors_collected():
    """All failing fields surface in one pass, not just the first."""
    doc = _valid_manifest()
    del doc["name"]
    doc["tool_namespace"] = "X"
    del doc["tools"][0]["scopes_required"]
    ok, errors = validate_manifest(doc)
    assert ok is False
    assert len(errors) >= 3
    _assert_field_error(errors, "name:")
    _assert_field_error(errors, "tool_namespace:")
    _assert_field_error(errors, "tools[0].scopes_required:")


def test_non_dict_manifest_fails():
    ok, errors = validate_manifest(["not", "a", "dict"])
    assert ok is False
    assert errors


def test_extract_registration_returns_right_keys():
    doc = _valid_manifest()
    # Guard: only extract from a doc that actually validates.
    ok, _ = validate_manifest(doc)
    assert ok is True

    reg = extract_registration(doc)
    assert set(reg.keys()) == {
        "name",
        "version",
        "tool_namespace",
        "mcp_endpoint",
        "expected_audience",
        "jwks_url",
        "tools",
    }
    assert reg["name"] == "Your-App-Name"
    assert reg["version"] == "1.4.2"
    assert reg["tool_namespace"] == "your_app"
    assert reg["mcp_endpoint"] == "https://your-app.example.com/mcp"
    assert reg["expected_audience"] == "your-app-name"
    assert reg["jwks_url"] == "https://brigade.unicorncommander.ai/.well-known/jwks.json"

    assert len(reg["tools"]) == 2
    first = reg["tools"][0]
    assert set(first.keys()) == {
        "name",
        "scopes_required",
        "tier_required",
        "read_only",
        "input_schema",
    }
    assert first["name"] == "search_widgets"
    assert first["scopes_required"] == ["read:widgets"]
    assert first["tier_required"] == "free"
    assert first["read_only"] is True
    assert first["input_schema"]["required"] == ["query"]


def test_extract_registration_empty_tools():
    doc = _valid_manifest()
    doc["tools"] = []
    reg = extract_registration(doc)
    assert reg["tools"] == []
    assert reg["name"] == "Your-App-Name"
