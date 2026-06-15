# Contributing

This document explains the processes and practices recommended for contributing
enhancements to this operator.

- Generally, before developing enhancements to this charm, you should consider
  [opening an issue](https://github.com/canonical/ubuntu-packages-operator/issues)
  explaining your use case.
- If you would like to chat with us about your use-cases or proposed
  implementation, you can reach us [on
  Matrix](https://ubuntu.com/community/communications/matrix) or
  [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Operator
  Framework](https://ops.readthedocs.io/en/latest/) library will help you a lot
  when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically
  examines code quality, test coverage, and user experience for Juju
  administrators of this charm.
- Please help us out in ensuring easy to review branches by rebasing your pull
  request branch onto the `main` branch. This also avoids merge commits and
  creates a linear Git commit history.

## Developing

This project uses [`uv`](https://github.com/astral-sh/uv) for managing
dependencies and virtual environments.

```bash
❯ make format        # update your code according to linting rules
❯ make lint          # code style
❯ make unit          # run unit tests
❯ make integration   # run integration tests
```

To create the environment manually:

```bash
❯ uv venv
❯ source .venv/bin/activate
❯ uv sync --all-extras
```

## Running tests

### Unit tests

Unit tests can be run locally with no additional tools by running `make unit`.
All of the project's unit tests are designed to run agnostic of machine and
network, and shouldn't require any additional dependencies other than those
injected by `uv run` and the `Make` target.

### Integration tests

Integration tests can be run directly with `make integration`, but this requires
a rather invasive juju setup and will create and destroy units.

```bash
❯ make integration
```

### Spread tests

If instead integration tests shall be run with isolation,
[Spread](https://github.com/canonical/spread/blob/master/README.md) is
configured to create the necessary environment, set up the components needed,
and then run the integration tests in there.

```bash
❯ charmcraft.spread -v -debug -reuse
```

## Build charm

Build the charm in this git repository using:

```bash
charmcraft pack
```

### Deploy and Debug

```bash
# Create a model
❯ juju add-model dev

# Enable DEBUG logging
❯ juju model-config logging-config="<root>=INFO;unit=DEBUG"
❯ juju debug-log --replay --level DEBUG

# Deploy for local testing
❯ juju deploy ./ubuntu-packages_amd64.charm --constraints "cpu-cores=2 mem=16G root-disk=1T"

# Trigger the first archive synchronization
❯ juju run ubuntu-packages/0 sync-now

# To blast it away no matter the open half debugged state
❯ juju remove-application --no-prompt --force --no-wait ubuntu-packages
```
