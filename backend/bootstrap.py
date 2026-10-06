"""Deployment initialization: apply migrations and initialize default standards."""
from alembic import command
from alembic.config import Config
from chromadb.errors import NotFoundError
from backend.rag.ingest import _get_chroma_client, resolve_active_collection, ingest


def main():
    command.upgrade(Config("alembic.ini"), "head")
    client = _get_chroma_client()
    try:
        existing = client.get_collection(resolve_active_collection())
    except NotFoundError:
        ingest()
    else:
        if existing.count() == 0:
            ingest()


if __name__ == "__main__":
    main()
