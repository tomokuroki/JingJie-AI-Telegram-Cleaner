from __future__ import annotations

import asyncio
from dataclasses import asdict

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from config import load_settings, save_env_value
from i18n import tr
from ollama_ai import OllamaClassifier
from telegram_cleaner import TelegramCleaner

console = Console()


def banner(lang: str) -> None:
    console.print(Panel.fit(
        f"[bold cyan]{tr(lang, 'title')}[/bold cyan]\n[dim]{tr(lang, 'subtitle')}[/dim]",
        border_style="cyan",
    ))


def setup_credentials() -> None:
    settings = load_settings()
    if settings.telegram_api_id and settings.telegram_api_hash:
        return
    console.print(f"[yellow]{tr(settings.lang, 'need_api')}[/yellow]")
    while True:
        api_id = Prompt.ask(tr(settings.lang, "api_id")).strip()
        if api_id.isdigit():
            break
        console.print("[red]API ID must be numeric[/red]")
    api_hash = Prompt.ask(tr(settings.lang, "api_hash"), password=True).strip()
    phone = Prompt.ask(tr(settings.lang, "phone"), default=settings.telegram_phone).strip()
    save_env_value("TELEGRAM_API_ID", api_id)
    save_env_value("TELEGRAM_API_HASH", api_hash)
    if phone:
        save_env_value("TELEGRAM_PHONE", phone)
    console.print(f"[green]{tr(settings.lang, 'saved')}[/green]")


def change_language() -> None:
    settings = load_settings()
    console.print(tr(settings.lang, "lang_pick"))
    choice = Prompt.ask(">", choices=["1", "2", "3"], default="1")
    lang = {"1": "zh", "2": "en", "3": "ru"}[choice]
    save_env_value("APP_LANG", lang)
    console.print("[green]OK[/green]")


def show_settings() -> None:
    settings = load_settings()
    safe = asdict(settings)
    safe["telegram_api_hash"] = "***" if settings.telegram_api_hash else ""
    safe["telegram_phone"] = settings.telegram_phone[:4] + "***" if settings.telegram_phone else ""
    console.print(Panel.fit("\n".join(f"[bold]{k}[/bold] = {v}" for k, v in safe.items()), title=tr(settings.lang, "config")))


async def run_scan(real_mode: bool) -> None:
    setup_credentials()
    settings = load_settings()
    classifier = OllamaClassifier(settings)
    console.print(f"[dim]{tr(settings.lang, 'ollama_check')}[/dim]")
    ok, detail = await asyncio.to_thread(classifier.check)
    if not ok:
        console.print(f"[bold red]{tr(settings.lang, 'ollama_missing')}[/bold red]\n[dim]{detail}[/dim]")
        return
    console.print(f"[green]✓ {tr(settings.lang, 'ollama_ok')}[/green]")
    console.print(f"[yellow]{tr(settings.lang, 'real' if real_mode else 'dry')}[/yellow]")

    cleaner = TelegramCleaner(settings, classifier, console)
    try:
        console.print(f"[dim]{tr(settings.lang, 'login')}[/dim]")
        await cleaner.connect()
        results = await cleaner.scan()
        cleaner.print_results(results)
        json_path, csv_path = cleaner.save_report(results)
        console.print(f"[dim]{tr(settings.lang, 'report')}: {json_path.name}, {csv_path.name}[/dim]")

        candidates = [item for item in results if item.action == "candidate"]
        if not candidates:
            console.print(f"[green]{tr(settings.lang, 'none')}[/green]")
            return
        if not real_mode:
            return

        confirm = Prompt.ask(f"[bold red]{tr(settings.lang, 'confirm')}[/bold red]", default="NO")
        if confirm.strip() != "LEAVE":
            console.print(f"[yellow]{tr(settings.lang, 'cancel')}[/yellow]")
            return

        success, failed = await cleaner.leave_candidates(results)
        json_path, csv_path = cleaner.save_report(results)
        console.print(f"[bold green]{tr(settings.lang, 'done')}: {success}[/bold green] | [red]failed: {failed}[/red]")
        console.print(f"[dim]{tr(settings.lang, 'report')}: {json_path.name}, {csv_path.name}[/dim]")
    finally:
        await cleaner.close()


def main() -> None:
    while True:
        settings = load_settings()
        console.clear()
        banner(settings.lang)
        console.print(f"\n[bold]{tr(settings.lang, 'menu')}[/bold]")
        console.print(f"[cyan]1[/cyan]. {tr(settings.lang, 'scan')}")
        console.print(f"[red]2[/red]. {tr(settings.lang, 'clean')}")
        console.print(f"[cyan]3[/cyan]. {tr(settings.lang, 'lang')}")
        console.print(f"[cyan]4[/cyan]. {tr(settings.lang, 'settings')}")
        console.print(f"[cyan]0[/cyan]. {tr(settings.lang, 'exit')}")
        choice = Prompt.ask(tr(settings.lang, "choice"), choices=["0", "1", "2", "3", "4"], default="1")
        try:
            if choice == "0":
                return
            if choice == "1":
                asyncio.run(run_scan(real_mode=False))
                Prompt.ask("Enter", default="")
            elif choice == "2":
                asyncio.run(run_scan(real_mode=True))
                Prompt.ask("Enter", default="")
            elif choice == "3":
                change_language()
            elif choice == "4":
                show_settings()
                Prompt.ask("Enter", default="")
        except KeyboardInterrupt:
            console.print(f"\n[yellow]{tr(settings.lang, 'ctrlc')}[/yellow]")
            return
        except Exception as exc:
            console.print(f"[bold red]{type(exc).__name__}: {exc}[/bold red]")
            Prompt.ask("Enter", default="")


if __name__ == "__main__":
    main()
