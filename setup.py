from setuptools import setup
import re


def derive_version() -> str:
    version = ''
    with open('src/async_pcloud/__init__.py') as f:
        version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE)
        if version:
            version = version.group(1)
        else:
            raise RuntimeError('Cannot find version')

    if not version:
        raise RuntimeError('version is not set')

    return version


setup(version=derive_version())
