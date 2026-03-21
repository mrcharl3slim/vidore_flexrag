from flexrag.retriever import FlexRetriever

RETRIEVER_PATH = "data/processed/vidore_flexrag_retriever"

def main():
    retriever = FlexRetriever.load_from_local(RETRIEVER_PATH)

    query = "What is the difference between volatile and non-volatile memory?"
    passages = retriever.search(query, top_k=3)[0]

    for i, p in enumerate(passages, start=1):
        print("=" * 80)
        print(f"Result {i}")
        print("ID:", p.context_id)
        print("Title:", p.data.get("title"))
        print("Page:", p.data.get("page_number"))
        print("Text:", p.data.get("text", "")[:800])

if __name__ == "__main__":
    main()