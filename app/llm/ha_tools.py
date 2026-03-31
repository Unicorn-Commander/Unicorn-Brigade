"""
Home Assistant Tools for Agent Execution

Provides tools for controlling Home Assistant devices via REST API.
Used by Carter Knox and other home automation agents.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import httpx

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

# Home Assistant configuration from environment
HA_URL = os.getenv("HOMEASSISTANT_URL", "http://192.168.10.138:8123")
HA_TOKEN = os.getenv("HOMEASSISTANT_TOKEN", "")


def _get_ha_client() -> httpx.AsyncClient:
    """Create an HTTP client for Home Assistant API calls."""
    return httpx.AsyncClient(
        base_url=HA_URL,
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


# ============== ha_list_entities ==============

async def ha_list_entities_handler(
    domain: Optional[str] = None,
    area: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """List Home Assistant entities with optional filtering."""
    logger.info(f"HA list_entities: domain={domain}, area={area}")
    try:
        async with _get_ha_client() as client:
            response = await client.get("/api/states")
            response.raise_for_status()
            entities = response.json()

            if domain:
                entities = [e for e in entities if e["entity_id"].startswith(f"{domain}.")]

            if area:
                area_lower = area.lower().replace("_", " ")
                entities = [
                    e for e in entities
                    if area_lower in e.get("attributes", {}).get("friendly_name", "").lower()
                ]

            entities = entities[:limit]

            return {
                "success": True,
                "count": len(entities),
                "entities": [
                    {
                        "entity_id": e["entity_id"],
                        "state": e["state"],
                        "friendly_name": e.get("attributes", {}).get("friendly_name", ""),
                    }
                    for e in entities
                ],
            }
    except Exception as e:
        logger.error(f"HA list_entities error: {e}")
        return {"success": False, "error": str(e)}


HA_LIST_ENTITIES_TOOL = ToolDefinition(
    name="ha_list_entities",
    description="List Home Assistant entities, optionally filtered by domain (light, switch, sensor, climate, lock, etc.) or area/room name.",
    parameters=[
        ToolParameter(
            name="domain",
            type="string",
            description="Filter by entity domain (e.g., 'light', 'switch', 'climate', 'lock', 'sensor')",
            required=False,
        ),
        ToolParameter(
            name="area",
            type="string",
            description="Filter by area/room name (e.g., 'living room', 'kitchen', 'bedroom')",
            required=False,
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Maximum number of entities to return (default: 100)",
            required=False,
            default=100,
        ),
    ],
    handler=ha_list_entities_handler,
)


# ============== ha_get_entity_state ==============

async def ha_get_entity_state_handler(entity_id: str) -> Dict[str, Any]:
    """Get current state and attributes of a specific entity."""
    logger.info(f"HA get_entity_state: {entity_id}")
    try:
        async with _get_ha_client() as client:
            response = await client.get(f"/api/states/{entity_id}")

            if response.status_code == 404:
                return {"success": False, "error": f"Entity not found: {entity_id}"}

            response.raise_for_status()
            entity = response.json()

            return {
                "success": True,
                "entity_id": entity["entity_id"],
                "state": entity["state"],
                "attributes": entity["attributes"],
                "last_changed": entity["last_changed"],
                "last_updated": entity["last_updated"],
            }
    except Exception as e:
        logger.error(f"HA get_entity_state error: {e}")
        return {"success": False, "error": str(e)}


HA_GET_ENTITY_STATE_TOOL = ToolDefinition(
    name="ha_get_entity_state",
    description="Get the current state and attributes of a specific Home Assistant entity.",
    parameters=[
        ToolParameter(
            name="entity_id",
            type="string",
            description="The entity ID (e.g., 'light.living_room', 'climate.bedroom', 'switch.kitchen')",
            required=True,
        ),
    ],
    handler=ha_get_entity_state_handler,
)


# ============== ha_call_service ==============

async def ha_call_service_handler(
    domain: str,
    service: str,
    entity_id: Optional[str] = None,
    data: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Call a Home Assistant service to control devices."""
    logger.info(f"HA call_service: {domain}.{service} entity={entity_id}")
    try:
        payload = data.copy() if data else {}
        if entity_id:
            payload["entity_id"] = entity_id

        async with _get_ha_client() as client:
            response = await client.post(
                f"/api/services/{domain}/{service}",
                json=payload,
            )

            return {
                "success": response.status_code == 200,
                "service": f"{domain}.{service}",
                "entity_id": entity_id,
                "status_code": response.status_code,
            }
    except Exception as e:
        logger.error(f"HA call_service error: {e}")
        return {"success": False, "error": str(e)}


HA_CALL_SERVICE_TOOL = ToolDefinition(
    name="ha_call_service",
    description="Call a Home Assistant service to control devices. Use this to turn on/off lights, set temperature, lock/unlock doors, activate scenes, etc.",
    parameters=[
        ToolParameter(
            name="domain",
            type="string",
            description="Service domain (e.g., 'light', 'switch', 'climate', 'lock', 'scene', 'media_player')",
            required=True,
        ),
        ToolParameter(
            name="service",
            type="string",
            description="Service name (e.g., 'turn_on', 'turn_off', 'toggle', 'set_temperature', 'lock', 'unlock')",
            required=True,
        ),
        ToolParameter(
            name="entity_id",
            type="string",
            description="Target entity ID (e.g., 'light.living_room'). Can be comma-separated for multiple.",
            required=False,
        ),
        ToolParameter(
            name="data",
            type="object",
            description="Additional service data (e.g., {\"brightness_pct\": 50}, {\"temperature\": 72}, {\"rgb_color\": [255, 0, 0]})",
            required=False,
        ),
    ],
    handler=ha_call_service_handler,
)


# ============== ha_search_entities ==============

async def ha_search_entities_handler(
    query: str,
    domain: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """Search for entities by name or characteristics."""
    logger.info(f"HA search_entities: query={query}, domain={domain}")
    try:
        async with _get_ha_client() as client:
            response = await client.get("/api/states")
            response.raise_for_status()
            entities = response.json()

            query_lower = query.lower()
            matches = [
                e for e in entities
                if query_lower in e["entity_id"].lower()
                or query_lower in e.get("attributes", {}).get("friendly_name", "").lower()
            ]

            if domain:
                matches = [m for m in matches if m["entity_id"].startswith(f"{domain}.")]

            matches = matches[:limit]

            return {
                "success": True,
                "query": query,
                "count": len(matches),
                "entities": [
                    {
                        "entity_id": e["entity_id"],
                        "state": e["state"],
                        "friendly_name": e.get("attributes", {}).get("friendly_name", ""),
                    }
                    for e in matches
                ],
            }
    except Exception as e:
        logger.error(f"HA search_entities error: {e}")
        return {"success": False, "error": str(e)}


HA_SEARCH_ENTITIES_TOOL = ToolDefinition(
    name="ha_search_entities",
    description="Search for Home Assistant entities by name or description. Use this when the user gives a vague description like 'living room lights' or 'bedroom thermostat'.",
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="Search query (matches entity ID and friendly name)",
            required=True,
        ),
        ToolParameter(
            name="domain",
            type="string",
            description="Optional domain filter (e.g., 'light', 'switch', 'climate')",
            required=False,
        ),
        ToolParameter(
            name="limit",
            type="number",
            description="Maximum results (default: 20)",
            required=False,
            default=20,
        ),
    ],
    handler=ha_search_entities_handler,
)


# ============== ha_get_history ==============

async def ha_get_history_handler(
    entity_ids: List[str],
    hours: float = 24,
) -> Dict[str, Any]:
    """Get historical state data for entities."""
    logger.info(f"HA get_history: entities={entity_ids}, hours={hours}")
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        filter_ids = ",".join(entity_ids)

        async with _get_ha_client() as client:
            response = await client.get(
                f"/api/history/period/{start_time.isoformat()}",
                params={
                    "filter_entity_id": filter_ids,
                    "end_time": end_time.isoformat(),
                },
            )
            response.raise_for_status()
            history = response.json()

            return {
                "success": True,
                "entity_ids": entity_ids,
                "hours": hours,
                "history": history,
            }
    except Exception as e:
        logger.error(f"HA get_history error: {e}")
        return {"success": False, "error": str(e)}


HA_GET_HISTORY_TOOL = ToolDefinition(
    name="ha_get_history",
    description="Get historical state data for Home Assistant entities over a time period. Useful for checking trends or past activity.",
    parameters=[
        ToolParameter(
            name="entity_ids",
            type="array",
            description="List of entity IDs to get history for",
            required=True,
            items={"type": "string"},
        ),
        ToolParameter(
            name="hours",
            type="number",
            description="Number of hours of history to retrieve (default: 24)",
            required=False,
            default=24,
        ),
    ],
    handler=ha_get_history_handler,
)


# ============== ha_list_areas ==============

async def ha_list_areas_handler() -> Dict[str, Any]:
    """List all configured areas/rooms."""
    logger.info("HA list_areas")
    try:
        async with _get_ha_client() as client:
            # HA uses a WebSocket-style API for area registry,
            # but we can use the REST template endpoint
            response = await client.post(
                "/api/template",
                json={"template": "{{ areas() | list }}"},
            )

            if response.status_code == 200:
                areas_text = response.text
                return {
                    "success": True,
                    "areas": areas_text,
                }

            # Fallback: try the states API and extract unique areas from friendly names
            response = await client.get("/api/states")
            response.raise_for_status()
            entities = response.json()

            # Extract unique area hints from friendly names
            areas = set()
            for e in entities:
                fname = e.get("attributes", {}).get("friendly_name", "")
                # Common patterns: "Living Room Light", "Kitchen Switch"
                parts = fname.rsplit(" ", 1)
                if len(parts) > 1:
                    areas.add(parts[0])

            return {
                "success": True,
                "count": len(areas),
                "areas": sorted(areas)[:50],
            }
    except Exception as e:
        logger.error(f"HA list_areas error: {e}")
        return {"success": False, "error": str(e)}


HA_LIST_AREAS_TOOL = ToolDefinition(
    name="ha_list_areas",
    description="List all areas/rooms configured in Home Assistant.",
    parameters=[],
    handler=ha_list_areas_handler,
)


# ============== ha_get_services ==============

async def ha_get_services_handler(
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Get available services for a domain."""
    logger.info(f"HA get_services: domain={domain}")
    try:
        async with _get_ha_client() as client:
            response = await client.get("/api/services")
            response.raise_for_status()
            services = response.json()

            if domain:
                # services is a list of {domain, services} dicts
                filtered = [s for s in services if s.get("domain") == domain]
                return {
                    "success": True,
                    "domain": domain,
                    "services": filtered,
                }

            # Return just domain names and service counts to avoid huge response
            summary = [
                {
                    "domain": s.get("domain", ""),
                    "service_count": len(s.get("services", {})),
                }
                for s in services
            ]

            return {
                "success": True,
                "count": len(summary),
                "domains": summary,
            }
    except Exception as e:
        logger.error(f"HA get_services error: {e}")
        return {"success": False, "error": str(e)}


HA_GET_SERVICES_TOOL = ToolDefinition(
    name="ha_get_services",
    description="Get available services for a Home Assistant domain. Useful for discovering what actions can be performed on devices.",
    parameters=[
        ToolParameter(
            name="domain",
            type="string",
            description="Domain to get services for (e.g., 'light', 'climate', 'media_player'). Omit to get all domains.",
            required=False,
        ),
    ],
    handler=ha_get_services_handler,
)
