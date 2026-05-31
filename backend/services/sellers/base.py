"""Abstract base for sell-side listing automation."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ListingDraft:
    """All the information needed to create a listing on any platform."""
    title: str
    description: str
    price: float
    condition: str            # NEW | LIKE_NEW | GOOD | FAIR | POOR
    category: Optional[str]
    photo_paths: list[Path]   # absolute paths to photos in order


@dataclass
class ListingResult:
    """Result of a create_listing attempt."""
    success: bool
    platform_listing_id: Optional[str] = None
    platform_url: Optional[str] = None
    action_url: Optional[str] = None        # manual-fallback URL
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    extra: dict = field(default_factory=dict)


class BaseSeller(ABC):
    platform: str = "unknown"

    @abstractmethod
    def create_listing(self, draft: ListingDraft) -> ListingResult:
        """Attempt to create a marketplace listing. Must not raise."""
        ...

    @abstractmethod
    def remove_listing(self, platform_listing_id: str) -> bool:
        """Remove / delist an item. Returns True on success."""
        ...
