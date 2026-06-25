# Ubuntu Packages Operator

**Ubuntu Packages Operator** is a [charm](https://juju.is/charms-architecture)
that deploys the [packages.ubuntu.com](https://packages.ubuntu.com) web service:
an Apache2 + mod_perl application that lets users browse and search the Ubuntu
archive.

The charm installs the dependencies, checks out the application source from the
upstream [Debian webmaster-team `packages`
repository](https://salsa.debian.org/webmaster-team/packages) (`ubuntu-master`
branch), generates its configuration with the upstream `bin/setup-site` helper,
serves it through Apache and refreshes the package indexes on a schedule.

## Behavior

- Apache serves the application on HTTP port 80. TLS termination is expected to
  be handled by a front-end proxy.
- A `packages-daily.timer` systemd timer runs the archive synchronization job
  (`bin/daily`) on a configurable schedule (default 03:23, 09:23, 15:23, 21:23).
- The first synchronization is triggered automatically at install time in
  background (non-blocking).
- Optional `ingress` relation support publishes routing data for front-door
  proxies such as Traefik/HAProxy while keeping backend traffic HTTP on port 80.
- The `sync-now` action triggers an immediate synchronization run.
- The application source lives in `/srv/packages.ubuntu.com`, owned by the
  stock `ubuntu` user. Apache serves the CGI as `www-data`.

## Requirements

The deployment requirements have been observed to be the following:

- Configured releases: Jammy Noble Questing Resolute Stonking, architectures: i386 amd64 arm64 armhf ppc64el riscv64 s390x
- Disk space used in the `/srv` folder: `145GiB`
- Stats from the systemd service, on a 8 cores VM: `packages-daily.service: Consumed 2h 15min 36.203s CPU time, 38.4M memory peak, 0B memory swap peak.`

## Basic usage

```bash
juju deploy ./ubuntu-packages_amd64.charm --constraints "cpu-cores=8 mem=16G root-disk=250G"
```

If an ingress controller is present, relate it to the charm:

```bash
juju relate ubuntu-packages:ingress <ingress-app>:ingress
```

Trigger the first archive synchronization (this populates the site):

```bash
juju run ubuntu-packages/0 sync-now
```

## Configuration

| Option             | Default                                          | Description                                 |
| ------------------ | ------------------------------------------------ | ------------------------------------------- |
| `sync_hours`       | `3,9,15,21`                                      | Hours of day at which the daily sync runs. |
| `suites`           | `jammy/noble/questing/resolute/stonking series` | Space-separated suites to index.            |
| `architectures`    | `i386 amd64 arm64 armhf ppc64el ...`            | Space-separated architectures to index.     |
| `ftpsite`          | `http://archive.ubuntu.com/ubuntu`              | Primary archive mirror.                     |
| `security_ftpsite` | `http://archive.ubuntu.com/ubuntu`              | Security archive mirror.                    |
| `debports_ftpsite` | `http://ports.ubuntu.com`                       | Ports archive mirror.                       |

For example, to index only the noble series:

```bash
juju config ubuntu-packages suites="noble noble-updates noble-backports"
```

## Service inspection

```bash
systemctl list-timers --all packages-daily.timer
systemctl status packages-daily.service
journalctl -u packages-daily.service
systemctl status apache2
```

## Testing

For information on tests and development workflows, see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Ubuntu Packages Operator is released under the [GPL-3.0 license](LICENSE).
