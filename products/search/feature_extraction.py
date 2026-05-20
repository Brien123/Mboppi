import os
import torch
import logging
from PIL import Image
import requests
from io import BytesIO
from sentence_transformers import SentenceTransformer

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_OFFLINE"] = "1" 
os.environ["TOKENIZERS_PARALLELISM"] = "false"

logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

try:
    _GLOBAL_MODEL = SentenceTransformer('clip-ViT-B-32', device=DEVICE)
except Exception:
    os.environ["HF_HUB_OFFLINE"] = "0"
    _GLOBAL_MODEL = SentenceTransformer('clip-ViT-B-32', device=DEVICE)

class CLIPFeatureExtractor:
    def encode_text(self, text: str) -> list:
        if not text:
            return []
        embedding = _GLOBAL_MODEL.encode(text, show_progress_bar=False)
        return embedding.tolist()

    def encode_image(self, image_source) -> list:
        try:
            if isinstance(image_source, str):
                if image_source.startswith(('http://', 'https://')):
                    response = requests.get(image_source, timeout=5)
                    img = Image.open(BytesIO(response.content))
                else:
                    img = Image.open(image_source)
            else:
                img = Image.open(image_source)
            
            if img.mode != 'RGB':
                img = img.convert('RGB')

            embedding = _GLOBAL_MODEL.encode(img, show_progress_bar=False)
            return embedding.tolist()
        except Exception:
            return []