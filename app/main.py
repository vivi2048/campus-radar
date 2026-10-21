from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_VERSION, Settings, env_value, load_settings, migrate_legacy_database
from .db import Database
from .llm import (
    LLMConfigError,
    LLMError,
    build_llm_fallback,
    get_llm_settings_view,
    save_llm_settings,
    test_llm_connection,
)
from .mail.imap import MailboxError
from .mail.providers import list_providers
from .schemas import AISettingsUpdate, AccountCreate, AccountUpdate, EventPayload, EventUpdate
from .security import SecretBox
from .services.accounts import (
    AccountError,
    clear_account_mail_data,
    create_account,
    delete_account,
    get_account,
    get_raw_account,
    list_accounts,
    test_account_connection,
    update_account,
)
from .services.events import (
    EventValidationError,
    clear_demo,
    create_manual_event,
    delete_event,
    get_event,
    list_events,
    seed_demo,
    update_event,
)
from .services.sync import AutoSyncWorker, SyncManager, SyncService
from .timeutil import local_now


def _configure_logger(settings: Settings) -> logging.Logger:
    logger = logging.getLogger("campus-radar")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    migrate_legacy_database(settings.data_dir)
    logger = _configure_logger(settings)
    db = Database(settings.db_path)
    db.init()
    vault = SecretBox(settings.secret_key_path, env_key=env_value("SECRET_KEY"))
    sync_service = SyncService(
        db,
        vault,
        logger,
        llm_factory=lambda: build_llm_fallback(db, vault, logger),
    )
    sync_manager = SyncManager(db, sync_service, logger)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        worker: AutoSyncWorker | None = None
        if settings.start_scheduler:
            worker = AutoSyncWorker(
                db,
                sync_manager,
                logger,
                interval_minutes=settings.auto_sync_minutes,
            )
            worker.start()
            logger.info("Auto sync worker started (interval=%s min)", settings.auto_sync_minutes)
        try:
            yield
        finally:
            if worker:
                worker.stop()

    app = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.vault = vault
    app.state.sync_manager = sync_manager
    app.state.logger = logger

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        # The bundled UI sets this header on writes. A cross-site form or simple
        # request cannot set it without a CORS preflight, which this app denies.
        if (
            request.url.path.startswith("/api/")
            and request.method not in {"GET", "HEAD", "OPTIONS"}
            and request.headers.get("X-Campus-Radar-Request") != "1"
        ):
            response = JSONResponse(status_code=403, content={"detail": "请求来源校验失败"})
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        if (
            request.url.path.startswith("/api/")
            or request.url.path.startswith("/static/")
            or request.url.path in {"/", "/favicon.svg"}
        ):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception(_: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=400, content={"detail": "请求参数格式不正确，请检查后重试。"})

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "服务发生内部错误，请查看日志。"})

    static_dir = settings.static_dir
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon():
        path = static_dir / "favicon.svg"
        if not path.exists():
            raise HTTPException(status_code=404)
        return FileResponse(path, media_type="image/svg+xml")

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"ok": True, "version": APP_VERSION}

    @app.get("/api/meta")
    async def meta() -> dict[str, Any]:
        demo_row = db.fetch_one("SELECT COUNT(*) AS count FROM events WHERE is_demo = 1")
        return {
            "app_name": settings.app_name,
            "version": APP_VERSION,
            "timezone": "Asia/Shanghai",
            "auto_sync_minutes": settings.auto_sync_minutes,
            "server_time": local_now().isoformat(timespec="seconds"),
            "demo_count": int(demo_row["count"]) if demo_row else 0,
        }

    @app.get("/api/providers")
    async def providers() -> list[dict[str, Any]]:
        return list_providers()

    @app.get("/api/ai-settings")
    def ai_settings_get() -> dict[str, Any]:
        return get_llm_settings_view(db)

    @app.put("/api/ai-settings")
    def ai_settings_update(payload: AISettingsUpdate) -> dict[str, Any]:
        try:
            return save_llm_settings(db, vault, payload.model_dump())
        except LLMConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-settings/test")
    def ai_settings_test() -> dict[str, Any]:
        try:
            message = test_llm_connection(db, vault)
        except LLMError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"message": message}

    @app.get("/api/accounts")
    async def accounts_list() -> list[dict[str, Any]]:
        return list_accounts(db)

    @app.post("/api/accounts", status_code=201)
    async def accounts_create(payload: AccountCreate):
        data = payload.model_dump()
        try:
            account = create_account(db, vault, data)
        except (AccountError, MailboxError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Failed to create account")
            raise HTTPException(status_code=500, detail="保存邮箱时发生错误，请稍后重试。") from exc
        sync_manager.trigger(int(account["id"]), reason="initial")
        updated = get_account(db, int(account["id"]))
        return {"account": updated or account, "sync_started": True}

    @app.patch("/api/accounts/{account_id}")
    async def accounts_update(account_id: int, payload: AccountUpdate):
        raw = get_raw_account(db, account_id)
        if not raw:
            raise HTTPException(status_code=404, detail="邮箱账号不存在")
        changes = payload.changes()
        if sync_manager.is_active(account_id) and ({"password", "folder"} & set(changes)):
            raise HTTPException(status_code=409, detail="邮箱正在同步，请稍后再修改授权码或文件夹。")
        try:
            updated = update_account(db, vault, account_id, changes)
        except (AccountError, MailboxError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not updated:
            raise HTTPException(status_code=404, detail="邮箱账号不存在")
        return updated

    @app.post("/api/accounts/{account_id}/test")
    async def accounts_test(account_id: int):
        try:
            message = test_account_connection(db, vault, account_id)
        except AccountError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except MailboxError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"message": message}

    @app.post("/api/accounts/{account_id}/sync", status_code=202)
    async def accounts_sync(account_id: int):
        if not get_raw_account(db, account_id):
            raise HTTPException(status_code=404, detail="邮箱账号不存在")
        if not sync_manager.trigger(account_id, reason="manual"):
            raise HTTPException(status_code=409, detail="这个邮箱正在同步中，请稍候。")
        return {"started": True, "account": get_account(db, account_id)}

    @app.post("/api/accounts/{account_id}/rescan", status_code=202)
    async def accounts_rescan(account_id: int):
        if not get_raw_account(db, account_id):
            raise HTTPException(status_code=404, detail="邮箱账号不存在")
        if not sync_manager.trigger(account_id, reason="rescan", rescan=True):
            raise HTTPException(status_code=409, detail="这个邮箱正在同步中，请稍候。")
        return {"started": True, "rescan": True, "account": get_account(db, account_id)}

    @app.delete("/api/accounts/{account_id}/messages")
    async def accounts_clear_messages(account_id: int, reset_cursor: bool = False):
        if sync_manager.is_active(account_id):
            raise HTTPException(status_code=409, detail="邮箱正在同步，请等同步结束后再清空。")
        result = clear_account_mail_data(
            db, account_id, reset_cursor=reset_cursor
        )
        if result is None:
            raise HTTPException(status_code=404, detail="邮箱账号不存在")
        return {"cleared": True, "reset_cursor": reset_cursor, **result}

    @app.delete("/api/accounts/{account_id}")
    async def accounts_delete(account_id: int):
        if sync_manager.is_active(account_id):
            raise HTTPException(status_code=409, detail="邮箱正在同步，请等同步结束后再删除。")
        if not delete_account(db, account_id):
            raise HTTPException(status_code=404, detail="邮箱账号不存在")
        return {"deleted": True}

    @app.post("/api/sync-all", status_code=202)
    async def sync_all():
        rows = list_accounts(db)
        started: list[int] = []
        skipped: list[int] = []
        for account in rows:
            if account["enabled"] and sync_manager.trigger(int(account["id"]), reason="manual-all"):
                started.append(int(account["id"]))
            else:
                skipped.append(int(account["id"]))
        return {"started": started, "skipped": skipped}

    @app.get("/api/events")
    async def events_list():
        return list_events(db)

    @app.get("/api/events/{event_id}")
    async def events_detail(event_id: int):
        event = get_event(db, event_id, include_source=True)
        if not event:
            raise HTTPException(status_code=404, detail="记录不存在")
        return event

    @app.post("/api/events", status_code=201)
    async def events_create(payload: EventPayload):
        try:
            return create_manual_event(db, payload.model_dump(exclude={"auto_notes"}))
        except EventValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/events/{event_id}")
    async def events_update(event_id: int, payload: EventUpdate):
        try:
            event = update_event(db, event_id, payload.changes())
        except EventValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not event:
            raise HTTPException(status_code=404, detail="记录不存在")
        return event

    @app.delete("/api/events/{event_id}")
    async def events_delete(event_id: int):
        if not delete_event(db, event_id):
            raise HTTPException(status_code=404, detail="记录不存在")
        return {"deleted": True}

    @app.post("/api/demo", status_code=201)
    async def demo_seed():
        inserted = seed_demo(db)
        return {"inserted": inserted, "demo_count": count_demo(db)}

    @app.delete("/api/demo")
    async def demo_clear():
        deleted = clear_demo(db)
        return {"deleted": deleted}

    return app


def count_demo(db: Database) -> int:
    row = db.fetch_one("SELECT COUNT(*) AS count FROM events WHERE is_demo = 1")
    return int(row["count"]) if row else 0


app = create_app()
