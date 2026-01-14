# Publishing obskit to PyPI

This guide covers the complete process of publishing obskit to PyPI.

## Prerequisites

1. **PyPI Account**: Create an account at [pypi.org](https://pypi.org/account/register/)
2. **TestPyPI Account**: Create an account at [test.pypi.org](https://test.pypi.org/account/register/)
3. **Build Tools**: Install required packages:
   ```bash
   pip install build twine
   ```

## First-Time Setup: Trusted Publishing (Recommended)

GitHub Actions uses **Trusted Publishing** (OIDC) for secure PyPI publishing without API tokens.

### Step 1: Configure PyPI Trusted Publisher

1. Go to [PyPI - Manage Account](https://pypi.org/manage/account/)
2. Navigate to **Publishing** → **Add a new pending publisher**
3. Fill in the details:
   - **PyPI Project Name**: `obskit`
   - **Owner**: `talaatmagdyx`
   - **Repository name**: `obskit`
   - **Workflow name**: `release.yml`
   - **Environment name**: `pypi`

4. Click **Add**

### Step 2: Configure TestPyPI (Optional)

Repeat for TestPyPI at [test.pypi.org](https://test.pypi.org/manage/account/publishing/):
- **Environment name**: `testpypi`

### Step 3: Create GitHub Environments

1. Go to your repository **Settings** → **Environments**
2. Create environment named `pypi`:
   - Add protection rules (optional): require approval, branch restrictions
3. Create environment named `testpypi` (optional, for pre-releases)

## Local Build & Test

Before publishing, always test locally:

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build the package
python -m build

# Check package metadata
twine check dist/*

# Test install from local wheel
pip install dist/obskit-*.whl --force-reinstall

# Verify
python -c "import obskit; print(obskit.__version__)"
```

## Publishing Methods

### Method 1: GitHub Release (Recommended)

This triggers automatic publishing via GitHub Actions.

1. **Update version** in `src/obskit/_version.py`:
   ```python
   __version__: str = "1.0.0"
   __version_info__: tuple[int, int, int] = (1, 0, 0)
   ```

2. **Update CHANGELOG.md** with release notes

3. **Commit and push**:
   ```bash
   git add -A
   git commit -m "chore: release v1.0.0"
   git push origin main
   ```

4. **Create GitHub Release**:
   - Go to **Releases** → **Draft a new release**
   - Tag: `v1.0.0` (create new tag)
   - Title: `v1.0.0`
   - Generate release notes or copy from CHANGELOG
   - ✅ Check "Set as the latest release"
   - Click **Publish release**

5. **Monitor workflow**:
   - Go to **Actions** → **Release** workflow
   - Verify package appears on [pypi.org/project/obskit](https://pypi.org/project/obskit/)

### Method 2: Manual Publishing (Alternative)

If you need to publish manually:

```bash
# Build
python -m build

# Upload to TestPyPI first
twine upload --repository testpypi dist/*

# Test installation from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ obskit

# If all works, upload to PyPI
twine upload dist/*
```

## Pre-release Publishing

For alpha/beta/rc releases:

1. Update version with pre-release suffix:
   ```python
   __version__: str = "1.1.0a1"  # alpha
   __version__: str = "1.1.0b1"  # beta
   __version__: str = "1.1.0rc1"  # release candidate
   ```

2. Create GitHub Release with "Pre-release" checked:
   - This publishes to **TestPyPI** automatically

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

| Change Type | Example | When to Use |
|-------------|---------|-------------|
| MAJOR | 1.0.0 → 2.0.0 | Breaking API changes |
| MINOR | 1.0.0 → 1.1.0 | New features, backwards compatible |
| PATCH | 1.0.0 → 1.0.1 | Bug fixes, backwards compatible |
| PRE-RELEASE | 1.1.0a1, 1.1.0b1, 1.1.0rc1 | Testing before stable release |

## Troubleshooting

### "Project not found" on PyPI

- Ensure trusted publisher is configured before first release
- Project name in pyproject.toml must match exactly: `obskit`

### GitHub Actions Fails

- Check environment name matches: `pypi` or `testpypi`
- Verify OIDC permissions are correct in workflow
- Check GitHub environment exists in repository settings

### Package Validation Fails

```bash
# Fix common issues
twine check dist/*

# Common fixes:
# - Ensure README.md has valid markdown
# - Check all URLs in pyproject.toml are valid
# - Verify classifiers are valid
```

### Import Errors After Install

```bash
# Debug installation
pip show obskit
pip install obskit[all] --force-reinstall

# Check what's installed
python -c "import obskit; print(dir(obskit))"
```

## Post-Release Checklist

After a successful release:

- [ ] Verify package on [PyPI](https://pypi.org/project/obskit/)
- [ ] Test installation: `pip install obskit`
- [ ] Update documentation if needed
- [ ] Announce release (GitHub Discussions, social media)
- [ ] Close related issues/PRs

## Security Best Practices

1. **Never commit API tokens** - Use trusted publishing instead
2. **Use environment protection rules** - Require approval for production releases
3. **Pin action versions** - Use exact versions like `@v4` not `@main`
4. **Review dependencies** - Run `pip-audit` before releases

## Useful Links

- [PyPI Project Page](https://pypi.org/project/obskit/)
- [TestPyPI Project Page](https://test.pypi.org/project/obskit/)
- [PyPI Trusted Publishing Docs](https://docs.pypi.org/trusted-publishers/)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
