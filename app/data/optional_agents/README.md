# Optional agents

Agent definitions that are **available but NOT auto-seeded** into the default roster
(unlike `app/data/seed_agents.json`, which loads on an empty DB). They ship with the
product so an operator can install them deliberately if the capability fits their fleet.

## cwo-lightsout — Out-of-Band / BMC Hardware Specialist (HPE iLO / Redfish)

Operates servers' iLO management processors over Redfish — firmware, power, thermal,
hardware health — the break-glass layer that works even when the host OS is down.
Reads run live; the destructive tools (`bmc_flash_firmware`, `bmc_power_control`) preview
by default and stay dormant until an operator arms `ILO_ALLOW_MUTATE=1`.

**Requirements to make it functional**
- Set `ILO_TARGETS` (JSON of your iLO management processors) + the referenced password env(s).
  The `bmc_*` tools register only when `ILO_TARGETS` is set. See `.env.example`.
- (Optional) `KNOWLEDGE_OPS_URL` for runbook grounding via an internal Knowledge-Ops KB.

**Install it** (it is NOT auto-seeded). Either:
- `POST /api/v1/agents` (operator auth) with the body in `cwo-lightsout.template.json`, or
- insert it with your own seeding/admin tooling.

**Access**: the template ships with `accessPolicy: {"tiers": ["admin"]}` (admins only) — a
BMC power/firmware agent should be admin-gated. Adjust to your policy if needed.
