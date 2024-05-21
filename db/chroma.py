# https://docs.trychroma.com/

import chromadb
from chromadb.utils import embedding_functions

# Configure Chroma to save and load from your local machine. Data will be persisted automatically
# and loaded on start (if it exists).
client = chromadb.PersistentClient(path="/storage")

