"""Human-editable clinical-semantic context for EMBED data."""

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    """The installed distribution's version."""
    try:
        return version("embed-context")
    except PackageNotFoundError:
        return "0+unknown"
