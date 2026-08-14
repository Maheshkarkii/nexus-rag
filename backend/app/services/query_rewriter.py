import logging
from typing import Any, Dict, List, Optional

from app.services.llm import LLMService

logger = logging.getLogger("ai_research_assistant.services.query_rewriter")


class ConversationQueryRewriter:
    """Reformulates multi-turn conversational follow-up questions into standalone retrieval queries."""

    async def rewrite(
        self,
        messages: List[Dict[str, Any]],
        current_query: str,
        llm_service: LLMService,
    ) -> str:
        """Analyze message history and current question, rewriting references to standalone search terms."""
        if not messages:
            return current_query.strip()

        # Build prompt with history details
        history_lines = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            content = msg["content"]
            history_lines.append(f"[{role}]: {content}")

        history_str = "\n".join(history_lines)

        system_prompt = (
            "You are an expert search query reformulation assistant.\n"
            "Your task is to rewrite the user's latest question into a standalone research query using the conversation history.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Output ONLY the rewritten standalone research query. Do not include any explanations, introduction, prefix, or markdown tags.\n"
            "2. Resolve all pronouns (like 'it', 'they', 'their', 'this', 'that') and conversational references to the exact entities discussed in the history.\n"
            "3. If the user question is already a complete, standalone question that does not need references resolved, output it exactly as-is.\n"
            "4. Do NOT attempt to answer the user's question. Focus solely on producing a standalone query suitable for document vector search."
        )

        user_prompt = (
            "Conversation History:\n"
            f"{history_str}\n\n"
            f"User's Latest Question: {current_query.strip()}\n\n"
            "Rewritten Standalone Query:"
        )

        try:
            rewritten = await llm_service.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            rewritten_clean = rewritten.strip()
            
            # Basic sanity checks on rewritten query
            if not rewritten_clean:
                logger.warning("Query rewriter returned empty response. Falling back to original query.")
                return current_query.strip()

            logger.info(f"Query reformulated: '{current_query.strip()}' -> '{rewritten_clean}'")
            return rewritten_clean

        except Exception as exc:
            logger.error(f"Query rewriter LLM call failed: {exc}. Falling back to original query.")
            return current_query.strip()

    def classify_intent(self, query: str, history: Optional[List[Dict[str, Any]]] = None) -> str:
        """Classify conversational query intent."""
        q_lower = query.strip().lower()

        if any(w in q_lower for w in ["thanks", "thank you", "hello", "hi", "good morning"]):
            return "general_conversation"
        elif any(w in q_lower for w in ["regenerate", "make the section", "shorter", "add more evidence to", "edit section"]):
            return "report_request"
        elif any(w in q_lower for w in ["compare", "versus", "vs", "difference between"]):
            return "comparison"
        elif any(w in q_lower for w in ["summarize", "summary", "overview"]):
            return "summarization"
        elif any(w in q_lower for w in ["why", "how come", "explain further", "which one", "the second paper", "this paper"]):
            return "follow_up"
        return "direct_answer"

    def needs_retrieval(self, intent: str, query: str) -> bool:
        """Determine whether a message requires document retrieval."""
        if intent == "general_conversation":
            return False
        q_lower = query.strip().lower()
        if len(q_lower.split()) <= 2 and any(w in q_lower for w in ["thanks", "ok", "okay", "got it", "cool"]):
            return False
        return True


# Singleton rewriter instance
default_query_rewriter = ConversationQueryRewriter()


def get_query_rewriter() -> ConversationQueryRewriter:
    """Dependency injection target for FastAPI."""
    return default_query_rewriter
