from pathlib import Path
from typing import List,Optional
import logging


from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

logger= logging.getLogger(__name__)

class PDFLoaderService:
    """
    Service class fro loading PDF researchpaper into Langchain Document objects.
    """
    def __init__(self, data_dir:str):
        self.data_dir= Path(data_dir)

        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data Directory not found: {self.data_dir}")
        
        if not self.data_dir.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {self.data_dir}")
        
    def load_single_pdf(self,file_path:Path) -> List[Document]:
        """
        Load a singl pdf file.

        args:
        file_path: path to the PDF file.

        return:
        list of langchian Document object.
        """

        if not file_path.exists():
            raise FileNotFoundError(f"Pdf file not found: {file_path}")
        
        if file_path.suffix.lower() != ".pdf" :
            raise ValueError (f"Invalid file type: {file_path.suffix}. Only PDF supported.")
        
        try:
            logger.info(f"Loading PDF: {file_path.name}")

            loader=PyPDFLoader(str(file_path))
            documents=loader.load()

            for doc in documents:
                doc.metadata['file_name']= file_path.name
                doc.metadata['file_path']=str(file_path)
                doc.metadata['file_type']="pdf"
            
            logger.info(f"Loaded {len(documents)} pages from{file_path.name}")

            return documents
        
        except Exception as e:
            logger.exception(f"Failed to loadm PDF: {file_path.name}")
            raise RuntimeError(f"Fail to laod PDF {file_path.name}: {e}") from e
        
    def load_all_pdfs(self, limit:Optional[int]=None)-> List[Document]:
        """
        load all pdf files from the data dorectory.

        args:
            limit:optional maximun number of pdf to load.

        return:
            list of langchain document objects.
        """

        pdf_files=sorted(self.data_dir.glob('**/*.pdf'))

        if limit:
            pdf_files= pdf_files[:limit]

        if not pdf_files:
            logger.warning(f"NO PDF files found in {self.data_dir}")
            return[]
        
        all_documents:list[Document]=[]
        
        for pdf_file in pdf_files:
            documents=self.load_single_pdf(pdf_file)
            all_documents.extend(documents)

        logger.info(f"Total  loaded documents/pages:{len(all_documents)}")

        return all_documents


