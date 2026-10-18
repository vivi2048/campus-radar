from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    short_name: str
    host: str
    port: int
    auth_label: str
    hint: str
    steps: tuple[str, ...]
    custom: bool = False

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = list(self.steps)
        return data


PROVIDERS: dict[str, Provider] = {
    "qq": Provider(
        id="qq",
        name="QQ 邮箱",
        short_name="QQ",
        host="imap.qq.com",
        port=993,
        auth_label="IMAP 授权码",
        hint="请填写邮箱设置中生成的 16 位授权码，不是 QQ 登录密码。",
        steps=(
            "登录 QQ 邮箱网页版，进入「设置 → 账号」。",
            "找到「IMAP/SMTP 服务」并开启。",
            "按页面提示生成授权码，将授权码填入下方。",
        ),
    ),
    "163": Provider(
        id="163",
        name="网易 163 邮箱",
        short_name="163",
        host="imap.163.com",
        port=993,
        auth_label="客户端授权码",
        hint="需要在网页版开启 IMAP 服务，并填写客户端授权码。",
        steps=(
            "登录 163 邮箱网页版，进入「设置 → POP3/SMTP/IMAP」。",
            "开启 IMAP 服务，并按提示获取客户端授权码。",
            "若提示需要短信验证，请按网页提示完成后再连接。",
        ),
    ),
    "126": Provider(
        id="126",
        name="网易 126 邮箱",
        short_name="126",
        host="imap.126.com",
        port=993,
        auth_label="客户端授权码",
        hint="需要在网页版开启 IMAP 服务，并填写客户端授权码。",
        steps=(
            "登录 126 邮箱网页版，进入「设置 → POP3/SMTP/IMAP」。",
            "开启 IMAP 服务，并按提示获取客户端授权码。",
            "若提示需要短信验证，请按网页提示完成后再连接。",
        ),
    ),
    "gmail": Provider(
        id="gmail",
        name="Gmail",
        short_name="Gmail",
        host="imap.gmail.com",
        port=993,
        auth_label="Google 应用专用密码",
        hint="建议开启两步验证后生成应用专用密码；普通 Google 密码无法登录 IMAP。",
        steps=(
            "在 Google 账号中开启两步验证。",
            "进入「应用专用密码」页面，创建一个用于邮件的密码。",
            "将生成的 16 位应用专用密码填入下方。",
        ),
    ),
    "custom": Provider(
        id="custom",
        name="自定义 IMAP",
        short_name="IMAP",
        host="",
        port=993,
        auth_label="密码或授权码",
        hint="仅支持 SSL/TLS 加密的 IMAP 邮箱。大多数高校和企业邮箱都提供此方式。",
        steps=(
            "向邮箱服务商确认 IMAP 服务器地址与端口（通常为 993）。",
            "确认账号允许第三方客户端登录，并使用密码或授权码。",
        ),
        custom=True,
    ),
}


def get_provider(provider_id: str) -> Provider | None:
    return PROVIDERS.get(provider_id)


def list_providers() -> list[dict[str, Any]]:
    return [provider.public_dict() for provider in PROVIDERS.values()]
