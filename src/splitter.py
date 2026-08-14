from typing import List
import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger=logging.getLogger(__name__)


class DocumentSplitterService:
    """
    Service responsible for splitting documents into chunks.
    """

    def __init__( self, chunk_size: int = 1000, chunk_overlap: int = 200):

        self.chunk_size= chunk_size
        self.chunk_overlap= chunk_overlap

        self.splitter=RecursiveCharacterTextSplitter (
            chunk_size= chunk_size,
            chunk_overlap = chunk_overlap
            )
        
    def split_documents(
            self,
            documents:List[Document] 
        ) -> List[Document]:
        """
        split langchain documents into chunks
        """

        chunks= self.splitter.split_documents(documents)

        logger.info(
            f"Created {len(chunks)} chunks "
            f"from {len(documents)} documents"
                    )
        
        return chunks



    