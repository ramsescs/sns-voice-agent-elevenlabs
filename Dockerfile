# Safety tool server for the ElevenLabs triage agent, deployed on Google Cloud Run.
# Build context needs only pyproject.toml and src/ (see .gcloudignore).
FROM python:3.14-slim

WORKDIR /app

# Install the package (deps + triage/ incl. the rules/*.yaml package data).
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

# Cloud Run injects PORT (default 8080); uvicorn must bind 0.0.0.0:$PORT.
ENV PORT=8080
CMD exec uvicorn triage.toolserver:app --host 0.0.0.0 --port ${PORT}
