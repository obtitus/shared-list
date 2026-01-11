# Use image with uv
FROM ghcr.io/astral-sh/uv:alpine

# Install curl for health checks
RUN apk add --no-cache curl

# Set working directory
WORKDIR /code

# Copy project files first to install dependencies
COPY pyproject.toml uv.lock README.md .python-version ./

# Install Python dependencies in the project directory
RUN uv sync --no-dev

# Copy application code
COPY app/ /code/app/

# Create data directory for SQLite database
RUN mkdir -p /code/data

# Expose port 8000
EXPOSE 8000

# Run the application
CMD ["uv", "run", "app/main.py"]
