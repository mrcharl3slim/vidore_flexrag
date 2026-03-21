from app.vidore_assistant import VidoreAssistant, VidoreAssistantConfig

def main():
    assistant = VidoreAssistant(
        VidoreAssistantConfig(
            retriever_path="data/processed/vidore_flexrag_retriever",
            used_indexes=["bm25", "dense"],
            model_name="qwen2:latest",
            ollama_base_url="http://127.0.0.1:11434",
            top_k=3,
        )
    )

    questions = [
        "What is the difference between volatile and non-volatile memory?",
        "How does a cache hit differ from a cache miss?",
        "What is the memory hierarchy in computer systems?",
    ]

    for q in questions:
        print(f"Q: {q}")
        print(f"A: {assistant.answer(q)}\n")

if __name__ == "__main__":
    main()
