# Copyright 2025 Canonical
# See LICENSE file for licensing details.

"""Unit tests for `src/packages.py`."""

import pytest

import packages
from packages import PackagesManager


def test_install_packages_calls_apt_update_before_adding_packages(monkeypatch):
    called = []

    monkeypatch.setattr(packages.apt, "update", lambda: called.append("update"))
    monkeypatch.setattr(packages.apt, "add_package", lambda pkg: called.append(pkg))
    manager = PackagesManager()

    manager._install_packages()

    assert called[0] == "update"
    assert set(called[1:]) == set(packages.PACKAGES)


def test_install_runs_expected_steps_in_order(monkeypatch):
    order = []
    for step in (
        "_install_packages",
        "_clone_or_update_source",
        "_run_setup_site",
        "_patch_cron_scripts",
        "_ensure_runtime_dirs",
        "_link_keyring",
        "_setup_apache",
        "_fix_ownership",
    ):
        monkeypatch.setattr(PackagesManager, step, lambda self, _step=step: order.append(_step))

    manager = PackagesManager()
    manager.install()

    assert order == [
        "_install_packages",
        "_clone_or_update_source",
        "_run_setup_site",
        "_patch_cron_scripts",
        "_ensure_runtime_dirs",
        "_link_keyring",
        "_setup_apache",
        "_fix_ownership",
    ]


def test_run_setup_site_ignores_benign_exit_code(monkeypatch):
    monkeypatch.setattr(packages.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(packages.Path, "is_file", lambda self: True)
    monkeypatch.setattr(packages.Path, "read_text", lambda self, encoding=None: "topdir=/srv")

    manager = PackagesManager()
    # setup-site returns non-zero even on success; this must not raise.
    manager._run_setup_site()


def test_run_setup_site_raises_when_files_missing(monkeypatch):
    monkeypatch.setattr(packages.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(packages.Path, "is_file", lambda self: False)

    manager = PackagesManager()
    with pytest.raises(packages.SetupSiteError):
        manager._run_setup_site()


def test_run_setup_site_raises_when_placeholder_not_substituted(monkeypatch):
    monkeypatch.setattr(packages.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(packages.Path, "is_file", lambda self: True)
    monkeypatch.setattr(packages.Path, "read_text", lambda self, encoding=None: "topdir=%TOPDIR%")

    manager = PackagesManager()
    with pytest.raises(packages.SetupSiteError):
        manager._run_setup_site()


def test_clone_or_update_source_clones_when_absent(monkeypatch):
    runs = []
    monkeypatch.setattr(PackagesManager, "_run", lambda self, args, cwd=None: runs.append(args))
    monkeypatch.setattr(packages.Path, "is_dir", lambda self: False)
    monkeypatch.setattr(packages.Path, "mkdir", lambda self, parents=False, exist_ok=False: None)

    manager = PackagesManager()
    manager._clone_or_update_source()

    assert runs == [
        [
            "git",
            "clone",
            "--branch",
            packages.REPO_BRANCH,
            packages.REPO_URL,
            str(packages.TOPDIR),
        ]
    ]


def test_clone_or_update_source_updates_when_present(monkeypatch):
    runs = []
    monkeypatch.setattr(PackagesManager, "_run", lambda self, args, cwd=None: runs.append(args))
    monkeypatch.setattr(packages.Path, "is_dir", lambda self: True)

    manager = PackagesManager()
    manager._clone_or_update_source()

    assert ["git", "fetch", "origin", packages.REPO_BRANCH] in runs
    assert ["git", "reset", "--hard", f"origin/{packages.REPO_BRANCH}"] in runs


def test_configure_appends_override_block(monkeypatch):
    stored = {"text": "topdir=/srv/packages.ubuntu.com\nftpsite=http://upstream\n"}

    monkeypatch.setattr(packages.Path, "read_text", lambda self, encoding=None: stored["text"])
    monkeypatch.setattr(
        packages.Path,
        "write_text",
        lambda self, text, encoding=None: stored.update(text=text),
    )
    monkeypatch.setattr(packages.shutil, "chown", lambda *a, **k: None)

    manager = PackagesManager()
    manager.configure(
        {
            "suites": "noble noble-updates",
            "architectures": "amd64 arm64",
            "ftpsite": "http://mirror/ubuntu",
            "security_ftpsite": "http://mirror/ubuntu",
            "debports_ftpsite": "http://ports",
        }
    )

    written = stored["text"]
    assert packages.CONFIG_OVERRIDES_MARKER in written
    assert 'suites="noble noble-updates"' in written
    assert 'architectures="amd64 arm64"' in written
    assert 'ftpsite="http://mirror/ubuntu"' in written


def test_configure_replaces_previous_override_block(monkeypatch):
    initial = (
        f'topdir=/srv/packages.ubuntu.com\n{packages.CONFIG_OVERRIDES_MARKER}\nsuites="old"\n'
    )
    stored = {"text": initial}

    monkeypatch.setattr(packages.Path, "read_text", lambda self, encoding=None: stored["text"])
    monkeypatch.setattr(
        packages.Path,
        "write_text",
        lambda self, text, encoding=None: stored.update(text=text),
    )
    monkeypatch.setattr(packages.shutil, "chown", lambda *a, **k: None)

    manager = PackagesManager()
    manager.configure(
        {
            "suites": "jammy",
            "architectures": "amd64",
            "ftpsite": "http://mirror/ubuntu",
            "security_ftpsite": "http://mirror/ubuntu",
            "debports_ftpsite": "http://ports",
        }
    )

    written = stored["text"]
    assert written.count(packages.CONFIG_OVERRIDES_MARKER) == 1
    assert 'suites="old"' not in written
    assert 'suites="jammy"' in written


def test_parse_sync_hours_rejects_out_of_range():
    manager = PackagesManager()
    with pytest.raises(ValueError):
        manager._parse_sync_hours("25")


def test_parse_sync_hours_rejects_empty():
    manager = PackagesManager()
    with pytest.raises(ValueError):
        manager._parse_sync_hours("  ")


def test_parse_sync_hours_deduplicates_and_parses():
    manager = PackagesManager()
    assert manager._parse_sync_hours("3, 9, 9, 15") == [3, 9, 15]


def test_configure_schedule_writes_timer_and_restarts(monkeypatch):
    written = {}
    monkeypatch.setattr(
        packages.Path,
        "write_text",
        lambda self, text, encoding=None: written.update({str(self): text}),
    )
    calls = []
    monkeypatch.setattr(packages.systemd, "daemon_reload", lambda: calls.append("reload"))
    monkeypatch.setattr(
        packages.systemd, "service_restart", lambda name: calls.append(("restart", name))
    )

    manager = PackagesManager()
    manager.configure_schedule("3,9")

    timer = written["/etc/systemd/system/packages-daily.timer"]
    assert "OnCalendar=*-*-* 03:23:00" in timer
    assert "OnCalendar=*-*-* 09:23:00" in timer
    assert "reload" in calls
    assert ("restart", "packages-daily.timer") in calls


def test_setup_systemd_units_injects_proxy_environment(monkeypatch):
    monkeypatch.setenv("JUJU_CHARM_HTTP_PROXY", "http://proxy.example:8080")
    monkeypatch.setenv("JUJU_CHARM_HTTPS_PROXY", "https://secure.example:8443")

    written = {}

    monkeypatch.setattr(
        packages.Path, "read_text", lambda self, encoding=None: "[Service]\nExecStart=/bin/true"
    )
    monkeypatch.setattr(
        packages.Path,
        "write_text",
        lambda self, text, encoding=None: written.update({str(self): text}),
    )
    monkeypatch.setattr(packages.Path, "mkdir", lambda self, parents=False, exist_ok=False: None)
    monkeypatch.setattr(packages.systemd, "daemon_reload", lambda: None)
    monkeypatch.setattr(packages.systemd, "service_restart", lambda name: None)
    monkeypatch.setattr(packages.systemd, "service_enable", lambda name: None)

    manager = PackagesManager()
    manager.setup_systemd_units()

    service = written["/etc/systemd/system/packages-daily.service"]
    assert "Environment=HTTP_PROXY=http://proxy.example:8080" in service
    assert "Environment=HTTPS_PROXY=https://secure.example:8443" in service


def test_start_restarts_apache(monkeypatch):
    calls = []
    monkeypatch.setattr(packages.systemd, "service_restart", lambda name: calls.append(name))

    manager = PackagesManager()
    manager.start()

    assert calls == ["apache2"]


def test_run_sync_starts_service_blocking(monkeypatch):
    starts = []
    monkeypatch.setattr(packages.systemd, "service_start", lambda *args: starts.append(args))

    manager = PackagesManager()
    manager.run_sync()

    assert ("packages-daily.service",) in starts


def test_trigger_sync_starts_service_async(monkeypatch):
    starts = []
    monkeypatch.setattr(packages.systemd, "service_start", lambda *args: starts.append(args))

    manager = PackagesManager()
    manager.trigger_sync()

    assert ("packages-daily.service", "--no-block") in starts


