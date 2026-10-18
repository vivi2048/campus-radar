from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn

from app.config import APP_VERSION, env_value, load_settings


def _open_browser_when_ready(url: str, health_url: str) -> None:
    for _ in range(80):
        try:
            with urllib.request.urlopen(health_url, timeout=0.6) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(0.25)


def main() -> None:
    settings = load_settings()
    if not (settings.static_dir / "index.html").exists():
        raise SystemExit("找不到 static/index.html，请确认项目文件完整。")

    from app.main import app

    display_host = settings.host
    if display_host in {"0.0.0.0", "::"}:
        display_host = "127.0.0.1"
    if ":" in display_host:
        display_host = f"[{display_host}]"
    url = f"http://{display_host}:{settings.port}"

    print("", flush=True)
    print(f"  campus-radar v{APP_VERSION}", flush=True)
    print(f"  看板地址  {url}", flush=True)
    print(f"  数据目录  {settings.data_dir}", flush=True)
    print("  停止服务  Ctrl+C", flush=True)
    print("", flush=True)

    if settings.host not in {"127.0.0.1", "localhost", "::1"}:
        print("  [提醒] 当前监听非本机地址，且应用没有登录验证，请勿暴露到公网。", flush=True)
        print("", flush=True)

    if env_value("NO_BROWSER").lower() not in {"1", "true", "yes"}:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(url, f"{url}/api/health"),
            daemon=True,
        ).start()

    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
