from __future__ import annotations

import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table
from telethon import TelegramClient, functions, types
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    RPCError,
    SessionPasswordNeededError,
)

from config import BASE_DIR, Settings
from i18n import tr
from models import ChannelSnapshot, ScanResult
from ollama_ai import OllamaClassifier


class TelegramCleaner:
    def __init__(self, settings: Settings, classifier: OllamaClassifier, console: Console) -> None:
        if settings.telegram_api_id is None or not settings.telegram_api_hash:
            raise ValueError("Telegram API credentials are missing")
        self.settings = settings
        self.classifier = classifier
        self.console = console
        self.client = TelegramClient(
            str(BASE_DIR / settings.session_name),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        self.results: list[ScanResult] = []
        self.entities_by_id: dict[int, types.Channel] = {}

    async def connect(self) -> None:
        # Explicit login flow instead of TelegramClient.start().  This lets the
        # UI show *where* Telegram delivered the code (Telegram app / SMS /
        # email / call) and gives useful errors instead of looking like the
        # code was never sent.
        await self.client.connect()
        if await self.client.is_user_authorized():
            self.console.print(f"[green]✓ {tr(self.settings.lang, 'already_authorized')}[/green]")
            return

        phone = self.settings.telegram_phone.strip() if self.settings.telegram_phone else ""
        if not phone:
            phone = Prompt.ask(tr(self.settings.lang, "phone_required")).strip()
        if not phone:
            raise ValueError(tr(self.settings.lang, "phone_empty"))

        self.console.print(f"[dim]{tr(self.settings.lang, 'requesting_code')}[/dim]")
        try:
            sent = await self.client.send_code_request(phone)
        except FloodWaitError as exc:
            raise RuntimeError(tr(self.settings.lang, "flood_wait").format(seconds=exc.seconds)) from exc
        except RPCError as exc:
            raise RuntimeError(f"{tr(self.settings.lang, 'code_request_failed')}: {exc}") from exc

        delivery = self._delivery_label(getattr(sent, "type", None))
        timeout = getattr(sent, "timeout", None)
        suffix = f" ({timeout}s)" if isinstance(timeout, int) and timeout > 0 else ""
        self.console.print(f"[bold cyan]{tr(self.settings.lang, 'code_sent_via').format(method=delivery)}{suffix}[/bold cyan]")
        self.console.print(f"[dim]{tr(self.settings.lang, 'code_hint')}[/dim]")

        phone_code_hash = getattr(sent, "phone_code_hash", None)
        for attempt in range(1, 4):
            code = Prompt.ask(tr(self.settings.lang, "enter_code")).strip().replace(" ", "")
            if not code:
                raise RuntimeError(tr(self.settings.lang, "code_empty"))
            try:
                await self.client.sign_in(
                    phone=phone,
                    code=code,
                    phone_code_hash=phone_code_hash,
                )
                self.console.print(f"[green]✓ {tr(self.settings.lang, 'authorized')}[/green]")
                return
            except SessionPasswordNeededError:
                password = Prompt.ask(tr(self.settings.lang, "twofa_password"), password=True).strip()
                await self.client.sign_in(password=password)
                self.console.print(f"[green]✓ {tr(self.settings.lang, 'authorized')}[/green]")
                return
            except PhoneCodeInvalidError:
                if attempt >= 3:
                    raise RuntimeError(tr(self.settings.lang, "code_invalid_final"))
                self.console.print(f"[red]{tr(self.settings.lang, 'code_invalid')}[/red]")
            except PhoneCodeExpiredError as exc:
                raise RuntimeError(tr(self.settings.lang, "code_expired")) from exc
            except RPCError as exc:
                raise RuntimeError(f"{tr(self.settings.lang, 'login_failed')}: {exc}") from exc

    def _delivery_label(self, sent_type: object | None) -> str:
        name = sent_type.__class__.__name__ if sent_type is not None else ""
        key = {
            "SentCodeTypeApp": "delivery_app",
            "SentCodeTypeSms": "delivery_sms",
            "SentCodeTypeCall": "delivery_call",
            "SentCodeTypeFlashCall": "delivery_call",
            "SentCodeTypeMissedCall": "delivery_call",
            "SentCodeTypeEmailCode": "delivery_email",
            "SentCodeTypeFragmentSms": "delivery_fragment",
            "SentCodeTypeFirebaseSms": "delivery_sms",
            "SentCodeTypeSmsWord": "delivery_sms",
            "SentCodeTypeSmsPhrase": "delivery_sms",
        }.get(name, "delivery_unknown")
        return tr(self.settings.lang, key)

    async def close(self) -> None:
        await self.client.disconnect()

    async def scan(self) -> list[ScanResult]:
        self.results = []
        self.entities_by_id = {}
        dialogs = await self.client.get_dialogs()
        candidates: list[types.Channel] = []

        for dialog in dialogs:
            entity = dialog.entity
            # Hard privacy boundary: Users (including bots) and ordinary private chats are skipped.
            if isinstance(entity, types.User):
                continue
            if not isinstance(entity, types.Channel):
                continue
            is_broadcast = bool(getattr(entity, "broadcast", False))
            is_megagroup = bool(getattr(entity, "megagroup", False))
            if is_broadcast and not self.settings.scan_broadcast_channels:
                continue
            if is_megagroup and not self.settings.scan_megagroups:
                continue
            if not is_broadcast and not is_megagroup:
                continue
            candidates.append(entity)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=False,
        ) as progress:
            task = progress.add_task(tr(self.settings.lang, "scan_start"), total=None)
            for index, entity in enumerate(candidates, 1):
                progress.update(task, description=f"[{index}/{len(candidates)}] {entity.title}")
                result = await self._process_channel(entity)
                self.results.append(result)
        return self.results

    async def _process_channel(self, entity: types.Channel) -> ScanResult:
        username = getattr(entity, "username", None)
        title = getattr(entity, "title", str(entity.id))

        if entity.id in self.settings.safe_ids or (username and username.lower() in self.settings.safe_usernames):
            return ScanResult(entity.id, title, username, None, "protected", tr(self.settings.lang, "allowlist"), True)

        if self.settings.protect_verified and bool(getattr(entity, "verified", False)):
            return ScanResult(entity.id, title, username, None, "protected", tr(self.settings.lang, "verified"), True)

        if self.settings.protect_admins:
            try:
                permissions = await self.client.get_permissions(entity, "me")
                if bool(getattr(permissions, "is_admin", False)) or bool(getattr(permissions, "is_creator", False)):
                    return ScanResult(entity.id, title, username, None, "protected", tr(self.settings.lang, "admin"), True)
            except RPCError as exc:
                return ScanResult(
                    entity.id,
                    title,
                    username,
                    None,
                    "protected",
                    "Could not verify admin/owner status; kept for safety",
                    True,
                    error=str(exc)[:300],
                )

        try:
            full = await self.client(functions.channels.GetFullChannelRequest(channel=entity))
            description = getattr(full.full_chat, "about", "") or ""
        except RPCError:
            description = ""

        messages: list[str] = []
        try:
            async for msg in self.client.iter_messages(entity, limit=self.settings.recent_messages):
                text = (msg.raw_text or "").strip()
                if text:
                    messages.append(text)
        except RPCError:
            pass

        snapshot = ChannelSnapshot(
            id=entity.id,
            title=title,
            username=username,
            description=description,
            recent_messages=messages,
            is_broadcast=bool(getattr(entity, "broadcast", False)),
            is_megagroup=bool(getattr(entity, "megagroup", False)),
            verified=bool(getattr(entity, "verified", False)),
        )
        try:
            classification = await asyncio.to_thread(self.classifier.classify, snapshot)
        except Exception as exc:
            return ScanResult(
                entity.id,
                title,
                username,
                None,
                "keep",
                tr(self.settings.lang, "ai_error"),
                error=str(exc)[:300],
            )

        if self.classifier.should_remove(classification):
            self.entities_by_id[entity.id] = entity
            return ScanResult(entity.id, title, username, classification, "candidate", classification.reason)

        return ScanResult(entity.id, title, username, classification, "keep", classification.reason)

    def print_results(self, results: list[ScanResult]) -> None:
        table = Table(show_lines=False)
        table.add_column("#", justify="right", style="dim", width=4)
        table.add_column("Channel", overflow="fold")
        table.add_column("Adult", justify="right", width=7)
        table.add_column("Spam", justify="right", width=7)
        table.add_column("Junk", justify="right", width=7)
        table.add_column("Action", width=11)
        table.add_column("Reason", overflow="fold")

        for i, item in enumerate(results, 1):
            c = item.classification
            scores = ("-", "-", "-") if c is None else (
                f"{c.adult_score:.2f}",
                f"{c.spam_score:.2f}",
                f"{c.junk_score:.2f}",
            )
            action_style = {
                "candidate": "bold red",
                "protected": "bold cyan",
                "keep": "green",
            }.get(item.action, "white")
            handle = f"@{item.username}" if item.username else f"id:{item.channel_id}"
            table.add_row(
                str(i),
                f"{item.title}\n[dim]{handle}[/dim]",
                *scores,
                f"[{action_style}]{item.action}[/{action_style}]",
                item.reason,
            )
        self.console.print(table)

    async def leave_candidates(self, results: list[ScanResult]) -> tuple[int, int]:
        success = 0
        failed = 0
        for item in results:
            if item.action != "candidate":
                continue
            entity = self.entities_by_id.get(item.channel_id)
            if entity is None:
                failed += 1
                continue
            try:
                # Final admin/owner re-check immediately before destructive action.
                if self.settings.protect_admins:
                    try:
                        permissions = await self.client.get_permissions(entity, "me")
                        if bool(getattr(permissions, "is_admin", False)) or bool(getattr(permissions, "is_creator", False)):
                            item.action = "protected"
                            item.reason = tr(self.settings.lang, "admin")
                            item.protected = True
                            continue
                    except RPCError:
                        # Fail closed: if we cannot verify protection at action time, do not leave.
                        item.action = "protected"
                        item.reason = "Could not verify admin status; kept for safety"
                        item.protected = True
                        continue
                await self.client(functions.channels.LeaveChannelRequest(channel=entity))
                item.action = "left"
                success += 1
                await asyncio.sleep(0.7)
            except FloodWaitError as exc:
                item.error = f"FloodWait {exc.seconds}s"
                failed += 1
                break
            except RPCError as exc:
                item.error = str(exc)
                failed += 1
        return success, failed

    def save_report(self, results: list[ScanResult]) -> tuple[Path, Path]:
        log_dir = BASE_DIR / "logs"
        log_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = log_dir / f"scan_{stamp}.json"
        csv_path = log_dir / f"scan_{stamp}.csv"

        with json_path.open("w", encoding="utf-8") as fh:
            json.dump([item.to_dict() for item in results], fh, ensure_ascii=False, indent=2)

        with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["channel_id", "title", "username", "adult", "spam", "junk", "action", "reason", "error"])
            for item in results:
                c = item.classification
                writer.writerow([
                    item.channel_id,
                    item.title,
                    item.username or "",
                    "" if c is None else f"{c.adult_score:.3f}",
                    "" if c is None else f"{c.spam_score:.3f}",
                    "" if c is None else f"{c.junk_score:.3f}",
                    item.action,
                    item.reason,
                    item.error or "",
                ])
        return json_path, csv_path
