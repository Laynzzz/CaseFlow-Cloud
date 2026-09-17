"""Test-only disposable Docker dependencies, ownership checks and raw evidence."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import threading
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BROKER = "127.0.0.1:19092"


def utc():
    return datetime.now(timezone.utc).isoformat()


def guard_resource(project, name, labels, kind):
    valid = re.fullmatch(r"caseflow-r3-restart-[a-f0-9]{32}", project)
    valid = valid and labels.get("com.docker.compose.project") == project
    if kind == "container":
        service = labels.get("com.docker.compose.service")
        valid = valid and service in {"postgres", "kafka"} and name == f"{project}-{service}-1"
    elif kind == "volume":
        valid = valid and name in {project + "_postgres-data", project + "_kafka-data"}
    elif kind == "network":
        valid = valid and name == project + "_default"
    else:
        valid = False
    if not valid:
        raise ValueError("requires an owned restart resource")


def until(check, timeout=35, message="condition not reached"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError(message)


class Dependencies:
    def __init__(self):
        self.project = "caseflow-r3-restart-" + uuid4().hex
        run = os.environ.get("CASEFLOW_RESTART_RUN_ID", "run-" + uuid4().hex)
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", run):
            raise ValueError("invalid restart evidence run ID")
        self.output = ROOT / "output/r3-dependency-restart" / run
        self.output.mkdir(parents=True, exist_ok=False)
        self.events = []
        self.event_lock = threading.Lock()
        self.compose = ["docker", "compose", "--project-name", self.project,
                        "--file", str(ROOT / "tests/resilience/compose.restart.yaml")]
        self.manifest = dict(started_at=utc(), project=self.project, python=sys.version,
                             platform=platform.platform(), command=sys.argv,
                             postgres_endpoint="127.0.0.1:55432", kafka_endpoint=BROKER,
                             negative_control=os.getenv("CASEFLOW_RESTART_NEGATIVE_CONTROL"),
                             limitations="Local production worker loops only; no Java completion, cloud, object store or AI calls.")

    def record(self, event, **data):
        with self.event_lock:
            self.events.append(dict(at=utc(), event=event, **data))
            (self.output / "events.json").write_text(json.dumps(self.events, indent=2, default=str), encoding="utf-8")

    def command(self, args, timeout=40):
        started = utc()
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        for key, value in os.environ.items():
            if value and len(value) >= 8 and any(word in key.upper() for word in ("PASSWORD", "SECRET", "API_KEY")):
                result.stdout = result.stdout.replace(value, "[REDACTED]")
                result.stderr = result.stderr.replace(value, "[REDACTED]")
        # Commands only contain paths, resource IDs and safe inspection templates.
        self.record("command", command=args, started_at=started, exit_code=result.returncode,
                    stdout=result.stdout, stderr=result.stderr)
        if result.returncode:
            raise RuntimeError(f"restart command failed: {args[0]} (see evidence)")
        return result.stdout.strip()

    def inspect(self, service):
        if service not in {"postgres", "kafka"}:
            raise ValueError("requires an owned restart service")
        name = f"{self.project}-{service}-1"
        # Never inspect Config.Env: it contains credentials.
        template = '{"name":{{json .Name}},"id":{{json .Id}},"labels":{{json .Config.Labels}},"state":{{json .State}},"image":{{json .Image}},"mounts":{{json .Mounts}}}'
        item = json.loads(self.command(["docker", "inspect", "--format", template, name]))
        guard_resource(self.project, item["name"].lstrip("/"), item["labels"], "container")
        item["mounts"] = sorted(item["mounts"], key=lambda mount: mount["Destination"])
        return item

    def stop(self, service):
        item = self.inspect(service)
        if os.getenv("CASEFLOW_RESTART_NEGATIVE_CONTROL") == service:
            self.record("negative_control_stop_omitted", service=service)
            return item
        self.command(["docker", "stop", "--time", "1", item["id"]])
        assert not self.inspect(service)["state"]["Running"]
        return item

    def start(self, service, before):
        item = self.inspect(service)
        assert item["id"] == before["id"] and item["mounts"] == before["mounts"]
        self.command(["docker", "start", item["id"]])
        self.ready(service)
        after = self.inspect(service)
        assert after["id"] == before["id"] and after["mounts"] == before["mounts"]
        assert after["state"]["StartedAt"] != before["state"]["StartedAt"]
        self.record("same_persisted_server_restarted", service=service, container_id=after["id"],
                    before_started_at=before["state"]["StartedAt"], after_started_at=after["state"]["StartedAt"])

    def ready(self, service):
        def healthy():
            result = self.inspect(service)["state"].get("Health", {}).get("Status") == "healthy"
            if not result:
                time.sleep(0.9)
            return result
        until(healthy,
              timeout=100, message=f"{service} not healthy before deadline")

    def open(self):
        self.manifest["revision"] = self.command(["git", "rev-parse", "HEAD"])
        self.manifest["docker_version"] = self.command(["docker", "version", "--format", "{{.Server.Version}}"])
        files = list((ROOT / "tests/resilience").glob("*")) + list((ROOT / "services/worker/caseflow_worker").glob("*.py")) + list((ROOT / "db/migrations").glob("*.sql"))
        files += [ROOT / "infrastructure/local/init-db.sh", ROOT / "services/worker/requirements.lock"]
        self.manifest["source_sha256"] = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}
        (self.output / "manifest.json").write_text(json.dumps(self.manifest, indent=2), encoding="utf-8")
        try:
            self.command(self.compose + ["up", "--detach", "--wait", "--wait-timeout", "120"], timeout=150)
        except Exception:
            for service in ("postgres", "kafka"):
                try:
                    item = self.inspect(service)
                    self.command(["docker", "logs", "--tail", "100", item["id"]], timeout=15)
                except Exception as error:
                    self.record("startup_diagnostics_unavailable", service=service, error_type=type(error).__name__)
            raise
        for service in ("postgres", "kafka"):
            self.inspect(service)

    def close(self):
        # Enumerate only exact project-labeled resources, then verify names and
        # labels again before deleting them. Never use global prune or demo names.
        for kind, plural in (("container", "ps"), ("volume", "volume"), ("network", "network")):
            query = ["docker", "ps", "-aq"] if kind == "container" else ["docker", plural, "ls", "-q"]
            ids = self.command(query + ["--filter", f"label=com.docker.compose.project={self.project}"]).splitlines()
            for resource in ids:
                template = '{"name":{{json .Name}},"labels":{{json .Labels}}}'
                if kind == "container":
                    template = '{"name":{{json .Name}},"labels":{{json .Config.Labels}}}'
                cmd = ["docker", "inspect"] if kind == "container" else ["docker", kind, "inspect"]
                item = json.loads(self.command(cmd + ["--format", template, resource]))
                guard_resource(self.project, item["name"].lstrip("/"), item["labels"], kind)
                remove = ["docker", "rm", "--force", "--volumes", resource] if kind == "container" else ["docker", kind, "rm", resource]
                self.command(remove)
            assert not self.command(query + ["--filter", f"label=com.docker.compose.project={self.project}"]), "owned resource cleanup incomplete"
        self.record("owned_resources_removed")
        self.manifest["ended_at"] = utc()
        (self.output / "manifest.json").write_text(json.dumps(self.manifest, indent=2), encoding="utf-8")
