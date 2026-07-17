"""Cross-tenant execution-disclosure fix — in-process proof (no infra).

Confirmed bug: the workflow + Ralph execution list/read endpoints authenticated
with ``require_api_key`` (a valid key for ANY org) but did NO org scoping, so org
A could enumerate + read org B's executions. This proof drives the REAL FastAPI
routers (``app.api.hierarchical_routes`` + ``app.api.ralph_routes``) via a
TestClient with the auth dependency overridden to impersonate four callers:

  * org-A operator   (bound org = ORG_A)
  * org-B operator   (bound org = ORG_B)
  * unbound operator (a valid key with NO bound org — e.g. a legacy/unbound key)
  * global admin     (UserRole.ADMIN — the legitimate cross-org operator view)

It seeds one execution per org directly into the engines' in-memory caches (the
same cache the SYNC, cache-backed getters read) and asserts, for BOTH the
hierarchical workflow engine and the Ralph engine:

  1. org-A key LISTS ONLY org-A executions (never org-B's).
  2. org-A GET of an org-B execution id -> 404 (NOT 403 — existence not leaked).
  3. unbound key -> EMPTY list + 404 on gets (fail closed, never everything).
  4. admin -> sees BOTH orgs (legitimate global view preserved).
  5. (Ralph) cross-org guidance INJECTION (a mutation) is also 404'd.

No Postgres, no network — pure in-process. Exit 0 only if every assertion holds.
"""
import sys
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.middleware import AuthUser, require_api_key, require_operator
from app.auth.roles import UserRole
from app.workflows.engine import WorkflowEngine
from app.workflows.schema import WorkflowExecution, WorkflowExecutionState
from app.workflows.ralph_engine import RalphWorkflowEngine, RalphWorkflowState
import app.api.hierarchical_routes as hier
import app.api.ralph_routes as ralph

ORG_A = str(uuid.uuid4())
ORG_B = str(uuid.uuid4())

FAILURES = []
PASSES = []


def check(label, condition, detail=""):
    tag = "PASS" if condition else "FAIL"
    (PASSES if condition else FAILURES).append(label)
    print(f"  [{tag}] {label}" + (f"  — {detail}" if detail else ""))


# ── Four impersonated callers (what the overridden auth dependency returns) ────
USER_A = AuthUser(id="user-a", role=UserRole.OPERATOR, org_id=ORG_A, auth_source="api_key")
USER_B = AuthUser(id="user-b", role=UserRole.OPERATOR, org_id=ORG_B, auth_source="api_key")
USER_UNBOUND = AuthUser(id="user-x", role=UserRole.OPERATOR, org_id=None, auth_source="api_key")
USER_ADMIN = AuthUser(id="admin", role=UserRole.ADMIN, org_id=None, auth_source="api_key")

# Mutable holder the dependency override reads; set before each request.
_CURRENT = {"user": None}


def _current_user() -> AuthUser:
    return _CURRENT["user"]


def as_user(user):
    _CURRENT["user"] = user


# ── Seed the workflow engine cache with one execution per org ──────────────────
engine = WorkflowEngine()
EXEC_A = WorkflowExecution(
    id="wf-org-a", workflow_id="due_diligence", workflow_name="A",
    state=WorkflowExecutionState.RUNNING, org_id=ORG_A,
)
EXEC_B = WorkflowExecution(
    id="wf-org-b", workflow_id="due_diligence", workflow_name="B",
    state=WorkflowExecutionState.RUNNING, org_id=ORG_B,
)
engine._executions[EXEC_A.id] = EXEC_A
engine._executions[EXEC_B.id] = EXEC_B


# ── Seed the Ralph active-execution registry with one engine per org ───────────
def _ralph_engine_for(org_id, exec_id):
    e = RalphWorkflowEngine(workflow_id="due_diligence", workflow_definition={"id": "due_diligence", "steps": []}, org_id=org_id)
    e.execution_id = exec_id
    e.state = RalphWorkflowState(workflow_id="due_diligence", execution_id=exec_id, org_id=org_id)
    return e


ralph._active_executions.clear()
ralph._active_executions["ralph-org-a"] = _ralph_engine_for(ORG_A, "ralph-org-a")
ralph._active_executions["ralph-org-b"] = _ralph_engine_for(ORG_B, "ralph-org-b")

# The Ralph list route rehydrates from Postgres; stub it to a no-op so the proof
# needs no DB (we are testing the org filter over the in-memory registry).
async def _no_rehydrate():
    return 0
ralph.rehydrate_active_executions = _no_rehydrate


# ── Build a minimal app mounting BOTH routers, with auth + engine overridden ───
app = FastAPI()
app.include_router(hier.router, prefix="/api/v1")     # -> /api/v1/hierarchical/...
app.include_router(ralph.router)                       # -> /api/v1/ralph/... (own prefix)
app.dependency_overrides[require_api_key] = _current_user
app.dependency_overrides[require_operator] = _current_user
app.dependency_overrides[hier.get_engine] = lambda: engine
client = TestClient(app)

HIER_LIST = "/api/v1/hierarchical/executions"
HIER_GET = "/api/v1/hierarchical/executions/{}"
RALPH_LIST = "/api/v1/ralph/executions"
RALPH_GET = "/api/v1/ralph/executions/{}"          # progress (read)
RALPH_GUIDE = "/api/v1/ralph/executions/{}/guidance"


def wf_ids(resp):
    return sorted(e["id"] for e in resp.json()["executions"])


def ralph_ids(resp):
    return sorted(e["execution_id"] for e in resp.json())


def main():
    print("=" * 78)
    print("HIERARCHICAL WORKFLOW ENGINE — /hierarchical/executions")
    print("=" * 78)

    # 1. org-A lists ONLY org-A
    as_user(USER_A)
    r = client.get(HIER_LIST)
    check("org-A list is 200", r.status_code == 200, f"status={r.status_code}")
    check("org-A list contains ONLY its own execution",
          wf_ids(r) == ["wf-org-a"], f"ids={wf_ids(r)}")
    check("org-A list does NOT contain org-B's execution", "wf-org-b" not in wf_ids(r))

    # org-B symmetric
    as_user(USER_B)
    r = client.get(HIER_LIST)
    check("org-B list contains ONLY its own execution",
          wf_ids(r) == ["wf-org-b"], f"ids={wf_ids(r)}")

    # 2. org-A GET of org-B's execution -> 404 (not 403)
    as_user(USER_A)
    r = client.get(HIER_GET.format("wf-org-b"))
    check("org-A GET of org-B execution -> 404 (existence not leaked)", r.status_code == 404,
          f"status={r.status_code}")
    check("org-A GET of org-B execution is NOT 403 (no existence leak)", r.status_code != 403)
    # sanity: org-A CAN read its own
    r = client.get(HIER_GET.format("wf-org-a"))
    check("org-A GET of its OWN execution -> 200", r.status_code == 200, f"status={r.status_code}")

    # 3. unbound key -> empty list + 404 on gets (fail closed)
    as_user(USER_UNBOUND)
    r = client.get(HIER_LIST)
    check("unbound key list is EMPTY (fail closed, not everything)",
          r.json()["executions"] == [] and r.json()["count"] == 0, f"body={r.json()}")
    r = client.get(HIER_GET.format("wf-org-a"))
    check("unbound key GET of any execution -> 404", r.status_code == 404, f"status={r.status_code}")

    # 4. admin -> sees BOTH orgs
    as_user(USER_ADMIN)
    r = client.get(HIER_LIST)
    check("admin list sees BOTH orgs' executions",
          wf_ids(r) == ["wf-org-a", "wf-org-b"], f"ids={wf_ids(r)}")
    check("admin GET of org-A execution -> 200", client.get(HIER_GET.format("wf-org-a")).status_code == 200)
    check("admin GET of org-B execution -> 200", client.get(HIER_GET.format("wf-org-b")).status_code == 200)

    print("\n" + "=" * 78)
    print("RALPH SELF-CORRECTION ENGINE — /ralph/executions")
    print("=" * 78)

    # 1. org-A lists ONLY org-A
    as_user(USER_A)
    r = client.get(RALPH_LIST)
    check("org-A ralph list is 200", r.status_code == 200, f"status={r.status_code}")
    check("org-A ralph list contains ONLY its own execution",
          ralph_ids(r) == ["ralph-org-a"], f"ids={ralph_ids(r)}")

    as_user(USER_B)
    r = client.get(RALPH_LIST)
    check("org-B ralph list contains ONLY its own execution",
          ralph_ids(r) == ["ralph-org-b"], f"ids={ralph_ids(r)}")

    # 2. org-A GET (progress) of org-B's ralph execution -> 404
    as_user(USER_A)
    r = client.get(RALPH_GET.format("ralph-org-b"))
    check("org-A ralph GET of org-B execution -> 404", r.status_code == 404, f"status={r.status_code}")
    check("org-A ralph GET of org-B execution is NOT 403", r.status_code != 403)
    r = client.get(RALPH_GET.format("ralph-org-a"))
    check("org-A ralph GET of its OWN execution -> 200", r.status_code == 200, f"status={r.status_code}")

    # 5. cross-org guidance INJECTION (a mutation) is also blocked with 404
    r = client.post(RALPH_GUIDE.format("ralph-org-b"), json={"guidance": "leak attempt"})
    check("org-A cross-org guidance injection -> 404 (mutation blocked, not leaked)",
          r.status_code == 404, f"status={r.status_code}")

    # 3. unbound key -> empty ralph list + 404 on gets
    as_user(USER_UNBOUND)
    r = client.get(RALPH_LIST)
    check("unbound key ralph list is EMPTY (fail closed)", r.json() == [], f"body={r.json()}")
    r = client.get(RALPH_GET.format("ralph-org-a"))
    check("unbound key ralph GET -> 404", r.status_code == 404, f"status={r.status_code}")

    # 4. admin -> sees BOTH orgs
    as_user(USER_ADMIN)
    r = client.get(RALPH_LIST)
    check("admin ralph list sees BOTH orgs' executions",
          ralph_ids(r) == ["ralph-org-a", "ralph-org-b"], f"ids={ralph_ids(r)}")
    check("admin ralph GET of org-B execution -> 200",
          client.get(RALPH_GET.format("ralph-org-b")).status_code == 200)

    print("\n" + "=" * 78)
    print(f"RESULT: {len(PASSES)} passed, {len(FAILURES)} failed")
    if FAILURES:
        print("FAILURES:")
        for f in FAILURES:
            print(f"   - {f}")
    print("=" * 78)
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
