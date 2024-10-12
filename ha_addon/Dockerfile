ARG BUILD_FROM
ARG BUILD_VERSION

# Build stage
FROM $BUILD_FROM AS builder

RUN apk add --no-cache \
    git \
    python3 \
    py3-pip

WORKDIR /app

# Clone the repository and remove .git directory
RUN git clone https://github.com/tomquist/b2500-meter.git . && \
    rm -rf .git && \
    rm -rf ha_addon

# Create a virtual environment and install dependencies
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip3 install --no-cache-dir pipenv && \
    pipenv requirements > requirements.txt && \
    pip3 install --no-cache-dir -r requirements.txt

# Final stage
FROM $BUILD_FROM

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python
RUN apk add --no-cache python3

WORKDIR /app

# Copy only necessary files from builder
COPY --from=builder /app /app

ENV PATH="/app/venv/bin:$PATH"

COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]