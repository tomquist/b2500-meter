ARG BUILD_FROM
ARG BUILD_VERSION

FROM ghcr.io/tomquist/b2500-meter:$BUILD_VERSION as base

FROM $BUILD_FROM

RUN \
  apk add --no-cache \
    python3 \
    py3-pip

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=base /app /app

# Create a virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install dependencies from Pipfile
RUN pip3 install --no-cache-dir pipenv && \
    pipenv requirements > requirements.txt && \
    pip3 install --no-cache-dir -r requirements.txt && \
    pip3 uninstall -y pipenv && \
    rm requirements.txt

COPY run.sh /
RUN chmod a+x /run.sh
COPY --from=base /app /app

CMD [ "/run.sh" ]