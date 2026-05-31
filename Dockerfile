# Dockerfile for Unicorn Brigade

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip for faster resolver
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements first for better caching
COPY requirements-prod.txt .

# Install Python dependencies (base)
RUN pip install --no-cache-dir -r requirements-prod.txt

# Install Graphiti in a second step so pip does not have to solve the full
# cross-package dependency graph at once (the resolver deadlocks otherwise).
RUN pip install --no-cache-dir 'graphiti-core[falkordb]>=0.28.0' ||     pip install --no-cache-dir --no-deps 'graphiti-core[falkordb]>=0.28.0' &&     pip install --no-cache-dir falkordb neo4j posthog diskcache 'openai>=1.91.0' 

# Patch falkordb/redis incompatibility (falkordb 1.6.0 imports redis.driver_info
# which was removed in redis-py 7.1.x). Makes the import optional via sed.
RUN for f in \
      /usr/local/lib/python3.11/site-packages/falkordb/falkordb.py \
      /usr/local/lib/python3.11/site-packages/falkordb/asyncio/falkordb.py; do \
    [ -f "$f" ] || continue; \
    sed -i 's/^from redis\.driver_info import DriverInfo$/try:\n    from redis.driver_info import DriverInfo\n    _HAS_DRIVER_INFO = True\nexcept ImportError:\n    _HAS_DRIVER_INFO = False/' "$f"; \
    sed -i 's/driver_info=DriverInfo(lib_name, lib_version or get_package_version()),/**({"driver_info": DriverInfo(lib_name, lib_version or get_package_version())} if _HAS_DRIVER_INFO else {}),/' "$f"; \
    echo "Patched $f"; \
    done

# Copy application code
COPY app/ app/
COPY tests/ tests/
COPY scripts/ scripts/
COPY pytest.ini .

# Create logs directory
RUN mkdir -p /app/logs

# Expose API port
EXPOSE 8100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8100/api/v1/health || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
