import logging
from typing  import Any, Dict, List


logger= logging.getLogger(__name__)

class PromptBuilderService:
    """
    Service responsible for building prompts for LLM
    using retrieved coontext and the user query.
    """

    DEFULT_SYSTEM_INSTRUCTION="""
    You are an AI  Research Assistant.

    use only the provided contect to answer the user's question,
    If the answer is not present in the context, say:
    "I don't know based on the provided documents."

    Be clear, consise, and cite the source information when available.
""".strip()
    
    def __init__(self,system_instruction:str| None =None):
        self.system_instruction=(
            system_instruction or self.DEFULT_SYSTEM_INSTRUCTION
        )

    def __extract_documents(self,retrieval_results: Dict[str, Any])-> List[str]:
        """
        Extract documents texts from chromaBD retrieval results.

        """


        documents=retrieval_results.get("documents")

        if not documents or not documents[0]:
            logger.warning("No retrieved documents found.")
            return[]
        
        return documents[0]
    
    def _extract_metadatas(self,retrival_results: Dict[str,Any])-> List[Dict[str,Any]]:
        metadatas = retrival_results.get("metadatas")

        if not metadatas or not metadatas[0]:
            logger.warning("No retrieved metadata foud.")
            return[]
        return metadatas[0]
    
    def build_context(self,retrieval_results: Dict[str,Any])-> str:
        """
        Combine retrived chunks into a single context string.
        """

        documents= self.__extract_documents(retrieval_results)
        metadatas =self._extract_metadatas(retrieval_results)

        if not documents:
            return ""
            
        context_blocks=[]

        for index,document in enumerate(documents, start=1):
            metadata = metadatas[index -1] if  index -1 < len(metadatas) else {}

            source=metadata.get("Source","Unknown source")
            page = metadata.get("Page","Unknown Page")    

            citation_id =f"[S{index}]"   

            block = f"""
            {citation_id}
            source: {source}
            page: {page}
            
            content:
            {document}
            """.strip()

            context_blocks.append(block)

            context="\n\n---\n\n".join(context_blocks)

        logger.info(f"Build context from {len(documents)} retrieved chunks")

        return context 
    
    def build_prompt(
            self,
            query:str,
            retrieval_results:Dict[str, Any],
    )-> str:
        """
        Build final prompt for LLM.
        """

        if not query or not query.strip():
            raise ValueError ("Query cannot be empty.")
        
        context=self.build_context(retrieval_results)

        if not context:
            logger.warning("Building prompt without context.")

        prompt=f"""

{self.system_instruction} 

context: 
{context}

question:
{query}

Answer:

""".strip()
        
        logger.info("prompt built successfully")

        return prompt
        



