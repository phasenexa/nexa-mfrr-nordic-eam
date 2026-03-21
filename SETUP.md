# SETUP.md — Manual setup steps

This document covers the one-time manual steps required to enable CI/CD publishing
from GitHub to PyPI and TestPyPI using OIDC trusted publishing (no API tokens needed).

## 1. PyPI trusted publishing

1. Sign in to [pypi.org](https://pypi.org)
2. Go to **Account Settings → Publishing**
3. Click **Add a new pending publisher** and fill in:
   - **PyPI Project Name**: `nexa-mfrr-nordic-eam`
   - **Owner**: `phasenexa`
   - **Repository name**: `nexa-mfrr-nordic-eam`
   - **Workflow filename**: `publish.yml`
   - **Environment name**: `pypi`
4. Click **Add**

## 2. TestPyPI trusted publishing

1. Sign in to [test.pypi.org](https://test.pypi.org)
2. Go to **Account Settings → Publishing**
3. Click **Add a new pending publisher** with:
   - **PyPI Project Name**: `nexa-mfrr-nordic-eam`
   - **Owner**: `phasenexa`
   - **Repository name**: `nexa-mfrr-nordic-eam`
   - **Workflow filename**: `publish.yml`
   - **Environment name**: `test-pypi`
4. Click **Add**

## 3. GitHub environment: `pypi` (with human approval gate)

1. In the GitHub repository, go to **Settings → Environments**
2. Click **New environment**, name it `pypi`
3. Under **Deployment protection rules**, enable **Required reviewers**
4. Add yourself (and any other maintainers) as required reviewers
5. Click **Save protection rules**

## 4. GitHub environment: `test-pypi` (no protection)

1. In the GitHub repository, go to **Settings → Environments**
2. Click **New environment**, name it `test-pypi`
3. Leave all protection rules disabled
4. Click **Save**

## 5. First release process

```bash
# Tag the release
git tag v0.1.0
git push origin v0.1.0

# Create the GitHub Release
# Go to: https://github.com/phasenexa/nexa-mfrr-nordic-eam/releases/new
# Select tag v0.1.0, add release notes, click "Publish release"
```

The publish workflow will:
1. Run all CI checks
2. Build the distribution
3. Auto-publish to TestPyPI
4. Wait for a human reviewer to approve the `pypi` environment gate
5. Publish to PyPI once approved

You can approve the gate in the **Actions** tab of the repository
(find the running workflow and click **Review deployments → Approve**).

## 6. Codecov (optional)

1. Sign in to [codecov.io](https://codecov.io) with your GitHub account
2. Click **Add a repository** and enable `phasenexa/nexa-mfrr-nordic-eam`
3. For public repositories, no token is required — the Codecov GitHub Action
   uploads automatically using OIDC

Coverage badges can then be added to the README:
```markdown
[![codecov](https://codecov.io/gh/phasenexa/nexa-mfrr-nordic-eam/branch/main/graph/badge.svg)](https://codecov.io/gh/phasenexa/nexa-mfrr-nordic-eam)
```

## 7. Verifying the setup locally

```bash
# Install dev dependencies
poetry install

# Run the full CI suite
make ci

# Build the package (produces dist/)
poetry build

# Quick import smoke test
pip install dist/nexa_mfrr_eam-0.1.0-py3-none-any.whl
python -c "from nexa_mfrr_eam.timing import gate_closure, current_mtu, mtu_range, MARIMode; print('OK')"
```
