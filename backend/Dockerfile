FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.5.4

# Copy dependency files first
COPY pyproject.toml uv.lock ./

# Create a dummy app directory so the build system doesn't fail, then install dependencies
RUN mkdir app && touch app/__init__.py && uv pip install --system --no-cache-dir .

# Copy the application
COPY . .

# Install dependencies
RUN uv pip install --system --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]