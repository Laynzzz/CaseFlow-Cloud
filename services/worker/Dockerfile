FROM python:3.12.14-slim-trixie@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
# Security updates published after the immutable upstream image; refresh these
# exact Debian versions with the image scan, rather than ignoring fixed CVEs.
RUN apt-get update && apt-get install -y --no-install-recommends --only-upgrade \
    gzip=1.13-1+deb13u1 perl-base=5.40.1-6+deb13u1 \
    libsqlite3-0=3.46.1-7+deb13u2 libpcre2-8-0=10.46-1~deb13u2 \
    && rm -rf /var/lib/apt/lists/*
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
