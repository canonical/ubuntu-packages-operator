# Copyright 2025 Canonical
# See LICENSE file for licensing details.

import os
import subprocess
from pathlib import Path

import jubilant
from pytest import fixture


@fixture(scope="module")
def juju():
    with jubilant.temp_model() as juju:
        yield juju


@fixture(scope="module")
def ubuntu_packages_charm(request):
    """Build or return the path to the ubuntu-packages charm file."""
    charm_file = request.config.getoption("--charm-path")
    if not charm_file:
        working_dir = os.getenv("SPREAD_PATH", Path("."))

        subprocess.run(
            ["/snap/bin/charmcraft", "pack", "--verbose"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=working_dir,
            check=True,
        )

        charm_file = next(Path.glob(Path(working_dir), "*.charm")).absolute()

    return charm_file
