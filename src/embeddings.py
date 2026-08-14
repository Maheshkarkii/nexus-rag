import logging
from typing import List , Any

import numpy as np
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer

logger= logging.getLogger(__name__)


class EmbeddingService:
    """
    Service class for generating embeddings for documents chunks and user queries.

    """
    def __init__(self, model_name:str="all-MiniLM-L6-v2"):
        self.model_name = model_name

        try:
            logger.info(f"Loading embedding model {self.model_name}")
            self.model=SentenceTransformer(self.model_name)
            logger.info("Embedding Model loaded sucessfully ")

        except Exception as e:
            logger.exception(f"Fail to load a embedding model")
            raise RuntimeError (f"Failed to laod embedding mdoel: {e}") from e

    def embed_documents(self ,documents: List[Document]) -> np.ndarray:
        """
        Generate embedding for the lsit of Langchain documents objects.
        """

        if not documents:
            raise ValueError ("No documents provided for embeddings")
        
        texts= [doc.page_content for doc in documents]
        
        try:
            logger.info(f"Generating Embedding for {len(texts)} documents")

            embeddings=self.model.encode(
                texts,
                show_progress_bar=True,
                convert_to_numpy=True,
                normalize_embeddings=True
            )

            logger.info(f"Generated embedding with shape: {embeddings.shape}")

            return embeddings
        
        except Exception as e:
            logger.exception(f"Fail to gernarate documents embeddings")
            raise RuntimeError(f"Failed to generate document embeddings: {e}") from e
        
    def embed_query(self, query:str):
        """
        Generate embeddings for a single user query.
        """
        self.query=query


        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        self.query=query

        try:
            logger.info(f"Generating query Embeddings")
            
            embedding=self.model.encode(
                query,
                convert_to_numpy=True,
                normalize_embeddings=True
            )

            logger.info("Generated query embeddings with :{embedding.shape}")

            return embedding
        
        except Exception as e:
            logger.exception(f"Failed to generate query embeddings")
            raise RuntimeError(f"Failed to gerenrate query embeddings:{e}") from e

        

