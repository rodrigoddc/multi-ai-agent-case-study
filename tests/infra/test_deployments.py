import json
import subprocess

import yaml


def load_yaml(path: str) -> dict:
    with open(path) as yaml_file:
        return yaml.safe_load(yaml_file)


def test_compose_fastapi_uses_dev_environment_for_container_network():
    compose = load_yaml("infra/container/app/docker-compose.yml")
    fastapi_service = compose["services"]["fastapi"]
    seed_service = compose["services"]["seed"]

    assert fastapi_service["environment"]["APP_ENV"] == "${APP_ENV:-dev}"
    assert seed_service["environment"]["APP_ENV"] == "${APP_ENV:-dev}"


def test_kubernetes_fastapi_uses_dev_environment_for_cluster_network():
    stable = load_yaml("infra/k8s/apps/fastapi/fastapi-api-deployment.yml")
    canary = load_yaml("infra/k8s/apps/fastapi/fastapi-api-canary-deployment.yml")

    for deployment in [stable, canary]:
        env = deployment["spec"]["template"]["spec"]["containers"][0]["env"]
        values = {item["name"]: item["value"] for item in env}
        assert values["APP_ENV"] == "dev"
        # API keys and Langfuse credentials are in secretRefs (envFrom), not inline env
        env_from = deployment["spec"]["template"]["spec"]["containers"][0].get(
            "envFrom", []
        )
        secret_names = [
            ref["secretRef"]["name"] for ref in env_from if "secretRef" in ref
        ]
        assert "app-secrets" in secret_names
        assert "postgres-secret" in secret_names


def test_kubernetes_seed_job_uses_runtime_environment_and_loaded_image():
    job = load_yaml("infra/k8s/jobs/seed-job.yml")
    container = job["spec"]["template"]["spec"]["containers"][0]

    assert container["image"] == "localhost/seed-hotels:latest"
    assert container["imagePullPolicy"] == "Never"
    assert {item["name"]: item["value"] for item in container["env"]}[
        "APP_ENV"
    ] == "dev"


def test_kubernetes_pgbouncer_uses_single_listen_port_for_service_and_probes():
    deployment = load_yaml("infra/k8s/apps/pgbouncer/pgbouncer-deployment.yml")
    service = load_yaml("infra/k8s/apps/pgbouncer/pgbouncer-service.yml")
    configmap = load_yaml("infra/k8s/apps/pgbouncer/pgbouncer-configmap.yml")

    container = deployment["spec"]["template"]["spec"]["containers"][0]
    service_port = service["spec"]["ports"][0]
    config = configmap["data"]["pgbouncer.ini"]

    assert "listen_port = 5432" in config
    assert "host=postgres-svc port=5432" in config
    assert container["ports"][0]["containerPort"] == 5432
    assert service_port["targetPort"] == 5432
    assert container["readinessProbe"]["tcpSocket"]["port"] == 5432
    assert container["livenessProbe"]["tcpSocket"]["port"] == 5432


def test_fastapi_container_command_does_not_use_reload():
    import pytest

    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "container-fastapi:latest"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError, FileNotFoundError:
        pytest.skip("Docker image not available or Docker not installed")

    image = json.loads(result.stdout)[0]
    command = image["Config"]["Cmd"]

    assert "--reload" not in command
