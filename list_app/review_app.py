"""Review and merge new applications via NiceGUI browser UI.

Workflow:
    1. File Selection — User enters or selects a JSON file containing new application entries.
    2. Review — Each application is shown in a split view (editable form + iframe preview).
       The user can edit name/description/tags and decide: Accept, Skip, or Reject.
    3. Summary — A table of all entries with their decisions. From here the user can:
       - Merge accepted entries into applications.json and regenerate README.md.
       - Save unmerged (skipped/pending) entries to a timestamped JSON file for later review.
"""

import argparse
import html
import importlib.util
import json
import pkgutil
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import quote

# Python 3.14 compatibility: pkgutil.find_loader was removed, but vbuild still uses it.
if not hasattr(pkgutil, "find_loader"):
    pkgutil.find_loader = lambda name: importlib.util.find_spec(name)  # type: ignore[attr-defined]

import requests
from loguru import logger
from nicegui import app, ui
from pydantic import ValidationError
from starlette.responses import Response

from list_app.data import ApplicationData
from list_app.data_utils import (
    DATA_TAGS_PATH,
    load_applications,
    save_applications,
    sort_application_tags,
)
from list_app.generate_readme import generate_and_save_readme
from list_app.log_utils import init_logs

PROXY_TIMEOUT = 15
PROXY_CACHE_TTL = 300  # Cache proxy responses for 5 minutes
PROXY_CACHE_MAX_SIZE = 50
DEFAULT_PORT = 8080

_cli_input_file: str = ""

# Reusable session for connection pooling
_http_session = requests.Session()
_http_session.headers.update({"User-Agent": "Mozilla/5.0"})

# Simple TTL cache for proxy responses: url -> (content, content_type, headers, status, timestamp)
_proxy_cache: dict[str, tuple[bytes, str, dict[str, str], int, float]] = {}


class Decision(StrEnum):
    """Possible review decisions for an application entry."""

    PENDING = "pending"
    ACCEPT = "accept"
    SKIP = "skip"
    REJECT = "reject"
    MERGED = "merged"


DECISION_COLORS: dict[Decision, str] = {
    Decision.ACCEPT: "green",
    Decision.SKIP: "grey",
    Decision.REJECT: "red",
    Decision.MERGED: "teal",
}


@dataclass
class ReviewState:
    """Mutable state for the review session."""

    input_file: Path | None = None
    current_index: int = 0
    decisions: list[Decision] = field(default_factory=list)
    edited_apps: list[ApplicationData] = field(default_factory=list)
    existing_urls: set[str] = field(default_factory=set)
    existing_names: set[str] = field(default_factory=set)
    all_tags: list[str] = field(default_factory=list)


def _load_tags() -> list[str]:
    """Load existing tags from tags.json.

    Returns:
        Sorted list of tag strings.
    """
    if not DATA_TAGS_PATH.exists():
        logger.warning(f"Tags file not found: {DATA_TAGS_PATH}")
        return []
    with DATA_TAGS_PATH.open("rt") as f:
        data: list[str] = json.load(f)
    logger.debug(f"Loaded {len(data)} tags from {DATA_TAGS_PATH}")
    return data


def perform_merge(accepted_apps: list[ApplicationData]) -> tuple[int, int]:
    """Merge accepted apps into applications.json and regenerate README.

    Args:
        accepted_apps: List of reviewed and accepted ApplicationData entries.

    Returns:
        Tuple of (added_count, replaced_count).
    """
    existing = load_applications()
    url_to_idx = {a.url: i for i, a in enumerate(existing)}

    added = 0
    replaced = 0
    for app_data in accepted_apps:
        if app_data.url in url_to_idx:
            logger.info(f"Replacing existing app: '{app_data.name}' ({app_data.url})")
            existing[url_to_idx[app_data.url]] = app_data
            replaced += 1
        else:
            logger.info(f"Adding new app: '{app_data.name}' ({app_data.url})")
            existing.append(app_data)
            added += 1

    existing.sort(key=lambda x: x.name.lower())
    save_applications(existing)
    generate_and_save_readme(existing)
    logger.info(f"Merge complete: {added} added, {replaced} replaced")
    return added, replaced


# --- Proxy endpoint for iframe preview ---


def _evict_stale_cache() -> None:
    """Remove expired entries from the proxy cache."""
    now = time.monotonic()
    stale_keys = [k for k, v in _proxy_cache.items() if now - v[4] > PROXY_CACHE_TTL]
    if stale_keys:
        logger.debug(f"Evicting {len(stale_keys)} stale proxy cache entries")
    for k in stale_keys:
        del _proxy_cache[k]
    # Evict oldest if over max size
    while len(_proxy_cache) > PROXY_CACHE_MAX_SIZE:
        oldest_key = min(_proxy_cache, key=lambda k: _proxy_cache[k][4])
        del _proxy_cache[oldest_key]


def _fetch_and_process(url: str) -> tuple[bytes, str, dict[str, str], int]:
    """Fetch URL, strip frame-blocking headers, inject base tag.

    Args:
        url: The external URL to fetch.

    Returns:
        Tuple of (content, content_type, filtered_headers, status_code).
    """
    resp = _http_session.get(url, timeout=PROXY_TIMEOUT)

    content = resp.content
    content_type = resp.headers.get("content-type", "")

    # Inject <base> tag for HTML pages so relative URLs resolve correctly
    if "text/html" in content_type:
        escaped_url = html.escape(url, quote=True)
        base_tag = f'<base href="{escaped_url}">'.encode()
        if b"<head>" in content:
            content = content.replace(b"<head>", b"<head>" + base_tag, 1)
        elif b"<HEAD>" in content:
            content = content.replace(b"<HEAD>", b"<HEAD>" + base_tag, 1)
        else:
            content = base_tag + content

    headers_to_strip = {
        "x-frame-options",
        "content-security-policy",
        "content-security-policy-report-only",
        "content-encoding",
        "transfer-encoding",
        "content-length",
    }
    filtered_headers = {k: v for k, v in resp.headers.items() if k.lower() not in headers_to_strip}

    return content, content_type, filtered_headers, resp.status_code


@app.get("/proxy")
def proxy_page(url: str) -> Response:
    """Fetch external URL and strip frame-blocking headers for iframe embedding.

    Args:
        url: The external URL to fetch and proxy.

    Returns:
        Proxied response with frame-blocking headers removed.
    """
    if not url.startswith(("http://", "https://")):
        logger.warning(f"Proxy rejected invalid URL scheme: {url}")
        return Response("Invalid URL scheme", status_code=400)

    # Check cache
    cached = _proxy_cache.get(url)
    if cached and (time.monotonic() - cached[4]) < PROXY_CACHE_TTL:
        logger.debug(f"Proxy cache hit: {url}")
        content, content_type, filtered_headers, status_code = cached[:4]
        return Response(
            content=content,
            status_code=status_code,
            headers=filtered_headers,
            media_type=content_type or "text/html",
        )

    logger.debug(f"Proxy fetching: {url}")
    try:
        content, content_type, filtered_headers, status_code = _fetch_and_process(url)
    except requests.RequestException as e:
        logger.error(f"Proxy fetch failed for {url}: {e}")
        return Response(f"Failed to fetch: {e}", status_code=502)

    # Store in cache
    _evict_stale_cache()
    _proxy_cache[url] = (content, content_type, filtered_headers, status_code, time.monotonic())

    return Response(
        content=content,
        status_code=status_code,
        headers=filtered_headers,
        media_type=content_type or "text/html",
    )


# --- UI ---


@ui.page("/")
def index_page() -> None:
    """Main review page with file selection, review, and summary phases."""
    state = ReviewState()
    main_container = ui.column().classes("w-full max-w-none p-4")

    def _load_file(file_path_str: str) -> None:
        """Load and validate the input JSON file, then show review screen."""
        file_path_str = file_path_str.strip()
        if not file_path_str:
            logger.warning("Empty file path provided")
            ui.notify("Please enter a file path", type="warning")
            return

        path = Path(file_path_str)
        logger.info(f"Loading file: {path}")
        if not path.exists():
            logger.error(f"File not found: {path}")
            ui.notify(f"File not found: {path}", type="negative")
            return

        try:
            with path.open("rt") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {path}: {e}")
            ui.notify(f"Invalid JSON: {e}", type="negative")
            return

        if not isinstance(raw_data, list):
            logger.error(f"JSON in {path} is not a list")
            ui.notify("JSON must be a list of objects", type="negative")
            return

        if not raw_data:
            logger.warning(f"JSON file is empty: {path}")
            ui.notify("JSON file is empty", type="negative")
            return

        edited: list[ApplicationData] = []
        errors: list[str] = []
        for idx, item in enumerate(raw_data):
            try:
                edited.append(ApplicationData(**item))
            except ValidationError as e:
                errors.append(f"Entry {idx + 1}: {e}")

        if errors:
            logger.warning(f"Validation errors in {path}: {len(errors)} entries failed")
            for err in errors:
                logger.warning(f"  {err}")
                ui.notify(err, type="warning", timeout=10000)
            if not edited:
                logger.error(f"No valid entries found in {path}")
                ui.notify("No valid entries found", type="negative")
                return

        existing = load_applications()
        state.input_file = path
        state.edited_apps = edited
        state.decisions = [Decision.PENDING] * len(edited)
        state.current_index = 0
        state.existing_urls = {a.url for a in existing}
        state.existing_names = {a.name for a in existing}
        state.all_tags = _load_tags()

        logger.info(f"Loaded {len(edited)} entries from {path}")
        _show_review()

    def _find_json_files() -> list[str]:
        """Find .json files in the current directory."""
        return [str(p) for p in sorted(Path().glob("*.json"))]

    def _show_file_selection() -> None:
        """Phase 1: file selection UI."""
        main_container.clear()
        with main_container:
            ui.label("Review New Applications").classes("text-2xl font-bold mb-4")
            with ui.card().classes("w-96"):
                json_files = _find_json_files()

                file_input = ui.input(
                    "Path to JSON file",
                    value=_cli_input_file,
                ).classes("w-full")

                if json_files:
                    ui.separator().classes("my-2")
                    ui.label("Or select a file:").classes("text-sm text-grey-7")
                    ui.select(
                        options=json_files,
                        with_input=True,
                        label="JSON files",
                        on_change=lambda e: file_input.set_value(str(e.value)) if e.value else None,
                    ).classes("w-full")

                ui.button(
                    "Load",
                    on_click=lambda: _load_file(file_input.value),
                ).classes("mt-2")

    def _show_review() -> None:
        """Phase 2: review screen with split view (form + iframe preview)."""
        if not state.edited_apps:
            _show_file_selection()
            return
        main_container.clear()
        idx = state.current_index
        app_data = state.edited_apps[idx]
        total = len(state.edited_apps)

        with main_container:
            # Header bar
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label(f"Reviewing {idx + 1} of {total}").classes("text-xl font-bold")
                decision = state.decisions[idx]
                if decision != Decision.PENDING:
                    ui.badge(decision.upper(), color=DECISION_COLORS.get(decision, "grey"))
                ui.button("Finish Review", on_click=_show_summary).props("flat")

            ui.linear_progress(value=(idx + 1) / total, show_value=False).classes("mb-2")

            # Duplicate warnings
            if app_data.url in state.existing_urls:
                logger.warning(f"Duplicate URL detected: '{app_data.name}' ({app_data.url})")
                with ui.row().classes("w-full mb-2 p-3 bg-yellow-100 rounded items-center gap-2"):
                    ui.icon("warning", color="orange")
                    ui.label("Duplicate URL — this application already exists. Accepting will overwrite it.")
            elif app_data.name in state.existing_names:
                logger.info(f"Duplicate name detected: '{app_data.name}' (different URL: {app_data.url})")
                with ui.row().classes("w-full mb-2 p-3 bg-blue-100 rounded items-center gap-2"):
                    ui.icon("info", color="blue")
                    ui.label("An application with this name already exists (different URL).")

            # Split view: form on left, preview on right
            with ui.splitter(value=45).classes("w-full") as splitter:
                with splitter.before, ui.column().classes("w-full p-2 gap-2"):
                    ui.input(
                        "Name",
                        value=app_data.name,
                        on_change=lambda e: setattr(app_data, "name", e.value),
                    ).classes("w-full")

                    ui.input("URL", value=app_data.url).props("readonly").classes("w-full")

                    ui.textarea(
                        "Description",
                        value=app_data.description,
                        on_change=lambda e: setattr(app_data, "description", e.value),
                    ).classes("w-full").props("rows=5")

                    # --- Tags section ---
                    ui.label("Tags").classes("font-bold mt-2")
                    tags_container = ui.column().classes("w-full")

                    def _rebuild_tags() -> None:
                        """Rebuild tag chips and the add-tag select."""
                        tags_container.clear()
                        with tags_container:
                            sorted_tags = sort_application_tags(app_data.tags)

                            def _remove_tag(tag_to_remove: str) -> None:
                                logger.debug(f"Removed tag '{tag_to_remove}' from '{app_data.name}'")
                                app_data.tags.discard(tag_to_remove)
                                _rebuild_tags()

                            with ui.row().classes("flex-wrap gap-1"):
                                for tag in sorted_tags:
                                    ui.chip(
                                        tag,
                                        removable=True,
                                        on_value_change=lambda e, t=tag: _remove_tag(t) if not e.value else None,
                                    ).props("dense")

                            all_options = sorted(
                                set(state.all_tags) | app_data.tags,
                                key=lambda x: x.lower(),
                            )

                            def _on_add_tag(e: Any) -> None:
                                if e.value and e.value not in app_data.tags:
                                    tag_value = str(e.value)
                                    if tag_value not in state.all_tags:
                                        logger.info(f"New tag created: '{tag_value}' (for '{app_data.name}')")
                                    app_data.tags.add(tag_value)
                                    _rebuild_tags()

                            ui.select(
                                options=all_options,
                                with_input=True,
                                new_value_mode="add-unique",
                                label="Add tag...",
                                on_change=_on_add_tag,
                            ).classes("w-full")

                    _rebuild_tags()

                    # --- Action buttons ---
                    with ui.row().classes("mt-4 gap-2"):
                        ui.button(
                            "Accept",
                            color="green",
                            on_click=lambda: _decide(Decision.ACCEPT),
                        ).props("icon=check")
                        ui.button(
                            "Skip",
                            color="grey",
                            on_click=lambda: _decide(Decision.SKIP),
                        ).props("icon=skip_next")
                        ui.button(
                            "Reject",
                            color="red",
                            on_click=lambda: _decide(Decision.REJECT),
                        ).props("icon=close")

                    # --- Navigation ---
                    with ui.row().classes("mt-2 gap-2"):
                        prev_btn = ui.button(
                            "Prev",
                            on_click=lambda: _navigate(-1),
                        ).props("flat icon=arrow_back")
                        if idx <= 0:
                            prev_btn.disable()
                        next_btn = ui.button(
                            "Next",
                            on_click=lambda: _navigate(1),
                        ).props("flat icon=arrow_forward")
                        if idx >= total - 1:
                            next_btn.disable()

                with splitter.after, ui.column().classes("w-full h-full p-2"):
                    encoded_url = quote(app_data.url, safe="")
                    ui.html(
                        f"""<div style="position:relative;width:100%;height:70vh;">
                        <div id="iframe-spinner" style="position:absolute;inset:0;display:flex;
                        align-items:center;justify-content:center;background:#f5f5f5;z-index:1;">
                        <span style="font-size:1.2em;color:#888;">Loading preview...</span></div>
                        <iframe src="/proxy?url={encoded_url}"
                        style="width:100%;height:100%;border:none;position:relative;z-index:2;"
                        onload="document.getElementById('iframe-spinner').style.display='none'"></iframe>
                        </div>"""
                    ).classes("w-full")
                    ui.link("Open in new tab", app_data.url, new_tab=True).classes("mt-1")

    def _navigate(delta: int) -> None:
        """Navigate between review entries."""
        new_idx = state.current_index + delta
        if 0 <= new_idx < len(state.edited_apps):
            logger.debug(f"Navigating from {state.current_index} to {new_idx}")
            state.current_index = new_idx
            _show_review()

    def _decide(decision: Decision) -> None:
        """Record decision for current entry and advance."""
        app_name = state.edited_apps[state.current_index].name
        logger.info(f"Decision for '{app_name}' (index {state.current_index}): {decision}")
        state.decisions[state.current_index] = decision
        if state.current_index < len(state.edited_apps) - 1:
            state.current_index += 1
            _show_review()
        else:
            _show_summary()

    def _show_summary() -> None:
        """Phase 3: summary table with merge action."""
        main_container.clear()
        with main_container:
            ui.label("Review Summary").classes("text-2xl font-bold mb-4")

            accepted_indices = [i for i, d in enumerate(state.decisions) if d == Decision.ACCEPT]
            skipped_count = sum(1 for d in state.decisions if d == Decision.SKIP)
            rejected_count = sum(1 for d in state.decisions if d == Decision.REJECT)
            pending_count = sum(1 for d in state.decisions if d == Decision.PENDING)
            merged_count = sum(1 for d in state.decisions if d == Decision.MERGED)

            logger.info(
                f"Summary: {len(accepted_indices)} accepted, {merged_count} merged, "
                f"{skipped_count} skipped, {rejected_count} rejected, {pending_count} pending"
            )

            with ui.row().classes("gap-4 mb-4"):
                ui.badge(f"{len(accepted_indices)} accepted", color="green").classes("text-sm p-2")
                if merged_count:
                    ui.badge(f"{merged_count} merged", color="teal").classes("text-sm p-2")
                ui.badge(f"{skipped_count} skipped", color="grey").classes("text-sm p-2")
                ui.badge(f"{rejected_count} rejected", color="red").classes("text-sm p-2")
                if pending_count:
                    ui.badge(f"{pending_count} pending", color="orange").classes("text-sm p-2")

            columns: list[dict[str, str]] = [
                {"name": "name", "label": "Name", "field": "name", "align": "left"},
                {"name": "url", "label": "URL", "field": "url", "align": "left"},
                {"name": "tags", "label": "Tags", "field": "tags", "align": "left"},
                {"name": "decision", "label": "Decision", "field": "decision", "align": "center"},
            ]
            rows: list[dict[str, str]] = []
            for i, app_entry in enumerate(state.edited_apps):
                sorted_tags = sort_application_tags(app_entry.tags)
                rows.append(
                    {
                        "name": app_entry.name,
                        "url": app_entry.url,
                        "tags": ", ".join(sorted_tags),
                        "decision": state.decisions[i].upper(),
                    }
                )
            ui.table(columns=columns, rows=rows).classes("w-full mb-4")

            unmerged_indices = [i for i, d in enumerate(state.decisions) if d in (Decision.SKIP, Decision.PENDING)]

            with ui.row().classes("gap-2"):
                if accepted_indices:
                    ui.button(
                        f"Merge {len(accepted_indices)} Accepted & Generate README",
                        color="green",
                        on_click=lambda: _do_merge(accepted_indices),
                    ).props("icon=merge_type")
                if unmerged_indices:
                    ui.button(
                        f"Save {len(unmerged_indices)} Unmerged to JSON",
                        color="blue",
                        on_click=lambda: _save_unmerged(unmerged_indices),
                    ).props("icon=save")
                ui.button("Back to Review", on_click=_show_review).props("flat icon=arrow_back")

    def _do_merge(accepted_indices: list[int]) -> None:
        """Perform the merge of accepted entries."""
        logger.info(f"Merging {len(accepted_indices)} accepted entries")
        accepted_apps = [state.edited_apps[i] for i in accepted_indices]
        try:
            added, replaced = perform_merge(accepted_apps)
            for i in accepted_indices:
                state.decisions[i] = Decision.MERGED
            state.existing_urls.update(a.url for a in accepted_apps)
            state.existing_names.update(a.name for a in accepted_apps)
            ui.notify(
                f"Merge complete: {added} added, {replaced} replaced",
                type="positive",
                timeout=10000,
            )
            _show_summary()
        except Exception as e:  # noqa: BLE001
            ui.notify(f"Merge failed: {e}", type="negative", timeout=10000)
            logger.exception("Merge failed")

    def _save_unmerged(unmerged_indices: list[int]) -> None:
        """Save unmerged (skipped/pending) entries back to the input file.

        Creates a backup of the current input file before overwriting.
        """
        if not state.input_file:
            logger.error("No input file set, cannot save unmerged entries")
            ui.notify("No input file set", type="negative")
            return

        apps = [state.edited_apps[i] for i in unmerged_indices]
        input_path = state.input_file
        try:
            # Backup current input file
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M")
            backup_path = input_path.with_name(f"{input_path.stem}-{timestamp}.json.bak")
            backup_path.write_bytes(input_path.read_bytes())
            logger.info(f"Backed up {input_path} to {backup_path}")

            # Overwrite input file with unmerged entries
            with input_path.open("wt") as f:
                json.dump([a.model_dump(mode="json") for a in apps], f, indent=4, ensure_ascii=False)
            ui.notify(
                f"Saved {len(apps)} entries to {input_path} (backup: {backup_path.name})",
                type="positive",
                timeout=10000,
            )
            logger.info(f"Saved {len(apps)} unmerged entries to {input_path}")
        except Exception as e:  # noqa: BLE001
            ui.notify(f"Save failed: {e}", type="negative", timeout=10000)
            logger.exception("Save unmerged failed")

    _show_file_selection()


def main() -> None:
    """Entry point: launch the NiceGUI review application."""
    global _cli_input_file

    parser = argparse.ArgumentParser(description="Review and merge new applications via GUI")
    parser.add_argument("input_file", type=Path, nargs="?", help="Path to JSON file with new applications")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to run the server on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    init_logs()

    if args.input_file:
        _cli_input_file = str(args.input_file)
        logger.info(f"CLI input file: {args.input_file}")

    logger.info(f"Starting review app on port {args.port}")
    ui.run(title="Review Applications", port=args.port, host="127.0.0.1", show=False, reload=args.reload)


if __name__ == "__main__":
    main()
