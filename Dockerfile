# Yak Similarity Analyzer Docker Image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY tools/ ./tools/
COPY run.py .
COPY setup.py .

# Create necessary directories
RUN mkdir -p uploads results data license_data dual_keys

# Create a demo/stub YOLO model file to prevent errors
RUN mkdir -p /app/data && \
    echo "# Demo model placeholder - replace with actual YOLO model" > /app/data/model_placeholder.txt

# Set environment variables
ENV PYTHONPATH=/app/src
ENV FLASK_ENV=production
ENV FLASK_DEBUG=False

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Default command
CMD ["python", "run.py"]