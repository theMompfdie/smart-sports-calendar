from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILES = (
    REPOSITORY_ROOT / "docker-compose.yml",
    REPOSITORY_ROOT / "tests" / "deployment" / "docker-compose.multi-instance.yml",
)
PROJECTS = (
    "smart-calendar-ci-one",
    "smart-calendar-ci-two",
    "smart-calendar-ci-three",
)
HEALTH_ATTEMPTS = 18
HEALTH_DELAY_SECONDS = 5
HEALTH_STATUS_TEMPLATE = "".join(
    (
        "{{if .State.Health}}{{.State.Health.Status}}",
        "{{else}}{{.State.Status}}{{end}}",
    )
)


def compose_command(project: str, *arguments: str) -> list[str]:
    command = ["docker", "compose"]
    for compose_file in COMPOSE_FILES:
        command.extend(("--file", str(compose_file)))
    command.extend(("--project-name", project, *arguments))
    return command


def instance_environment(project: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "INSTANCE_NAME": project,
            "M365_TENANT_ID": f"{project}-tenant",
            "M365_CLIENT_ID": f"{project}-client",
            "M365_CLIENT_SECRET": f"{project}-non-secret-test-value",
            "M365_USER_ID": f"{project}@example.invalid",
            "OUTLOOK_CALENDAR_ID": f"{project}-calendar",
            "GRAPH_STARTUP_VALIDATION_ENABLED": "false",
            "API_FOOTBALL_ENABLED": "false",
        }
    )
    return environment


def run(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
        capture_output=capture_output,
        text=True,
    )


def output(
    command: list[str],
    *,
    environment: dict[str, str],
) -> str:
    return run(
        command,
        environment=environment,
        capture_output=True,
    ).stdout.strip()


def wait_until_healthy(project: str, environment: dict[str, str]) -> str:
    container_id = output(
        compose_command(project, "ps", "--quiet", "calendar-sync"),
        environment=environment,
    )
    if not container_id:
        raise RuntimeError(f"No container found for project {project}.")

    for _attempt in range(HEALTH_ATTEMPTS):
        status = output(
            [
                "docker",
                "inspect",
                "--format",
                HEALTH_STATUS_TEMPLATE,
                container_id,
            ],
            environment=environment,
        )
        if status == "healthy":
            return container_id
        if status in {"dead", "exited"}:
            raise RuntimeError(f"Container for {project} entered state {status}.")
        time.sleep(HEALTH_DELAY_SECONDS)

    raise RuntimeError(f"Container for {project} did not become healthy.")


def inspect_isolation(
    project: str,
    container_id: str,
    environment: dict[str, str],
) -> tuple[str, str, str]:
    inspection = json.loads(
        output(
            ["docker", "inspect", container_id],
            environment=environment,
        )
    )[0]
    volume = next(
        mount["Name"]
        for mount in inspection["Mounts"]
        if mount["Destination"] == "/data"
    )
    networks = tuple(inspection["NetworkSettings"]["Networks"])
    if len(networks) != 1:
        raise RuntimeError(f"Unexpected networks for {project}: {networks}")

    container_name = inspection["Name"].lstrip("/")
    image_name = inspection["Config"]["Image"]
    if not container_name.startswith(f"{project}-calendar-sync-"):
        raise RuntimeError(f"Container name is not project-scoped: {container_name}")
    if not image_name.startswith(f"{project}-calendar-sync:"):
        raise RuntimeError(f"Image name is not project-scoped: {image_name}")
    if not networks[0].startswith(f"{project}_"):
        raise RuntimeError(f"Network is not project-scoped: {networks[0]}")

    probe = output(
        compose_command(
            project,
            "exec",
            "-T",
            "calendar-sync",
            "python",
            "-c",
            (
                "import os, sqlite3; "
                "connection = sqlite3.connect(os.environ['DATABASE_PATH']); "
                "value = connection.execute("
                "'SELECT instance_name FROM instance_probe').fetchone()[0]; "
                "connection.close(); "
                "assert value == os.environ['INSTANCE_NAME']; "
                "print(value)"
            ),
        ),
        environment=environment,
    )
    if probe != project:
        raise RuntimeError(f"Unexpected database probe for {project}: {probe}")

    logs = output(
        compose_command(project, "logs", "--no-color", "calendar-sync"),
        environment=environment,
    )
    if f"instance_probe_ready={project}" not in logs:
        raise RuntimeError(f"Instance-specific log marker missing for {project}.")
    for other_project in PROJECTS:
        if other_project != project and other_project in logs:
            raise RuntimeError(f"Logs for {project} contain {other_project}.")

    return volume, networks[0], image_name


def inspect_compose_configuration(
    project: str,
    environment: dict[str, str],
) -> tuple[str, str, str]:
    configuration = json.loads(
        output(
            compose_command(project, "config", "--format", "json"),
            environment=environment,
        )
    )
    service = configuration["services"]["calendar-sync"]
    volume = configuration["volumes"]["smart_sports_data"]["name"]
    network = configuration["networks"]["default"]["name"]
    image = service["image"]

    if configuration["name"] != project:
        raise RuntimeError(f"Unexpected Compose project name for {project}.")
    if "container_name" in service:
        raise RuntimeError(f"Container name is hard-coded for {project}.")
    if service["environment"]["INSTANCE_NAME"] != project:
        raise RuntimeError(f"Instance environment is not isolated for {project}.")
    if service["labels"]["org.smart-sports-calendar.instance"] != project:
        raise RuntimeError(f"Instance label is not isolated for {project}.")
    if not volume.startswith(f"{project}_"):
        raise RuntimeError(f"Volume is not project-scoped: {volume}")
    if not network.startswith(f"{project}_"):
        raise RuntimeError(f"Network is not project-scoped: {network}")
    if not image.startswith(f"{project}-calendar-sync:"):
        raise RuntimeError(f"Image is not project-scoped: {image}")

    return volume, network, image


def require_distinct_resources(
    isolation: list[tuple[str, str, str]],
) -> None:
    volumes = {item[0] for item in isolation}
    networks = {item[1] for item in isolation}
    images = {item[2] for item in isolation}
    if len(volumes) != len(PROJECTS):
        raise RuntimeError(f"Volumes are not isolated: {sorted(volumes)}")
    if len(networks) != len(PROJECTS):
        raise RuntimeError(f"Networks are not isolated: {sorted(networks)}")
    if len(images) != len(PROJECTS):
        raise RuntimeError(f"Images are not isolated: {sorted(images)}")


def main(*, config_only: bool = False) -> int:
    environments = {project: instance_environment(project) for project in PROJECTS}
    attempted_projects: list[str] = []

    rendered_isolation = [
        inspect_compose_configuration(project, environments[project])
        for project in PROJECTS
    ]
    require_distinct_resources(rendered_isolation)
    print("Three isolated Compose configurations validated successfully.")
    if config_only:
        return 0

    try:
        for project in PROJECTS:
            attempted_projects.append(project)
            run(
                compose_command(project, "up", "--detach", "--build"),
                environment=environments[project],
            )

        isolation = []
        for project in PROJECTS:
            container_id = wait_until_healthy(project, environments[project])
            isolation.append(
                inspect_isolation(project, container_id, environments[project])
            )

        require_distinct_resources(isolation)

        print("Three isolated Compose instances validated successfully.")
        for project, (volume, network, image) in zip(
            PROJECTS,
            isolation,
            strict=True,
        ):
            print(f"{project}: volume={volume}, network={network}, image={image}")
        return 0
    finally:
        for project in reversed(attempted_projects):
            try:
                run(
                    compose_command(
                        project,
                        "down",
                        "--volumes",
                        "--remove-orphans",
                    ),
                    environment=environments[project],
                )
            except subprocess.CalledProcessError as error:
                print(
                    f"Cleanup warning for {project}: exit code {error.returncode}",
                    file=sys.stderr,
                )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate isolated SMART Sports Calendar Compose instances."
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Validate rendered Compose isolation without starting Docker containers.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_arguments()
    sys.exit(main(config_only=arguments.config_only))
