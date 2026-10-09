# SafeBox Multi-Language Hardened Execution Runtime
FROM python:3.10-slim-bullseye

# Install C++ (GCC) & Node.js runtimes
RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged non-root execution user
RUN groupadd -g 10001 safebox && \
    useradd -u 10001 -g safebox -m -s /bin/bash safebox

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and profiles
COPY safebox ./safebox
RUN mkdir -p /app/.safebox_tmp && chown -R safebox:safebox /app

USER safebox

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV SAFEBOX_POOL_SIZE=5

CMD ["uvicorn", "safebox.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
