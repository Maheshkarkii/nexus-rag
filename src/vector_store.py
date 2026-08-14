import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List

import chromadb
import numpy as np
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class ChromaVectorStoreService:
    """
    Service class for storing and retrieving document chunks using ChromaDB.
    """

    def __init__(
        self,
        persist_directory: str = "storage/chroma",
        collection_name: str = "research_paper",
    ):
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name

        try:
            self.persist_directory.mkdir(parents=True, exist_ok=True)

            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory)
            )

            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "Research paper chunks for AI Research Assistant"
                },
            )

            logger.info(
                f"Connected to ChromaDB collection: {self.collection_name}"
            )

        except Exception as e:
            logger.exception("Failed to initialize ChromaDB")
            raise RuntimeError(f"Failed to initialize ChromaDB: {e}") from e

    def add_documents(
        self,
        documents: List[Document],
        embeddings: np.ndarray,
    ) -> None:
        """
        Store document chunks, embeddings, and metadata in ChromaDB.
        """

        if not documents:
            raise ValueError("No documents provided to store.")

        if len(documents) != len(embeddings):
            raise ValueError(
                "Number of documents and embeddings must match."
            )

        ids: List[str] = []
        texts: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        embedding_list: List[List[float]] = []

        for index, (doc, embedding) in enumerate(zip(documents, embeddings)):
            doc_id = f"chunk_{uuid.uuid4().hex[:12]}_{index}"

            ids.append(doc_id)
            texts.append(doc.page_content)
            metadatas.append(doc.metadata)
            embedding_list.append(embedding.tolist())

        try:
            self.collection.add(
                ids=ids,
                documents=texts,
                metadatas=metadatas,
                embeddings=embedding_list,
            )

            logger.info(
                f"Stored {len(documents)} document chunks in ChromaDB"
            )

        except Exception as e:
            logger.exception("Failed to add documents to ChromaDB")
            raise RuntimeError(
                f"Failed to add documents to ChromaDB: {e}"
            ) from e

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Search most similar chunks using a query embedding.
        """

        if query_embedding is None:
            raise ValueError("Query embedding cannot be None.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than 0.")

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            logger.info(
                f"Retrieved top {top_k} results from ChromaDB"
            )

            return results

        except Exception as e:
            logger.exception("Failed to search ChromaDB")
            raise RuntimeError(f"Failed to search ChromaDB: {e}") from e

            






