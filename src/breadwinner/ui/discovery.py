"""ADR-002 Stage 3: Interactive Ingredient Discovery & Selection Modal."""

import os
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Label, Button, SelectionList
from textual.widgets.selection_list import Selection
from textual.screen import ModalScreen
from textual.binding import Binding

from rich.markup import escape

from breadwinner.core.ingestor import (
    UniversalIngestor,
    classify_document,
    clean_user_input_path,
    normalize_source,
    parse_dropped_sources
)


class DiscoveredIngredient:
    """Represents a discovered route, document, or text artifact ready for ingestion."""

    def __init__(self, label: str, value: str, category: str, is_default: bool = True):
        self.label = label
        self.value = value
        self.category = category
        self.is_default = is_default


def discover_all_ingredients(raw_sources: List[str]) -> List[DiscoveredIngredient]:
    """Sniff and expand raw user inputs (URLs, file paths, raw text) into granular selectable ingredients."""
    discovered: List[DiscoveredIngredient] = []
    seen_values: set[str] = set()

    # Flatten any multi-source strings if passed as one entry
    flattened_sources: List[str] = []
    for s in raw_sources:
        parsed = parse_dropped_sources(s)
        if len(parsed) > 1:
            flattened_sources.extend(parsed)
        else:
            flattened_sources.append(s)

    for item in flattened_sources:
        clean_item = clean_user_input_path(str(item).strip())
        if not clean_item:
            continue

        # 1. URL / Website Discovery
        if clean_item.startswith("http://") or clean_item.startswith("https://"):
            root_url = clean_item.rstrip("/")
            if root_url not in seen_values:
                seen_values.add(root_url)
                display_host = root_url.replace("https://", "").replace("http://", "")
                discovered.append(
                    DiscoveredIngredient(
                        label=f"[bold #50fa7b][WEB][/bold #50fa7b] Portfolio Homepage — [bold #fefae0]{escape(display_host)}[/bold #fefae0]",
                        value=root_url,
                        category="web",
                        is_default=True
                    )
                )

            # Discover subpages & assets via lightweight probe
            try:
                sub_routes = UniversalIngestor.discover_portfolio_routes(root_url, timeout=4)
                for r_url, cat, title in sub_routes:
                    r_clean = r_url.rstrip("/")
                    if r_clean in seen_values:
                        continue
                    seen_values.add(r_clean)

                    raw_title = str(title).strip() if title else ""
                    clean_title = raw_title.strip("[]").strip(".").strip("/").strip()
                    if not clean_title or len(clean_title) < 2:
                        clean_title = r_clean.split("/")[-1].replace("-", " ").replace("_", " ").title() or "Page"

                    esc_title = escape(clean_title)
                    path_preview = r_clean.replace(root_url, "") if root_url in r_clean else r_clean.split("/")[-1]
                    if len(path_preview) > 36:
                        path_preview = path_preview[:33] + "..."
                    esc_path = escape(path_preview)

                    if cat == "resume_pdf":
                        badge = "[bold #ffb86c][RESUME][/bold #ffb86c]"
                        lbl = f"{badge} Discovered PDF — [bold #fefae0]{esc_title}[/bold #fefae0] [dim]({esc_path})[/dim]"
                    elif cat == "about":
                        badge = "[bold #8be9fd][BIO][/bold #8be9fd]"
                        lbl = f"{badge} About & Experience — [bold #fefae0]{esc_title}[/bold #fefae0]"
                    elif cat == "projects":
                        badge = "[bold #bd93f9][PROJECT][/bold #bd93f9]"
                        lbl = f"{badge} Projects & Showcase — [bold #fefae0]{esc_title}[/bold #fefae0]"
                    elif cat == "research":
                        badge = "[bold #f1fa8c][RESEARCH][/bold #f1fa8c]"
                        lbl = f"{badge} Research & Thesis — [bold #fefae0]{esc_title}[/bold #fefae0]"
                    elif cat == "articles":
                        badge = "[bold #ff79c6][DOSSIER][/bold #ff79c6]"
                        lbl = f"{badge} Technical Writing / Blog — [bold #fefae0]{esc_title}[/bold #fefae0]"
                    else:
                        badge = "[dim][PAGE][/dim]"
                        lbl = f"{badge} Subpage — [bold #fefae0]{esc_title}[/bold #fefae0]"

                    discovered.append(
                        DiscoveredIngredient(
                            label=lbl,
                            value=r_url,
                            category=cat,
                            is_default=True
                        )
                    )
            except Exception:
                pass
            continue

        # 2. Local File or Directory Discovery
        p = Path(os.path.expanduser(clean_item)).resolve()
        if p.exists():
            val = str(p)
            if val not in seen_values:
                seen_values.add(val)
                if p.is_file():
                    try:
                        snippet = UniversalIngestor.extract_text_from_file(p)[:3000]
                        doc_type = classify_document(snippet, source_label=p.name)
                    except Exception:
                        doc_type = "general"

                    esc_pname = escape(p.name)
                    if doc_type == "academic":
                        lbl = f"[bold #f1fa8c][RESEARCH][/bold #f1fa8c] Academic Thesis / Dissertation — [bold #fefae0]{esc_pname}[/bold #fefae0]"
                    elif doc_type == "resume":
                        lbl = f"[bold #ffb86c][RESUME][/bold #ffb86c] Resume / CV Document — [bold #fefae0]{esc_pname}[/bold #fefae0]"
                    elif doc_type == "project_readme":
                        lbl = f"[bold #bd93f9][PROJECT][/bold #bd93f9] Project Documentation — [bold #fefae0]{esc_pname}[/bold #fefae0]"
                    else:
                        lbl = f"[bold #8be9fd][DOC][/bold #8be9fd] Document ({p.suffix.upper().lstrip('.') or 'FILE'}) — [bold #fefae0]{esc_pname}[/bold #fefae0]"

                    discovered.append(
                        DiscoveredIngredient(
                            label=lbl,
                            value=val,
                            category=doc_type,
                            is_default=True
                        )
                    )
                elif p.is_dir():
                    esc_dname = escape(p.name)
                    discovered.append(
                        DiscoveredIngredient(
                            label=f"[bold #8be9fd][FOLDER][/bold #8be9fd] Local Directory — [bold #fefae0]{esc_dname}/[/bold #fefae0]",
                            value=val,
                            category="directory",
                            is_default=True
                        )
                    )
            continue

        # 3. Raw notes / bio text
        val = clean_item
        if val not in seen_values:
            seen_values.add(val)
            char_count = len(clean_item)
            preview = escape(clean_item[:32].replace("\n", " "))
            discovered.append(
                DiscoveredIngredient(
                    label=f"[bold #50fa7b][NOTES][/bold #50fa7b] Manual Notes / Bio ({char_count} chars) — [bold #fefae0]\"{preview}...\"[/bold #fefae0]",
                    value=val,
                    category="notes",
                    is_default=True
                )
            )

    return discovered


class IngredientDiscoveryModal(ModalScreen[Optional[List[str]]]):
    """Interactive modal screen for reviewing and selecting discovered ingredients before baking."""

    DEFAULT_CSS = """
    IngredientDiscoveryModal {
        align: center middle;
        background: rgba(11, 14, 23, 0.85);
    }

    #discovery-modal-container {
        width: 88;
        max-width: 94;
        height: 32;
        max-height: 85%;
        background: #10141f;
        border: heavy #d4a373;
        padding: 1 2;
    }

    #discovery-header-bar {
        height: 3;
        align: center middle;
        border-bottom: heavy #3d271d;
        margin-bottom: 0;
    }

    #discovery-title {
        width: 1fr;
        text-align: center;
        color: #ffb86c;
        text-style: bold;
    }

    #btn-modal-close {
        dock: right;
        min-width: 4;
        width: 4;
        height: 1;
        background: transparent;
        color: #a89f91;
        border: none;
    }

    #btn-modal-close:hover {
        color: #ff5555;
        text-style: bold;
    }

    #discovery-subtitle {
        text-align: center;
        color: #a89f91;
        margin-top: 0;
        margin-bottom: 1;
        height: 1;
    }

    #discovery-selection-list {
        height: 1fr;
        background: #0b0e17;
        border: round #3d271d;
        padding: 0 1;
        margin-bottom: 1;
        scrollbar-color: #d4a373 #10141f;
    }

    #discovery-selection-list:focus {
        border: round #d4a373;
    }

    #discovery-counter-bar {
        height: 1;
        text-align: center;
        color: #f4a261;
        margin-bottom: 1;
    }

    #discovery-actions {
        height: 3;
        align: center middle;
    }

    #discovery-actions Button {
        margin: 0 1;
        height: 3;
        min-width: 14;
    }

    #btn-disc-bake {
        background: #1b4332;
        color: #d8f3dc;
        border: heavy #52b788;
        text-style: bold;
    }

    #btn-disc-bake:hover {
        background: #2d6a4f;
    }

    #btn-disc-all, #btn-disc-none {
        background: #1e293b;
        color: #cbd5e1;
        border: heavy #475569;
    }

    #btn-disc-all:hover, #btn-disc-none:hover {
        background: #334155;
    }

    #btn-disc-cancel {
        background: #3f1d1d;
        color: #fca5a5;
        border: heavy #7f1d1d;
    }

    #btn-disc-cancel:hover {
        background: #5f2525;
    }
    """

    BINDINGS = [
        Binding("enter", "submit", "Bake Selected", priority=True),
        Binding("escape", "cancel", "Cancel Bake", priority=True),
        Binding("a", "select_all", "Select All"),
        Binding("c", "clear_all", "Clear All"),
    ]

    def __init__(self, sources: List[str]):
        super().__init__()
        self.raw_sources = sources
        self.discovered_ingredients: List[DiscoveredIngredient] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="discovery-modal-container"):
            with Horizontal(id="discovery-header-bar"):
                yield Label("[bold #ffb86c][✦] DISCOVERED CAREER INGREDIENTS [✦][/bold #ffb86c]", id="discovery-title")
                yield Button("✕", id="btn-modal-close", classes="modal-close-btn")

            yield Label(
                "[dim]Review detected documents, subpages, and files. Select what to bake into your Career Pantry.[/dim]",
                id="discovery-subtitle"
            )

            yield SelectionList[str](id="discovery-selection-list")

            yield Label("", id="discovery-counter-bar")

            with Horizontal(id="discovery-actions"):
                yield Button("Select All (a)", variant="default", id="btn-disc-all")
                yield Button("Clear All (c)", variant="default", id="btn-disc-none")
                yield Button("Cancel (Esc)", variant="error", id="btn-disc-cancel")
                yield Button("Bake Selected (Enter)", variant="success", id="btn-disc-bake")

    def on_mount(self) -> None:
        self.discovered_ingredients = discover_all_ingredients(self.raw_sources)
        sel_list = self.query_one("#discovery-selection-list", SelectionList)

        for idx, item in enumerate(self.discovered_ingredients):
            sel_list.add_option(
                Selection(
                    item.label,
                    item.value,
                    initial_state=item.is_default,
                    id=f"disc_item_{idx}"
                )
            )

        self._update_counter_label()
        try:
            sel_list.focus()
        except Exception:
            pass

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        self._update_counter_label()

    def _update_counter_label(self) -> None:
        try:
            sel_list = self.query_one("#discovery-selection-list", SelectionList)
            count = len(sel_list.selected)
            total = len(self.discovered_ingredients)
            lbl = self.query_one("#discovery-counter-bar", Label)
            lbl.update(f"◈ [bold #50fa7b]{count}[/bold #50fa7b] of [bold]{total}[/bold] ingredients selected for kneading")
        except Exception:
            pass

    def action_select_all(self) -> None:
        try:
            self.query_one("#discovery-selection-list", SelectionList).select_all()
            self._update_counter_label()
        except Exception:
            pass

    def action_clear_all(self) -> None:
        try:
            self.query_one("#discovery-selection-list", SelectionList).deselect_all()
            self._update_counter_label()
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        sel_list = self.query_one("#discovery-selection-list", SelectionList)
        selected_values = list(sel_list.selected)
        if not selected_values:
            # Fallback to all items if nothing selected
            selected_values = [item.value for item in self.discovered_ingredients]
        self.dismiss(selected_values)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid in ("btn-disc-cancel", "btn-modal-close"):
            self.action_cancel()
        elif bid == "btn-disc-all":
            self.action_select_all()
        elif bid == "btn-disc-none":
            self.action_clear_all()
        elif bid == "btn-disc-bake":
            self.action_submit()
