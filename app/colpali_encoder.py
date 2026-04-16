"""
ColPali encoder compatible with FlexRAG's EncoderBase interface.

Uses colpali-engine to load ColPali (vidore/colpali-v1.2), which handles the
LoRA adapter loading on top of PaliGemma automatically.

ColPali produces multi-vector embeddings (one per image patch / text token).
We mean-pool them to a single vector so it fits FlexRAG's FAISS index pipeline.
This is a single-vector approximation — it loses full late-interaction MaxSim
scoring but still uses ColPali's document-aware vision-language backbone, which
far outperforms general-purpose CLIP on document page retrieval.

Note: EncoderConfig's pydantic validator only accepts FlexRAG's built-in types,
so ColPaliEncoder must be injected directly onto FaissIndex instances rather
than passed through EncoderConfig. See build_colpali_index.py.
"""

import numpy as np
import torch
import torch.nn.functional as F
from PIL.Image import Image as PILImage

from colpali_engine.models import ColPali, ColPaliProcessor

from flexrag.models.model_base import EncoderBase, EncoderBaseConfig
from flexrag.utils import configure


@configure
class ColPaliEncoderConfig(EncoderBaseConfig):
    """Configuration for ColPaliEncoder.

    :param model_path: HuggingFace model path. Default: vidore/colpali-v1.2
    :param device: torch device string. Default: cpu
    :param normalize: Whether to L2-normalise embeddings. Default: True
    """
    model_path: str = "vidore/colpali-v1.2"
    device: str = "cpu"
    normalize: bool = True


class ColPaliEncoder(EncoderBase):
    """FlexRAG encoder wrapping ColPali with mean-pooled single-vector output."""

    def __init__(self, cfg: ColPaliEncoderConfig):
        super().__init__(cfg)
        self.device = torch.device(cfg.device)
        self.normalize = cfg.normalize

        print(f"Loading ColPali: {cfg.model_path} ...")
        self.model = ColPali.from_pretrained(
            cfg.model_path,
            torch_dtype=torch.bfloat16,
        ).to(self.device).eval()
        self.processor = ColPaliProcessor.from_pretrained(cfg.model_path)
        print("ColPali loaded.")

    @torch.no_grad()
    def encode_image(self, images: list[PILImage]) -> np.ndarray:
        inputs = self.processor.process_images(images)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        embeddings = self.model(**inputs)  # (batch, n_patches, dim)
        emb = embeddings.float().mean(dim=1)  # mean pool → (batch, dim)
        if self.normalize:
            emb = F.normalize(emb, dim=-1)
        return emb.cpu().numpy()

    @torch.no_grad()
    def encode_text(self, texts: list[str]) -> np.ndarray:
        inputs = self.processor.process_queries(queries=texts)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        embeddings = self.model(**inputs)  # (batch, seq_len, dim)
        emb = embeddings.float().mean(dim=1)
        if self.normalize:
            emb = F.normalize(emb, dim=-1)
        return emb.cpu().numpy()

    def _encode(self, data: list) -> np.ndarray:
        if isinstance(data[0], str):
            return self.encode_text(data)
        return self.encode_image(data)

    @property
    def embedding_size(self) -> int:
        return self.model.config.hidden_size
