"""The restart harness must refuse resources outside its disposable project."""
import pytest

from restart_probe import guard_resource


@pytest.mark.parametrize("project,name,labels,kind", [
    ("caseflow-local", "caseflow-local-postgres-1", {}, "container"),
    ("caseflow-r3-restart-" + "a" * 32, "caseflow-local-postgres-1", {}, "container"),
    ("caseflow-r3-restart-" + "a" * 32,
     "caseflow-r3-restart-" + "a" * 32 + "-postgres-1",
     {"com.docker.compose.project": "caseflow-local", "com.docker.compose.service": "postgres"}, "container"),
    ("caseflow-r3-restart-" + "a" * 32,
     "caseflow-r3-restart-" + "a" * 32 + "_postgres-data",
     {"com.docker.compose.project": "caseflow-local"}, "volume"),
])
def test_refuses_nonowned_resource(project, name, labels, kind):
    with pytest.raises(ValueError, match="owned restart"):
        guard_resource(project, name, labels, kind)


@pytest.mark.parametrize("suffix,kind,extra", [
    ("-postgres-1", "container", {"com.docker.compose.service": "postgres"}),
    ("-kafka-1", "container", {"com.docker.compose.service": "kafka"}),
    ("_postgres-data", "volume", {}),
    ("_kafka-data", "volume", {}),
    ("_default", "network", {}),
])
def test_accepts_only_exact_owned_resource(suffix, kind, extra):
    project = "caseflow-r3-restart-" + "a" * 32
    guard_resource(project, project + suffix, {"com.docker.compose.project": project, **extra}, kind)
