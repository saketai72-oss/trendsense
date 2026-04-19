"""
Multimodal Engine — Phân tích toàn diện Video TikTok
1. Lắng nghe (Audio-to-Text bằng faster-whisper)
2. Đọc chữ (OCR bằng EasyOCR)
3. Nhìn bối cảnh (Vision bằng BLIP)
4. Tư duy & Tổng hợp (LLM bằng Ollama)
"""
import os
import sys
import json
import requests
from collections import Counter
import cv2
from PIL import Image

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.config import service_settings as settings

# --- TẢI CÁC MODEL LAZY ---
_whisper_model = None
_ocr_reader = None
_caption_processor = None
_caption_model = None

def get_whisper():
    global _whisper_model
    if _whisper_model is None:
        print(f"[*] Đang tải Whisper model ({settings.WHISPER_MODEL})...")
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type=settings.WHISPER_COMPUTE_TYPE)
        print("[✓] Whisper sẵn sàng.")
    return _whisper_model

def get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        print(f"[*] Đang tải EasyOCR ({settings.OCR_LANG})...")
        import easyocr
        import logging
        logging.getLogger("easyocr").setLevel(logging.ERROR) # Bỏ qua cảnh báo chạy CPU
        _ocr_reader = easyocr.Reader(settings.OCR_LANG, gpu=False)
        print("[✓] EasyOCR sẵn sàng.")
    return _ocr_reader

def get_blip():
    global _caption_processor, _caption_model
    if _caption_processor is None:
        from transformers import BlipProcessor, BlipForConditionalGeneration
        print(f"[*] Đang tải BLIP captioning...")
        _caption_processor = BlipProcessor.from_pretrained(settings.VISION_CAPTION_MODEL)
        _caption_model = BlipForConditionalGeneration.from_pretrained(settings.VISION_CAPTION_MODEL)
        print("[✓] BLIP sẵn sàng.")
    return _caption_processor, _caption_model


# --- CÁC HÀM XỬ LÝ THÀNH PHẦN ---
def extract_audio_and_transcribe(video_path):
    import tempfile
    from moviepy import VideoFileClip
    
    mp3_path = None
    transcript = ""
    try:
        # Tách mp3 tạm thời
        clip = VideoFileClip(video_path)
        if clip.audio is None:
            return "Không có âm thanh."
            
        fd, mp3_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        
        # Chỉ lấy tối đa 30s để dịch tiết kiệm CPU
        duration = min(clip.duration, 30.0) 
        sub_clip = clip.subclipped(0, duration)
        
        import logging
        logging.getLogger("moviepy").setLevel(logging.ERROR)
        sub_clip.audio.write_audiofile(mp3_path, logger=None)
        clip.close()
        sub_clip.close()
        
        # Transcribe
        model = get_whisper()
        segments, info = model.transcribe(mp3_path, beam_size=5)
        text_parts = [segment.text for segment in segments]
        transcript = " ".join(text_parts).strip()
        
    except Exception as e:
        print(f"    [!] Lỗi Whisper: {e}")
    finally:
        # Xoá file mp3 tạm
        if mp3_path and os.path.exists(mp3_path):
            try:
                os.remove(mp3_path)
            except Exception as e:
                pass
                
    return transcript if transcript else "Không nghe được tiếng."


def extract_frames(video_path, total_frames=4, ocr_frames=2):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return [], []
    
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        return [], []
        
    start_f = int(total * 0.1)
    end_f = int(total * 0.9)
    usable_range = max(end_f - start_f, 1)
    
    positions = [start_f + int(usable_range * (i + 0.5) / total_frames) for i in range(total_frames)]
    
    pil_frames = []
    cv2_frames = [] # For OCR
    
    for i, pos in enumerate(positions):
        cap.set(cv2.CAP_PROP_POS_FRAMES, min(pos, total - 1))
        ret, frame = cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_frames.append(Image.fromarray(frame_rgb))
            if i < ocr_frames:
                cv2_frames.append(frame_rgb)
                
    cap.release()
    return pil_frames, cv2_frames


def run_blip(pil_frames):
    import torch
    if not pil_frames: return ""
    processor, model = get_blip()
    captions = []
    
    for frame in pil_frames:
        try:
            inputs = processor(frame, return_tensors="pt")
            with torch.no_grad():
                out = model.generate(**inputs, max_new_tokens=50)
            caption = processor.decode(out[0], skip_special_tokens=True).strip()
            if caption and caption not in captions:
                captions.append(caption)
        except:
            pass
            
    return ". ".join(captions)


def run_ocr(cv2_frames):
    if not cv2_frames: return ""
    reader = get_ocr()
    all_text = []
    for frame in cv2_frames:
        try:
            results = reader.readtext(frame, detail=0, paragraph=True)
            for t in results:
                if t not in all_text and len(t) > 3: # bỏ qua text rác quá ngắn
                    all_text.append(t)
        except:
            pass
            
    return " | ".join(all_text)


def summarize_with_ollama(audio_text, ocr_text, blip_text, original_caption=""):
    from services.ai_engine.categorizer import STANDARD_CATEGORIES
    import re
    
    categories_str = ", ".join(STANDARD_CATEGORIES)
    
    prompt = f"""Bạn là một trợ lý AI thông minh phân tích video TikTok.
Dưới đây là các dữ liệu tôi trích xuất được từ một video:
1. Âm thanh (Transcript): {audio_text}
2. Chữ trên màn hình (OCR): {ocr_text}
3. Bối cảnh hình ảnh (Vision): {blip_text}
4. Tiêu đề gốc: {original_caption}

NHIỆM VỤ:
1. Hãy viết 1 câu tóm tắt nội dung video (~20 từ), ngắn gọn, khách quan, tiếng Việt.
2. Từ nội dung đó, hãy chọn ra 1 danh mục phù hợp nhất từ danh sách sau: [{categories_str}].

BẮT BUỘC TRẢ VỀ ĐỊNH DẠNG JSON SAU:
{{"summary": "...", "category": "..."}}

Chỉ xuất ra JSON, không giải thích thêm."""

    try:
        response = requests.post(
            settings.OLLAMA_URL,
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json" # Ép Ollama 3+ trả về JSON
            },
            timeout=120
        )
        if response.status_code == 200:
            res_json = response.json()
            # Lấy data thô từ 'response' của Ollama
            raw_content = res_json.get('response', '').strip()
            
            # JSON Guard: Thử parse trực tiếp hoặc dùng regex nếu AI nói leo
            try:
                data = json.loads(raw_content)
                summary = data.get('summary', '').strip()
                category = data.get('category', '🌍 Khác').strip()
                
                # Robust category matching (xử lý trường hợp có/không có emoji)
                matched_category = "🌍 Khác"
                for std_cat in STANDARD_CATEGORIES:
                    if std_cat.lower() == category.lower():
                        matched_category = std_cat
                        break
                    # Bỏ emoji ở đầu (vd: '🎭 Giải trí' -> 'Giải trí')
                    if " " in std_cat:
                        std_name = std_cat.split(" ", 1)[-1].lower()
                        if std_name in category.lower():
                            matched_category = std_cat
                            break
                            
                return summary, matched_category
            except:
                # Fallback: Nếu JSON hỏng, cố gắng lấy summary từ raw_content
                print(f"    [!] Lỗi parse JSON Ollama, dùng fallback raw content.")
                return raw_content[:150], "🌍 Khác"
        else:
            print(f"    [!] Lỗi Ollama (HTTP {response.status_code}): {response.text[:100]}")
    except requests.exceptions.RequestException as e:
        print(f"    [!] Lỗi Timeout/Kết nối Ollama: {str(e)[:80]}")
        
    return "Lỗi tổng hợp dữ liệu.", "🌍 Khác"


def analyze_multimodal(video_path, caption):
    global _whisper_model, _ocr_reader, _caption_processor, _caption_model
    import gc

    # 1. Trích xuất Frames
    print("      [1/4] Đang trích xuất frames...")
    pil_frames, cv2_frames = extract_frames(video_path, settings.VISION_KEYFRAMES, settings.OCR_FRAMES)
    
    # 2. Nghe (Whisper)
    print("      [2/4] Đang chạy Whisper (Audio)...")
    audio_t = extract_audio_and_transcribe(video_path)
    
    # 3. OCR (EasyOCR)
    print("      [3/4] Đang chạy EasyOCR (Text)...")
    ocr_t = run_ocr(cv2_frames)
    
    # 4. Nhìn (BLIP)
    print("      [4/4] Đang chạy BLIP (Vision)...")
    blip_t = run_blip(pil_frames)
    
    # --- QUAN TRỌNG: Dọn dẹp RAM trước khi gọi Ollama ---
    print("      🧹 Đang dọn dẹp RAM (Whisper/OCR/BLIP)...")
    _whisper_model = None
    _ocr_reader = None
    _caption_processor = None
    _caption_model = None
    gc.collect()
    
    # 5. Nghĩ (Ollama)
    print("      🧠 Đang gửi cho Ollama phân tích tổng hợp & phân loại...")
    final_summary, final_category = summarize_with_ollama(audio_t, ocr_t, blip_t, caption)
    
    return final_summary, final_category, audio_t, ocr_t, blip_t


# --- CHẠY MAIN PIPELINE ---
def run_multimodal_analysis():
    from core.db.models import get_videos_for_vision_analysis, update_vision_results
    
    videos = get_videos_for_vision_analysis()
    if not videos:
        print("[✓] 👁️ Không có video mới cần phân tích Multimodal AI.")
        return
        
    print(f"\n{'=' * 60}")
    print(f"👁️ MULTIMODAL AI — PHÂN TÍCH NỘI DUNG {len(videos)} VIDEO")
    print(f"{'=' * 60}")

    success = 0
    for i, video in enumerate(videos, 1):
        vid = video['video_id']
        path = video['video_path']
        caption = video.get('caption', '')
        
        print(f"\n  [{i}/{len(videos)}] Phân tích: {vid}")
        if not os.path.exists(path):
            print(f"    [!] File MP4 không tồn tại, bỏ qua.")
            update_vision_results(vid, "File video không tồn tại.")
            continue
            
        try:
            summary, cat, a_txt, o_txt, b_txt = analyze_multimodal(path, caption)
            print(f"    🎧 Audio: {a_txt[:60]}...")
            print(f"    📝 OCR:   {o_txt[:60]}...")
            print(f"    👁️ Vision:{b_txt[:60]}...")
            print(f"    ✨ Tóm tắt Ollama: {summary}")
            print(f"    🏷️ Phân loại Ollama: {cat}")
            
            update_vision_results(vid, summary)
            success += 1
            
        except Exception as e:
            print(f"    [!] Lỗi Multimodal: {e}")
            update_vision_results(vid, f"Lỗi phân tích: {str(e)[:100]}")

    print(f"\n{'=' * 60}")
    print(f"👁️ MULTIMODAL HOÀN TẤT! Đã xử lý {success}/{len(videos)} video.")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    run_multimodal_analysis()
