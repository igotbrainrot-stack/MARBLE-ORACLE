"""Entry point used by PyInstaller for the packaged executable.

Kept outside the package so the frozen program starts exactly like
``python -m oggcultist`` without relying on the working directory.
"""
from oggcultist.startup import main

if __name__ == '__main__':
    main()
