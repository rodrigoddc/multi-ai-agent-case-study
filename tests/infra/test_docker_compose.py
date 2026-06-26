import yaml


def test_compose_fastapi_uses_dev_environment_for_container_network():
    with open("infra/container/app/docker-compose.yml") as compose_file:
        compose = yaml.safe_load(compose_file)

    fastapi_service = compose["services"]["fastapi"]
    seed_service = compose["services"]["seed"]

    assert fastapi_service["environment"]["APP_ENV"] == "${APP_ENV:-dev}"
    assert seed_service["environment"]["APP_ENV"] == "${APP_ENV:-dev}"
