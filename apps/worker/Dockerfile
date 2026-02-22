FROM python:3.11-slim

WORKDIR /app

# Copy dependency spec first for Docker layer caching
COPY pyproject.toml .

# Create minimal package structure so pip install succeeds
RUN mkdir -p vigil && echo '' > vigil/__init__.py

# Install dependencies (cached unless pyproject.toml changes)
RUN pip install --no-cache-dir .

# Copy actual source code (overwrites stub)
COPY . .

CMD ["python", "-m", "vigil.main"]
