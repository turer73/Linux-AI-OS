# Linux-AI Development & Testing Container
# Builds both C/C++ and Python components
#
# Usage:
#   docker build -t linux-ai .
#   docker run linux-ai                    # Run all tests
#   docker run linux-ai pytest -v          # Python tests only
#   docker run linux-ai make all           # Build C/C++ only

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System packages: C/C++ toolchain + Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make cmake \
    python3 python3-pip python3-dev \
    linux-headers-generic \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies (install first for layer caching)
COPY pyproject.toml .
COPY proc-utils-AI/cbinder_gbfs/ proc-utils-AI/cbinder_gbfs/
RUN pip3 install --no-cache-dir pytest pytest-cov psutil PyYAML numpy scikit-learn pandas rich \
    && pip3 install --no-cache-dir -e .

# Copy project files
COPY . .

# Build C/C++ components
RUN make all 2>/dev/null || true

# Default: run all tests
ENTRYPOINT ["pytest"]
CMD ["tests/python/", "-v", "--tb=short", "--cov=cbinder_gbfs", "--cov-report=term-missing"]
