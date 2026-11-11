"""Optional Elastic lexical/vector retrieval; SQL remains business authority."""

import os
from urllib.parse import quote

import httpx


class SearchUnavailable(Exception):
    pass


def embedding(text, task):
    if os.getenv("PAYPOOL_EMBEDDINGS_ENABLED", "false") != "true":
        return None
    from google import genai
    from google.genai import types

    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise SearchUnavailable("Embedding credentials are not configured")
    try:
        result = genai.Client(api_key=key).models.embed_content(
            model=os.getenv("PAYPOOL_EMBEDDING_MODEL", "gemini-embedding-001"),
            contents=text,
            config=types.EmbedContentConfig(task_type=task, output_dimensionality=768),
        )
        values = result.embeddings[0].values
        if len(values) != 768:
            raise SearchUnavailable(
                "Embedding dimensionality does not match the search index"
            )
        return values
    except SearchUnavailable:
        raise
    except Exception as error:
        raise SearchUnavailable("Embedding service is unavailable") from error


class ElasticSearch:
    def __init__(self):
        self.base = os.getenv("ELASTICSEARCH_URL", "").rstrip("/")
        self.index = "paypool-products-v1"
        self.headers = (
            {"Authorization": "ApiKey " + os.getenv("ELASTICSEARCH_API_KEY")}
            if os.getenv("ELASTICSEARCH_API_KEY")
            else {}
        )

    def call(self, method, path, payload=None):
        if not self.base:
            raise SearchUnavailable("External search is not configured")
        try:
            response = httpx.request(
                method, self.base + path, headers=self.headers, json=payload, timeout=10
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except (httpx.HTTPError, ValueError) as error:
            raise SearchUnavailable(
                "External search is unavailable; catalog authority remains in SQL"
            ) from error

    def index_product(self, product):
        # Create an index once; tolerate only the expected concurrent-create
        # collision, rather than hiding arbitrary mapping/provider errors.
        try:
            response = httpx.request(
                "PUT",
                self.base + "/" + self.index,
                headers=self.headers,
                json={
                    "mappings": {
                        "properties": {
                            "text": {"type": "text"},
                            "embedding": {
                                "type": "dense_vector",
                                "dims": 768,
                                "similarity": "cosine",
                            },
                            "seller_id": {"type": "keyword"},
                        }
                    }
                },
                timeout=10,
            )
            if (
                response.status_code >= 400
                and response.json().get("error", {}).get("type")
                != "resource_already_exists_exception"
            ):
                response.raise_for_status()
        except (httpx.HTTPError, ValueError) as error:
            raise SearchUnavailable("Search index initialization failed") from error
        # PUT mapping is idempotent, and may extend the mapping of an already
        # created dynamic index. Indexing never includes buyer identity/location.
        self.call(
            "PUT",
            f"/{self.index}/_mapping",
            {
                "properties": {
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 768,
                        "similarity": "cosine",
                    },
                    "seller_id": {"type": "keyword"},
                }
            },
        )
        text = (
            product["title"]
            + " "
            + product.get("description", "")
            + " "
            + str(product.get("attributes", {}))
        )
        document = {
            "text": text,
            "seller_id": product["seller_id"],
            "active": product.get("active", True),
        }
        vector = embedding(text, "RETRIEVAL_DOCUMENT")
        if vector:
            document["embedding"] = vector
        self.call(
            "PUT", f"/{self.index}/_doc/{quote(product['id'], safe='')}", document
        )

    def rank(self, query, eligible_ids):
        filters = [{"ids": {"values": eligible_ids}}]
        lexical = self.call(
            "POST",
            f"/{self.index}/_search",
            {
                "size": 100,
                "query": {
                    "bool": {"filter": filters, "must": [{"match": {"text": query}}]}
                },
            },
        )
        rankings = [[hit["_id"] for hit in lexical["hits"]["hits"]]]
        vector = embedding(query, "RETRIEVAL_QUERY")
        if vector:
            semantic = self.call(
                "POST",
                f"/{self.index}/_search",
                {
                    "size": 100,
                    "knn": {
                        "field": "embedding",
                        "query_vector": vector,
                        "k": 100,
                        "num_candidates": 200,
                        "filter": {"bool": {"filter": filters}},
                    },
                },
            )
            rankings.append([hit["_id"] for hit in semantic["hits"]["hits"]])
        scores = {}
        for ranking in rankings:
            for index, sku in enumerate(ranking, 1):
                if sku in eligible_ids:
                    scores[sku] = scores.get(sku, 0) + 1 / (60 + index)
        return sorted(
            scores, key=lambda sku: (-scores[sku], sku)
        ), "elastic-hybrid-rrf" if vector else "elastic-keyword"


def ranked(query, products):
    if not query:
        return products, "catalog", None
    if os.getenv("ELASTICSEARCH_URL"):
        try:
            ids, engine = ElasticSearch().rank(query, [p["id"] for p in products])
            indexed = {p["id"]: p for p in products}
            return [indexed[sku] for sku in ids if sku in indexed], engine, None
        except SearchUnavailable:
            warning = "External search unavailable; showing explicit keyword fallback"
    else:
        warning = None
    words = query.casefold().split()
    matches = [
        p
        for p in products
        if all(
            w
            in (
                p["title"]
                + " "
                + p.get("description", "")
                + " "
                + str(p.get("attributes", {}))
            ).casefold()
            for w in words
        )
    ]
    return matches, "keyword", warning
