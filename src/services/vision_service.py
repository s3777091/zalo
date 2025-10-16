import io
import logging
import base64
from typing import Optional
from dataclasses import dataclass

import httpx
from PIL import Image
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from src.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
DEFAULT_MAX_SIDE = 1024  # pixels


def _ext_from_url(url: str) -> str:
    """Extracts a supported image extension from a URL."""
    q = url.split('?', 1)[0]
    for ext in SUPPORTED_EXT:
        if q.lower().endswith(ext):
            return ext
    return ''


def _resize_image(img: Image.Image, max_side: int = DEFAULT_MAX_SIDE) -> Image.Image:
    """Resizes an image to have its longest side equal to max_side."""
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    if w >= h:
        new_w = max_side
        new_h = int(h * (max_side / w))
    else:
        new_h = max_side
        new_w = int(w * (max_side / h))
    return img.resize((new_w, new_h), Image.LANCZOS)


def _to_base64(img: Image.Image, ext: str) -> str:
    """Encodes a PIL Image to a base64 string in the specified format."""
    fmt = 'PNG'
    if ext in ['.jpg', '.jpeg']:
        fmt = 'JPEG'
    elif ext == '.webp':
        fmt = 'WEBP'
    elif ext == '.gif':
        fmt = 'GIF'
    
    # Ensure image is in RGB mode for formats that require it (like JPEG)
    if fmt == 'JPEG' and img.mode != 'RGB':
        img = img.convert('RGB')

    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


@dataclass
class VisionResult:
    success: bool
    description: str
    model: str
    width: int
    height: int
    size_bytes: int
    base64_size: int
    error: Optional[str] = None


class VisionService:
    def __init__(self):
        self._client: Optional[ChatOpenAI] = None

    def _client_lazy(self) -> ChatOpenAI:
        if self._client is None:
            self._client = ChatOpenAI(
                model=settings.vision_model,
                api_key=settings.openai_api_key,
                max_tokens=1500
            )
        return self._client

    async def analyze_image_url(self, image_url: str, prompt: str = "Mô tả chi tiết nội dung hình ảnh") -> VisionResult:
        """
        Analyzes an image from a URL using a vision model.
        """
        try:
            ext = _ext_from_url(image_url)
            if not ext:
                return VisionResult(False, '', settings.vision_model, 0, 0, 0, 0, error='unsupported_extension')

            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                data = resp.content

            size_bytes = len(data)
            img = Image.open(io.BytesIO(data))
            img = img.convert('RGB')
            resized = _resize_image(img)
            b64 = _to_base64(resized, ext)

            llm_client = self._client_lazy()

            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{ext.lstrip('.')};base64,{b64}"}
                    },
                ]
            )
            response = await llm_client.ainvoke([message])
            
            text_out = response.content if response.content else ""

            return VisionResult(
                True,
                text_out,
                settings.vision_model,
                resized.width,
                resized.height,
                size_bytes,
                len(b64)
            )
        except Exception as e:
            logger.error(f"Vision analysis error: {e}", exc_info=True)
            return VisionResult(False, '', settings.vision_model, 0, 0, 0, 0, error=str(e))

vision_service = VisionService()