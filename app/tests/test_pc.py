from pinecone import Pinecone
from dotenv import find_dotenv, dotenv_values

from ..utils import oai_utils

config = dotenv_values(find_dotenv())

pc = Pinecone(api_key=config["PC_API_KEY"])
pc_index = pc.Index("postmortem")

test_stack = "at onAddToCart (webpack-internal:///(app-client)/./components/info.tsx:21:19)"
test_embedding = oai_utils.generate_embedding(test_stack)
print(test_embedding)

query_response = pc_index.query(
    namespace='stack_trace_embedding',
    vector=test_embedding,
    top_k=3,
    include_metadata=True,

)

print(query_response)
