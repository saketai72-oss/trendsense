"""
Subscription & Payment Routes — VietQR + SePay Webhook
=======================================================
Endpoints:
  GET  /api/subscription/status           — quota hôm nay + gói hiện tại
  POST /api/subscription/create-payment   — tạo QR VietQR (MB Bank)
  GET  /api/subscription/check-payment/{ref} — poll trạng thái payment
  POST /api/webhook/sepay                 — webhook từ SePay (tự động kích hoạt Pro)
"""
import hashlib
import hmac
import logging
import os
import time

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional

from backend.auth.dependencies import get_current_user
from core.db.models import (
    check_video_quota,
    complete_payment,
    create_payment,
    get_payment_by_reference,
    get_payment_history,
    get_user_subscription,
    PLAN_QUOTAS,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Config ─────────────────────────────────────────────────────────────────────

VIETQR_API_URL = "https://api.vietqr.io/v2/generate"
MB_BANK_ACQ_ID = "970422"             # MB Bank BIN code
MB_ACCOUNT_NO = os.getenv("MB_ACCOUNT_NO", "")
MB_ACCOUNT_NAME = os.getenv("MB_ACCOUNT_NAME", "TRENDSENSE")
SEPAY_WEBHOOK_SECRET = os.getenv("SEPAY_WEBHOOK_SECRET", "")

PLAN_PRICES: dict[str, int] = {
    "pro_49k": 49_000,   # VND
}

PLAN_LABELS: dict[str, str] = {
    "free": "Free",
    "pro_49k": "Pro",
}


def _make_reference_code(user_id: str) -> str:
    """
    Tạo nội dung chuyển khoản duy nhất.
    Format: TSPRO{6 ký tự user_id}{timestamp 6 chữ số cuối}
    VD: TSPRO-abc123-716042
    Phải ngắn (< 25 ký tự), không dấu, không ký tự đặc biệt để ngân hàng nhận đúng.
    """
    uid_part = user_id.replace("-", "")[:6].upper()
    ts_part = str(int(time.time()))[-6:]
    return f"TSPRO{uid_part}{ts_part}"


# ── GET /api/subscription/status ───────────────────────────────────────────────

@router.get("/subscription/status")
def subscription_status(user: dict = Depends(get_current_user)):
    """
    Trả về gói hiện tại, quota hôm nay và ngày hết hạn.
    Frontend dùng để hiển thị badge Pro và thanh quota.
    """
    user_id = str(user["id"])
    allowed, used, limit = check_video_quota(user_id)
    sub = get_user_subscription(user_id)

    expires_at = sub.get("expires_at")
    if hasattr(expires_at, "isoformat"):
        expires_at = expires_at.isoformat()

    return {
        "plan": sub.get("plan", "free"),
        "plan_label": PLAN_LABELS.get(sub.get("plan", "free"), "Free"),
        "status": sub.get("status", "active"),
        "expires_at": expires_at,
        "quota": {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "allowed": allowed,
        },
    }


# ── POST /api/subscription/create-payment ──────────────────────────────────────

class CreatePaymentRequest(BaseModel):
    plan: str = "pro_49k"


@router.post("/subscription/create-payment")
def create_payment_request(
    body: CreatePaymentRequest,
    user: dict = Depends(get_current_user),
):
    """
    Tạo QR VietQR (MB Bank) và lưu payment record trạng thái pending.
    Frontend hiển thị QR → user quét và chuyển khoản → SePay webhook xử lý tiếp.
    """
    if body.plan not in PLAN_PRICES:
        raise HTTPException(status_code=400, detail=f"Gói không hợp lệ: {body.plan}")

    if not MB_ACCOUNT_NO:
        raise HTTPException(status_code=503, detail="Chưa cấu hình tài khoản ngân hàng.")

    user_id = str(user["id"])
    amount = PLAN_PRICES[body.plan]
    reference_code = _make_reference_code(user_id)

    # Lưu payment record
    try:
        payment = create_payment(user_id, amount, body.plan, reference_code)
    except Exception as e:
        logger.error(f"[Payment] create_payment lỗi: {e}")
        raise HTTPException(status_code=500, detail="Không thể tạo đơn thanh toán.")

    # Gọi VietQR API
    vietqr_payload = {
        "accountNo": MB_ACCOUNT_NO,
        "accountName": MB_ACCOUNT_NAME,
        "acqId": MB_BANK_ACQ_ID,
        "amount": amount,
        "addInfo": reference_code,
        "format": "text",
        "template": "compact2",
    }

    qr_url = None
    try:
        resp = http_requests.post(
            VIETQR_API_URL,
            json=vietqr_payload,
            timeout=8,
            headers={"x-client-id": "trendsense", "x-api-key": "DEMO"},
        )
        if resp.status_code == 200:
            data = resp.json()
            qr_url = data.get("data", {}).get("qrDataURL")  # base64 image
            if not qr_url:
                # Fallback: dùng URL shortcut của VietQR nếu API không trả base64
                qr_url = (
                    f"https://img.vietqr.io/image/{MB_BANK_ACQ_ID}-{MB_ACCOUNT_NO}"
                    f"-compact2.png?amount={amount}&addInfo={reference_code}"
                    f"&accountName={MB_ACCOUNT_NAME.replace(' ', '+')}"
                )
        else:
            logger.warning(f"[VietQR] Status {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        logger.warning(f"[VietQR] API lỗi, dùng URL fallback: {e}")

    # Fallback URL không cần gọi API
    if not qr_url:
        qr_url = (
            f"https://img.vietqr.io/image/{MB_BANK_ACQ_ID}-{MB_ACCOUNT_NO}"
            f"-compact2.png?amount={amount}&addInfo={reference_code}"
            f"&accountName={MB_ACCOUNT_NAME.replace(' ', '+')}"
        )

    return {
        "payment_id": str(payment["id"]),
        "reference_code": reference_code,
        "amount": amount,
        "amount_formatted": f"{amount:,} VND",
        "plan": body.plan,
        "plan_label": PLAN_LABELS[body.plan],
        "qr_url": qr_url,
        "bank": {
            "name": "MB Bank",
            "account_no": MB_ACCOUNT_NO,
            "account_name": MB_ACCOUNT_NAME,
        },
        "instructions": [
            f"1. Mở app ngân hàng và quét mã QR",
            f"2. Kiểm tra nội dung chuyển khoản: {reference_code}",
            f"3. Xác nhận số tiền: {amount:,} VND",
            f"4. Hệ thống sẽ tự động kích hoạt Pro trong vòng 1-2 phút sau khi nhận được tiền",
        ],
    }


# ── GET /api/subscription/check-payment/{ref} ──────────────────────────────────

@router.get("/subscription/check-payment/{reference_code}")
def check_payment_status(reference_code: str, user: dict = Depends(get_current_user)):
    """Frontend polling endpoint để kiểm tra trạng thái payment sau khi quét QR."""
    payment = get_payment_by_reference(reference_code)
    if not payment or str(payment["user_id"]) != str(user["id"]):
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch.")

    paid_at = payment.get("paid_at")
    if hasattr(paid_at, "isoformat"):
        paid_at = paid_at.isoformat()

    return {
        "status": payment["status"],       # 'pending' | 'completed'
        "paid_at": paid_at,
        "plan": payment["plan"],
        "amount": payment["amount"],
    }


# ── GET /api/subscription/history ──────────────────────────────────────────────

@router.get("/subscription/history")
def payment_history(user: dict = Depends(get_current_user)):
    """Lịch sử thanh toán của user."""
    user_id = str(user["id"])
    rows = get_payment_history(user_id)
    result = []
    for r in rows:
        r = dict(r)
        for key in ("paid_at", "created_at"):
            if hasattr(r.get(key), "isoformat"):
                r[key] = r[key].isoformat()
        result.append(r)
    return {"payments": result}


# ── POST /api/webhook/sepay ────────────────────────────────────────────────────

@router.post("/webhook/sepay", status_code=200)
async def sepay_webhook(request: Request):
    """
    Nhận webhook từ SePay khi có giao dịch khớp tài khoản MB Bank.
    SePay gửi POST với body JSON chứa thông tin giao dịch.
    Xác thực bằng HMAC-SHA256 signature trong header X-Sepay-Signature.

    Docs: https://docs.sepay.vn/webhook
    """
    body_bytes = await request.body()

    # Xác thực chữ ký SePay (bỏ qua nếu chưa có secret — chỉ trong dev)
    if SEPAY_WEBHOOK_SECRET:
        signature = request.headers.get("X-Sepay-Signature", "")
        mac = hmac.new(
            SEPAY_WEBHOOK_SECRET.encode(),
            body_bytes,
            hashlib.sha256,
        )
        expected = mac.hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("[SePay] Webhook signature không khớp!")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # SePay webhook format:
    # { "id": "...", "gateway": "MB Bank", "transactionDate": "...",
    #   "accountNumber": "...", "code": "TSPRO...",  ← nội dung CK
    #   "content": "TSPRO...", "transferType": "in",
    #   "transferAmount": 49000, "referenceCode": "...", ... }

    transfer_type = data.get("transferType", "")
    if transfer_type != "in":
        # Chỉ xử lý giao dịch tiền vào
        return {"status": "ignored", "reason": "not_incoming"}

    content: str = data.get("content", "") or data.get("code", "")
    transaction_id: str = str(data.get("id", "") or data.get("referenceCode", ""))
    amount: int = int(data.get("transferAmount", 0))

    # Tìm reference_code trong nội dung chuyển khoản
    # Nội dung có thể là "TSPRO ABC123 716042" hoặc "TSPRO ABC123716042"
    reference_code = None
    for token in content.upper().split():
        if token.startswith("TSPRO") and len(token) >= 11:
            reference_code = token
            break

    if not reference_code:
        logger.info(f"[SePay] Giao dịch {transaction_id} không khớp reference. Content: {content[:50]}")
        return {"status": "ignored", "reason": "no_reference_code"}

    # Lấy payment record
    payment = get_payment_by_reference(reference_code)
    if not payment:
        logger.warning(f"[SePay] reference_code {reference_code} không tồn tại trong DB")
        return {"status": "ignored", "reason": "reference_not_found"}

    # Kiểm tra số tiền (±1000 VND để tránh lỗi làm tròn)
    expected_amount = PLAN_PRICES.get(payment["plan"], 0)
    if abs(amount - expected_amount) > 1000:
        logger.warning(
            f"[SePay] Số tiền không khớp: nhận {amount}, mong đợi {expected_amount} "
            f"(ref: {reference_code})"
        )
        return {"status": "ignored", "reason": "amount_mismatch"}

    # Kích hoạt subscription
    success = complete_payment(reference_code, transaction_id)
    if success:
        logger.info(f"[SePay] ✅ Kích hoạt Pro thành công: ref={reference_code}, tx={transaction_id}")
        return {"status": "ok", "message": "Subscription activated"}
    else:
        logger.error(f"[SePay] ❌ complete_payment thất bại: ref={reference_code}")
        raise HTTPException(status_code=500, detail="Không thể kích hoạt subscription")
