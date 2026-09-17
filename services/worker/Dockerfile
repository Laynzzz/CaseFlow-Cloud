FROM python:3.12.14-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
ARG REVISION=unknown
LABEL org.opencontainers.image.title="CaseFlow worker" org.opencontainers.image.revision=${REVISION}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/worker/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && pip check
COPY services/worker/caseflow_worker/ ./caseflow_worker/
COPY services/worker/tools/ ./tools/
COPY contracts/ /contracts/
USER 10001:10001
EXPOSE 8090
HEALTHCHECK --interval=5s --timeout=5s --start-period=20s --retries=12 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3).read()"]
CMD ["python", "-m", "uvicorn", "caseflow_worker.app:app", "--host", "0.0.0.0", "--port", "8090"]
