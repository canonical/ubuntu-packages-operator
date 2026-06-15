# Copyright 2025 Canonical
# See LICENSE file for licensing details.

APPNAME = "ubuntu-packages"


def address(juju, app: str = APPNAME) -> str:
    """Return the public address of the application's first unit."""
    status = juju.status()
    units = status.apps[app].units
    unit = next(iter(units.values()))
    return unit.public_address
