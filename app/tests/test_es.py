from ..utils.oai_utils import get_oai_client, generate_embedding
from ..utils.endpoint_utils import get_es_client, es_search


def test_es_search():
    test_stack = (
        "at onAddToCart (webpack-internal:///(app-client)/./components/info.tsx:21:19)"
    )
    test_embedding = generate_embedding(test_stack, 512)
    query = {
        "knn": {
            "field": "stacktrace-vector",
            "query_vector": test_embedding,
            "k": 1,
            "num_candidates": 1,
        },
        "fields": ["title"],
    }

    try:
        response = es_search(index="incidents-index", query=query)
        id = response["hits"]["hits"][0]["_id"]
    except Exception as e:
        print(f"ES search Error: {e}")

    assert id == "PM-20240202-002", "Retutnrd unexpected ID, ES vector seach failed!"
