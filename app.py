import logging

from src.rag_pipeline import RAGPipeline


logging.basicConfig(
    level=logging.INFO,
    format=" %(asctime)s - %(levelname)s - %(name)s - %(message)s ",
)

logger = logging.getLogger(__name__)

def main()->None:
    pipeline = RAGPipeline(
        data_dir="data",
        persist_directory="storage/chroma",
        collection_name="research_papers",
        top_k=5,
    )

    pipeline.ingest_documents()

    print("\nAI  Research Assistant is ready.")
    print("Type your question. Type 'exit' to quit.\n")

    while True:
        question = input("Ask: ").strip()

        if question.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not question:
            print("Plese enter a valid question.")
            continue


        answer=pipeline.query(question)

        print("\n Answer")
        print(answer)
        print("_"*80)


if __name__ == "__main__":
    main()
