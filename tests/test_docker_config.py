"""Test Docker configuration and startup commands.

These tests ensure that:
1. Gunicorn command-line arguments are valid
2. Dockerfile CMD uses correct syntax
3. Environment variables are properly used
"""

import pytest
import re
import subprocess


def test_dockerfiles_use_correct_gunicorn_args():
    """Test that all Dockerfiles use --keep-alive not --keepalive."""

    dockerfiles = [
        "E:\\source\\mostlylucid-nmt\\Dockerfile",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.min",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu.min",
    ]

    for dockerfile_path in dockerfiles:
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()

            # Check for incorrect --keepalive (without hyphen in "alive")
            if "--keepalive" in content and "--keep-alive" not in content.replace("--keepalive", ""):
                pytest.fail(
                    f"{dockerfile_path} uses '--keepalive' instead of '--keep-alive'. "
                    f"Gunicorn requires '--keep-alive' with a hyphen."
                )

            # Verify correct version is present
            assert "--keep-alive" in content, \
                f"{dockerfile_path} missing '--keep-alive' argument"

        except FileNotFoundError:
            pytest.skip(f"Dockerfile not found: {dockerfile_path}")


def test_dockerfiles_use_exec_form_for_cmd():
    """Test that Dockerfiles use exec form for CMD (not shell form)."""

    dockerfiles = [
        "E:\\source\\mostlylucid-nmt\\Dockerfile",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.min",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu.min",
    ]

    for dockerfile_path in dockerfiles:
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()

            # Find CMD lines
            cmd_lines = [line for line in content.split('\n') if line.strip().startswith('CMD')]

            for line in cmd_lines:
                # Should use exec form: CMD ["executable", "param1", "param2"]
                # OR shell with exec: CMD ["bash", "-lc", "exec ..."]
                assert '[' in line or 'exec' in line.lower(), \
                    f"{dockerfile_path} CMD should use exec form or exec keyword: {line}"

        except FileNotFoundError:
            pytest.skip(f"Dockerfile not found: {dockerfile_path}")


def test_dockerfiles_use_same_base_python_version():
    """Test that CPU Dockerfiles use consistent Python version."""

    dockerfiles = {
        "E:\\source\\mostlylucid-nmt\\Dockerfile": None,
        "E:\\source\\mostlylucid-nmt\\Dockerfile.min": None,
    }

    python_versions = {}

    for dockerfile_path in dockerfiles.keys():
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()

            # Find FROM python:X.Y-slim
            match = re.search(r'FROM python:([\d.]+)-slim', content)
            if match:
                python_versions[dockerfile_path] = match.group(1)

        except FileNotFoundError:
            pytest.skip(f"Dockerfile not found: {dockerfile_path}")

    # All CPU images should use same Python version
    if python_versions:
        versions = list(python_versions.values())
        assert all(v == versions[0] for v in versions), \
            f"CPU Dockerfiles use different Python versions: {python_versions}"

        # Should be Python 3.12 (not 3.13 which has compatibility issues)
        assert versions[0].startswith("3.12"), \
            f"Should use Python 3.12.x, found: {versions[0]}"


def test_gpu_dockerfiles_use_ubuntu_24():
    """Test that GPU Dockerfiles use Ubuntu 24.04."""

    dockerfiles = [
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu.min",
    ]

    for dockerfile_path in dockerfiles:
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()

            # Should use ubuntu24.04
            assert "ubuntu24.04" in content or "ubuntu-24.04" in content, \
                f"{dockerfile_path} should use Ubuntu 24.04"

        except FileNotFoundError:
            pytest.skip(f"Dockerfile not found: {dockerfile_path}")


def test_gpu_dockerfiles_use_break_system_packages():
    """Test that GPU Dockerfiles use --break-system-packages for pip."""

    dockerfiles = [
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu.min",
    ]

    for dockerfile_path in dockerfiles:
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()

            # Find pip install commands
            pip_lines = [line for line in content.split('\n')
                        if 'pip' in line and 'install' in line]

            assert pip_lines, f"{dockerfile_path} has no pip install commands"

            # All pip installs should use --break-system-packages for Ubuntu 24.04
            for line in pip_lines:
                if 'RUN' in line and 'pip3 install' in line:
                    assert '--break-system-packages' in line, \
                        f"{dockerfile_path} pip install missing --break-system-packages: {line}"

        except FileNotFoundError:
            pytest.skip(f"Dockerfile not found: {dockerfile_path}")


def test_all_dockerfiles_have_oci_labels():
    """Test that all Dockerfiles include OCI labels."""

    dockerfiles = [
        "E:\\source\\mostlylucid-nmt\\Dockerfile",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.min",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu.min",
    ]

    required_labels = [
        "org.opencontainers.image.title",
        "org.opencontainers.image.description",
        "org.opencontainers.image.version",
        "org.opencontainers.image.source",
    ]

    for dockerfile_path in dockerfiles:
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()

            for label in required_labels:
                assert label in content, \
                    f"{dockerfile_path} missing OCI label: {label}"

        except FileNotFoundError:
            pytest.skip(f"Dockerfile not found: {dockerfile_path}")


def test_all_dockerfiles_use_same_oci_title():
    """Test that all Dockerfiles use the same org.opencontainers.image.title.

    This ensures all images go to ONE Docker Hub repository.
    """

    dockerfiles = [
        "E:\\source\\mostlylucid-nmt\\Dockerfile",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.min",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu.min",
    ]

    titles = {}

    for dockerfile_path in dockerfiles:
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()

            # Find org.opencontainers.image.title
            match = re.search(r'org\.opencontainers\.image\.title="([^"]+)"', content)
            if match:
                titles[dockerfile_path] = match.group(1)

        except FileNotFoundError:
            pytest.skip(f"Dockerfile not found: {dockerfile_path}")

    # All should have the same title
    if titles:
        unique_titles = set(titles.values())
        assert len(unique_titles) == 1, \
            f"Dockerfiles use different OCI titles (should all be 'mostlylucid-nmt'): {titles}"

        # Should be exactly "mostlylucid-nmt"
        assert list(unique_titles)[0] == "mostlylucid-nmt", \
            f"OCI title should be 'mostlylucid-nmt', found: {unique_titles}"


def test_gunicorn_command_is_valid_syntax():
    """Test that the gunicorn command in Dockerfiles has valid syntax."""

    # Extract gunicorn command from a Dockerfile
    dockerfile_path = "E:\\source\\mostlylucid-nmt\\Dockerfile"

    try:
        with open(dockerfile_path, 'r') as f:
            content = f.read()

        # Find CMD with gunicorn
        cmd_match = re.search(r'CMD \[(.*?)\]', content, re.DOTALL)
        if not cmd_match:
            pytest.skip("No CMD with gunicorn found")

        cmd_content = cmd_match.group(1)

        # Check for common issues
        assert "--keep-alive" in cmd_content, "Missing --keep-alive"
        assert "--timeout" in cmd_content, "Missing --timeout"
        assert "--graceful-timeout" in cmd_content, "Missing --graceful-timeout"
        assert "uvicorn.workers.UvicornWorker" in cmd_content, "Missing UvicornWorker"
        assert "app:app" in cmd_content, "Missing app:app"

    except FileNotFoundError:
        pytest.skip(f"Dockerfile not found: {dockerfile_path}")


def test_dockerfiles_use_stopsignal_sigterm():
    """Test that all Dockerfiles use STOPSIGNAL SIGTERM for graceful shutdown."""

    dockerfiles = [
        "E:\\source\\mostlylucid-nmt\\Dockerfile",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.min",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu",
        "E:\\source\\mostlylucid-nmt\\Dockerfile.gpu.min",
    ]

    for dockerfile_path in dockerfiles:
        try:
            with open(dockerfile_path, 'r') as f:
                content = f.read()

            assert "STOPSIGNAL SIGTERM" in content, \
                f"{dockerfile_path} should use STOPSIGNAL SIGTERM"

        except FileNotFoundError:
            pytest.skip(f"Dockerfile not found: {dockerfile_path}")
