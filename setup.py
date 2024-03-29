"""
This is a file to describe the Python module distribution and
helps with installation.

More info on various arguments here:
https://setuptools.readthedocs.io/en/latest/setuptools.html
"""
from setuptools import setup, find_packages
from subprocess import check_output


def get_version():
    # https://github.com/uc-cdis/dictionaryutils/pull/37#discussion_r257898408
    try:
        tag = check_output(
            ["git", "describe", "--tags", "--abbrev=0", "--match=[0-9]*"]
        )
        return tag.decode("utf-8").strip("\n")
    except Exception:
        raise RuntimeError(
            "The version number cannot be extracted from git tag in this source "
            "distribution; please either download the source from PyPI, or check out "
            "from GitHub and make sure that the git CLI is available."
        )


setup(
    name="gen3config",
    version=get_version(),
    description="Gen3 Configuration Library",
    url="https://github.com/uc-cdis/gen3config",
    license="Apache",
    packages=find_packages(),
    install_requires=[
        "cdiserrors",
        "cdislogging",
        "jinja2",
        "PyYAML",
        "six",
    ],
)
