"""Entrypoint shim.

The Dockerfile and any external caller invokes ``python app.py``; we
forward to ``core.__main__:main``. All logic lives under ``core/``.
"""

from core.__main__ import main


if __name__ == "__main__":
    main()