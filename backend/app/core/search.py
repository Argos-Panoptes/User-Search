from typing import Any
from opensearchpy import OpenSearch
from app.core.config import settings
from app.core.logging import logger


def get_opensearch_client() -> OpenSearch:
    """
    Returns a configured OpenSearch client.
    """
    client = OpenSearch(
        settings.OPENSEARCH_URL,
    )
    return client


def create_index_if_not_exists(
    client: OpenSearch, index_name: str, mapping: dict[str, Any] | None = None
):
    """
    Creates an index if it doesn't exist.
    """
    if not client.indices.exists(index=index_name):
        logger.info(f"Creating OpenSearch index: {index_name}")
        body = {}
        if mapping:
            body["mappings"] = mapping

        client.indices.create(index=index_name, body=body)
    else:
        logger.info(
            f"OpenSearch index {index_name} already exists. Updating mapping..."
        )
        if mapping:
            try:
                client.indices.put_mapping(index=index_name, body=mapping)
            except Exception as e:
                logger.warning(
                    f"Could not update mapping for {index_name}: {e}. Some changes (like doc_values) may require re-indexing."
                )


def search_index(
    client: OpenSearch,
    index_name: str,
    query: dict[str, Any],
    size: int = 100,
    from_: int = 0,
) -> list[dict[str, Any]]:
    """
    Executes a search query against the specified index and returns the source of hits.
    """
    try:
        # Add pagination to body
        query["size"] = size
        query["from"] = from_

        response = client.search(
            body=query,
            index=index_name,
        )
        hits = response["hits"]["hits"]
        return [hit["_source"] for hit in hits]
    except Exception as e:
        logger.error(f"Error searching index {index_name}: {e}")
        return []


def search_index_with_total(
    client: OpenSearch,
    index_name: str,
    query: dict[str, Any],
    size: int = 100,
    from_: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """
    Executes a search query and returns (hits_sources, total_count).
    Enables track_total_hits for accurate counts.
    """
    try:
        query["size"] = size
        query["from"] = from_
        query["track_total_hits"] = True

        response = client.search(
            body=query,
            index=index_name,
        )
        hits = response["hits"]["hits"]
        total = response["hits"]["total"]
        total_count = total["value"] if isinstance(total, dict) else int(total)
        return [hit["_source"] for hit in hits], total_count
    except Exception as e:
        logger.error(f"Error searching index {index_name}: {e}")
        return [], 0
