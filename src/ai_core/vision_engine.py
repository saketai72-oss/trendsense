"""
Vision Engine — Phân tích nội dung video bằng AI thị giác.
1. Trích xuất keyframes từ video MP4 (OpenCV)
2. Sinh mô tả nội dung bằng BLIP (tiếng Anh → dịch sang tiếng Việt)
3. Xác minh danh mục bằng CLIP zero-shot image classification

Chạy trên CPU. Mỗi video mất khoảng 15-30 giây.
"""
import os
import sys
from collections import Counter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from config import settings

# =====================================================
# MAPPING DANH MỤC EMOJI → TIẾNG ANH CHO CLIP
# =====================================================
CLIP_CATEGORY_LABELS = {
    "entertainment and comedy video": "🎭 Giải trí",
    "music and dance performance": "🎵 Âm nhạc",
    "food and cooking video": "🍳 Ẩm thực",
    "technology and gadget review": "💻 Công nghệ",
    "fashion and outfit showcase": "👗 Thời trang",
    "education and tutorial": "📚 Giáo dục",
    "sports and fitness activity": "🏋️ Thể thao",
    "animals and pets video": "🐾 Động vật",
    "beauty and makeup tutorial": "💄 Làm đẹp",
    "news and current events": "📰 Tin tức",
    "finance and business content": "💰 Tài chính",
}

# Labels tiếng Anh cho CLIP
CLIP_LABELS = list(CLIP_CATEGORY_LABELS.keys())


def extract_keyframes(video_path, num_frames=None):
    """
    Trích xuất N keyframes đại diện từ video MP4.
    Chia video thành N đoạn đều, lấy frame giữa mỗi đoạn.
    Trả về list các PIL Image objects.
    """
    import cv2
    from PIL import Image

    if num_frames is None:
        num_frames = settings.VISION_KEYFRAMES

    if not os.path.exists(video_path):
        print(f"    [!] File không tồn tại: {video_path}")
        return []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"    [!] Không thể mở video: {video_path}")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        return []

    # Tính vị trí frame cần lấy (chia đều)
    # Bỏ 10% đầu/cuối để tránh intro/outro
    start_frame = int(total_frames * 0.1)
    end_frame = int(total_frames * 0.9)
    usable_range = max(end_frame - start_frame, 1)

    positions = [
        start_frame + int(usable_range * (i + 0.5) / num_frames)
        for i in range(num_frames)
    ]

    frames = []
    for pos in positions:
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(pos, total_frames - 1))
        ret, frame = cap.read()
        if ret:
            # Chuyển BGR (OpenCV) → RGB (PIL)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            frames.append(pil_image)

    cap.release()
    return frames


def _load_captioner():
    """Load BLIP model (lazy, chỉ load 1 lần) — Dùng trực tiếp classes thay vì pipeline"""
    from transformers import BlipProcessor, BlipForConditionalGeneration
    print(f"[*] Đang tải model captioning: {settings.VISION_CAPTION_MODEL}...")
    processor = BlipProcessor.from_pretrained(settings.VISION_CAPTION_MODEL)
    model = BlipForConditionalGeneration.from_pretrained(settings.VISION_CAPTION_MODEL)
    print("[✓] Model captioning sẵn sàng.")
    return processor, model


def _load_clip_classifier():
    """Load CLIP model (lazy, chỉ load 1 lần)"""
    from transformers import pipeline
    print(f"[*] Đang tải model CLIP: {settings.VISION_CLIP_MODEL}...")
    classifier = pipeline(
        "zero-shot-image-classification",
        model=settings.VISION_CLIP_MODEL,
        device=-1  # CPU
    )
    print("[✓] Model CLIP sẵn sàng.")
    return classifier


def _load_translator():
    """Load model dịch Anh → Việt (lazy, chỉ load 1 lần)"""
    from transformers import MarianMTModel, MarianTokenizer
    print(f"[*] Đang tải model dịch: {settings.VISION_TRANSLATE_MODEL}...")
    tokenizer = MarianTokenizer.from_pretrained(settings.VISION_TRANSLATE_MODEL)
    model = MarianMTModel.from_pretrained(settings.VISION_TRANSLATE_MODEL)
    print("[✓] Model dịch Anh → Việt sẵn sàng.")
    return tokenizer, model


def generate_video_description(frames, captioner, translator):
    """
    Sinh mô tả video từ các keyframes.
    1. BLIP caption từng frame (tiếng Anh)
    2. Tổng hợp thành mô tả gọn
    3. Dịch sang tiếng Việt
    """
    import torch

    if not frames:
        return "Không thể trích xuất frame từ video."

    processor, model = captioner  # unpack processor và model
    trans_tok, trans_mod = translator

    captions_en = []
    for i, frame in enumerate(frames):
        try:
            inputs = processor(frame, return_tensors="pt")
            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=50)
            caption = processor.decode(out[0], skip_special_tokens=True).strip()
            if caption and caption not in captions_en:
                captions_en.append(caption)
        except Exception as e:
            print(f"    [!] Lỗi caption frame {i}: {e}")

    if not captions_en:
        return "Không thể phân tích nội dung video."

    # Tổng hợp thành 1 câu mô tả tiếng Anh
    combined_en = ". ".join(captions_en)

    # Dịch sang tiếng Việt
    try:
        translated = trans_mod.generate(**trans_tok(combined_en, return_tensors="pt", padding=True))
        description_vi = trans_tok.decode(translated[0], skip_special_tokens=True).strip()
    except Exception as e:
        print(f"    [!] Lỗi dịch, giữ nguyên tiếng Anh: {e}")
        description_vi = combined_en

    return description_vi


def verify_category_by_vision(frames, current_category, classifier):
    """
    Xác minh danh mục video bằng CLIP zero-shot.
    Chạy trên từng keyframe → bình chọn (vote) danh mục cuối cùng.
    
    Trả về:
        - (new_category, confidence) nếu CLIP muốn ghi đè
        - (None, 0.0) nếu giữ nguyên category cũ
    """
    if not frames:
        return None, 0.0

    # Vote: cho mỗi frame bầu 1 danh mục
    votes = Counter()
    confidence_sums = Counter()

    for frame in frames:
        try:
            results = classifier(frame, candidate_labels=CLIP_LABELS)
            if results:
                top_label = results[0]['label']
                top_score = results[0]['score']
                votes[top_label] += 1
                confidence_sums[top_label] += top_score
        except Exception as e:
            print(f"    [!] Lỗi CLIP classify: {e}")

    if not votes:
        return None, 0.0

    # Danh mục thắng bầu cử
    winner_label = votes.most_common(1)[0][0]
    winner_votes = votes[winner_label]
    avg_confidence = confidence_sums[winner_label] / winner_votes

    # Map lại về emoji label
    winner_category = CLIP_CATEGORY_LABELS.get(winner_label, None)

    if not winner_category:
        return None, 0.0

    # Kiểm tra xem có cần ghi đè hay không
    threshold = settings.VISION_CATEGORY_OVERRIDE_THRESHOLD

    # Nếu confidence >= ngưỡng VÀ danh mục vision khác danh mục text hiện tại
    if avg_confidence >= threshold:
        # Kiểm tra xem winner_category đã nằm trong category cũ chưa
        current_cats = [c.strip() for c in (current_category or "").split(settings.CATEGORY_SEPARATOR)]
        if winner_category not in current_cats:
            return winner_category, avg_confidence

    return None, avg_confidence


def force_classify_by_vision(frames, classifier):
    """
    Phân loại CƯỠNG BỨC bằng CLIP — luôn trả về danh mục top-1.
    Dùng cho video "🌍 Khác" khi cần ÉP BUỘC phân loại.
    KHÔNG CÓ ngưỡng confidence — luôn chọn danh mục thắng bầu cử.

    Trả về:
        (category, confidence) — luôn trả về danh mục, không bao giờ None
    """
    if not frames:
        return None, 0.0

    # Vote: cho mỗi frame bầu 1 danh mục
    votes = Counter()
    confidence_sums = Counter()

    for frame in frames:
        try:
            results = classifier(frame, candidate_labels=CLIP_LABELS)
            if results:
                top_label = results[0]['label']
                top_score = results[0]['score']
                votes[top_label] += 1
                confidence_sums[top_label] += top_score
        except Exception as e:
            print(f"    [!] Lỗi CLIP classify: {e}")

    if not votes:
        return None, 0.0

    # Danh mục thắng bầu cử — LUÔN TRẢ VỀ dù confidence thấp
    winner_label = votes.most_common(1)[0][0]
    winner_votes = votes[winner_label]
    avg_confidence = confidence_sums[winner_label] / winner_votes

    # Map lại về emoji label
    winner_category = CLIP_CATEGORY_LABELS.get(winner_label, None)

    return winner_category, avg_confidence


def analyze_video_content(video_path, current_category, captioner, classifier, translator):
    """
    Pipeline chính: Extract → Caption → Verify.
    
    Args:
        video_path: Đường dẫn file MP4
        current_category: Danh mục hiện tại (từ text-based classification)
        captioner: BLIP pipeline (đã load sẵn)
        classifier: CLIP pipeline (đã load sẵn)
        translator: Translator pipeline (đã load sẵn)
    
    Returns:
        (description_vi, new_category_or_none, clip_confidence)
    """
    # 1. Trích xuất keyframes
    frames = extract_keyframes(video_path)
    if not frames:
        return "Không thể trích xuất frame.", None, 0.0

    # 2. Sinh mô tả (BLIP + dịch)
    description = generate_video_description(frames, captioner, translator)

    # 3. Xác minh danh mục (CLIP)
    new_category, confidence = verify_category_by_vision(
        frames, current_category, classifier
    )

    return description, new_category, confidence


def run_vision_analysis():
    """
    Hàm chính: Phân tích Vision cho tất cả video chưa xử lý.
    Được gọi từ ai_core_main.py (bước 9).
    """
    sys.path.append(os.path.join(settings.SRC_DIR, 'scraper'))
    from database import get_videos_for_vision_analysis, update_vision_results

    videos = get_videos_for_vision_analysis()

    if not videos:
        print("[✓] 👁️ Không có video mới cần phân tích Vision AI.")
        return

    print(f"\n{'=' * 60}")
    print(f"👁️ VISION AI — PHÂN TÍCH NỘI DUNG {len(videos)} VIDEO")
    print(f"{'=' * 60}")

    # Load models 1 lần duy nhất cho toàn bộ batch
    captioner = _load_captioner()
    classifier = _load_clip_classifier()
    translator = _load_translator()

    success = 0
    category_overrides = 0

    for i, video in enumerate(videos, 1):
        vid = video['video_id']
        path = video['video_path']
        current_cat = video.get('category', '')

        print(f"\n  [{i}/{len(videos)}] Phân tích: {vid}")

        # Kiểm tra file tồn tại
        if not os.path.exists(path):
            print(f"    [!] File MP4 không tồn tại, bỏ qua.")
            update_vision_results(vid, "File video không tồn tại.")
            continue

        try:
            description, new_cat, confidence = analyze_video_content(
                path, current_cat, captioner, classifier, translator
            )

            # Hiện kết quả
            print(f"    📝 Mô tả: {description[:80]}...")
            print(f"    🔍 CLIP confidence: {confidence:.1%}")

            if new_cat:
                print(f"    ⚡ GHI ĐÈ DANH MỤC: [{current_cat}] → [{new_cat}]")
                update_vision_results(vid, description, new_cat)
                category_overrides += 1
            else:
                print(f"    ✅ Giữ nguyên danh mục: {current_cat}")
                update_vision_results(vid, description)

            success += 1

        except Exception as e:
            print(f"    [!] Lỗi phân tích {vid}: {e}")
            update_vision_results(vid, f"Lỗi phân tích: {str(e)[:100]}")

    print(f"\n{'=' * 60}")
    print(f"👁️ VISION AI HOÀN TẤT!")
    print(f"   ✅ Đã phân tích: {success}/{len(videos)} video")
    print(f"   ⚡ Ghi đè danh mục: {category_overrides} video")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_vision_analysis()
