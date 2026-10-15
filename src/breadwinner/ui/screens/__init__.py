"""Screen modules and UI decomposition for Breadwinner Studio."""

from breadwinner.ui.screens.models import (
    PaletteModelItem,
    PaletteSearchInput,
    PromptTextArea,
    ModelQuickSwitcherModal,
    BakerySettingsModal,
    ModelsScreenMixin,
)
from breadwinner.ui.screens.breadbox import (
    StatusModal,
    FlagModal,
    DeleteJobModal,
    BreadboxScreenMixin,
)
from breadwinner.ui.screens.studio import (
    JobStrategyModal,
    PersonaSynthesizerModal,
    DiffModal,
    FineTuneModal,
    StudioScreenMixin,
)
from breadwinner.ui.screens.pantry import (
    PantryIngestModal,
    PantryInterviewModal,
    PantryHistoryModal,
    PantryEditorModal,
    PantryScreenMixin,
)

__all__ = [
    "PaletteModelItem",
    "PaletteSearchInput",
    "PromptTextArea",
    "ModelQuickSwitcherModal",
    "BakerySettingsModal",
    "ModelsScreenMixin",
    "StatusModal",
    "FlagModal",
    "DeleteJobModal",
    "BreadboxScreenMixin",
    "JobStrategyModal",
    "PersonaSynthesizerModal",
    "DiffModal",
    "FineTuneModal",
    "StudioScreenMixin",
    "PantryIngestModal",
    "PantryInterviewModal",
    "PantryHistoryModal",
    "PantryEditorModal",
    "PantryScreenMixin",
]
