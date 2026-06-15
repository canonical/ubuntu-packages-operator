# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Unit tests for the charm."""

from subprocess import CalledProcessError
from unittest.mock import patch

import pytest
from charmlibs.apt import PackageError, PackageNotFoundError
from ops.testing import (
    ActiveStatus,
    BlockedStatus,
    Context,
    State,
    TCPPort,
)

from charm import UbuntuPackagesCharm


@pytest.fixture
def ctx():
    return Context(UbuntuPackagesCharm)


@pytest.fixture
def base_state():
    return State(leader=True)


@patch("charm.PackagesManager.trigger_sync")
@patch("charm.PackagesManager.install")
@patch("charm.PackagesManager.configure")
@patch("charm.PackagesManager.setup_systemd_units")
@patch("charm.PackagesManager.configure_schedule")
def test_install_event_sets_active_status_on_success(
    configure_schedule_mock, setup_units_mock, configure_mock, install_mock, trigger_sync_mock, ctx
):
    state_in = State(leader=True, config={"sync_hours": "5,11"})

    out = ctx.run(ctx.on.install(), state_in)

    assert out.unit_status == ActiveStatus()
    install_mock.assert_called_once()
    configure_mock.assert_called_once()
    setup_units_mock.assert_called_once()
    configure_schedule_mock.assert_called_once_with("5,11")


@patch("charm.PackagesManager.trigger_sync")
@patch("charm.PackagesManager.configure_schedule")
@patch("charm.PackagesManager.setup_systemd_units")
@patch("charm.PackagesManager.configure")
@patch("charm.PackagesManager.install")
def test_install_event_uses_default_schedule_when_unset(
    install_mock,
    configure_mock,
    setup_units_mock,
    configure_schedule_mock,
    trigger_sync_mock,
    ctx,
    base_state,
):
    out = ctx.run(ctx.on.install(), base_state)

    assert out.unit_status == ActiveStatus()
    configure_schedule_mock.assert_called_once_with("3,9,15,21")


@patch("charm.PackagesManager.trigger_sync")
@patch("charm.PackagesManager.configure_schedule")
@patch("charm.PackagesManager.setup_systemd_units")
@patch("charm.PackagesManager.configure")
@patch("charm.PackagesManager.install")
def test_install_event_triggers_sync(
    install_mock,
    configure_mock,
    setup_units_mock,
    configure_schedule_mock,
    trigger_sync_mock,
    ctx,
):
    state_in = State(leader=True)

    out = ctx.run(ctx.on.install(), state_in)

    assert out.unit_status == ActiveStatus()
    trigger_sync_mock.assert_called_once()


@patch("charm.PackagesManager.trigger_sync")
@patch("charm.PackagesManager.configure_schedule")
@patch("charm.PackagesManager.setup_systemd_units")
@patch("charm.PackagesManager.configure")
@patch("charm.PackagesManager.install")
def test_upgrade_charm_does_not_trigger_sync(
    install_mock,
    configure_mock,
    setup_units_mock,
    configure_schedule_mock,
    trigger_sync_mock,
    ctx,
    base_state,
):
    out = ctx.run(ctx.on.upgrade_charm(), base_state)

    assert out.unit_status == ActiveStatus()
    trigger_sync_mock.assert_not_called()


@patch("charm.PackagesManager.install")
@pytest.mark.parametrize(
    "exception",
    [
        PackageError,
        PackageNotFoundError,
        CalledProcessError(1, "foo"),
    ],
)
def test_install_event_blocks_charm_on_environment_setup_failure(
    install_mock, exception, ctx, base_state
):
    install_mock.side_effect = exception

    out = ctx.run(ctx.on.install(), base_state)

    assert out.unit_status == BlockedStatus(
        "Failed to set up the environment. Check `juju debug-log` for details."
    )


@patch("charm.PackagesManager.start")
def test_start_event_opens_port_80_and_sets_active_status(start_mock, ctx, base_state):
    out = ctx.run(ctx.on.start(), base_state)

    assert out.unit_status == ActiveStatus()
    start_mock.assert_called_once()
    assert out.opened_ports == {TCPPort(port=80, protocol="tcp")}


@patch("charm.PackagesManager.start")
def test_start_event_blocks_charm_when_service_start_fails(start_mock, ctx, base_state):
    start_mock.side_effect = CalledProcessError(1, "foo")

    out = ctx.run(ctx.on.start(), base_state)

    assert out.unit_status == BlockedStatus(
        "Failed to start services. Check `juju debug-log` for details."
    )
    assert out.opened_ports == frozenset()


@patch("charm.PackagesManager.configure")
@patch("charm.PackagesManager.configure_schedule")
def test_config_changed_event_applies_configuration(configure_schedule_mock, configure_mock, ctx):
    state_in = State(leader=True, config={"sync_hours": "6"})

    out = ctx.run(ctx.on.config_changed(), state_in)

    assert out.unit_status == ActiveStatus()
    configure_mock.assert_called_once()
    configure_schedule_mock.assert_called_once_with("6")


@patch("charm.PackagesManager.configure")
@patch("charm.PackagesManager.configure_schedule")
def test_config_changed_event_blocks_charm_on_invalid_schedule(
    configure_schedule_mock, configure_mock, ctx
):
    state_in = State(leader=True, config={"sync_hours": "25"})
    configure_schedule_mock.side_effect = ValueError("invalid")

    out = ctx.run(ctx.on.config_changed(), state_in)

    assert out.unit_status == BlockedStatus(
        "Invalid sync hours. Use comma-separated integers in [0,23], e.g. '3,9,15,21'."
    )


@patch("charm.PackagesManager.run_sync")
def test_sync_now_action_triggers_sync_and_logs_message(run_sync_mock, ctx, base_state):
    out = ctx.run(ctx.on.action("sync-now"), base_state)

    assert ctx.action_logs == ["Running archive synchronization"]
    assert out.unit_status == ActiveStatus()
    run_sync_mock.assert_called_once()


@patch("charm.PackagesManager.run_sync")
def test_sync_now_action_sets_status_message_when_run_fails(run_sync_mock, ctx, base_state):
    run_sync_mock.side_effect = CalledProcessError(1, "sync")

    out = ctx.run(ctx.on.action("sync-now"), base_state)

    assert out.unit_status == ActiveStatus(
        "Failed to run synchronization. Check `juju debug-log` for details."
    )
