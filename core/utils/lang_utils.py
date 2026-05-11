import re

# Danh sách các ký tự đặc trưng của chữ cái tiếng Việt có dấu
VIETNAMESE_CHARS = re.compile(
    r'[ăâđêôơưĂÂĐÊÔƠƯ]'
    r'|[áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ]'
    r'|[ÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ]'
)

def is_vietnamese_text(text: str) -> bool | None:
    """
    Kiểm tra xem văn bản có chứa ký tự đặc trưng của tiếng Việt có dấu hay không.
    - Trả về True nếu có ít nhất một ký tự Việt có dấu.
    - Trả về False nếu không có bất kỳ ký tự Việt có dấu nào (văn bản có thể là tiếng Việt không dấu, tiếng Anh, hoặc chỉ emoji/số).
    - Trả về None nếu text rỗng hoặc None.
    """
    if not text:
        return None
    # Tìm kiếm bất kỳ ký tự nào trong pattern
    if VIETNAMESE_CHARS.search(text):
        return True
    return False