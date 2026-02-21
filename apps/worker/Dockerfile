FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for SC captcha OCR and PDF extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency spec first for Docker layer caching
COPY pyproject.toml .

# Create minimal package structure so pip install succeeds
RUN mkdir -p vigil && echo '' > vigil/__init__.py

# Install dependencies (cached unless pyproject.toml changes)
RUN pip install --no-cache-dir .

# Copy actual source code (overwrites stub)
COPY . .

CMD ["python", "-m", "vigil.main"]
