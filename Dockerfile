# Use the official Python image as the base image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Copy the Pipfile and Pipfile.lock to the working directory
COPY Pipfile Pipfile.lock /app/

# Install pipenv and use it to install dependencies
RUN pip install pipenv && pipenv install --deploy --ignore-pipfile

# Copy the rest of the application code to the working directory
COPY . /app/

# Expose the ports your application will be listening on
EXPOSE 12345/tcp
EXPOSE 12345/udp

# Run the SmartMeter script when the container starts
CMD ["pipenv", "run", "python", "main.py", "--loglevel", "info"]