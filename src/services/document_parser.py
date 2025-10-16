import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from src.services.ocr_service import OcrService
from src.common.constants import BankingVisionKeywords
from src.config import settings
logger = logging.getLogger(__name__)

class DocumentParser:
    def __init__(self, recipient_account: str, recipient_name_keywords: List[str]):
        self.ocr_service = OcrService(api_key=settings.ocr_api_key)
        self.recipient_account = recipient_account
        self.recipient_name_keywords = [kw.lower() for kw in recipient_name_keywords]
        self.date_regex = re.compile(r'(\d{2}:\d{2}(?::\d{2})?\s*[-]?\s*\d{2}[/-]\d{2}[/-]\d{4}|\d{2}[/-]\d{2}[/-]\d{4}\s*\d{2}:\d{2}(?::\d{2})?)')
        self.amount_regex = re.compile(r'((?:-?[\d]{1,3}(?:[.,]\d{3})*)\s?(?:VND|đ))')
        id_keywords = "|".join(BankingVisionKeywords.TRANSACTION_ID_KEYWORDS)
        self.transaction_id_regex = re.compile(
            rf'(?:{id_keywords})\s*:?\s*([A-Z0-9a-z]+)', re.IGNORECASE
        )
        content_keywords = "|".join(BankingVisionKeywords.CONTENT_KEYWORDS)
        self.content_regex = re.compile(
            rf'(?:{content_keywords})\s*:?\s*(.*)', re.IGNORECASE
        )

    def _check_is_insurance(self, text: str) -> bool:
        lower_text = text.lower()
        found_count = 0
        for keyword in BankingVisionKeywords.INSURANCE_KEYWORDS:
            if keyword in lower_text:
                found_count += 1
        return found_count >= 3

    def _check_is_signboard(self, text: str) -> bool:
        lower_text = text.lower()
        found_count = 0
        for keyword in BankingVisionKeywords.SIGNBOARD_KEYWORDS:
            if keyword in lower_text:
                found_count += 1
        return found_count >= 2

    def _normalize_date(self, date_str: str) -> str:
        formats_to_try = ['%d/%m/%Y %H:%M:%S', '%d-%m-%Y %H:%M:%S', '%H:%M - %d/%m/%Y', '%H:%M - %d-%m-%Y', '%d/%m/%Y %H:%M', '%d-%m-%Y %H:%M', '%d/%m/%Y, %H:%M']
        for fmt in formats_to_try:
            try: return datetime.strptime(date_str, fmt).strftime('%Y-%m-%dT%H:%M:%S')
            except ValueError: continue
        return date_str

    def _extract_banking_name(self, text: str) -> Optional[str]:
        lower_text = text.lower()
        for keyword, bank_name in BankingVisionKeywords.BANKS.items():
            if keyword in lower_text: return bank_name
        return None

    def _extract_transaction_date(self, text: str) -> Optional[str]:
        match = self.date_regex.search(text)
        return self._normalize_date(match.group(0).strip()) if match else None

    def _extract_amount(self, text: str) -> Optional[str]:
        amount_keywords_pattern = "|".join(BankingVisionKeywords.AMOUNT_KEYWORDS)
        for line in text.splitlines():
            if re.search(amount_keywords_pattern, line, re.IGNORECASE):
                match = self.amount_regex.search(line)
                if match: return match.group(0).strip()
        matches = self.amount_regex.findall(text)
        return matches[0].strip() if matches else None

    def _extract_recipient_account(self, text: str) -> Optional[str]:
        cleaned_text = text.replace(' ', '').replace('-', '')
        if self.recipient_account in cleaned_text: return self.recipient_account
        return None
        
    def _extract_recipient_name(self, text: str) -> Optional[str]:
        lower_text = text.lower()
        for keyword in self.recipient_name_keywords:
            if keyword in lower_text: return "CONG TY CO PHAN BAO HIEM CONG NGHE PHUONG DONG INSURTECH"
        return None

    def _extract_transaction_id(self, text: str) -> Optional[str]:
        match = self.transaction_id_regex.search(text)
        if match: return match.group(1).strip()
        fallback_match = re.search(r'\b(?=[A-Z0-9]*[A-Z])[A-Z0-9]{10,}\b', text, re.IGNORECASE)
        return fallback_match.group(0) if fallback_match else None
        
    def _extract_content(self, text: str) -> Optional[str]:
        match = self.content_regex.search(text)
        if match:
            content = match.group(1).strip()
            if 'chuyen tien' in content.lower(): content = content.lower().split('chuyen tien')[0].strip()
            return content.capitalize() if content else None
        return None

    async def parse_from_url(self, image_url: str) -> Dict[str, Any]:
        try:
            ocr_result = await self.ocr_service.ocr_from_url(url=image_url)
            if not ocr_result.get('ParsedResults'):
                raise ValueError("OCR parsing failed or returned no results.")
            extracted_text = ocr_result['ParsedResults'][0].get('ParsedText', '')
        except Exception as e:
            logger.error(f"Error during OCR processing: {e}")
            return {"is_insurance": False, "is_signboard": False, "is_banking": False, "error": str(e), "data": None}

        if self._check_is_insurance(extracted_text):
            return {
                "is_insurance": True,
                "is_signboard": False,
                "is_banking": False,
                "data": None
            }

        if self._check_is_signboard(extracted_text):
            return {
                "is_insurance": False,
                "is_signboard": True,
                "is_banking": False,
                "data": None
            }

        banking_data = {
            "banking_name": self._extract_banking_name(extracted_text),
            "transaction_date": self._extract_transaction_date(extracted_text),
            "amount": self._extract_amount(extracted_text),
            "recipient_account": self._extract_recipient_account(extracted_text),
            "recipient_name": self._extract_recipient_name(extracted_text),
            "transaction_id": self._extract_transaction_id(extracted_text),
            "content": self._extract_content(extracted_text)
        }
        
        key_fields = [
            banking_data["banking_name"], banking_data["transaction_date"],
            banking_data["amount"], banking_data["recipient_account"]
        ]
        found_count = sum(1 for field in key_fields if field is not None)
        is_banking = found_count >= 3
        
        return {
            "is_insurance": False,
            "is_signboard": False,
            "is_banking": is_banking,
            "data": banking_data if is_banking else None
        }