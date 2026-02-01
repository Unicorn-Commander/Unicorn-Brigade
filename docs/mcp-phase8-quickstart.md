# MCP Phase 8 Quickstart Guide
## Product Analytics & Customer Data Platforms

**Integration Date**: January 31, 2026
**Status**: Complete
**Servers Added**: 4 (Amplitude, Mixpanel, Segment, PostHog)
**Total Tools Added**: 213
**Total Platform Tools**: 1,207

---

## Overview

Phase 8 adds **product analytics and customer data platform (CDP) capabilities** to the Unicorn Brigade MCP Server Registry. These servers enable comprehensive user behavior tracking, funnel analysis, retention cohorts, A/B testing, and unified data collection across all customer touchpoints.

### Phase 8 Servers

| Server | Tools | Priority | Use Cases |
|--------|-------|----------|-----------|
| **Amplitude** | 44 | HIGH | User behavior tracking, funnel analysis, retention cohorts, A/B testing |
| **Mixpanel** | 54 | HIGH | Advanced analytics, user journey analysis, predictive analytics, JQL queries |
| **Segment** | 55 | MEDIUM-HIGH | Unified data collection, 300+ integrations, data warehouse sync, identity resolution |
| **PostHog** | 60 | MEDIUM | Self-hosted analytics, session replay, feature flags, A/B testing, heatmaps |

---

## Prerequisites

- Unicorn Brigade platform installed and running
- Node.js 18+ (for npx package execution)
- Docker (for self-hosted PostHog, optional)
- Account credentials for desired analytics platforms

---

## Server Configuration

### 1. Amplitude Analytics

**Setup Steps**:

1. **Create Account**: Sign up at [amplitude.com](https://amplitude.com/)
2. **Get API Credentials**:
   - Navigate to **Settings > Projects > YOUR_PROJECT > General**
   - Copy **API Key** and **Secret Key** from "API Keys" section
   - Note your **Project ID** (visible in settings or URL)

3. **Add to `.env`**:
```bash
# Amplitude Analytics
AMPLITUDE_API_KEY=your_amplitude_api_key
AMPLITUDE_SECRET_KEY=your_amplitude_secret_key
AMPLITUDE_PROJECT_ID=123456
```

4. **Start Server**:
```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/amplitude/start \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY"
```

**Pricing**:
- **Starter**: Free (up to 10M events/month)
- **Growth**: $49/month (advanced features, higher limits)
- **Enterprise**: Custom pricing

**Rate Limits**: 30 requests/second per project (Starter), 100/sec (Growth+)

---

### 2. Mixpanel Analytics

**Setup Steps**:

1. **Create Account**: Sign up at [mixpanel.com](https://mixpanel.com/)
2. **Get API Credentials**:
   - Navigate to **Project Settings > Access Keys**
   - Copy **Project Token** (for event tracking)
   - Copy **API Secret** (for query API)
   - Note your **Service Account** username (admin API)

3. **Add to `.env`**:
```bash
# Mixpanel Analytics
MIXPANEL_PROJECT_TOKEN=your_mixpanel_project_token
MIXPANEL_API_SECRET=your_mixpanel_api_secret
MIXPANEL_SERVICE_ACCOUNT=your_mixpanel_service_account_username
```

4. **Start Server**:
```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/mixpanel/start \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY"
```

**Pricing**:
- **Free**: Up to 20M events/month
- **Growth**: $25/month (advanced features, higher limits)
- **Enterprise**: Custom pricing

**Rate Limits**: 2,000 requests/hour (Free), 4,000/hour (Growth), unlimited (Enterprise)

---

### 3. Segment CDP

**Setup Steps**:

1. **Create Account**: Sign up at [segment.com](https://segment.com/)
2. **Get API Credentials**:
   - Navigate to **Workspace > Settings > API Access**
   - Create **Access Token** for Config API
   - Get **Write Key** from source settings (for event tracking)
   - Note your **Workspace Slug** (e.g., "my-company" from URL)

3. **Add to `.env`**:
```bash
# Segment Customer Data Platform
SEGMENT_WRITE_KEY=your_segment_write_key
SEGMENT_ACCESS_TOKEN=your_segment_access_token
SEGMENT_WORKSPACE_SLUG=your-workspace-slug
```

4. **Start Server**:
```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/segment/start \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY"
```

**Pricing**:
- **Free**: 2 sources, 1,000 MTU (Monthly Tracked Users)
- **Team**: $120/month (10,000 MTU, more sources)
- **Business**: Custom pricing

**Rate Limits**: 500 requests/second per source (Free), custom for paid plans

---

### 4. PostHog Analytics

**Setup Steps**:

#### Option A: PostHog Cloud (Easiest)

1. **Create Account**: Sign up at [app.posthog.com](https://app.posthog.com/)
2. **Get API Credentials**:
   - Navigate to **Project > Settings > Project API Key**
   - Copy **API Key**
   - Note **Project ID** (numeric, from settings or URL)

3. **Add to `.env`**:
```bash
# PostHog Open-Source Analytics (Cloud)
POSTHOG_API_KEY=phc_your_posthog_project_api_key
POSTHOG_HOST=https://app.posthog.com
POSTHOG_PROJECT_ID=12345
```

#### Option B: Self-Hosted PostHog (Privacy-First)

1. **Deploy PostHog**:
```bash
# Docker Compose
git clone https://github.com/PostHog/posthog.git
cd posthog
docker compose -f docker-compose.yml up -d

# Or use Helm chart for Kubernetes
helm repo add posthog https://posthog.github.io/charts-clickhouse
helm install posthog posthog/posthog
```

2. **Get API Credentials**:
   - Access PostHog at `http://localhost:8000`
   - Create account and project
   - Navigate to **Project Settings > API Key**
   - Copy **API Key** and **Project ID**

3. **Add to `.env`**:
```bash
# PostHog Open-Source Analytics (Self-Hosted)
POSTHOG_API_KEY=phc_your_posthog_project_api_key
POSTHOG_HOST=http://localhost:8000
POSTHOG_PROJECT_ID=12345
```

4. **Start Server**:
```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/servers/posthog/start \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY"
```

**Pricing**:
- **Cloud Free**: 1M events/month, then $0.000225/event
- **Self-Hosted**: Unlimited (free, requires infrastructure)

**Rate Limits**: 100 requests/second per project (cloud), unlimited (self-hosted)

---

## Verification

### Check Server Status

```bash
# List all running servers
curl http://localhost:8100/api/v1/mcp/registry/servers/running \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY"

# Check specific server
curl http://localhost:8100/api/v1/mcp/registry/servers/amplitude \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY"
```

### Test Tool Execution

#### Amplitude: Track Event
```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY" \
  -d '{
    "server_name": "amplitude",
    "tool_name": "track_event",
    "arguments": {
      "user_id": "test_user_123",
      "event_type": "button_clicked",
      "event_properties": {
        "button_name": "signup_cta",
        "page": "homepage"
      }
    }
  }'
```

#### Mixpanel: Get Segmentation
```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY" \
  -d '{
    "server_name": "mixpanel",
    "tool_name": "get_segmentation",
    "arguments": {
      "event": "page_view",
      "from_date": "2026-01-01",
      "to_date": "2026-01-31"
    }
  }'
```

#### Segment: Track Event
```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY" \
  -d '{
    "server_name": "segment",
    "tool_name": "track_event",
    "arguments": {
      "user_id": "test_user_456",
      "event": "product_viewed",
      "properties": {
        "product_id": "prod_123",
        "product_name": "Premium Plan",
        "price": 99.99
      }
    }
  }'
```

#### PostHog: Create Insight
```bash
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BRIGADE_ADMIN_KEY" \
  -d '{
    "server_name": "posthog",
    "tool_name": "create_insight",
    "arguments": {
      "name": "Daily Active Users",
      "insight_type": "trends",
      "events": [{"id": "$pageview"}],
      "date_from": "-30d"
    }
  }'
```

---

## Example Workflows

### 1. Product Analytics Pipeline

**Objective**: Unified product analytics with Segment, Amplitude, and Mixpanel

```bash
# Step 1: Track events via Segment (unified collection)
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "segment",
    "tool_name": "track_event",
    "arguments": {
      "user_id": "user_789",
      "event": "signup_completed",
      "properties": {"plan": "premium", "trial": false}
    }
  }'

# Step 2: Analyze funnel in Amplitude
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "amplitude",
    "tool_name": "get_funnel_analysis",
    "arguments": {
      "events": ["page_view", "signup_started", "signup_completed"],
      "date_range": "last_30_days"
    }
  }'

# Step 3: Deep-dive user journey in Mixpanel
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "mixpanel",
    "tool_name": "get_user_journey",
    "arguments": {
      "distinct_id": "user_789",
      "from_date": "2026-01-01"
    }
  }'
```

---

### 2. Feature Launch with A/B Testing

**Objective**: Roll out new feature with PostHog feature flags and track adoption

```bash
# Step 1: Create feature flag in PostHog
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "posthog",
    "tool_name": "create_feature_flag",
    "arguments": {
      "key": "new_checkout_flow",
      "name": "New Checkout Flow Experiment",
      "rollout_percentage": 10,
      "filters": {"groups": [{"properties": []}]}
    }
  }'

# Step 2: Create experiment
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "posthog",
    "tool_name": "create_experiment",
    "arguments": {
      "name": "Checkout Flow Optimization",
      "feature_flag_key": "new_checkout_flow",
      "variants": [
        {"key": "control", "rollout_percentage": 50},
        {"key": "variant_a", "rollout_percentage": 50}
      ]
    }
  }'

# Step 3: Track adoption in Amplitude
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "amplitude",
    "tool_name": "get_event_segmentation",
    "arguments": {
      "event": "checkout_completed",
      "group_by": ["experiment_variant"],
      "date_range": "last_7_days"
    }
  }'

# Step 4: Get experiment results from PostHog
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "posthog",
    "tool_name": "get_experiment_results",
    "arguments": {
      "experiment_id": 123
    }
  }'
```

---

### 3. User Churn Prevention

**Objective**: Identify at-risk users and trigger re-engagement

```bash
# Step 1: Create at-risk cohort in Mixpanel (low engagement)
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "mixpanel",
    "tool_name": "create_cohort",
    "arguments": {
      "name": "At-Risk Users (Low Engagement)",
      "criteria": {
        "events": [{"event": "login", "count": "<2", "window": "14d"}]
      }
    }
  }'

# Step 2: Export cohort via Segment
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "segment",
    "tool_name": "create_audience",
    "arguments": {
      "name": "At-Risk Users",
      "description": "Users with low engagement, need re-engagement",
      "computation_class": "audience"
    }
  }'

# Step 3: Track re-engagement campaign effectiveness in Amplitude
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "amplitude",
    "tool_name": "get_retention_analysis",
    "arguments": {
      "cohort_id": "at_risk_users",
      "retention_type": "weekly",
      "date_range": "last_30_days"
    }
  }'
```

---

### 4. Data Pipeline Management

**Objective**: Unified data collection and warehouse syncing with Segment

```bash
# Step 1: Create source in Segment
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "segment",
    "tool_name": "create_source",
    "arguments": {
      "name": "Web Application",
      "slug": "web-app",
      "type": "javascript"
    }
  }'

# Step 2: Configure warehouse destination
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "segment",
    "tool_name": "create_destination",
    "arguments": {
      "source_id": "src_123",
      "destination_name": "Snowflake",
      "enabled": true,
      "settings": {
        "account": "your_account",
        "database": "analytics",
        "warehouse": "COMPUTE_WH"
      }
    }
  }'

# Step 3: Validate tracking plan
curl -X POST http://localhost:8100/api/v1/mcp/registry/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "segment",
    "tool_name": "validate_tracking_plan",
    "arguments": {
      "tracking_plan_id": "tp_456",
      "event": "order_completed",
      "properties": {
        "order_id": "ord_789",
        "total": 149.99,
        "currency": "USD"
      }
    }
  }'
```

---

## Multi-Server Workflow Examples

### Growth Experimentation Workflow

**Servers**: PostHog + Amplitude + Segment + Notion

1. **Hypothesis**: Document in Notion
2. **Setup**: Create A/B test in PostHog
3. **Track**: Events via Segment to all destinations
4. **Monitor**: Real-time metrics in Amplitude
5. **Analyze**: Statistical significance in PostHog
6. **Decide**: Roll out winner, document in Notion

### Product Analytics Stack

**Servers**: Segment + Amplitude + Mixpanel + PostgreSQL

1. **Collect**: Unified events via Segment from all sources
2. **Analyze**: Behavioral analytics in Amplitude
3. **Deep-Dive**: User journeys and JQL queries in Mixpanel
4. **Store**: Raw events in PostgreSQL warehouse
5. **Activate**: Export cohorts back to marketing tools

---

## Best Practices

### Event Tracking
- **Consistent Naming**: Use snake_case for event names (e.g., `signup_completed`)
- **Properties**: Include context (page, source, campaign) in event properties
- **User IDs**: Use consistent user identifiers across platforms
- **Timestamps**: Always include ISO 8601 timestamps

### Performance
- **Batch Events**: Use batch APIs for high-volume tracking (reduces API calls)
- **Async Processing**: Track events asynchronously to avoid blocking user flows
- **Rate Limiting**: Respect API rate limits, implement exponential backoff
- **Caching**: Cache cohort/segment definitions to reduce repeated queries

### Privacy & Compliance
- **PII Handling**: Avoid tracking sensitive PII (SSN, credit cards)
- **Consent**: Respect user consent preferences (GDPR/CCPA)
- **Data Retention**: Configure retention policies per platform
- **Anonymization**: Use anonymous IDs for public/logged-out users

### Cost Optimization
- **Event Filtering**: Only track meaningful events (reduce noise)
- **Sampling**: Sample high-volume events for cost control
- **Self-Hosting**: Consider PostHog self-hosted for unlimited free events
- **Plan Management**: Monitor MTU/event counts, upgrade before overages

---

## Troubleshooting

### Server Won't Start

**Issue**: Server fails to start or immediately exits

**Solutions**:
1. **Check Credentials**: Verify all environment variables are set correctly
2. **Test Connectivity**: Ensure network access to API endpoints
3. **Check Logs**: Review server output for error messages
```bash
# View server logs
docker logs brigade-backend-1 | grep amplitude
```

### API Rate Limiting

**Issue**: "Rate limit exceeded" errors

**Solutions**:
1. **Implement Backoff**: Add exponential backoff retry logic
2. **Batch Requests**: Use batch APIs to reduce request count
3. **Upgrade Plan**: Consider higher-tier plans with increased limits
4. **Cache Results**: Cache frequently accessed data (cohorts, etc.)

### Event Validation Errors

**Issue**: Events rejected due to schema validation

**Solutions**:
1. **Check Schema**: Verify event properties match tracking plan
2. **Type Conversion**: Ensure property types match (string vs number)
3. **Required Fields**: Include all required event properties
4. **Testing**: Use validation endpoints before production

### Missing Data in Analytics

**Issue**: Events tracked but not appearing in dashboards

**Solutions**:
1. **Processing Delay**: Wait 5-15 minutes for event processing
2. **Date Range**: Verify dashboard date range includes event timestamps
3. **Filters**: Check if filters exclude your test events
4. **Source Mapping**: Ensure Segment source is connected to destinations

---

## Cost Comparison

| Platform | Free Tier | Paid Plan | Enterprise |
|----------|-----------|-----------|------------|
| **Amplitude** | 10M events/mo | $49/mo (Growth) | Custom |
| **Mixpanel** | 20M events/mo | $25/mo (Growth) | Custom |
| **Segment** | 1,000 MTU | $120/mo (10K MTU) | Custom |
| **PostHog** | 1M events/mo | $0.000225/event | Self-hosted (free) |

**Recommended Stack by Budget**:
- **$0/month**: PostHog self-hosted + Segment free (1K MTU)
- **$49/month**: Amplitude Growth + PostHog cloud
- **$169/month**: Segment Team + Amplitude Growth + Mixpanel Growth
- **Enterprise**: Full stack with all platforms (custom pricing)

---

## Next Steps

1. **Configure Production Keys**: Replace example credentials with production API keys
2. **Test Workflows**: Run example workflows to verify server functionality
3. **Build Agent Templates**: Create specialized agents using Phase 8 analytics
4. **Monitor Usage**: Track API usage and costs to optimize plan selection
5. **Explore Advanced Features**: Experiment with predictive analytics, JQL queries, reverse ETL

---

## Additional Resources

### Documentation
- **Amplitude**: [amplitude.com/docs](https://amplitude.com/docs)
- **Mixpanel**: [docs.mixpanel.com](https://docs.mixpanel.com)
- **Segment**: [segment.com/docs](https://segment.com/docs)
- **PostHog**: [posthog.com/docs](https://posthog.com/docs)

### Support
- **Phase 8 Status**: `docs/mcp-phase8-status.json`
- **Registry Code**: `app/mcp/registry.py` (lines 841+)
- **Environment Config**: `.env.example` (Phase 8 section)
- **Brigade Docs**: `CLAUDE.md`

### Community
- **Amplitude Community**: [community.amplitude.com](https://community.amplitude.com)
- **Mixpanel Community**: [community.mixpanel.com](https://community.mixpanel.com)
- **Segment Community**: [community.segment.com](https://community.segment.com)
- **PostHog Slack**: [posthog.com/slack](https://posthog.com/slack)

---

**Last Updated**: January 31, 2026
**Phase 8 Integration**: COMPLETE
**Total MCP Servers**: 42 (10 baseline + 4×8 phases)
**Total Platform Tools**: 1,207
