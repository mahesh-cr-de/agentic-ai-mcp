"""Legacy shim so ``pip install -e .`` and packaging tools that still probe
for ``setup.py`` work; all real metadata lives in ``pyproject.toml``
(PEP 621).
"""

from setuptools import setup

if __name__ == "__main__":
    setup()
