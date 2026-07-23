FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Set working directory
WORKDIR /app

# Install system dependencies (if any needed for C-extensions, though mysql-connector is usually fine)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Gunicorn for production server
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY . .

# Ensure upload and session directories exist
RUN mkdir -p static/uploads/hotels static/uploads/rooms flask_session

# Expose port
EXPOSE 5000

# Command to run the application using Gunicorn
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:5000", "app:app"]
