"""Ler arquivos fechando na hora (open(...).read() deixa o arquivo aberto até o GC)."""


def read_text(path, newline=None, encoding="utf-8"):
    """newline="" preserva \\r\\n como está no arquivo."""
    with open(path, newline=newline, encoding=encoding) as f:
        return f.read()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()
