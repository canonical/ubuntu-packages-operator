#!/usr/bin/env python3
# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Charmed Operator for the packages.ubuntu.com web service."""

import logging
import shutil
from subprocess import CalledProcessError, SubprocessError

import ops
from charmlibs.apt import PackageError, PackageNotFoundError
from charmlibs.systemd import SystemdError
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer as IngressRequirer

from packages import DEFAULT_SYNC_HOURS, PackagesManager, SetupSiteError

logger = logging.getLogger(__name__)

PORT = 80


class UbuntuPackagesCharm(ops.CharmBase):
    """Charmed Operator for the packages.ubuntu.com web service."""

    def __init__(self, framework: ops.Framework):
        super().__init__(framework)

        self.ingress = IngressRequirer(self, port=PORT, strip_prefix=True, relation_name="ingress")

        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.sync_now_action, self._on_sync_now)

        # Route URL changes can affect how the service is reached externally.
        framework.observe(self.ingress.on.ready, self._on_config_changed)
        framework.observe(self.ingress.on.revoked, self._on_config_changed)

        self._packages = PackagesManager()

    def _config_options(self) -> dict[str, str]:
        """Collect the application configuration options from charm config."""
        return {
            "suites": str(self.config.get("suites", "")),
            "architectures": str(self.config.get("architectures", "")),
            "ftpsite": str(self.config.get("ftpsite", "")),
            "security_ftpsite": str(self.config.get("security_ftpsite", "")),
            "debports_ftpsite": str(self.config.get("debports_ftpsite", "")),
        }

    def _sync_hours(self) -> str:
        """Return the configured sync hours, falling back to the default."""
        return str(self.config.get("sync_hours", "")).strip() or DEFAULT_SYNC_HOURS

    def _setup_environment(self) -> bool:
        """Install and configure workload components.

        Returns True on success and sets BlockedStatus on failure.
        """
        try:
            self._packages.install()
            self._packages.configure(self._config_options())
            self._packages.setup_systemd_units()
            self._packages.configure_schedule(self._sync_hours())
        except (
            CalledProcessError,
            SubprocessError,
            PackageError,
            PackageNotFoundError,
            SetupSiteError,
            SystemdError,
            ValueError,
            IOError,
            OSError,
            shutil.Error,
        ) as e:
            logger.warning("Failed to set up the environment: %s", e)
            self.unit.status = ops.BlockedStatus(
                "Failed to set up the environment. Check `juju debug-log` for details."
            )
            return False

        return True

    def _on_install(self, event: ops.InstallEvent):
        """Handle install events."""
        self.unit.status = ops.MaintenanceStatus("Setting up environment")
        if not self._setup_environment():
            return

        try:
            self._packages.trigger_sync()
        except CalledProcessError as e:
            logger.warning("Failed to trigger initial sync: %s", e)

        self.unit.status = ops.ActiveStatus()

    def _on_upgrade_charm(self, event: ops.UpgradeCharmEvent):
        """Handle charm upgrades without forcing an immediate sync run."""
        self.unit.status = ops.MaintenanceStatus("Applying charm upgrade")
        if not self._setup_environment():
            return

        self.unit.status = ops.ActiveStatus()

    def _on_start(self, event: ops.StartEvent):
        """Start Apache and advertise the service port."""
        self.unit.status = ops.MaintenanceStatus("Starting web server")
        try:
            self._packages.start()
        except CalledProcessError:
            self.unit.status = ops.BlockedStatus(
                "Failed to start services. Check `juju debug-log` for details."
            )
            return
        self.unit.set_ports(PORT)
        self.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, event: ops.ConfigChangedEvent):
        """Apply configuration changes to the application and the schedule."""
        logger.debug("config changed event")
        self.unit.status = ops.MaintenanceStatus("Updating configuration")
        try:
            self._packages.configure(self._config_options())
            self._packages.configure_schedule(self._sync_hours())
        except ValueError:
            self.unit.status = ops.BlockedStatus(
                "Invalid sync hours. Use comma-separated integers in [0,23], e.g. '3,9,15,21'."
            )
            return
        except (SystemdError, IOError, OSError):
            self.unit.status = ops.BlockedStatus(
                "Failed to update configuration. Check `juju debug-log` for details."
            )
            return
        self.unit.status = ops.ActiveStatus()

    def _on_sync_now(self, event: ops.ActionEvent):
        """Trigger an immediate archive synchronization run."""
        self.unit.status = ops.MaintenanceStatus("Running archive synchronization")
        try:
            event.log("Running archive synchronization")
            self._packages.run_sync()
        except (CalledProcessError, IOError):
            event.log("Archive synchronization run failed")
            self.unit.status = ops.ActiveStatus(
                "Failed to run synchronization. Check `juju debug-log` for details."
            )
            return
        self.unit.status = ops.ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    ops.main(UbuntuPackagesCharm)
