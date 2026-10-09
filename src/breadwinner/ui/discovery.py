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
                discovered.append(
                    DiscoveredIngredient(
                        label=f"[bold #50fa7b][WEB][/bold #50fa7b] Portfolio Homepage — [cyan]{root_url}[/cyan]",
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

                    if cat == "resume_pdf":
                        badge = "[bold #ffb86c][RESUME][/bold #ffb86c]"
                        lbl = f"{badge} Discovered PDF — [cyan]{title}[/cyan] ({r_url})"
                    elif cat == "about":
                        badge = "[bold #8be9fd][BIO][/bold #8be9fd]"
                        lbl = f"{badge} About & Experience — [cyan]{title}[/cyan]"
                    elif cat == "projects":
                        badge = "[bold #bd93f9][PROJECT][/bold #bd93f9]"
                        lbl = f"{badge} Projects & Showcase — [cyan]{title}[/cyan]"
                    elif cat == "research":
                        badge = "[bold #f1fa8c][RESEARCH][/bold #f1fa8c]"
                        lbl = f"{badge} Research & Thesis — [cyan]{title}[/cyan]"
                    elif cat == "articles":
                        badge = "[bold #ff79c6][DOSSIER][/bold #ff79c6]"
                        lbl = f"{badge} Technical Writing / Blog — [cyan]{title}[/cyan]"
                    else:
                        badge = "[dim][PAGE][/dim]"
                        lbl = f"{badge} Subpage — [cyan]{title}[/cyan]"

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

                    if doc_type == "academic":
                        lbl = f"[bold #f1fa8c][RESEARCH][/bold #f1fa8c] Academic Thesis / Dissertation — [yellow]{p.name}[/yellow]"
                    elif doc_type == "resume":
                        lbl = f"[bold #ffb86c][RESUME][/bold #ffb86c] Resume / CV Document — [green]{p.name}[/green]"
                    elif doc_type == "project_readme":
                        lbl = f"[bold #bd93f9][PROJECT][/bold #bd93f9] Project Documentation — [cyan]{p.name}[/cyan]"
                    else:
                        lbl = f"[bold #8be9fd][DOC][/bold #8be9fd] Document ({p.suffix.upper().lstrip('.') or 'FILE'}) — [white]{p.name}[/white]"

                    discovered.append(
                        DiscoveredIngredient(
                            label=lbl,
                            value=val,
                            category=doc_type,
                            is_default=True
                        )
                    )
                elif p.is_dir():
                    discovered.append(
                        DiscoveredIngredient(
                            label=f"[bold #8be9fd][FOLDER][/bold #8be9fd] Local Directory — [white]{p.name}/[/white]",
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
            preview = clean_item[:50].replace("\n", " ")
            discovered.append(
                DiscoveredIngredient(
                    label=f"[bold #50fa7b][NOTES][/bold #50fa7b] Manual Notes / Bio ({char_count} chars) — [dim]\"{preview}...\"[/dim]",
                    value=val,
                    category="notes",
                    is_default=True
                )
            )

    return discovered


class IngredientDiscoveryModal(ModalScreen[Optional[List[str]]]):
    """Interactive modal screen for reviewing and selecting discovered ingredients before baking."""

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
                "[dim]Review detected documents, subpages, and files. Select what to bake into your Canonical Pantry.[/dim]",
                id="discovery-subtitle"
            )

            yield SelectionList[str](id="discovery-selection-list")

            with Horizontal(id="discovery-actions"):
                yield Button("Select All (a)", variant="default", id="btn-disc-all")
                yield Button("Clear All (c)", variant="default", id="btn-disc-none")
                yield Button("Cancel", variant="error", id="btn-disc-cancel")
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

        try:
            sel_list.focus()
        except Exception:
            pass

    def action_select_all(self) -> None:
        try:
            self.query_one("#discovery-selection-list", SelectionList).select_all()
        except Exception:
            pass

    def action_clear_all(self) -> None:
        try:
            self.query_one("#discovery-selection-list", SelectionList).deselect_all()
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
