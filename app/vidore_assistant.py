import requests

from flexrag.assistant import ASSISTANTS, AssistantBase
from flexrag.retriever import FlexRetrieverConfig, FlexRetriever
from flexrag.prompt import ChatPrompt, ChatTurn
from flexrag.utils import configure

@configure
class VidoreAssistantConfig(FlexRetrieverConfig):
    model_name: str = "qwen2:latest"
    ollama_base_url: str = "http://127.0.0.1:11434"
    top_k: int = 3

@ASSISTANTS("vidore_simple", config_class=VidoreAssistantConfig)
class VidoreAssistant(AssistantBase):
    def __init__(self, config: VidoreAssistantConfig):
        self.retriever = FlexRetriever(config)
        self.model_name = config.model_name
        self.ollama_base_url = config.ollama_base_url.rstrip("/")
        self.top_k = config.top_k

    def _generate(self, prompt: str) -> str:
        r = requests.post(
            f"{self.ollama_base_url}/api/generate",
            json={
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
            },
            timeout=300,
        )
        r.raise_for_status()
        return r.json()["response"].strip()

    def answer(self, question: str) -> str:
        prompt = ChatPrompt()
        contexts = self.retriever.search(question, top_k=self.top_k)[0]

        prompt_str = "Please answer the following question based only on the given contexts.\n\n"
        prompt_str += f"Question: {question}\n\n"
        for i, ctx in enumerate(contexts, start=1):
            prompt_str += f"Context {i}: {ctx.data.get('text', '')}\n\n"
        prompt_str += "If the answer is not supported, say 'Insufficient evidence.'"

        prompt.update(ChatTurn(role="user", content=prompt_str))
        response = self._generate(prompt_str)
        prompt.update(ChatTurn(role="assistant", content=response))
        return response
