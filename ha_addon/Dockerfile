ARG BUILD_FROM
ARG BUILD_VERSION

# Build stage
FROM ${BUILD_FROM:-ghcr.io/hassio-addons/base:17.0.1} AS builder

RUN apk add --no-cache \
    python3 \
    py3-pip

WORKDIR /app

# Copy the source code from build context (current checkout state)
COPY . ./
# Save run.sh before removing ha_addon directory and remove ha_addon directory to avoid conflicts
RUN mv ha_addon/run.sh /tmp/run.sh && rm -rf ha_addon

# Create a virtual environment and install dependencies
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip3 install --no-cache-dir pipenv && \
    pipenv requirements > requirements.txt && \
    pip3 install --no-cache-dir -r requirements.txt

# Final stage
FROM ${BUILD_FROM:-ghcr.io/hassio-addons/base:17.0.1}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python
RUN apk add --no-cache python3

WORKDIR /app

# Copy only necessary files from builder
COPY --from=builder /app /app

ENV PATH="/app/venv/bin:$PATH"

COPY --from=builder /tmp/run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]