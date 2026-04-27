FROM python:3.12-slim

# Install git (needed for git-clone scan mode)
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Create result and tmp directories
RUN mkdir -p result tmp

ENTRYPOINT ["python3", "main.py"]
