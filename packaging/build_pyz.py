"""Monta dist/ficha.pyz: o ficha inteiro num arquivo só, roda com `python3 ficha.pyz`.
No Linux não precisa de mais nada (só a biblioteca padrão)."""

import os
import shutil
import tempfile
import zipapp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", "ficha.pyz")
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copytree(os.path.join(ROOT, "ficha"), os.path.join(tmp, "ficha"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        zipapp.create_archive(tmp, out, interpreter="/usr/bin/env python3",
                              main="ficha.__main__:main", compressed=True)
    print(out)


if __name__ == "__main__":
    main()
