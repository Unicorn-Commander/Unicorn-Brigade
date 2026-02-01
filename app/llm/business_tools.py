"""
Business Tools for Agent Execution

Practical tools for common business operations:
- CSV/Spreadsheet operations
- RSS feed reading
- Translation
- Calendar/scheduling helpers
- Weather information
"""

import asyncio
import csv
import io
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

from app.llm.ops_center_client import ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)


# ============== CSV/Spreadsheet Tool ==============

async def csv_handler(
    operation: str,
    data: Optional[str] = None,
    rows: Optional[List[Dict[str, Any]]] = None,
    columns: Optional[List[str]] = None,
    filter_column: Optional[str] = None,
    filter_value: Optional[str] = None,
    sort_column: Optional[str] = None,
    sort_descending: bool = False,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    CSV/Spreadsheet operations for data manipulation.

    Operations:
    - parse: Parse CSV string into rows
    - generate: Generate CSV from rows
    - filter: Filter rows by column value
    - sort: Sort rows by column
    - stats: Get column statistics
    - transform: Apply transformations
    """
    logger.info(f"CSV operation: {operation}")

    try:
        if operation == "parse":
            if not data:
                return {"success": False, "error": "CSV data required for parse"}

            reader = csv.DictReader(io.StringIO(data))
            parsed_rows = list(reader)[:limit]

            return {
                "success": True,
                "rows": parsed_rows,
                "columns": reader.fieldnames,
                "count": len(parsed_rows),
            }

        elif operation == "generate":
            if not rows:
                return {"success": False, "error": "Rows required for generate"}

            if not columns and rows:
                columns = list(rows[0].keys())

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

            return {
                "success": True,
                "csv": output.getvalue(),
                "row_count": len(rows),
                "columns": columns,
            }

        elif operation == "filter":
            if not rows or not filter_column:
                return {"success": False, "error": "Rows and filter_column required"}

            filtered = [
                row for row in rows
                if str(row.get(filter_column, "")).lower() == str(filter_value or "").lower()
            ]

            return {
                "success": True,
                "rows": filtered[:limit],
                "count": len(filtered),
                "filter": {"column": filter_column, "value": filter_value},
            }

        elif operation == "sort":
            if not rows or not sort_column:
                return {"success": False, "error": "Rows and sort_column required"}

            sorted_rows = sorted(
                rows,
                key=lambda x: x.get(sort_column, ""),
                reverse=sort_descending
            )

            return {
                "success": True,
                "rows": sorted_rows[:limit],
                "count": len(sorted_rows),
                "sorted_by": sort_column,
                "descending": sort_descending,
            }

        elif operation == "stats":
            if not rows or not columns:
                return {"success": False, "error": "Rows and columns required"}

            stats = {}
            for col in columns:
                values = [row.get(col) for row in rows if row.get(col) is not None]

                # Try numeric stats
                try:
                    numeric = [float(v) for v in values if v]
                    if numeric:
                        stats[col] = {
                            "type": "numeric",
                            "count": len(numeric),
                            "sum": sum(numeric),
                            "avg": sum(numeric) / len(numeric),
                            "min": min(numeric),
                            "max": max(numeric),
                        }
                        continue
                except (ValueError, TypeError):
                    pass

                # String stats
                stats[col] = {
                    "type": "string",
                    "count": len(values),
                    "unique": len(set(str(v) for v in values)),
                    "sample": list(set(str(v) for v in values))[:5],
                }

            return {
                "success": True,
                "stats": stats,
                "total_rows": len(rows),
            }

        elif operation == "aggregate":
            if not rows or not columns:
                return {"success": False, "error": "Rows and columns required"}

            # Group by first column, aggregate rest
            group_col = columns[0]
            agg_cols = columns[1:] if len(columns) > 1 else []

            groups = {}
            for row in rows:
                key = str(row.get(group_col, ""))
                if key not in groups:
                    groups[key] = []
                groups[key].append(row)

            result = []
            for key, group_rows in groups.items():
                agg_row = {group_col: key, "count": len(group_rows)}
                for col in agg_cols:
                    try:
                        values = [float(r.get(col, 0)) for r in group_rows]
                        agg_row[f"{col}_sum"] = sum(values)
                        agg_row[f"{col}_avg"] = sum(values) / len(values) if values else 0
                    except (ValueError, TypeError):
                        pass
                result.append(agg_row)

            return {
                "success": True,
                "aggregated": result,
                "groups": len(result),
            }

        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}

    except Exception as e:
        logger.error(f"CSV handler error: {e}")
        return {"success": False, "error": str(e)}


CSV_TOOL = ToolDefinition(
    name="csv",
    description="CSV/Spreadsheet operations: parse CSV to rows, generate CSV from data, filter, sort, statistics, aggregate.",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: parse, generate, filter, sort, stats, aggregate",
            required=True,
            enum=["parse", "generate", "filter", "sort", "stats", "aggregate"],
        ),
        ToolParameter(name="data", type="string", description="CSV string for parse operation", required=False),
        ToolParameter(name="rows", type="array", description="Array of row objects (dicts with column:value pairs)", required=False, items={"type": "object"}),
        ToolParameter(name="columns", type="array", description="Column names (for generate/stats/aggregate)", required=False, items={"type": "string"}),
        ToolParameter(name="filter_column", type="string", description="Column to filter on", required=False),
        ToolParameter(name="filter_value", type="string", description="Value to filter for", required=False),
        ToolParameter(name="sort_column", type="string", description="Column to sort by", required=False),
        ToolParameter(name="sort_descending", type="boolean", description="Sort descending (default false)", required=False, default=False),
        ToolParameter(name="limit", type="number", description="Max rows to return (default 100)", required=False, default=100),
    ],
    handler=csv_handler,
)


# ============== RSS Feed Tool ==============

async def rss_handler(
    url: str,
    limit: int = 10,
    include_content: bool = False,
) -> Dict[str, Any]:
    """
    Read and parse RSS/Atom feeds.

    Returns feed items with title, link, published date, and optionally content.
    """
    logger.info(f"RSS fetch: {url}")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, follow_redirects=True)

            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}

            content = response.text

            # Simple RSS/Atom parsing (no external dependencies)
            items = []

            # Try RSS 2.0 format
            item_pattern = r'<item>(.*?)</item>'
            item_matches = re.findall(item_pattern, content, re.DOTALL)

            if not item_matches:
                # Try Atom format
                item_pattern = r'<entry>(.*?)</entry>'
                item_matches = re.findall(item_pattern, content, re.DOTALL)

            for item_xml in item_matches[:limit]:
                item = {}

                # Extract title
                title_match = re.search(r'<title[^>]*>(.*?)</title>', item_xml, re.DOTALL)
                if title_match:
                    item["title"] = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title_match.group(1)).strip()

                # Extract link
                link_match = re.search(r'<link[^>]*>([^<]*)</link>', item_xml) or \
                            re.search(r'<link[^>]*href=["\']([^"\']+)["\']', item_xml)
                if link_match:
                    item["link"] = link_match.group(1).strip()

                # Extract date
                date_match = re.search(r'<pubDate[^>]*>(.*?)</pubDate>', item_xml) or \
                            re.search(r'<published[^>]*>(.*?)</published>', item_xml) or \
                            re.search(r'<updated[^>]*>(.*?)</updated>', item_xml)
                if date_match:
                    item["published"] = date_match.group(1).strip()

                # Extract description/content if requested
                if include_content:
                    desc_match = re.search(r'<description[^>]*>(.*?)</description>', item_xml, re.DOTALL) or \
                                re.search(r'<content[^>]*>(.*?)</content>', item_xml, re.DOTALL) or \
                                re.search(r'<summary[^>]*>(.*?)</summary>', item_xml, re.DOTALL)
                    if desc_match:
                        content_text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', desc_match.group(1))
                        # Strip HTML tags
                        content_text = re.sub(r'<[^>]+>', '', content_text).strip()
                        item["content"] = content_text[:500]  # Limit content length

                # Extract author
                author_match = re.search(r'<author[^>]*>(.*?)</author>', item_xml, re.DOTALL) or \
                              re.search(r'<dc:creator[^>]*>(.*?)</dc:creator>', item_xml, re.DOTALL)
                if author_match:
                    author_text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', author_match.group(1))
                    author_text = re.sub(r'<[^>]+>', '', author_text).strip()
                    item["author"] = author_text

                if item.get("title") or item.get("link"):
                    items.append(item)

            # Extract feed title
            feed_title_match = re.search(r'<title[^>]*>(.*?)</title>', content)
            feed_title = feed_title_match.group(1).strip() if feed_title_match else url
            feed_title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', feed_title)

            return {
                "success": True,
                "feed_title": feed_title,
                "feed_url": url,
                "items": items,
                "count": len(items),
            }

    except Exception as e:
        logger.error(f"RSS handler error: {e}")
        return {"success": False, "error": str(e)}


RSS_TOOL = ToolDefinition(
    name="rss",
    description="Read RSS/Atom feeds. Returns feed items with title, link, date, and optionally content. Useful for news monitoring and content aggregation.",
    parameters=[
        ToolParameter(name="url", type="string", description="RSS/Atom feed URL", required=True),
        ToolParameter(name="limit", type="number", description="Max items to return (default 10)", required=False, default=10),
        ToolParameter(name="include_content", type="boolean", description="Include item content/description", required=False, default=False),
    ],
    handler=rss_handler,
)


# ============== Translation Tool ==============

# Free translation API (LibreTranslate or fallback to simple word replacement)
LIBRETRANSLATE_URL = os.getenv("LIBRETRANSLATE_URL", "https://libretranslate.com")


async def translate_handler(
    text: str,
    source: str = "auto",
    target: str = "en",
) -> Dict[str, Any]:
    """
    Translate text between languages using LibreTranslate or similar.

    Common language codes: en, es, fr, de, it, pt, ru, zh, ja, ko, ar
    """
    logger.info(f"Translation: {source} -> {target}, {len(text)} chars")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Try LibreTranslate API
            try:
                response = await client.post(
                    f"{LIBRETRANSLATE_URL}/translate",
                    json={
                        "q": text,
                        "source": source,
                        "target": target,
                        "format": "text",
                    },
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "translated": result.get("translatedText", ""),
                        "source_language": source,
                        "target_language": target,
                        "provider": "libretranslate",
                    }
            except Exception as e:
                logger.warning(f"LibreTranslate failed: {e}")

            # Fallback: Use MyMemory API (free, no auth needed)
            try:
                langpair = f"{source if source != 'auto' else 'en'}|{target}"
                response = await client.get(
                    "https://api.mymemory.translated.net/get",
                    params={"q": text[:500], "langpair": langpair},  # 500 char limit
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("responseStatus") == 200:
                        return {
                            "success": True,
                            "translated": result["responseData"]["translatedText"],
                            "source_language": source,
                            "target_language": target,
                            "provider": "mymemory",
                        }
            except Exception as e:
                logger.warning(f"MyMemory failed: {e}")

            return {
                "success": False,
                "error": "Translation services unavailable. Try again later.",
            }

    except Exception as e:
        logger.error(f"Translation handler error: {e}")
        return {"success": False, "error": str(e)}


TRANSLATE_TOOL = ToolDefinition(
    name="translate",
    description="Translate text between languages. Supports auto-detection. Common codes: en, es, fr, de, it, pt, ru, zh, ja, ko, ar.",
    parameters=[
        ToolParameter(name="text", type="string", description="Text to translate", required=True),
        ToolParameter(name="source", type="string", description="Source language code (default 'auto')", required=False, default="auto"),
        ToolParameter(name="target", type="string", description="Target language code (default 'en')", required=False, default="en"),
    ],
    handler=translate_handler,
)


# ============== Weather Tool ==============

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")


async def weather_handler(
    location: str,
    units: str = "metric",
    forecast_days: int = 0,
) -> Dict[str, Any]:
    """
    Get current weather and forecast for a location.

    Uses OpenWeatherMap API if configured, falls back to Open-Meteo (free, no key).
    """
    logger.info(f"Weather: {location}, units={units}")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Try to geocode the location first using Open-Meteo geocoding
            geo_response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1, "language": "en"},
            )

            if geo_response.status_code != 200:
                return {"success": False, "error": f"Geocoding failed: {geo_response.status_code}"}

            geo_data = geo_response.json()
            if not geo_data.get("results"):
                return {"success": False, "error": f"Location not found: {location}"}

            place = geo_data["results"][0]
            lat, lon = place["latitude"], place["longitude"]
            location_name = f"{place['name']}, {place.get('admin1', '')}, {place.get('country', '')}".strip(", ")

            # Get weather from Open-Meteo (free, no API key)
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "timezone": "auto",
            }

            if units == "imperial":
                params["temperature_unit"] = "fahrenheit"
                params["wind_speed_unit"] = "mph"

            if forecast_days > 0:
                params["daily"] = "temperature_2m_max,temperature_2m_min,weather_code,precipitation_sum"
                params["forecast_days"] = min(forecast_days, 7)

            weather_response = await client.get(
                "https://api.open-meteo.com/v1/forecast",
                params=params,
            )

            if weather_response.status_code != 200:
                return {"success": False, "error": f"Weather API failed: {weather_response.status_code}"}

            weather = weather_response.json()
            current = weather.get("current", {})

            # Map weather codes to descriptions
            weather_codes = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Fog", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
                77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
                82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
                95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
            }

            result = {
                "success": True,
                "location": location_name,
                "coordinates": {"lat": lat, "lon": lon},
                "current": {
                    "temperature": current.get("temperature_2m"),
                    "humidity": current.get("relative_humidity_2m"),
                    "wind_speed": current.get("wind_speed_10m"),
                    "conditions": weather_codes.get(current.get("weather_code", 0), "Unknown"),
                    "units": "celsius" if units == "metric" else "fahrenheit",
                },
            }

            if forecast_days > 0 and "daily" in weather:
                daily = weather["daily"]
                forecast = []
                for i in range(len(daily.get("time", []))):
                    forecast.append({
                        "date": daily["time"][i],
                        "high": daily["temperature_2m_max"][i],
                        "low": daily["temperature_2m_min"][i],
                        "conditions": weather_codes.get(daily["weather_code"][i], "Unknown"),
                        "precipitation_mm": daily["precipitation_sum"][i],
                    })
                result["forecast"] = forecast

            return result

    except Exception as e:
        logger.error(f"Weather handler error: {e}")
        return {"success": False, "error": str(e)}


WEATHER_TOOL = ToolDefinition(
    name="weather",
    description="Get current weather and forecast for any location. Returns temperature, humidity, wind, and conditions.",
    parameters=[
        ToolParameter(name="location", type="string", description="City name or location (e.g., 'New York', 'London, UK')", required=True),
        ToolParameter(name="units", type="string", description="Units: 'metric' (Celsius) or 'imperial' (Fahrenheit)", required=False, default="metric", enum=["metric", "imperial"]),
        ToolParameter(name="forecast_days", type="number", description="Days of forecast (0-7, default 0 for current only)", required=False, default=0),
    ],
    handler=weather_handler,
)


# ============== Calendar/Scheduling Helper Tool ==============

async def schedule_handler(
    operation: str,
    date: Optional[str] = None,
    end_date: Optional[str] = None,  # For working_days operation
    timezone: str = "UTC",
    duration_minutes: int = 60,
    participants: Optional[List[str]] = None,
    working_hours_start: int = 9,
    working_hours_end: int = 17,
) -> Dict[str, Any]:
    """
    Calendar and scheduling helper operations.

    Operations:
    - parse_date: Parse natural language date
    - add_time: Add time to a date
    - working_days: Calculate working days between dates
    - time_slots: Generate available time slots
    - timezone_convert: Convert between timezones
    """
    logger.info(f"Schedule operation: {operation}")

    try:
        now = datetime.utcnow()

        if operation == "parse_date":
            if not date:
                return {"success": False, "error": "Date string required"}

            # Parse common date expressions
            date_lower = date.lower().strip()

            if date_lower in ["today", "now"]:
                parsed = now
            elif date_lower == "tomorrow":
                parsed = now + timedelta(days=1)
            elif date_lower == "yesterday":
                parsed = now - timedelta(days=1)
            elif date_lower.startswith("next "):
                weekday_map = {
                    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                    "friday": 4, "saturday": 5, "sunday": 6
                }
                day_name = date_lower[5:].strip()
                if day_name in weekday_map:
                    target = weekday_map[day_name]
                    days_ahead = target - now.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    parsed = now + timedelta(days=days_ahead)
                else:
                    return {"success": False, "error": f"Unknown day: {day_name}"}
            else:
                # Try standard date formats
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y"]:
                    try:
                        parsed = datetime.strptime(date, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return {"success": False, "error": f"Could not parse date: {date}"}

            return {
                "success": True,
                "date": parsed.strftime("%Y-%m-%d"),
                "day_of_week": parsed.strftime("%A"),
                "iso": parsed.isoformat(),
                "timestamp": int(parsed.timestamp()),
            }

        elif operation == "add_time":
            if not date:
                base = now
            else:
                try:
                    base = datetime.fromisoformat(date)
                except ValueError:
                    base = datetime.strptime(date, "%Y-%m-%d")

            new_date = base + timedelta(minutes=duration_minutes)

            return {
                "success": True,
                "original": base.isoformat(),
                "new_date": new_date.isoformat(),
                "added_minutes": duration_minutes,
            }

        elif operation == "working_days":
            # Parse start date (defaults to now)
            if date:
                try:
                    start = datetime.fromisoformat(date)
                except ValueError:
                    start = datetime.strptime(date, "%Y-%m-%d")
            else:
                start = now

            # Parse end date (required)
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date)
                except ValueError:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            else:
                return {"success": False, "error": "end_date required for working_days operation"}

            # Calculate working days
            working = 0
            current = start

            while current <= end_dt:
                if current.weekday() < 5:  # Monday = 0, Friday = 4
                    working += 1
                current += timedelta(days=1)

            return {
                "success": True,
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": end_dt.strftime("%Y-%m-%d"),
                "working_days": working,
                "calendar_days": (end_dt - start).days + 1,
            }

        elif operation == "time_slots":
            if not date:
                target_date = now.date()
            else:
                try:
                    target_date = datetime.fromisoformat(date).date()
                except ValueError:
                    target_date = datetime.strptime(date, "%Y-%m-%d").date()

            slots = []
            current_time = datetime.combine(target_date, datetime.min.time().replace(hour=working_hours_start))
            end_time = datetime.combine(target_date, datetime.min.time().replace(hour=working_hours_end))

            while current_time + timedelta(minutes=duration_minutes) <= end_time:
                slots.append({
                    "start": current_time.strftime("%H:%M"),
                    "end": (current_time + timedelta(minutes=duration_minutes)).strftime("%H:%M"),
                    "iso_start": current_time.isoformat(),
                })
                current_time += timedelta(minutes=30)  # 30-min increments

            return {
                "success": True,
                "date": target_date.strftime("%Y-%m-%d"),
                "slots": slots,
                "count": len(slots),
                "duration_minutes": duration_minutes,
            }

        elif operation == "timezone_convert":
            # Simple UTC offset conversion (without pytz dependency)
            if not date:
                return {"success": False, "error": "Date required for timezone conversion"}

            # Common timezone offsets
            tz_offsets = {
                "UTC": 0, "GMT": 0,
                "EST": -5, "EDT": -4,
                "CST": -6, "CDT": -5,
                "MST": -7, "MDT": -6,
                "PST": -8, "PDT": -7,
                "CET": 1, "CEST": 2,
                "JST": 9, "KST": 9,
                "IST": 5.5, "AEST": 10,
            }

            offset = tz_offsets.get(timezone.upper(), 0)

            try:
                dt = datetime.fromisoformat(date)
            except ValueError:
                dt = datetime.strptime(date, "%Y-%m-%d %H:%M")

            converted = dt + timedelta(hours=offset)

            return {
                "success": True,
                "original": date,
                "converted": converted.isoformat(),
                "timezone": timezone,
                "offset_hours": offset,
            }

        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}

    except Exception as e:
        logger.error(f"Schedule handler error: {e}")
        return {"success": False, "error": str(e)}


SCHEDULE_TOOL = ToolDefinition(
    name="schedule",
    description="Calendar and scheduling helper: parse dates, add time, calculate working days, generate time slots, timezone conversion.",
    parameters=[
        ToolParameter(
            name="operation",
            type="string",
            description="Operation: parse_date, add_time, working_days, time_slots, timezone_convert",
            required=True,
            enum=["parse_date", "add_time", "working_days", "time_slots", "timezone_convert"],
        ),
        ToolParameter(name="date", type="string", description="Start date (ISO format YYYY-MM-DD or natural language like 'tomorrow', 'next Monday')", required=False),
        ToolParameter(name="end_date", type="string", description="End date for working_days operation (ISO format YYYY-MM-DD)", required=False),
        ToolParameter(name="timezone", type="string", description="Timezone (EST, PST, UTC, etc.)", required=False, default="UTC"),
        ToolParameter(name="duration_minutes", type="number", description="Duration in minutes (for add_time/time_slots)", required=False, default=60),
        ToolParameter(name="working_hours_start", type="number", description="Working day start hour (default 9)", required=False, default=9),
        ToolParameter(name="working_hours_end", type="number", description="Working day end hour (default 17)", required=False, default=17),
    ],
    handler=schedule_handler,
)


# ============== Company/Business Info Tool ==============

async def company_handler(
    query: str,
    operation: str = "search",
) -> Dict[str, Any]:
    """
    Look up company information using free APIs.

    Operations:
    - search: Search for company by name
    - domain: Get company info from domain
    """
    logger.info(f"Company lookup: {operation} - {query}")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            if operation == "domain":
                # Use Clearbit Logo API (free, no auth)
                # and try to extract info from domain
                domain = query.replace("http://", "").replace("https://", "").split("/")[0]

                return {
                    "success": True,
                    "domain": domain,
                    "logo_url": f"https://logo.clearbit.com/{domain}",
                    "note": "For detailed company info, use web_search with the company name",
                }

            elif operation == "search":
                # Note: For production, integrate with APIs like:
                # - Clearbit Company API
                # - People Data Labs
                # - Apollo.io
                # - ZoomInfo

                return {
                    "success": True,
                    "query": query,
                    "suggestion": f"For company research, try: web_search with query '{query} company information'",
                    "note": "Detailed company lookup requires API integration (Clearbit, Apollo, etc.)",
                }

            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}

    except Exception as e:
        logger.error(f"Company handler error: {e}")
        return {"success": False, "error": str(e)}


COMPANY_TOOL = ToolDefinition(
    name="company",
    description="Look up company information. Operations: search (by name), domain (get logo/basic info from domain).",
    parameters=[
        ToolParameter(name="query", type="string", description="Company name or domain to look up", required=True),
        ToolParameter(name="operation", type="string", description="Operation: search, domain", required=False, default="search", enum=["search", "domain"]),
    ],
    handler=company_handler,
)


# ============== Export all business tools ==============

BUSINESS_TOOLS = [
    CSV_TOOL,
    RSS_TOOL,
    TRANSLATE_TOOL,
    WEATHER_TOOL,
    SCHEDULE_TOOL,
    COMPANY_TOOL,
]
