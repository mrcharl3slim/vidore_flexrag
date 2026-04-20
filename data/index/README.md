---
language: en
library_name: FlexRAG
tags:
- FlexRAG
- retrieval
- search
- lexical
- RAG
---

# FlexRAG Retriever

This is a FlexRetriever created with the [`FlexRAG`](https://github.com/ictnlp/flexrag) library (version `{version}`).

## Installation

You can install the `FlexRAG` library with `pip`:

```bash
pip install flexrag
```

## Loading a `FlexRAG` retriever

You can use this retriever for information retrieval tasks. Here is an example:

```python
from flexrag.retriever import LocalRetriever


# Load the retriever from the HuggingFace Hub
retriever = LocalRetriever.load_from_hub("")


# You can retrieve now
results = retriever.search("Who is Bruce Wayne?")
```

FlexRAG Related Links:
* 📚[Documentation](https://flexrag.readthedocs.io/en/latest/)
* 💻[GitHub Repository](https://github.com/ictnlp/flexrag)