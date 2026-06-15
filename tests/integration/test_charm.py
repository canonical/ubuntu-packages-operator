# Copyright 2025 Canonical
# See LICENSE file for licensing details.

import jubilant
import requests

from . import APPNAME, address


def test_service_state_after_deploy(juju: jubilant.Juju, ubuntu_packages_charm):
    """Deploy the charm via jubilant and wait until the application is active."""
    juju.deploy(
        ubuntu_packages_charm,
        app=APPNAME,
        constraints={"mem": "16G", "cores": 2, "root-disk": "100G"},
    )
    juju.wait(jubilant.all_active, timeout=1800)


def test_web_server_serves_http(juju: jubilant.Juju):
    """Check that Apache answers on port 80.

    The index pages are only generated after a full archive synchronization, so
    a fresh unit returns 404 rather than 200. We only assert here that Apache is
    up and serving the application virtual host.
    """
    response = requests.get(f"http://{address(juju)}:80/", timeout=60)
    assert response.status_code in (200, 404)
    assert "Server" in response.headers
    assert response.headers["Server"].startswith("Apache")
