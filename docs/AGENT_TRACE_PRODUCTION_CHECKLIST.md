# Agent Trace - Production Deployment Checklist

**Feature**: Code Attribution Tracking System
**Version**: 1.0.0
**Status**: Ready for Production Deployment
**Date**: January 31, 2026

---

## Pre-Deployment Verification ✅

All items verified and passing:

- [x] **Database migrations applied** - `code_attributions` table exists with 14 columns, 6 indexes
- [x] **Environment variables configured** - `AGENT_TRACE_ENABLED=true` in `.env`
- [x] **Test suite passes** - 9/9 comprehensive tests passing
- [x] **API endpoints verified** - All 7 endpoints responding correctly
- [x] **Frontend service layer updated** - `traceService.js` aligned with backend API
- [x] **Bug fixes applied** - File path normalization, foreign key constraints
- [x] **Documentation complete** - Deployment, verification, and integration guides
- [x] **Demo script working** - Successfully tracks test attributions

---

## Production Deployment Steps

### Step 1: Database Setup (5 minutes)

#### 1.1 Verify Database Connection
```bash
# Test connection
PGPASSWORD=leads_password_dev psql -h localhost -p 5434 -U leads_user -d unicorn_brigade -c "SELECT version();"
```

**Expected**: PostgreSQL version printed

#### 1.2 Verify Table Exists
```bash
PGPASSWORD=leads_password_dev psql -h localhost -p 5434 -U leads_user -d unicorn_brigade -c "SELECT COUNT(*) FROM code_attributions;"
```

**Expected**: Number of existing attributions (0 or more)

#### 1.3 Run Test Suite (Optional but Recommended)
```bash
cd /Volumes/Studio\ Storage/Development/Unicorn-Brigade
source venv/bin/activate
python scripts/test_agent_trace_full.py
```

**Expected**: `Passed: 9/9 | Failed: 0/9`

---

### Step 2: Backend Configuration (2 minutes)

#### 2.1 Verify Environment Variables
```bash
# Check .env file
grep AGENT_TRACE_ENABLED .env
```

**Expected**: `AGENT_TRACE_ENABLED=true`

#### 2.2 Restart API Server
```bash
# Stop current server
pkill -f "uvicorn app.main:app"

# Start with production settings
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8100 --workers 4 > logs/api.log 2>&1 &
```

#### 2.3 Verify Server Started
```bash
# Wait 5 seconds for startup
sleep 5

# Check health
curl -s http://localhost:8100/api/v1/trace/health | jq .
```

**Expected**:
```json
{
  "status": "healthy",
  "subsystem": "agent_trace",
  "database": "connected",
  "totalAttributions": 0,
  "uniqueAgents": 0,
  "uniqueFiles": 0,
  "timestamp": "2026-01-31T..."
}
```

---

### Step 3: API Endpoint Verification (5 minutes)

Run each endpoint test:

#### 3.1 Health Check
```bash
curl -s http://localhost:8100/api/v1/trace/health
```
**Expected**: `"status": "healthy"`

#### 3.2 Statistics
```bash
curl -s http://localhost:8100/api/v1/trace/stats
```
**Expected**: JSON with `totalAttributions`, `uniqueAgents`, `byOperation`

#### 3.3 Recent Attributions
```bash
curl -s "http://localhost:8100/api/v1/trace/recent?days=7"
```
**Expected**: Array of attributions (may be empty initially)

#### 3.4 Test Attribution Recording (Important!)
```bash
# Run demo to create test attributions
python examples/agent_trace_demo.py
```

**Expected**:
```
✅ Successfully recorded code generation!
✅ Successfully recorded code edit!
```

#### 3.5 Verify Attributions Recorded
```bash
curl -s http://localhost:8100/api/v1/trace/stats | jq .totalAttributions
```
**Expected**: Number > 0 (should show demo attributions)

---

### Step 4: Frontend Deployment (10 minutes)

#### 4.1 Build Frontend
```bash
cd frontend
npm run build
```

**Expected**: `dist/` directory created with built assets

#### 4.2 Test Frontend Locally (Optional)
```bash
# Start dev server
npm run dev

# Visit http://localhost:3000/code-attribution
# Verify data displays correctly
```

#### 4.3 Deploy Static Files
```bash
# Copy built files to web server / CDN
# Example for Nginx:
sudo cp -r dist/* /var/www/brigade/

# Example for CDN (replace with your CDN):
aws s3 sync dist/ s3://your-bucket/brigade/
```

#### 4.4 Verify Frontend Loads
```bash
# Visit your production URL
open https://your-domain.com/code-attribution

# Or test locally:
open http://localhost:3000/code-attribution
```

**Expected**: Page loads, shows navigation, can fetch attributions

---

### Step 5: Integration Testing (5 minutes)

#### 5.1 Record Code via LLM Client
Test that actual agent code generation is tracked:

```bash
# Chat with an agent and ask it to generate code
curl -X POST http://localhost:8100/api/v1/agents/cpt-fullstack/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Write a simple Python function that adds two numbers",
    "stream": false
  }'
```

#### 5.2 Verify Attribution Recorded
```bash
# Check recent attributions
curl -s "http://localhost:8100/api/v1/trace/recent?days=1" | jq .[0]
```

**Expected**: Attribution with `agentName: "Cpt. Fullstack"` and generated code

#### 5.3 Export Report (CSV)
```bash
curl -X POST http://localhost:8100/api/v1/trace/report \
  -H "Content-Type: application/json" \
  -d '{
    "format": "csv",
    "startDate": "2026-01-01",
    "endDate": "2026-12-31"
  }' > code_attributions.csv

# Verify CSV created
head -5 code_attributions.csv
```

**Expected**: CSV file with attribution data

---

### Step 6: Monitoring Setup (10 minutes)

#### 6.1 Add Health Check to Monitoring
```bash
# Add to your monitoring system (example for cron)
*/5 * * * * curl -sf http://localhost:8100/api/v1/trace/health || echo "Agent Trace DOWN" | mail -s "Alert" admin@example.com
```

#### 6.2 Set Up Log Monitoring
```bash
# Watch for Agent Trace errors
tail -f logs/api.log | grep -i "agent_trace"
```

**Look for**:
- `INFO - Successfully recorded code generation`
- `WARNING - Agent Trace is disabled` (should NOT appear)
- `ERROR - Error persisting contribution` (investigate if appears)

#### 6.3 Set Up Metrics (Optional)
If using Prometheus/Grafana:
- Track `totalAttributions` over time
- Track `uniqueAgents` count
- Track API endpoint response times
- Alert on health check failures

---

## Post-Deployment Validation (5 minutes)

Run through this checklist 24 hours after deployment:

### Day 1 Check
- [ ] Health check returns `healthy`
- [ ] At least 1 attribution recorded from actual usage
- [ ] No errors in application logs
- [ ] Frontend displays data correctly
- [ ] CSV export works
- [ ] Database query performance acceptable (<100ms)

### Day 7 Check
- [ ] Attributions accumulating normally
- [ ] No database performance issues
- [ ] Frontend loading quickly
- [ ] Users able to search/filter attributions
- [ ] Reports generating successfully

---

## Rollback Plan

If issues arise, follow this rollback procedure:

### Rollback Step 1: Disable Agent Trace
```bash
# Edit .env
AGENT_TRACE_ENABLED=false

# Restart API server
pkill -f "uvicorn app.main:app"
uvicorn app.main:app --host 0.0.0.0 --port 8100 --workers 4 &
```

**Impact**: Code attribution stops, but system continues working normally

### Rollback Step 2: Remove from Frontend (if needed)
```bash
# Hide Code Attribution from navigation
# Edit frontend/src/components/Navigation.jsx
# Comment out Code Attribution menu item
# Rebuild and redeploy
```

**Impact**: Users can't access Code Attribution page

### Rollback Step 3: Drop Table (LAST RESORT)
```sql
-- Only if database issues occur
DROP TABLE IF EXISTS code_attributions CASCADE;
```

**WARNING**: This deletes ALL attribution data permanently!

---

## Troubleshooting Guide

### Issue: Health check fails with "database not connected"

**Solution**:
```bash
# Check database connection
PGPASSWORD=leads_password_dev psql -h localhost -p 5434 -U leads_user -d unicorn_brigade -c "SELECT 1;"

# If fails, check DATABASE_URL in .env
grep DATABASE_URL .env

# Restart PostgreSQL if needed
docker-compose restart postgres
```

---

### Issue: Attributions not appearing

**Check**:
1. Is `AGENT_TRACE_ENABLED=true`?
   ```bash
   grep AGENT_TRACE_ENABLED .env
   ```

2. Are agents actually generating code?
   ```bash
   # Test with demo
   python examples/agent_trace_demo.py
   ```

3. Check logs for errors:
   ```bash
   tail -100 logs/api.log | grep -i "agent_trace"
   ```

---

### Issue: Frontend not displaying data

**Check**:
1. API endpoints returning data?
   ```bash
   curl -s http://localhost:8100/api/v1/trace/recent?days=7
   ```

2. Browser console errors?
   - Open DevTools (F12)
   - Check Console tab for errors
   - Check Network tab for failed requests

3. CORS issues?
   ```bash
   # Check CORS_ORIGINS in .env includes frontend URL
   grep CORS_ORIGINS .env
   ```

---

### Issue: Slow queries (>100ms)

**Check**:
1. Are indexes created?
   ```sql
   SELECT schemaname, tablename, indexname
   FROM pg_indexes
   WHERE tablename = 'code_attributions';
   ```
   **Expected**: 6 indexes

2. Large dataset?
   ```sql
   SELECT COUNT(*) FROM code_attributions;
   ```
   **If >100k rows**: Consider partitioning or archiving old data

3. Add query timing:
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM code_attributions
   WHERE created_at > NOW() - INTERVAL '7 days'
   ORDER BY created_at DESC
   LIMIT 100;
   ```

---

## Security Checklist

### Authentication
- [ ] `AUTH_BYPASS=false` in production .env
- [ ] API key authentication enabled for trace endpoints
- [ ] Admin role required for sensitive operations

### Data Protection
- [ ] Review prompts for PII before storing
- [ ] Database backups configured
- [ ] Access logs enabled

### API Security
- [ ] Rate limiting configured (if applicable)
- [ ] HTTPS/TLS enabled in production
- [ ] CORS properly configured

---

## Performance Benchmarks

### Expected Performance (Production)

| Metric | Target | Acceptable | Alert |
|--------|--------|------------|-------|
| Health check | <20ms | <50ms | >100ms |
| Statistics endpoint | <50ms | <100ms | >200ms |
| Recent query (7 days) | <50ms | <100ms | >200ms |
| File attributions | <50ms | <100ms | >200ms |
| Agent attributions | <50ms | <100ms | >200ms |
| Session attributions | <50ms | <100ms | >200ms |
| Report generation (CSV) | <500ms | <1000ms | >2000ms |

### Database Size Projections

| Usage Level | Attributions/Day | Storage/Month | Annual Storage |
|-------------|------------------|---------------|----------------|
| Light | 10-50 | ~10 MB | ~120 MB |
| Medium | 50-200 | ~50 MB | ~600 MB |
| Heavy | 200-1000 | ~250 MB | ~3 GB |
| Enterprise | 1000+ | ~1 GB | ~12 GB |

**Note**: Each attribution ~2-10 KB depending on code length

---

## Maintenance Tasks

### Weekly
- [ ] Check disk space (database growth)
- [ ] Review error logs
- [ ] Verify backup ran successfully

### Monthly
- [ ] Review old attributions (>90 days)
- [ ] Consider archiving or cleanup
- [ ] Check index statistics
- [ ] Review performance metrics

### Quarterly
- [ ] Generate compliance reports
- [ ] Review user feedback
- [ ] Plan feature enhancements
- [ ] Update documentation

---

## Success Metrics

### Week 1
- [ ] Zero downtime deployments
- [ ] <5 support tickets
- [ ] Health check 99.9% uptime
- [ ] Users able to view attributions

### Month 1
- [ ] 100+ attributions recorded
- [ ] Users actively using search/filter
- [ ] CSV exports being generated
- [ ] Positive user feedback

### Quarter 1
- [ ] Feature used by majority of agents
- [ ] Compliance reports generated successfully
- [ ] No major bugs reported
- [ ] Feature considered "stable"

---

## Support Contacts

### Technical Issues
- **Documentation**: `docs/AGENT_TRACE_DEPLOYMENT.md`
- **Troubleshooting**: This checklist
- **API Docs**: http://localhost:8100/docs#/trace

### Testing
- **Test Suite**: `python scripts/test_agent_trace_full.py`
- **Demo Script**: `python examples/agent_trace_demo.py`
- **Health Check**: `curl http://localhost:8100/api/v1/trace/health`

---

## Sign-Off

### Pre-Deployment Approval
- [ ] All pre-deployment checks completed
- [ ] Test suite passes (9/9)
- [ ] Documentation reviewed
- [ ] Rollback plan understood

**Approved By**: _________________
**Date**: _________________

### Post-Deployment Validation
- [ ] Day 1 checks completed
- [ ] Day 7 checks completed
- [ ] No critical issues reported
- [ ] Feature marked as "stable"

**Validated By**: _________________
**Date**: _________________

---

**Production Deployment Status**: ✅ **READY**

**Last Updated**: January 31, 2026
**Version**: 1.0.0
**Next Review**: February 7, 2026 (Day 7 check)

---
