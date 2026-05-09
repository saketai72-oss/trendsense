import re
import json

def _safe_int(value, default=0):
    """Chuyển đổi an toàn sang int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def _extract_video_json(html):
    """
    Trích xuất dữ liệu JSON nhúng từ HTML TikTok.
    TikTok luôn nhúng toàn bộ data vào thẻ script đặc biệt.
    Trả về dict chứa thông tin video chính xác.
    """
    # Phương pháp 1: __UNIVERSAL_DATA_FOR_REHYDRATION__ (TikTok hiện tại)
    pattern = r'<script\s+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            # Thử lấy từ __DEFAULT_SCOPE__
            scope = data.get("__DEFAULT_SCOPE__", {})
            
            # Ưu tiên webapp.video-detail (trang detail)
            video_detail = scope.get("webapp.video-detail") or scope.get("webapp.videoDetail")
            if video_detail:
                item = video_detail.get("itemInfo", {}).get("itemStruct")
                if item and item.get("id"):
                    return item

            # Thử tìm trực tiếp trong scope nếu là cấu trúc khác
            for key, val in scope.items():
                if isinstance(val, dict) and "itemInfo" in val:
                    item = val["itemInfo"].get("itemStruct")
                    if item and item.get("id"):
                        return item
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Phương pháp 2: SIGI_STATE (TikTok cũ / fallback)
    pattern2 = r'<script\s+id="SIGI_STATE"[^>]*>(.*?)</script>'
    match2 = re.search(pattern2, html, re.DOTALL)
    if match2:
        try:
            data = json.loads(match2.group(1))
            item_module = data.get("ItemModule", {})
            if item_module:
                # Lấy video đầu tiên
                for vid_id, item in item_module.items():
                    if isinstance(item, dict) and item.get("id"):
                        return item
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # Phương pháp 3: __NEXT_DATA__
    pattern3 = r'<script\s+id="__NEXT_DATA__"[^>]*>(.*?)</script>'
    match3 = re.search(pattern3, html, re.DOTALL)
    if match3:
        try:
            data = json.loads(match3.group(1))
            props = data.get("props", {}).get("pageProps", {})
            item = props.get("itemInfo", {}).get("itemStruct")
            if item and item.get("id"):
                return item
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    return None

def _extract_stats_regex_safe(html):
    """
    Fallback: Dùng regex nhưng AN TOÀN hơn.
    """
    def get_first_match(patterns, text):
        """Thử nhiều pattern, lấy giá trị hợp lệ đầu tiên"""
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    val = match.group(1)
                    # Nếu là digit -> trả về
                    if val.isdigit():
                        return val
                    # Nếu là string số trong quotes -> trả về
                    clean_val = val.strip('"\'')
                    if clean_val.isdigit():
                        return clean_val
                except (ValueError, IndexError):
                    pass
        return "0"

    # TikTok stats keys can be quoted or not, and values can be strings or numbers
    views_patterns = [r'"playCount"\s*:\s*"?(\d+)"?', r'"play_count"\s*:\s*"?(\d+)"?']
    likes_patterns = [r'"diggCount"\s*:\s*"?(\d+)"?', r'"likeCount"\s*:\s*"?(\d+)"?']
    comments_patterns = [r'"commentCount"\s*:\s*"?(\d+)"?']
    shares_patterns = [r'"shareCount"\s*:\s*"?(\d+)"?']
    saves_patterns = [r'"collectCount"\s*:\s*"?(\d+)"?']
    time_patterns = [r'"createTime"\s*:\s*"?(\d+)"?', r'"create_time"\s*:\s*"?(\d+)"?']

    caption = "Không tìm thấy"
    try:
        # Thử tìm caption trong "desc"
        desc_match = re.search(r'"desc"\s*:\s*"(.*?)"\s*,\s*"createTime"', html)
        if desc_match:
            caption = desc_match.group(1).encode().decode('unicode_escape', errors='ignore')
        else:
            # Fallback string slicing if regex fails
            start = html.find('"desc":"') + len('"desc":"')
            if start > 7:
                end = html.find('"', start)
                if end > start:
                    caption = html[start:end]
    except Exception:
        pass

    return {
        'Caption': caption,
        'Views': _safe_int(get_first_match(views_patterns, html)),
        'Likes': _safe_int(get_first_match(likes_patterns, html)),
        'Comments': _safe_int(get_first_match(comments_patterns, html)),
        'Shares': _safe_int(get_first_match(shares_patterns, html)),
        'Saves': _safe_int(get_first_match(saves_patterns, html)),
        'Create_Time': get_first_match(time_patterns, html),
    }

def extract_basic_stats(html):
    """
    Bóc tách stats video từ HTML TikTok.
    ƯU TIÊN: Parse JSON nhúng (chính xác, chỉ lấy data video đang xem).
    FALLBACK: Regex trên JSON block của video chính (không dùng max toàn trang nữa).
    """
    # === PHƯƠNG PHÁP CHÍNH: Parse JSON nhúng ===
    item = _extract_video_json(html)
    if item:
        stats = item.get("stats", {})
        return {
            'Caption': item.get("desc", "Không tìm thấy"),
            'Views': _safe_int(stats.get("playCount", 0)),
            'Likes': _safe_int(stats.get("diggCount", 0)),
            'Comments': _safe_int(stats.get("commentCount", 0)),
            'Shares': _safe_int(stats.get("shareCount", 0)),
            'Saves': _safe_int(stats.get("collectCount", 0)),
            'Create_Time': str(_safe_int(item.get("createTime", 0))),
        }

    # === FALLBACK: Regex nhưng chỉ trên block JSON đầu tiên ===
    print("  [!] Không parse được JSON nhúng, dùng fallback regex (giới hạn block đầu tiên)...")
    return _extract_stats_regex_safe(html)