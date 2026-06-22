# -*- coding: utf-8 -*-
"""Notification sender package exports.

Keep package imports lazy so importing a lightweight helper like
``src.notification_sender.gotify_sender`` does not eagerly pull in optional
heavy dependencies such as the Feishu SDK during FastAPI startup.
"""

from importlib import import_module
from typing import Any, Dict, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "AstrbotSender": (".astrbot_sender", "AstrbotSender"),
    "CustomWebhookSender": (".custom_webhook_sender", "CustomWebhookSender"),
    "DiscordSender": (".discord_sender", "DiscordSender"),
    "EmailSender": (".email_sender", "EmailSender"),
    "FeishuSender": (".feishu_sender", "FeishuSender"),
    "GotifySender": (".gotify_sender", "GotifySender"),
    "resolve_gotify_message_endpoint": (".gotify_sender", "resolve_gotify_message_endpoint"),
    "NtfySender": (".ntfy_sender", "NtfySender"),
    "resolve_ntfy_endpoint": (".ntfy_sender", "resolve_ntfy_endpoint"),
    "PushoverSender": (".pushover_sender", "PushoverSender"),
    "PushplusSender": (".pushplus_sender", "PushplusSender"),
    "Serverchan3Sender": (".serverchan3_sender", "Serverchan3Sender"),
    "SlackSender": (".slack_sender", "SlackSender"),
    "TelegramSender": (".telegram_sender", "TelegramSender"),
    "WechatSender": (".wechat_sender", "WechatSender"),
    "WECHAT_IMAGE_MAX_BYTES": (".wechat_sender", "WECHAT_IMAGE_MAX_BYTES"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    export = _EXPORTS.get(name)
    if export is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = export
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
