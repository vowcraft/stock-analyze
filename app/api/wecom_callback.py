from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.services.wecom_crypto import WeComCallbackCrypto


logger = logging.getLogger(__name__)
router = APIRouter(prefix=settings.wecom_callback_path)
crypto = WeComCallbackCrypto(
    token=settings.wecom_callback_token,
    encoding_aes_key=settings.wecom_callback_encoding_aes_key,
    receive_id=settings.wecom_callback_receive_id,
)


@router.get("", response_class=PlainTextResponse)
def verify_callback_url(
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
) -> str:
    return crypto.verify_url(msg_signature, timestamp, nonce, echostr)


@router.post("", response_class=PlainTextResponse)
async def receive_callback_message(
    request: Request,
    msg_signature: str,
    timestamp: str,
    nonce: str,
) -> str:
    request_body = (await request.body()).decode("utf-8")
    plain_message = crypto.decrypt_message(msg_signature, timestamp, nonce, request_body)
    logger.info("[wecom-callback] received: %s", plain_message)
    return "success"
