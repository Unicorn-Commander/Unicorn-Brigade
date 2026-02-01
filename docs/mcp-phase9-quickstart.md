# MCP Phase 9 Quickstart - UX & Product Analytics Platforms

**Status**: ✅ Complete (January 31, 2026)
**Servers**: 4 (Heap, Pendo, FullStory, Hotjar)
**Total Tools**: 163
**Platform Total**: 46 servers, ~1,360 tools

---

## Overview

Phase 9 integrates **UX & Product Analytics platforms** focused on user experience optimization, session analytics, and product adoption tracking. These tools complement Phase 8's behavioral analytics with specialized UX capabilities.

### Key Capabilities

- **Auto-Capture Analytics** - Heap's retroactive event tracking without instrumentation
- **Product Experience** - Pendo's in-app guidance and feature adoption
- **Digital Experience Intelligence** - FullStory's session replay and frustration detection
- **UX Optimization** - Hotjar's heatmaps, surveys, and feedback widgets

---

## Quick Start

### 1. Environment Setup

Add to `.env`:

```bash
# Heap Auto-Capture Analytics
HEAP_APP_ID=12345678
HEAP_API_KEY=your_heap_server_api_key
HEAP_ACCOUNT_ID=your_heap_account_id

# Pendo Product Experience
PENDO_API_KEY=int.your_pendo_integration_key
PENDO_SUBDOMAIN=yourcompany
PENDO_INTEGRATION_KEY=your_pendo_integration_key

# FullStory Digital Experience
FULLSTORY_API_KEY=your_fullstory_api_key
FULLSTORY_ORG_ID=ABCD1

# Hotjar UX Optimization
HOTJAR_API_KEY=your_hotjar_api_key
HOTJAR_SITE_ID=1234567
```

### 2. Start MCP Servers

```bash
# Start individual servers
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/heap/start
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/pendo/start
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/fullstory/start
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/hotjar/start

# Verify running
curl http://localhost:8100/api/v1/mcp/registry/servers/running
```

### 3. Test Tool Invocation

```bash
# Heap - Get session replay
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "heap",
    "tool_name": "get_session_replay",
    "arguments": {
      "session_id": "12345",
      "include_events": true
    }
  }'

# Pendo - Create in-app guide
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "pendo",
    "tool_name": "create_guide",
    "arguments": {
      "name": "Feature Onboarding",
      "type": "tooltip",
      "steps": [{"title": "Welcome", "content": "Let us show you around"}]
    }
  }'

# FullStory - Search frustrated users
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "fullstory",
    "tool_name": "detect_frustrated_users",
    "arguments": {
      "time_range": "last_24_hours",
      "threshold": "high"
    }
  }'

# Hotjar - Get heatmap data
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "hotjar",
    "tool_name": "get_click_heatmap",
    "arguments": {
      "heatmap_id": "67890",
      "page_url": "https://example.com/pricing"
    }
  }'
```

---

## Server Configuration

### 1. Heap Auto-Capture Analytics

**Account Setup**:
1. Create account at [heap.io](https://heap.io/)
2. Navigate to Account Settings > Projects > API Keys
3. Copy App ID (8-digit numeric)
4. Generate Server-side API Key
5. Note your Account ID

**Key Features**:
- ✅ **Retroactive Analytics** - Analyze events from the past without prior setup
- ✅ **Auto-Capture** - Track all user interactions automatically
- ✅ **Session Replay** - Visual playback of user sessions
- ✅ **SQL Interface** - Advanced queries on event data

**Pricing**: Growth plan minimum ($3,600/year)
**Rate Limits**: 600 requests/minute

**Top Tools** (42 total):
- `capture_event` - Track custom events
- `get_autocaptured_events` - Retrieve auto-captured events
- `create_segment` - Define user segments
- `get_session_replay` - Get session playback
- `get_user_journey` - Visualize user paths
- `get_retention_analysis` - Cohort retention data
- `export_data` - Export to data warehouse
- `get_sql_query_results` - Run SQL queries

---

### 2. Pendo Product Experience

**Account Setup**:
1. Create account at [pendo.io](https://www.pendo.io/)
2. Navigate to Settings > Integrations > API Keys
3. Generate Integration Key (starts with "int.")
4. Copy your subdomain (e.g., "yourcompany" from yourcompany.pendo.io)

**Key Features**:
- ✅ **In-App Guides** - Onboarding walkthroughs and tooltips
- ✅ **Feature Tagging** - Track adoption of specific features
- ✅ **NPS Surveys** - Measure user sentiment
- ✅ **Product Analytics** - Feature usage and adoption

**Pricing**: Starter plan minimum ($7,000/year)
**Rate Limits**: 100 requests/minute (Starter), 300/min (Growth)

**Top Tools** (47 total):
- `create_guide` - Build in-app onboarding
- `get_feature_adoption` - Track feature usage
- `create_nps_survey` - Launch NPS campaigns
- `get_feature_usage` - Detailed feature analytics
- `create_poll` - Quick user polls
- `get_visitor_journey` - User path analysis
- `get_sentiment_report` - Aggregate NPS data
- `create_product_area` - Define product areas

---

### 3. FullStory Digital Experience

**Account Setup**:
1. Create account at [fullstory.com](https://www.fullstory.com/)
2. Navigate to Settings > Integrations & API Keys
3. Create API Key with required scopes
4. Copy Organization ID (e.g., "ABCD1")

**Key Features**:
- ✅ **Session Replay** - Pixel-perfect session playback
- ✅ **Frustration Signals** - Rage clicks, error clicks, dead clicks
- ✅ **OmniSearch** - Search across all sessions
- ✅ **Error Tracking** - JavaScript, network, console errors

**Pricing**: Business plan minimum ($199/month for 5K sessions)
**Rate Limits**: 400 requests/minute (Business), 1000/min (Enterprise)

**Top Tools** (41 total):
- `get_session_replay` - Full session playback
- `detect_frustrated_users` - Find struggling users
- `get_rage_clicks` - Rapid repeated clicks
- `search_sessions` - OmniSearch queries
- `get_funnel` - Conversion analysis
- `get_console_errors` - JS error tracking
- `create_segment` - User segments
- `create_watchlist` - Monitor specific users

---

### 4. Hotjar UX Optimization

**Account Setup**:
1. Create account at [hotjar.com](https://www.hotjar.com/)
2. Navigate to Account Settings > API Keys
3. Generate API Key with full permissions
4. Copy Site ID (6-7 digit numeric, from site settings)

**Key Features**:
- ✅ **Heatmaps** - Click, move, and scroll heatmaps
- ✅ **Recordings** - Session recordings with filters
- ✅ **Surveys** - On-site surveys and polls
- ✅ **Feedback** - User feedback widgets

**Pricing**: Plus plan minimum ($39/month)
**Rate Limits**: 600 requests/hour (Plus), 1200/hour (Business)

**Top Tools** (33 total):
- `get_click_heatmap` - Click pattern visualization
- `get_scroll_heatmap` - Scroll depth analysis
- `get_recording` - Session recordings
- `create_survey` - On-site surveys
- `get_feedback` - User feedback
- `analyze_form_abandonment` - Form drop-off analysis
- `create_funnel` - Conversion funnels
- `get_page_views` - Page analytics

---

## Workflow Examples

### 1. UX Improvement Pipeline

**Objective**: Identify and fix UX friction points

```python
# Step 1: Identify friction with Hotjar heatmaps
heatmap_data = mcp_call("hotjar", "get_click_heatmap", {
    "page_url": "https://example.com/checkout",
    "date_range": "last_7_days"
})

# Step 2: Watch sessions of frustrated users with FullStory
frustrated_users = mcp_call("fullstory", "detect_frustrated_users", {
    "page_url": "https://example.com/checkout",
    "time_range": "last_7_days",
    "threshold": "medium"
})

sessions = [mcp_call("fullstory", "get_session_replay", {
    "session_id": user["session_id"]
}) for user in frustrated_users]

# Step 3: Create in-app guidance with Pendo
guide = mcp_call("pendo", "create_guide", {
    "name": "Checkout Assistance",
    "type": "tooltip",
    "target_page": "/checkout",
    "steps": [
        {"title": "Payment Info", "content": "Your payment is secure..."}
    ]
})

# Step 4: Validate improvement with Heap retroactive analytics
improvement = mcp_call("heap", "get_retention_analysis", {
    "event": "checkout_completed",
    "cohort_start": guide["published_at"],
    "time_range": "7_days"
})
```

### 2. Product Analytics Stack

**Objective**: Complete product behavior tracking

```python
# Auto-capture all events with Heap
heap_events = mcp_call("heap", "get_autocaptured_events", {
    "time_range": "last_24_hours"
})

# Unify data in Segment CDP
for event in heap_events:
    mcp_call("segment", "track_event", {
        "user_id": event["user_id"],
        "event_name": event["event_name"],
        "properties": event["properties"]
    })

# Analyze behavior in Amplitude
funnel = mcp_call("amplitude", "get_funnel_analysis", {
    "steps": [
        {"event": "page_view", "page": "/pricing"},
        {"event": "click", "element": "start_trial"},
        {"event": "signup_completed"}
    ],
    "time_range": "last_30_days"
})
```

### 3. Frustrated User Recovery

**Objective**: Convert frustrated users into successful ones

```python
# Detect frustration with FullStory
frustrated = mcp_call("fullstory", "get_frustration_signals", {
    "time_range": "last_hour",
    "signals": ["rage_clicks", "error_clicks", "dead_clicks"]
})

# Trigger NPS survey with Pendo
for user in frustrated:
    mcp_call("pendo", "create_nps_survey", {
        "target_user": user["user_id"],
        "question": "How can we improve your experience?",
        "trigger": "immediate"
    })

# Create support ticket in Zendesk for low NPS
responses = mcp_call("pendo", "get_nps_results", {
    "survey_id": survey["id"],
    "score_filter": "detractors"
})

for response in responses:
    mcp_call("zendesk", "create_ticket", {
        "subject": f"Frustrated User - NPS {response['score']}",
        "description": response["feedback"],
        "priority": "high"
    })
```

### 4. Feature Adoption Tracking

**Objective**: Measure and improve feature adoption

```python
# Tag feature in Pendo
feature = mcp_call("pendo", "create_feature", {
    "name": "AI Assistant",
    "selector": "#ai-assistant-button"
})

# Track adoption over time
adoption = mcp_call("pendo", "get_feature_adoption", {
    "feature_id": feature["id"],
    "time_range": "last_30_days",
    "segment": "new_users"
})

# Retroactive analysis with Heap (even before tagging)
heap_adoption = mcp_call("heap", "get_sql_query_results", {
    "query": """
        SELECT COUNT(DISTINCT user_id) as adopters
        FROM events
        WHERE event_name = 'AI Assistant Clicked'
        AND time >= '2026-01-01'
    """
})

# Funnel analysis in Mixpanel
funnel = mcp_call("mixpanel", "get_funnel", {
    "steps": [
        {"event": "Feature Discovered"},
        {"event": "Feature First Click"},
        {"event": "Feature Regular Use"}
    ],
    "segment": "new_users"
})
```

### 5. Form Optimization

**Objective**: Reduce form abandonment

```python
# Analyze form abandonment with Hotjar
form_data = mcp_call("hotjar", "analyze_form_abandonment", {
    "form_url": "/signup",
    "time_range": "last_14_days"
})

# Watch sessions of users who abandoned
abandoned_sessions = mcp_call("fullstory", "search_sessions", {
    "query": "visited /signup AND NOT visited /signup/success",
    "limit": 50
})

# A/B test improvements with PostHog
experiment = mcp_call("posthog", "create_experiment", {
    "name": "Simplified Signup Form",
    "feature_flag": "new_signup_form",
    "variants": ["control", "test"],
    "goal_event": "signup_completed"
})

# Track results
results = mcp_call("posthog", "get_experiment_results", {
    "experiment_id": experiment["id"],
    "metrics": ["conversion_rate", "time_to_complete"]
})
```

---

## Integration with Existing Phases

### Phase 8 Product Analytics

**Before Phase 9**:
- Amplitude, Mixpanel, Segment, PostHog provided behavioral analytics

**With Phase 9**:
- **Heap**: Adds retroactive analytics and auto-capture
- **Pendo**: Adds in-app guidance and feature adoption
- **FullStory**: Adds session replay and frustration detection
- **Hotjar**: Adds heatmaps and on-site surveys

**Combined Power**:
```python
# Complete product analytics workflow
# 1. Auto-capture with Heap
# 2. Unify in Segment CDP
# 3. Analyze behavior in Amplitude/Mixpanel
# 4. Identify friction with FullStory/Hotjar
# 5. Guide users with Pendo
# 6. A/B test improvements with PostHog
```

### Phase 4 Support Platforms

**Zendesk Integration**:
```python
# Frustrated user → Support ticket workflow
frustrated = fullstory.detect_frustrated_users()
for user in frustrated:
    # Create ticket with session replay link
    zendesk.create_ticket({
        "subject": f"Frustrated User: {user['id']}",
        "description": f"Session replay: {user['session_url']}",
        "priority": "high",
        "tags": ["frustrated_user", "session_replay"]
    })
```

### Phase 7 Automation

**Zapier/Make Integration**:
- Trigger Zap on Pendo NPS detractor response → Create Zendesk ticket
- Trigger Make scenario on FullStory rage click → Send Slack alert
- Trigger Zapier on Hotjar negative feedback → Create Linear issue

---

## Best Practices

### 1. Privacy & Compliance

**PII Masking**:
```python
# FullStory - Exclude sensitive data
fullstory.update_settings({
    "privacy_rules": [
        {"selector": ".credit-card-number", "action": "exclude"},
        {"selector": ".ssn", "action": "exclude"}
    ]
})

# Hotjar - Suppress sensitive fields
hotjar.update_site_settings({
    "suppress_fields": ["password", "credit_card", "ssn"]
})
```

**GDPR Compliance**:
```python
# Delete user data across all platforms
user_email = "user@example.com"

heap.delete_user({"email": user_email})
pendo.delete_visitor({"email": user_email})
fullstory.delete_person({"email": user_email})
hotjar.delete_user_data({"email": user_email})
```

### 2. Performance Optimization

**Rate Limit Management**:
```python
import time

def batch_call(server, tool, args_list, batch_size=10):
    results = []
    for i in range(0, len(args_list), batch_size):
        batch = args_list[i:i+batch_size]
        batch_results = [mcp_call(server, tool, args) for args in batch]
        results.extend(batch_results)
        time.sleep(1)  # Respect rate limits
    return results
```

**Caching**:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_feature_adoption(feature_id, time_range):
    return mcp_call("pendo", "get_feature_adoption", {
        "feature_id": feature_id,
        "time_range": time_range
    })
```

### 3. Multi-Platform Correlation

**User Journey Across Platforms**:
```python
def get_complete_user_journey(user_id):
    # Heap: Auto-captured events
    heap_events = heap.get_user_activity({"user_id": user_id})

    # FullStory: Session replays
    sessions = fullstory.get_user_sessions({"user_id": user_id})

    # Pendo: Feature interactions
    features = pendo.get_visitor_activity({"user_id": user_id})

    # Hotjar: Page views and interactions
    page_views = hotjar.get_visitor_attributes({"user_id": user_id})

    return {
        "events": heap_events,
        "sessions": sessions,
        "features": features,
        "pages": page_views
    }
```

---

## Troubleshooting

### Common Issues

**1. Heap API Key Invalid**
```bash
# Error: "Invalid API key"
# Solution: Ensure you're using the SERVER-side API key, not client-side
# Regenerate key at: Account Settings > Projects > API Keys > Server-side
```

**2. Pendo Integration Key Format**
```bash
# Error: "Authentication failed"
# Solution: Integration key must start with "int."
# Verify at: Settings > Integrations > API Keys
```

**3. FullStory Rate Limit**
```bash
# Error: "Rate limit exceeded"
# Solution: Business plan = 400 req/min, Enterprise = 1000 req/min
# Implement exponential backoff or upgrade plan
```

**4. Hotjar Site ID Not Found**
```bash
# Error: "Site not found"
# Solution: Site ID is 6-7 digits, found in site settings URL
# Navigate to: Settings > Sites > Your Site > Copy numeric ID
```

### Validation

```bash
# Check server health
curl http://localhost:8100/api/v1/mcp/registry/health

# List running servers
curl http://localhost:8100/api/v1/mcp/registry/servers/running

# Test tool invocation
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "heap",
    "tool_name": "get_events",
    "arguments": {"limit": 10}
  }'
```

---

## Migration Notes

### From Previous Phases

**Phase 8 to Phase 9**:
- No breaking changes
- All 42 previous servers remain functional
- Phase 9 adds UX-specific capabilities

**Registry Updates**:
- Total servers: 38 → 46 (+8 from Phases 8-9)
- Total tools: 1,197 → 1,360 (+163)

---

## Next Steps

### Phase 10

**Status**: MCP server integration complete (46 servers)

**Future Expansions**:
- Custom MCP servers for vertical-specific needs
- Enhanced multi-server workflow orchestration
- Cross-platform analytics correlation
- Real-time event streaming integration

---

**Phase 9 Complete**: ✅ January 31, 2026
**Platform Status**: 46 MCP servers, ~1,360 tools, production-ready
**Documentation**: Complete and validated
