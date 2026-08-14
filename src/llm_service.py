import logging
import os

from dotenv import load_dotenv
from groq import Groq

logger=logging.getLogger(__name__)


class LLMService:
    """
    Service responsible for generating answers using  Groq.
    """

    def __init__(self, model_name:str="llama-3.3-70b-versatile"):
        
        load_dotenv()

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found in environment variable."
            )
        
        self.client= Groq(api_key=api_key)
        self.model_name=model_name

        logger.info(
            f"Initialized groq model: {self.model_name}"
        )

    def generate_answer(self,prompt:str)-> str:

        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role":"user",
                        "content":prompt,
                    }
                ],
                temperature=0.2
            )

            answer = response.choices[0].message.content

            logger.info("LLM response generated successfully.")
            
            return answer
        
        except Exception as e:
            logging.exception("Failed t generate response from Groq")
            
            raise RuntimeError(f"Failed to generate response: {e}") from e
        
        


        