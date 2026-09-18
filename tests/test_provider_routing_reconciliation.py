"""Provider routing keeps organization metering and BR-6.4 call contracts."""
import ast
import inspect
from pathlib import Path

import pytest

from app.llm import ops_center_client as module
from app.llm.ops_center_client import OpsCenterLLMClient
from app.llm.org_gateway import clear_org_gateway_cache


@pytest.fixture
def client(monkeypatch):
    for name in ('OPENAI_DIRECT_KEY', 'DASHSCOPE_API_KEY', 'OPENROUTER_API_KEY', 'LITELLM_DIRECT_KEY'):
        monkeypatch.setattr(module, name, '')
    monkeypatch.setattr(module, 'UC_GATEWAY_URL', 'https://gateway.invalid/v1')
    monkeypatch.setattr(module, 'OPS_CENTER_LLM_ENDPOINT', '')
    return OpsCenterLLMClient(ops_center_url='http://ops.invalid', service_key='fixture-only')


@pytest.mark.parametrize('model,keyvar,expected,route', [
    ('openai/gpt-fixture', 'OPENAI_DIRECT_KEY', 'gpt-fixture', 'openai'),
    ('dashscope/qwen-plus', 'DASHSCOPE_API_KEY', 'qwen-plus', 'dashscope'),
    ('alibaba/qwen-max', 'DASHSCOPE_API_KEY', 'qwen-max', 'dashscope'),
    ('openrouter/anthropic/claude-fixture', 'OPENROUTER_API_KEY', 'anthropic/claude-fixture', 'openrouter'),
])
def test_provider_endpoint_and_key(client, monkeypatch, model, keyvar, expected, route):
    monkeypatch.setattr(module, keyvar, 'fixture-provider-key')
    target, resolved, kind = client._resolve_local_model(model)
    endpoint, headers = client._endpoint_and_headers(kind, target, 'user-fixture', 'org-fixture')
    assert (resolved, kind) == (expected, route)
    assert endpoint == target + '/chat/completions'
    assert headers['Authorization'] == 'Bearer fixture-provider-key'


@pytest.mark.parametrize('model,resolved', [
    ('anthropic/claude-fixture', 'claude-fixture'),
    ('openai/gpt-fixture', 'gpt-fixture'),
    ('qwen-plus', 'qwen-plus'),
])
def test_gateway_fallback_retains_org_headers(client, monkeypatch, model, resolved):
    monkeypatch.setattr(module, 'OPENAI_DIRECT_KEY', 'local-dummy')
    monkeypatch.setenv('UC_GATEWAY_PER_ORG_KEYS_ENABLED', '1')
    monkeypatch.setenv('UC_GATEWAY_ORG_KEYS_JSON', '{"org-fixture":"fixture-org-key"}')
    clear_org_gateway_cache()
    try:
        target, actual, kind = client._resolve_local_model(model)
        assert (actual, kind) == (resolved, 'gateway')
        _, headers = client._endpoint_and_headers(kind, target, 'user-fixture', 'org-fixture')
        assert headers['Authorization'] == 'Bearer fixture-org-key'
        assert headers['X-Org-ID'] == 'org-fixture'
        assert headers['X-User-ID'] == 'user-fixture'
        with pytest.raises(RuntimeError):
            client._endpoint_and_headers(kind, target, 'user-fixture', 'another-org')
    finally:
        clear_org_gateway_cache()


def test_explicit_openrouter_overrides_direct_provider(client, monkeypatch):
    monkeypatch.setattr(module, 'OPENAI_DIRECT_KEY', 'fixture-openai')
    monkeypatch.setattr(module, 'OPENROUTER_API_KEY', 'fixture-openrouter')
    assert client._resolve_local_model('openrouter/openai/gpt-fixture')[2] == 'openrouter'


def test_client_retains_guard_and_org_call_contract():
    signature = inspect.signature(OpsCenterLLMClient.execute_tool_loop)
    assert 'tool_guard' in signature.parameters
    assert 'org_id' in signature.parameters


@pytest.mark.parametrize('method', ['_chat_completion_once', 'chat_completion_stream', '_chat_completion_with_tools_once'])
def test_client_request_modes_forward_org_to_shared_helper(method):
    # AST regression: consolidation must cover streaming as well as POSTs.
    tree = ast.parse(Path('app/llm/ops_center_client.py').read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == method)
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == '_endpoint_and_headers']
    assert len(calls) == 1
    assert any(k.arg == 'org_id' and ast.unparse(k.value) == 'org_id' for k in calls[0].keywords)


@pytest.mark.parametrize('method', ['_passthrough_chat', '_dual_layer_chat', '_enhanced_stream_chat'])
def test_openai_paths_keep_authorization_before_provider_request(method):
    tree = ast.parse(Path('app/api/openai_compat_routes.py').read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == method)
    auth = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_authorize_caller']
    route = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == '_endpoint_and_headers']
    assert len(auth) == len(route) == 1
    assert auth[0].lineno < route[0].lineno
    assert any(k.arg == 'org_id' and 'auth_user' in ast.unparse(k.value) for k in route[0].keywords)
    if method != '_passthrough_chat':
        assert any(isinstance(n, ast.Call) and ast.unparse(n.func) == '_tool_guard.check' for n in ast.walk(fn))
