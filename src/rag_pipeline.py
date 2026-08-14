import logging
from typing import Any, List, Dict

from langchain_core.documents import Document

from src.loader import PDFLoaderService
from src.embeddings import EmbeddingService
from src.splitter import DocumentSplitterService
from src.vector_store import ChromaVectorStoreService
from src.retriver import RetrieverService
from src.prompt_builder import PromptBuilderService
from src.llm_service import LLMService

logger=logging.getLogger(__name__)

class RAGPipeline:
    """
    End-to-end RAG pipeline for the AI research Assistant.
    """
    def __init__(
            self,
            data_dir:str="data",
            persist_directory:str="storage/chroma",
            collection_name:str="research_paper",
            chunk_size : int =1000,
            chunk_overlap :int=200,
            top_k:int=5,
            
    ):
        self.data_dir = data_dir
        self.top_k = top_k

        self.loader= PDFLoaderService(data_dir=data_dir)

        self.splitter= DocumentSplitterService(
            chunk_size= chunk_size,
            chunk_overlap=chunk_overlap
        )

        self.embedding_service = EmbeddingService()

        self.vector_store= ChromaVectorStoreService(
            persist_directory=persist_directory,
            collection_name=collection_name,
        )

        self.retriever=RetrieverService(
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
            top_k=top_k,
        )

        self.prompt_builder=PromptBuilderService()

        self.llm_service =LLMService()

        logger.info("RAG Pipeline Initilized successfully.")

    def ingest_documents(self)->None :
        """
        load, split, embed, and store documents in the vector databsae.
        """

        documents: List[Document] = self.loader.load_all_pdfs()

        if not documents:
            raise ValueError("No documents found for ingestions")
        
        chunks= self.splitter.split_documents(documents)

        if not chunks:
            raise ValueError("No Chunks created from documents")
        
        embeddings=self.embedding_service.embed_documents(chunks)

        if len(chunks) != len(embeddings):
            raise ValueError("Numbers of chunks and embeddings must match")
        
        self.vector_store.add_documents(
            documents=chunks,
            embeddings=embeddings,

        )

        logger.info(
            f"Ingestion complete: {len(documents)} documents, {len(chunks)} chunks"
        )

    def retrieve(self,query:str) -> Dict[str,Any]:
        """
        Retrieve relevent chunks forna query.
        """

        return self.retriever.retrieve(query)

    def query( self, query: str)-> str:
        """"
        Run full RAG query flow:
        query-> retriver -> prompt -> LLM answer
        """

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")
        
        retrieval_results=self.retrieve(query)

        prompt = self.prompt_builder.build_prompt(
            query=query,
            retrieval_results= retrieval_results
        )

        answer = self.llm_service.generate_answer(prompt)
        sources = self._format_sources(retrieval_results)

        logger.info("RAG query completed successfully")

        return {
            "answer": answer,
            "sources": sources
        }

    def _format_sources(self, retrieval_results:Dict[str,Any])-> List[Dict[str,Any]]:
        """
        Format retrieved metadata into citation sources.
        """

        sources=[]
        metadatas = retrieval_results.get("metadatas", [[]])[0]

        for index, metadata in enumerate (metadatas, start=1):
            sources.append(
                {
                    "citation":f"[S{index}]",
                    "source": metadata.get("source", "unknown source"),
                    "page":metadata.get("page","Unknown page")
                }
            )

        return sources 


