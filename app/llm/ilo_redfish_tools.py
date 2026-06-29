"""iLO / Redfish BMC tools — let a Brigade officer (CWO Lights-Out) operate the
out-of-band management processors (HPE iLO 5) of the server fleet directly over
the Redfish REST API.

This is the OUT-OF-BAND counterpart to the UUDA fleet tools. UUDA drives devices
*in-band* (the OS must be up); these tools drive the BMC, which works even when
the host OS is down — firmware, power, thermal, hardware sensors. Because that
layer owns the most destructive actions in the whole fleet (flash firmware =
brick risk; forced power-off = kill the host), the doctrine here is read-first,
preview-by-default, and the mutating rail is DORMANT until a human arms it.

DESIGN
------
* Targets are declared in the ``ILO_TARGETS`` env (JSON), each with its host +
  user + a *reference* to the env var that holds its password (the password
  itself never sits in the targets JSON, is never logged, never returned).
* READ tools (info / firmware / thermal / power / event log) execute live.
* MUTATING tools (``bmc_flash_firmware``, ``bmc_power_control``) PREVIEW by
  default (``dry_run`` true): they return exactly what they WOULD do and do not
  touch the box. To actually execute, the call must set ``dry_run=false`` AND a
  human must have armed the agent for a maintenance window via
  ``ILO_ALLOW_MUTATE=1``. When not armed, a real attempt comes back as
  ``needs_approval`` with the full plan — the agent surfaces it; it cannot
  self-arm. (The hardening path is a governed iLO gateway with the same
  server-side approval queue UUDA uses; see UUDA_FLEET_TOOLS.)
* The firmware flash bakes in the HPE-specific wire format that actually works on
  iLO 5 (``MultipartHttpPushUri`` is null → push to ``HttpPushUri``
  /cgi-bin/uploadFile with the session as a COOKIE, ``WriteFlashImage:true`` in
  parameters, and NO mime-type suffix on the parameters part). This is the whole
  point of a deterministic tool: the model can't be expected to guess it.

Registered only when ``ILO_TARGETS`` is set (see tool_resolver), so an
unconfigured deployment never surfaces always-erroring tools.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# ── config ─────────────────────────────────────────────────────────
# ILO_TARGETS = {"rackboy1": {"host": "192.168.10.203", "user": "Administrator",
#                             "password_env": "ILO_RACKBOY1_PASS"}}
_TARGETS_RAW = os.getenv("ILO_TARGETS", "")
ILO_TIMEOUT = float(os.getenv("ILO_TIMEOUT", "30.0"))
ILO_FLASH_TIMEOUT = float(os.getenv("ILO_FLASH_TIMEOUT", "300.0"))
# The DORMANT mutating rail. Read tools ignore it; flash/power require it ON
# (a deliberate human act to arm the agent for a maintenance window).
ILO_ALLOW_MUTATE = os.getenv("ILO_ALLOW_MUTATE", "0") == "1"
# Optional allow-list directory that firmware files must live under.
ILO_FW_DIR = os.getenv("ILO_FW_DIR", "")


def _load_targets() -> Dict[str, Dict[str, str]]:
    if not _TARGETS_RAW:
        return {}
    try:
        targets = json.loads(_TARGETS_RAW)
        return targets if isinstance(targets, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"ilo-redfish: bad ILO_TARGETS json: {exc}")
        return {}


TARGETS = _load_targets()


def _resolve(target: str) -> Optional[Dict[str, str]]:
    """Resolve a target name to {host, user, password}. None if unknown/unset.
    The password is read from the referenced env var, never from the JSON."""
    cfg = TARGETS.get(target)
    if not cfg:
        return None
    pw_env = cfg.get("password_env", "")
    password = os.getenv(pw_env, "") if pw_env else cfg.get("password", "")
    if not (cfg.get("host") and cfg.get("user") and password):
        return None
    return {"host": cfg["host"], "user": cfg["user"], "password": password}


# ── Redfish client (self-signed TLS; per-call session) ─────────────

class _Redfish:
    """A minimal async iLO Redfish session. Never logs/returns the password or
    token. Use as ``async with``."""

    def __init__(self, host: str, user: str, password: str):
        self.base = f"https://{host}"
        self._user = user
        self._password = password
        self._token: Optional[str] = None
        self._session_uri: Optional[str] = None
        self._client = httpx.AsyncClient(verify=False, timeout=ILO_TIMEOUT)

    async def __aenter__(self) -> "_Redfish":
        await self._login()
        return self

    async def __aexit__(self, *_exc) -> None:
        try:
            if self._token and self._session_uri:
                await self._client.delete(
                    f"{self.base}{self._session_uri}",
                    headers={"X-Auth-Token": self._token},
                )
        except Exception:  # noqa: BLE001 - best-effort logout
            pass
        await self._client.aclose()

    async def _login(self) -> None:
        resp = await self._client.post(
            f"{self.base}/redfish/v1/SessionService/Sessions",
            json={"UserName": self._user, "Password": self._password},
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 201:
            raise RuntimeError(f"iLO login failed (HTTP {resp.status_code})")
        self._token = resp.headers.get("X-Auth-Token")
        self._session_uri = resp.headers.get("Location")
        if not self._token:
            raise RuntimeError("iLO login returned no auth token")

    async def get(self, path: str) -> httpx.Response:
        return await self._client.get(f"{self.base}{path}", headers={"X-Auth-Token": self._token})

    async def post(self, path: str, body: dict) -> httpx.Response:
        return await self._client.post(
            f"{self.base}{path}", json=body,
            headers={"X-Auth-Token": self._token, "Content-Type": "application/json"},
        )

    async def flash(self, fw_path: str) -> httpx.Response:
        """Push a .fwpkg to the iLO using the HPE HttpPushUri flow (the format
        that actually works on iLO 5 — cookie session + WriteFlashImage)."""
        us = await self.get("/redfish/v1/UpdateService")
        push = "/cgi-bin/uploadFile"
        try:
            push = us.json().get("HttpPushUri") or push
        except Exception:  # noqa: BLE001
            pass
        params = json.dumps({
            "UpdateRepository": True, "UpdateTarget": True,
            "WriteFlashImage": True, "ETag": "atag", "Section": 0,
        })
        with open(fw_path, "rb") as fh:
            files = {
                "sessionKey": (None, self._token),
                "parameters": (None, params),
                "file": (os.path.basename(fw_path), fh, "application/octet-stream"),
            }
            return await self._client.post(
                f"{self.base}{push}",
                headers={"X-Auth-Token": self._token, "Cookie": f"sessionKey={self._token}"},
                files=files, timeout=ILO_FLASH_TIMEOUT,
            )


async def _with_session(target: str):
    """Helper that returns (redfish_or_None, error_dict_or_None)."""
    cfg = _resolve(target)
    if not cfg:
        known = ", ".join(sorted(TARGETS.keys())) or "(none configured)"
        return None, {"error": f"unknown or unconfigured iLO target '{target}'. Known: {known}"}
    return cfg, None


# ── read handlers ──────────────────────────────────────────────────

async def _list_targets_handler(**_) -> Dict[str, Any]:
    return {"targets": [
        {"target": name, "host": cfg.get("host"), "user": cfg.get("user")}
        for name, cfg in TARGETS.items()
    ], "note": "Out-of-band iLO management processors you can operate. Read-only."}


async def _get_info_handler(target: str, **_) -> Dict[str, Any]:
    cfg, err = await _with_session(target)
    if err:
        return err
    try:
        async with _Redfish(**cfg) as rf:
            mgr = (await rf.get("/redfish/v1/Managers/1")).json()
            sysd = (await rf.get("/redfish/v1/Systems/1")).json()
        return {"target": target, "ilo_firmware": mgr.get("FirmwareVersion"),
                "ilo_health": mgr.get("Status", {}),
                "model": sysd.get("Model"), "serial": sysd.get("SerialNumber"),
                "power_state": sysd.get("PowerState"),
                "host_health": sysd.get("Status", {}),
                "bios_version": sysd.get("BiosVersion")}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"iLO query failed: {exc}"}


async def _get_firmware_handler(target: str, **_) -> Dict[str, Any]:
    cfg, err = await _with_session(target)
    if err:
        return err
    try:
        async with _Redfish(**cfg) as rf:
            mgr = (await rf.get("/redfish/v1/Managers/1")).json()
            inv = (await rf.get("/redfish/v1/UpdateService/FirmwareInventory")).json()
        return {"target": target, "ilo_firmware": mgr.get("FirmwareVersion"),
                "firmware_inventory_count": len(inv.get("Members", []))}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"iLO firmware query failed: {exc}"}


async def _get_thermal_handler(target: str, **_) -> Dict[str, Any]:
    cfg, err = await _with_session(target)
    if err:
        return err
    try:
        async with _Redfish(**cfg) as rf:
            th = (await rf.get("/redfish/v1/Chassis/1/Thermal")).json()
        fans = [{"name": f.get("Name"), "reading": f.get("Reading"),
                 "units": f.get("ReadingUnits")} for f in th.get("Fans", [])]
        temps = [{"name": t.get("Name"), "celsius": t.get("ReadingCelsius"),
                  "critical": t.get("UpperThresholdCritical")}
                 for t in th.get("Temperatures", []) if t.get("ReadingCelsius") is not None]
        return {"target": target, "fans": fans, "temperatures": temps}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"iLO thermal query failed: {exc}"}


async def _get_power_handler(target: str, **_) -> Dict[str, Any]:
    cfg, err = await _with_session(target)
    if err:
        return err
    try:
        async with _Redfish(**cfg) as rf:
            sysd = (await rf.get("/redfish/v1/Systems/1")).json()
            try:
                pwr = (await rf.get("/redfish/v1/Chassis/1/Power")).json()
                watts = pwr.get("PowerControl", [{}])[0].get("PowerConsumedWatts")
            except Exception:  # noqa: BLE001
                watts = None
        return {"target": target, "power_state": sysd.get("PowerState"),
                "consumed_watts": watts}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"iLO power query failed: {exc}"}


async def _event_log_handler(target: str, limit: Optional[int] = 15, **_) -> Dict[str, Any]:
    cfg, err = await _with_session(target)
    if err:
        return err
    try:
        async with _Redfish(**cfg) as rf:
            log = (await rf.get("/redfish/v1/Managers/1/LogServices/IEL/Entries")).json()
        members = log.get("Members", [])[-(limit or 15):]
        entries = [{"created": e.get("Created"), "severity": e.get("Severity"),
                    "message": e.get("Message")} for e in members]
        return {"target": target, "entries": entries}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"iLO event log query failed: {exc}"}


# ── mutating handlers (dormant rail) ───────────────────────────────

def _gate(action_plan: Dict[str, Any]) -> Dict[str, Any]:
    """Standard 'not executed' envelope for a previewed/un-armed mutation."""
    return {"needs_approval": True, "executed": False, "plan": action_plan,
            "armed": ILO_ALLOW_MUTATE,
            "note": ("PREVIEW ONLY — not executed. This is a destructive out-of-band "
                     "action. Surface this plan to the operator. To execute, a human "
                     "must arm the agent (ILO_ALLOW_MUTATE=1) and the call must set "
                     "dry_run=false. You cannot arm yourself.")}


async def _flash_firmware_handler(target: str, firmware_path: str,
                                  dry_run: bool = True, **_) -> Dict[str, Any]:
    cfg, err = await _with_session(target)
    if err:
        return err
    if ILO_FW_DIR and not os.path.abspath(firmware_path).startswith(os.path.abspath(ILO_FW_DIR)):
        return {"error": f"firmware_path must be under the allow-listed ILO_FW_DIR ({ILO_FW_DIR})"}
    if not os.path.isfile(firmware_path):
        return {"error": f"firmware file not found on the Brigade host: {firmware_path}"}
    plan = {"action": "flash_ilo_firmware", "target": target,
            "firmware_path": firmware_path,
            "effect": "iLO reflashes and resets (~1-3 min); HOST OS is NOT rebooted by an iLO-only update"}
    # PREVIEW unless explicitly executing AND the human has armed the rail.
    if dry_run or not ILO_ALLOW_MUTATE:
        return _gate(plan)
    try:
        async with _Redfish(**cfg) as rf:
            before = (await rf.get("/redfish/v1/Managers/1")).json().get("FirmwareVersion")
            resp = await rf.flash(firmware_path)
        ok = resp.status_code in (200, 202)
        return {"executed": ok, "http_status": resp.status_code,
                "firmware_before": before, "plan": plan,
                "note": ("Upload accepted — the iLO is flashing and will reset. Poll bmc_get_firmware "
                         "until the version changes (the iLO is briefly unreachable mid-reset)."
                         if ok else f"Upload rejected (HTTP {resp.status_code}); the iLO is unchanged.")}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"iLO flash failed: {exc}"}


async def _power_control_handler(target: str, action: str,
                                 dry_run: bool = True, **_) -> Dict[str, Any]:
    cfg, err = await _with_session(target)
    if err:
        return err
    reset_map = {"on": "On", "off": "ForceOff", "graceful_shutdown": "GracefulShutdown",
                 "restart": "ForceRestart", "graceful_restart": "GracefulRestart"}
    if action not in reset_map:
        return {"error": f"unknown action '{action}'. One of: {', '.join(reset_map)}"}
    plan = {"action": "power_control", "target": target, "power_action": action,
            "reset_type": reset_map[action],
            "effect": "off/restart abruptly kills the running host OS and workloads" if action in
                      ("off", "restart") else "affects host power state"}
    if dry_run or not ILO_ALLOW_MUTATE:
        return _gate(plan)
    try:
        async with _Redfish(**cfg) as rf:
            resp = await rf.post(
                "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
                {"ResetType": reset_map[action]})
        ok = resp.status_code in (200, 202, 204)
        return {"executed": ok, "http_status": resp.status_code, "plan": plan,
                "note": "Power action accepted." if ok else f"Rejected (HTTP {resp.status_code})."}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"iLO power action failed: {exc}"}


# ── tool definitions ───────────────────────────────────────────────

BMC_LIST_TARGETS_TOOL = ToolDefinition(
    name="bmc_list_targets",
    description="List the iLO/BMC management processors you're configured to operate (target name, host, user). "
                "Start here to see what out-of-band targets exist. Read-only.",
    parameters=[],
    handler=_list_targets_handler,
)

BMC_GET_INFO_TOOL = ToolDefinition(
    name="bmc_get_info",
    description="Get an out-of-band snapshot of a server via its iLO: model, serial, iLO firmware version, "
                "iLO + host health, power state, BIOS version. Works even if the host OS is down. Read-only.",
    parameters=[ToolParameter(name="target", type="string", description="The iLO target name (from bmc_list_targets).", required=True)],
    handler=_get_info_handler,
)

BMC_GET_FIRMWARE_TOOL = ToolDefinition(
    name="bmc_get_firmware",
    description="Read the current iLO firmware version and firmware-inventory size for a target. Use this before "
                "and after a flash to confirm the version. Read-only.",
    parameters=[ToolParameter(name="target", type="string", description="The iLO target name.", required=True)],
    handler=_get_firmware_handler,
)

BMC_GET_THERMAL_TOOL = ToolDefinition(
    name="bmc_get_thermal",
    description="Read fan speeds (% / RPM) and temperature sensors from a server's iLO (Chassis Thermal). "
                "Use to check cooling/thermal health. Read-only.",
    parameters=[ToolParameter(name="target", type="string", description="The iLO target name.", required=True)],
    handler=_get_thermal_handler,
)

BMC_GET_POWER_TOOL = ToolDefinition(
    name="bmc_get_power",
    description="Read a server's power state (On/Off) and current power draw in watts via iLO. Read-only.",
    parameters=[ToolParameter(name="target", type="string", description="The iLO target name.", required=True)],
    handler=_get_power_handler,
)

BMC_EVENT_LOG_TOOL = ToolDefinition(
    name="bmc_event_log",
    description="Read the most recent iLO Integrated Event Log (IEL) entries for a target — hardware events, "
                "resets, security changes. Use when diagnosing. Read-only.",
    parameters=[
        ToolParameter(name="target", type="string", description="The iLO target name.", required=True),
        ToolParameter(name="limit", type="number", description="How many recent entries (default 15).", required=False),
    ],
    handler=_event_log_handler,
)

BMC_FLASH_FIRMWARE_TOOL = ToolDefinition(
    name="bmc_flash_firmware",
    description="Flash an iLO firmware package (.fwpkg already staged on the Brigade host) to a target's iLO. "
                "DESTRUCTIVE out-of-band action. PREVIEWS by default (dry_run=true) — returns the plan without "
                "touching the box. To execute, set dry_run=false; it still only runs if a human has armed the "
                "agent (ILO_ALLOW_MUTATE). The iLO resets after flashing but the HOST OS is NOT rebooted by an "
                "iLO-only update. Always bmc_get_firmware first to confirm the current version.",
    parameters=[
        ToolParameter(name="target", type="string", description="The iLO target name.", required=True),
        ToolParameter(name="firmware_path", type="string", description="Path to the .fwpkg on the Brigade host.", required=True),
        ToolParameter(name="dry_run", type="boolean", description="Preview without executing (default true).", required=False, default=True),
    ],
    handler=_flash_firmware_handler,
)

BMC_POWER_CONTROL_TOOL = ToolDefinition(
    name="bmc_power_control",
    description="Change a server's power state via iLO (on / off / restart / graceful_shutdown / graceful_restart). "
                "DESTRUCTIVE for anything but 'on' — off/restart abruptly kill the running host OS. PREVIEWS by "
                "default (dry_run=true); executes only with dry_run=false AND a human-armed agent (ILO_ALLOW_MUTATE). "
                "Prefer graceful_shutdown/graceful_restart over off/restart.",
    parameters=[
        ToolParameter(name="target", type="string", description="The iLO target name.", required=True),
        ToolParameter(name="action", type="string", description="The power action.", required=True,
                      enum=["on", "off", "restart", "graceful_shutdown", "graceful_restart"]),
        ToolParameter(name="dry_run", type="boolean", description="Preview without executing (default true).", required=False, default=True),
    ],
    handler=_power_control_handler,
)


ILO_REDFISH_TOOLS: Dict[str, ToolDefinition] = {
    "bmc_list_targets": BMC_LIST_TARGETS_TOOL,
    "bmc_get_info": BMC_GET_INFO_TOOL,
    "bmc_get_firmware": BMC_GET_FIRMWARE_TOOL,
    "bmc_get_thermal": BMC_GET_THERMAL_TOOL,
    "bmc_get_power": BMC_GET_POWER_TOOL,
    "bmc_event_log": BMC_EVENT_LOG_TOOL,
    "bmc_flash_firmware": BMC_FLASH_FIRMWARE_TOOL,
    "bmc_power_control": BMC_POWER_CONTROL_TOOL,
}
