import json
import logging
from typing import Any, Dict, List
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from deepagents import create_deep_agent
from src.agent.prompt import INSURANCE_VISION_PROMPT
from src.services.document_parser import DocumentParser
from src.config import settings
from src.services.vision_service import vision_service
logger = logging.getLogger(__name__)


class VisionAgent:
    def __init__(self):
        self.document_parser = DocumentParser(
            recipient_account=settings.recipient_account,
            recipient_name_keywords=["phuong dong insurtech"]
        )
        self.vision_service = vision_service

    async def analyze_image(self, image_url: str) -> Dict[str, Any]:
        logger.info(f"Initial classification result: {image_url}")
        classification_result = await self.document_parser.parse_from_url(image_url)

        match classification_result:
            case {'is_banking': True, **rest}:
                logger.info("Banking receipt detected")
                return classification_result
            
            case {'is_signboard': True, **rest}:
                logger.info("Signboard detected")
                return classification_result

            case {'is_insurance': True, **rest}:
                vision_result = await self.vision_service.analyze_image_url(
                    image_url=image_url,
                    prompt=INSURANCE_VISION_PROMPT
                )

                if not vision_result.success:
                    logger.error(f"VisionService failed: {vision_result.error}")
                    return {"status": "error", "message": f"Lỗi phân tích hình ảnh: {vision_result.error}"}
                
                try:
                    extracted_data = json.loads(vision_result.description)
                    logger.info(f"Successfully parsed JSON from VisionService: {extracted_data}")
                    
                    analysis_content = extracted_data.get("INSURANCE_ANALYSIS", extracted_data)

                    if not any(value is not None for value in analysis_content.values()):
                        logger.warning("Extraction result is empty, might need clarification.")
                        return {
                             "status": "clarification_needed",
                             "message": "Không thể trích xuất thông tin. Hình ảnh có thể bị mờ. Vui lòng chụp lại ảnh rõ nét hơn."
                         }
                    
                    return {"status": "success", "data": extracted_data}

                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from LLM response: {vision_result.description}")
                    return {"status": "error", "message": "Lỗi định dạng JSON từ AI."}
                except Exception as e:
                    logger.error(f"An unexpected error occurred: {e}", exc_info=True)
                    return {"status": "error", "message": f"Lỗi không xác định: {e}"}

            case _:
                logger.info("Unknown document type detected")
                return {"status": "unknown_document", "message": "Không thể xác định loại tài liệu."}

vision_agent = VisionAgent()