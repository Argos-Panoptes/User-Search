import logging
from app.core.search import get_opensearch_client
from app.ingestion.search_indexer import index_groups_from_db, INDEX_GROUPS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def apply_mapping():
    client = get_opensearch_client()

    if client.indices.exists(index=INDEX_GROUPS):
        logger.info(f"Deleting existing index: {INDEX_GROUPS}")
        client.indices.delete(index=INDEX_GROUPS)
    else:
        logger.info(f"Index {INDEX_GROUPS} does not exist.")

    logger.info(
        "Re-indexing groups from DB (this will create index with new mapping)..."
    )
    count = index_groups_from_db(job_id=None)  # None job_id indexes all
    logger.info(f"Indexed {count} groups.")

    # Verify mapping
    mapping = client.indices.get_mapping(index=INDEX_GROUPS)
    logger.info(f"New Mapping: {mapping}")


if __name__ == "__main__":
    apply_mapping()
