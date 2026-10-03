"""ATS Adapters package for Breadwinner."""

from typing import List, Optional
from breadwinner.core.adapters.base import BaseATSAdapter
from breadwinner.core.adapters.greenhouse import GreenhouseAdapter
from breadwinner.core.adapters.lever import LeverAdapter
from breadwinner.core.adapters.ashby import AshbyAdapter
from breadwinner.core.adapters.workable import WorkableAdapter
from breadwinner.core.adapters.smartrecruiters import SmartRecruitersAdapter
from breadwinner.core.adapters.workday import WorkdayAdapter
from breadwinner.core.adapters.linkedin import LinkedInGuestAdapter

ALL_ADAPTERS: List[BaseATSAdapter] = [
    GreenhouseAdapter(),
    LeverAdapter(),
    AshbyAdapter(),
    WorkableAdapter(),
    SmartRecruitersAdapter(),
    WorkdayAdapter(),
    LinkedInGuestAdapter(),
]


def find_adapter(url: str) -> Optional[BaseATSAdapter]:
    """Finds a matching Tier 1 ATS adapter for a given URL."""
    for adapter in ALL_ADAPTERS:
        if adapter.matches(url):
            return adapter
    return None
