# Use the official Python image as the base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies including curl for health check
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the Pipfile and Pipfile.lock to the working directory
COPY Pipfile Pipfile.lock /app/

# Install pipenv and use it to install dependencies
RUN pip install pipenv && pipenv install --deploy --ignore-pipfile

# Copy the rest of the application code to the working directory
COPY . /app/

# Remove ha_addon directory to avoid conflicts
RUN rm -rf /app/ha_addon

# Expose the ports your application will be listening on
EXPOSE 12345/tcp
EXPOSE 12345/udp
EXPOSE 52500/tcp

# Add health check that uses the same endpoint as HA addon
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:52500/health || exit 1

# Run the SmartMeter script when the container starts
CMD ["pipenv", "run", "python", "main.py", "--loglevel", "info"]