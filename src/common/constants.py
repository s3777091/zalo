class Lexicon:
    INSURANCE_STOP_WORDS = {
        'bảo', 'hiểm', 'bảo hiểm', 'bao', 'hiem', 'bao hiem',
        'gói', 'goi', 'package', 'mua', 'buy', 'đặt', 'dat', 'order',
        'cho', 'tôi', 'toi', 'me', 'i', 'want', 'muốn', 'muon',
        'cần', 'can', 'need', 'xem', 'view', 'show',
    }
    
    # Error messages for insurance operations
    INSURANCE_ERROR_MESSAGES = {
        'product_not_found': 'Không tìm thấy sản phẩm bảo hiểm "{product_name}"',
        'invalid_quantity': 'Số lượng không hợp lệ',
        'create_order_failed': 'Không thể tạo đơn hàng',
        'update_order_failed': 'Không thể cập nhật đơn hàng',
        'order_not_found': 'Không tìm thấy đơn hàng',
        'database_error': 'Lỗi cơ sở dữ liệu',
        'generic_error': 'Đã xảy ra lỗi',
    }
    ORDER_SUCCESS_MESSAGES = {
        'order_created': 'Đã tạo đơn hàng thành công',
        'order_updated': 'Đã cập nhật đơn hàng thành công',
        'order_deleted': 'Đã xóa đơn hàng thành công',
        'payment_link_sent': 'Đã gửi link thanh toán',
    }
    VN_TYPE_TO_CODE = {
        # Vietnamese
        'suc khoe': 'health', 'sức khỏe': 'health', 'y te': 'health', 'y tế': 'health',
        'du lich': 'travel', 'du lịch': 'travel', 
        'tai nan': 'personal_accident', 'tai nạn': 'personal_accident', 'personal_accident': 'personal_accident', 'accident': 'personal_accident',
        'o to': 'car', 'ô tô': 'car', 'xe hơi': 'car', 'xe ô tô': 'car', 'xe oto': 'car', 'auto': 'car',
        'xe may': 'motorbike', 'xe máy': 'motorbike', 'motorbike': 'motorbike', 'motorcycle': 'motorbike',
        'nha': 'home', 'nhà': 'home',
        'nhan tho': 'life', 'nhân thọ': 'life',
        'health': 'health', 'travel': 'travel', 'car': 'car', 'home': 'home', 'life': 'life',
        '健康保险': 'health', '健康': 'health',
        '旅行保险': 'travel', '旅行': 'travel', 
        '意外保险': 'personal_accident', '意外': 'personal_accident',
        '汽车保险': 'car', '汽车': 'car',
        '摩托车保险': 'motorbike', '摩托车': 'motorbike', 
        '房屋保险': 'home', '房屋': 'home',
        '人寿保险': 'life', '人寿': 'life'
    }

    @staticmethod
    def _strip_accents(s: str) -> str:
        import unicodedata
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

    @classmethod
    def normalize_insurance_type(cls, text: str | None) -> str | None:
        """Normalize arbitrary user-provided insurance type phrase to canonical internal code.

        Returns one of: health, travel, personal_accident, car, motorbike, home, life or None.
        Accent-insensitive, case-insensitive and tolerant to extra spaces.
        """
        if not text:
            return None
        lowered = cls._strip_accents(text.lower().strip())
        # try direct match keys first (accent stripped entries already covered in VN_TYPE_TO_CODE)
        if lowered in cls.VN_TYPE_TO_CODE:
            return cls.VN_TYPE_TO_CODE[lowered]
        # fallback: scan for any key substring (short phrases inside longer sentence)
        for key, code in cls.VN_TYPE_TO_CODE.items():
            if key in lowered:
                return code
        return None



class RoutingKeywords:
    """Centralized keyword management for routing decisions."""
    
    INSURANCE_TYPE_KEYWORDS = [
        # Vietnamese
        'sức khỏe', 'suc khoe', 
        'du lịch', 'du lich', 
        'tai nạn', 'tai nan',
        'ô tô', 'o to',
        'xe máy', 'xe may',
        'nhà', 'nha',
        'nhân thọ', 'nhan tho',
        # English
        'health', 'travel', 'accident', 'personal accident', 
        'auto', 'car', 'motorbike', 'motorcycle', 'home', 'life',
        # Chinese
        '健康保险', '健康', '旅行保险', '旅行', '意外保险', '意外',
        '汽车保险', '汽车', '摩托车保险', '摩托车', '人寿保险', '人寿'
    ]
    
    # Order intent keywords
    ORDER_INTENT_KEYWORDS = {
        'DELETE': ['xóa', 'hủy', 'bỏ', 'cancel', 'delete'],
        'UPDATE': ['thêm', 'tăng', 'giảm', 'chỉ muốn', 'cập nhật', 'cap nhat', 'update', 'modify'],
        'VIEW': ['xem', 'kiểm tra', 'kiem tra', 'đơn hàng', 'don hang', 'view', 'show', 'list'],
        'CREATE': ['mua', 'đặt', 'dat', 'order', 'buy', 'create', 'new']
    }
    
    # Vietnamese number mapping
    VIETNAMESE_NUMBERS = {
        'một': 1, 'mot': 1, 'hai': 2, 'ba': 3, 
        'bốn': 4, 'bon': 4, 'năm': 5, 'nam': 5,
        'sáu': 6, 'sau': 6, 'bảy': 7, 'bay': 7,
        'tám': 8, 'tam': 8, 'chín': 9, 'chin': 9, 
        'mười': 10, 'muoi': 10
    }
    
    # Vision field correction patterns
    VISION_FIELD_PATTERNS = {
        'chassis_number': ['số khung', 'so khung', 'khung'],
        'engine_number': ['số máy', 'so may', 'máy', 'may'],
        'license_plate': ['biển', 'bien', 'biển số', 'bien so'],
        'series_number': ['series', 'số series', 'so series'],
        'owner_name': ['tên chủ', 'ten chu', 'chủ xe', 'chu xe', 'tên', 'ten'],
        'owner_address': ['địa chỉ', 'dia chi', 'address'],
        'vehicle_type': ['loại xe', 'loai xe']
    }
    
    # Payment keywords (highest priority)
    PAYMENT_KEYWORDS = [
        # Vietnamese
        'thanh toán', 'thanh toan', 'qr code', 'qr', 'mã qr', 'ma qr',  
        'chuyển khoản', 'chuyen khoan', 'link thanh toán', 'link thanh toan',
        'hướng dẫn thanh toán', 'huong dan thanh toan',
        'gửi link', 'gui link', 'cho tôi link', 'cho toi link',
        'thanh toán đơn hàng', 'thanh toan don hang',
        'mã thanh toán', 'ma thanh toan',
        # English
        'payment', 'pay', 'payment link', 'transfer',
        # Chinese 
        '支付', '付款', '付钱', '支付链接', '支付二维码', 
        '转账', '付款码', '扫码支付', '二维码'
    ]
    
    # Order management action keywords
    ORDER_ACTION_KEYWORDS = [
        'xem don', 'xem đơn', 'kiem tra don', 'kiểm tra đơn', 'view order',
        'tinh trang don', 'tình trạng đơn', 'tinh trang', 'tình trạng', 'status', 'check status',
        'xoa don', 'xóa đơn', 'huy don', 'hủy đơn', 'cancel order', 'delete order',
        'cap nhat don', 'cập nhật đơn', 'update order', 'sua don', 'sửa đơn', 
        'them goi', 'thêm gói', 'add package', 'giam goi', 'giảm gói', 'reduce'
    ]
    
    # Purchase action keywords
    PURCHASE_ACTION_KEYWORDS = [
        # Vietnamese
        'mua', 'dat', 'đặt',
        # English  
        'order', 'buy',
        # Chinese
        '买', '购买', '想买', '要买'
    ]
    
    # Generic purchase patterns (need consultation)
    GENERIC_PURCHASE_PATTERNS = [
        # Vietnamese - generic (no specific type)
        'toi muon mua bao hiem', 'tôi muốn mua bảo hiểm', 
        'muon mua bao hiem', 'muốn mua bảo hiểm',
        'can bao hiem', 'cần bảo hiểm', 
        'tim bao hiem', 'tìm bảo hiểm',
        'mua bao hiem', 'mua bảo hiểm',  # Added missing patterns
        # English - generic
        'buy insurance', 'want insurance',
        # Chinese - generic (no specific type)
        '我想买保险', '想买保险', '要买保险', '需要保险'
    ]
    
    # Vision/Image patterns
    VISION_PATTERNS = ['http', 'jpg', 'png', 'jpeg', 'webp', 'gif']
    
    # Payment vision verification keywords (for OCR validation of payment screenshots)
    PAYMENT_VISION_KEYWORDS = [
        # Vietnamese
        'xác minh giao dịch', 'xac minh giao dich', 
        'kiểm tra giao dịch', 'kiem tra giao dich',
        'xác nhận thanh toán', 'xac nhan thanh toan',
        'check giao dịch', 'check giao dich',
        'verify giao dịch', 'verify transaction',
        'xác minh chuyển tiền', 'xac minh chuyen tien',
        'kiểm tra chuyển khoản', 'kiem tra chuyen khoan',
        'xác nhận chuyển tiền', 'xac nhan chuyen tien',
        # English
        'verify payment', 'verify transaction', 'check payment',
        'validate payment', 'payment verification', 'transaction verification',
        # Chinese
        '验证交易', '验证支付', '检查交易', '确认支付'
    ]
    
    # Quick response templates
    QUICK_RESPONSES = {
        # Greetings - Chào hỏi
        'xin chào': 'Xin chào! Tôi có thể giúp bạn tư vấn bảo hiểm hoặc quản lý đơn hàng. Bạn cần hỗ trợ gì?',
        'chào': 'Chào bạn! Tôi là trợ lý bảo hiểm. Bạn muốn xem gói bảo hiểm nào không?',
        'chào bạn': 'Chào bạn! Tôi có thể hỗ trợ tư vấn bảo hiểm và quản lý đơn hàng. Bạn cần gì?',
        'hello': 'Hello! I can help you with insurance consultation. What do you need?',
        'hi': 'Chào bạn! Bạn cần tư vấn bảo hiểm hay quản lý đơn hàng?',
        'good morning': 'Chào buổi sáng! Tôi có thể giúp bạn về bảo hiểm. Bạn quan tâm gì?',
        'good afternoon': 'Chào buổi chiều! Bạn cần tư vấn bảo hiểm không?',
        'good evening': 'Chào buổi tối! Tôi có thể hỗ trợ bạn về bảo hiểm.',
        
        # Help & Menu - Trợ giúp & Menu
        'help': 'Tôi có thể giúp bạn: 1) Tư vấn gói bảo hiểm 2) Quản lý đơn hàng 3) Thanh toán. Bạn cần gì?',
        'giúp đỡ': 'Tôi có thể hỗ trợ:  Tư vấn bảo hiểm |  Quản lý đơn hàng |  Thanh toán. Bạn muốn gì?',
        'hướng dẫn': 'Gửi "sức khỏe", "du lịch" để xem bảo hiểm. Gửi "xem đơn" để kiểm tra đơn hàng.',
        'menu': 'Các tính năng:  Tư vấn bảo hiểm | 🛒 Quản lý đơn hàng |  Thanh toán',
        'chức năng': 'Tôi có thể: 1️⃣ Tư vấn các loại bảo hiểm 2️⃣ Quản lý đơn hàng 3️⃣ Hỗ trợ thanh toán',
        'làm được gì': 'Tôi giúp bạn: tư vấn bảo hiểm, tạo đơn hàng, xem gói bảo hiểm, thanh toán. Bạn cần gì?',
        
        # Consultation starters - Bắt đầu tư vấn
        'tư vấn bảo hiểm': 'Bạn muốn xem loại nào? (sức khỏe/du lịch/tai nạn/ô tô/xe máy/nhà/nhân thọ)',
        'tu van bao hiem': 'Bạn muốn xem loại nào? (sức khỏe/du lịch/tai nạn/ô tô/xe máy/nhà/nhân thọ)',
        'bảo hiểm gì tốt': 'Tùy nhu cầu! Bạn muốn bảo vệ sức khỏe, tài sản hay đi du lịch an toàn?',
        'gói nào rẻ': 'Mỗi loại có nhiều mức giá. Bạn quan tâm bảo hiểm gì trước?',
        'có gói nào': 'Có: sức khỏe/du lịch/tai nạn/ô tô/xe máy/nhà/nhân thọ. Bạn muốn xem loại nào?',
        'giá bao nhiêu': 'Giá tùy loại và mức bảo hiểm. Bạn quan tâm bảo hiểm gì trước?',
        'bảo hiểm rẻ nhất': 'Giá phụ thuộc loại và mức bảo hiểm. Bạn muốn xem loại nào trước?',
        'so sánh': 'Bạn muốn so sánh loại bảo hiểm nào? (VD: sức khỏe vs du lịch)',
        
        # Order queries - Truy vấn đơn hàng
        'có đơn nào': 'Để xem đơn hàng, gửi "xem đơn" nhé!',
        'đơn hàng': 'Gửi "xem đơn" để kiểm tra đơn hàng của bạn.',
        'tình trạng': 'Bạn muốn xem tình trạng đơn hàng hay cần tư vấn bảo hiểm?',
        'đơn của tôi': 'Gửi "xem đơn" để xem tất cả đơn hàng của bạn.',
        
        # Affirmations - Khẳng định
        'ok': 'Bạn cần hỗ trợ gì thêm không?',
        'được': 'Tốt! Bạn còn cần hỗ trợ gì khác?',
        'ừ': 'Vâng! Bạn cần gì nữa không?',
        'oke': 'Được rồi! Còn gì khác tôi có thể giúp?',
        'đồng ý': 'Tuyệt! Bạn còn câu hỏi nào khác?',
        
        # Thanks - Cảm ơn
        'cảm ơn': 'Không có gì! Tôi luôn sẵn sàng hỗ trợ bạn.',
        'cảm ơn bạn': 'Rất vui được giúp đỡ! Bạn cần gì thêm không?',
        'thank you': 'You\'re welcome! Need anything else?',
        'thanks': 'Rất vui được hỗ trợ bạn! 😊',
        'cám ơn': 'Không có gì! Hãy liên hệ khi bạn cần hỗ trợ.',
        
        # Goodbyes - Tạm biệt
        'tạm biệt': 'Tạm biệt! Hẹn gặp lại bạn! ',
        'bye': 'Goodbye! Come back anytime! ',
        'chào tạm biệt': 'Chào bạn! Mong sớm được hỗ trợ bạn lại! 😊',
        'hẹn gặp lại': 'Hẹn gặp lại bạn! Chúc bạn một ngày tốt lành! 🌟',
        
        # Confusion - Không hiểu
        'không hiểu': 'Bạn có thể hỏi về: bảo hiểm sức khỏe, đơn hàng, thanh toán. Bạn cần gì?',
        'hả': 'Tôi có thể giúp tư vấn bảo hiểm và quản lý đơn hàng. Bạn muốn biết gì?',
        'gì': 'Bạn có thể hỏi về các gói bảo hiểm hoặc đơn hàng. Cần hỗ trợ gì?',
        'sao': 'Tôi là trợ lý bảo hiểm. Bạn muốn xem gói bảo hiểm hay kiểm tra đơn hàng?',
        
        # Common short queries - Câu hỏi ngắn thường gặp
        'có không': 'Có nhiều loại bảo hiểm. Bạn quan tâm loại nào?',
        'như thế nào': 'Bạn muốn biết quy trình nào? Mua bảo hiểm hay thanh toán?',
        'bao nhiêu': 'Giá phụ thuộc loại bảo hiểm. Bạn muốn xem loại nào?',
        'ở đâu': 'Bạn có thể mua bảo hiểm ngay tại đây. Muốn xem gói nào?',
        'khi nào': 'Bạn có thể mua bảo hiểm bất cứ lúc nào. Quan tâm loại nào?',
        
        # Encouragement - Động viên
        'tốt': 'Tuyệt vời! Bạn còn muốn biết gì khác?',
        'hay': 'Cảm ơn! Tôi có thể hỗ trợ bạn thêm gì nữa?',
        'giỏi': 'Cảm ơn bạn! Hãy cho tôi biết nếu cần hỗ trợ gì.',
    }


class VisionToolDescriptions:
    ImageInsurance = """
    Extract insurance certificate information from images using OpenAI Vision.

    Multi-strategy approach:
    1. Direct OpenAI vision model with structured prompt
    2. Fallback to prompty chain if critical fields missing
    3. Regex augmentation to fill remaining gaps

    Args:
        images_json: JSON string containing list of image objects with 'url' field
        user_message: User's message context (optional)
        language: User's language preference (default: 'vi')

    Returns:
        JSON string with insurance certificate information
    """

    PAYMENT_DETECTION ="""
    Detect and extract payment transaction information from images.
    Args:
        images_json: JSON string containing list of image objects with 'url' field  
        user_message: User's message context (optional)

    Returns:
        JSON string with payment transaction information
    """
    
    PAYMENT_VALIDATE = """Full OCR + validation style extraction for bank transaction screenshots.

    Returns JSON schema:
    {
      "is_valid": bool,
      "photo_description": str,
      "extracted_text": str,
      "parsed_fields": { bank_name, amount_numeric, amount_text, currency, datetime_original, datetime_iso, payer_name, status },
      "validation": { bank_name, amount, datetime, name, summary }
    }
    Expected (for validation) reference sample embedded in prompt.
    """

class BankingVisionKeywords:
    BANKS = {
        'agribank': 'Agribank',
        'acb': 'ACB',
        'bidv': 'BIDV',
        'cake': 'CAKE by VPBank',
        'hdbank': 'HDBank',
        'lpbank': 'LPBank',
        'mb bank': 'MBBank',
        'mbbank': 'MBBank',
        'military bank': 'MBBank',
        'quan doi': 'MBBank',
        'mb': 'MBBank',
        'msb': 'MSB',
        'maritime bank': 'MSB',
        'nam a bank': 'Nam A Bank',
        'namabank': 'Nam A Bank',
        'sacombank': 'Sacombank',
        'shb': 'SHB',
        'techcombank': 'Techcombank',
        'tcb': 'Techcombank',
        'tpbank': 'TPBank',
        'tien phong bank': 'TPBank',
        'vcb': 'Vietcombank',
        'vietcombank': 'Vietcombank',
        'vpb': 'VPBank',
        'vpbank': 'VPBank',
        'vietinbank': 'Vietinbank',
        'ctg': 'Vietinbank'
    }

    # Keywords that typically precede or are associated with the transaction amount.
    AMOUNT_KEYWORDS = [
        'số tiền', 'so tien',
        'amount',
        'tổng số tiền', 'tong so tien',
        'gia tri', 'giá trị',
        'thanh toan' # payment
    ]
    
    # Keywords that label the transaction's date and time.
    DATE_KEYWORDS = [
        'thời gian giao dịch', 'thoi gian giao dich',
        'thời gian', 'thoi gian',
        'ngày giao dịch', 'ngay giao dich',
        'ngày thực hiện', 'ngay thuc hien',
        'time',
        'date'
    ]
    
    # Keywords for the sender's information.
    SENDER_KEYWORDS = [
       'người chuyển', 'nguoi chuyen',
       'tài khoản nguồn', 'tai khoan nguon',
       'từ tài khoản', 'tu tai khoan',
       'số tài khoản chuyển', 'so tai khoan chuyen',
       'nguồn tiền', 'nguon tien',
       'sender'
    ]

    # Keywords for the recipient's information.
    RECIPIENT_KEYWORDS = [
        'đến:', 'den:',
        'tới', 'toi',
        'người nhận', 'nguoi nhan',
        'tên người thụ hưởng', 'ten nguoi thu huong',
        'người thụ hưởng', 'nguoi thu huong',
        'tài khoản nhận', 'tai khoan nhan',
        'tài khoản thụ hưởng', 'tai khoan thu huong',
        'tài khoản đích', 'tai khoan dich',
        'recipient name',
        'beneficiary'
    ]
    
    # Keywords that label the unique reference code for the transaction.
    TRANSACTION_ID_KEYWORDS = [
        'mã giao dịch', 'ma giao dich',
        'số tham chiếu', 'so tham chieu',
        'mã tham chiếu', 'ma tham chieu',
        'mgd',
        'số giao dịch', 'so giao dich',
        'transaction id',
        'transaction code',
        'reference no'
    ]
    
    # Keywords that label the transaction description or message.
    CONTENT_KEYWORDS = [
        'nội dung', 'noi dung',
        'nội dung chuyển tiền', 'noi dung chuyen tien',
        'lời nhắn', 'loi nhan',
        'diễn giải', 'dien giai',
        'description',
        'message'
    ]

    SIGNBOARD_KEYWORDS = [
        'cộng hòa xã hội chủ nghĩa việt nam',
        'biên bản bàn giao',
        'tnds xe máy',
        '170 duy tân',
        'pleiku, gia lai'
    ]
    
    INSURANCE_KEYWORDS = [
        'bảo hiểm bắt buộc',
        'tnds',
        'giấy chứng nhận bảo hiểm',
        'thời hạn bảo hiểm',
        'phí bảo hiểm',
        'biển kiểm soát',
        'số khung',
        'chủ xe'
    ]
