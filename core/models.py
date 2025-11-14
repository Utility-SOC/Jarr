"""
Shared data models for type-safe data transfer between components.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List


@dataclass
class ProviderIds:
    """External provider IDs for media items."""
    tmdb: Optional[str] = None
    tvdb: Optional[str] = None
    imdb: Optional[str] = None
    musicbrainz: Optional[str] = None
    goodreads: Optional[str] = None


@dataclass
class MediaItem:
    """Base class for all media items."""
    id: str
    name: str
    path: Optional[str] = None
    year: Optional[int] = None
    provider_ids: ProviderIds = field(default_factory=ProviderIds)


@dataclass
class Movie(MediaItem):
    """Movie-specific media item."""
    runtime: Optional[int] = None  # minutes
    genres: List[str] = field(default_factory=list)


@dataclass
class Series(MediaItem):
    """TV series media item."""
    season_count: Optional[int] = None
    episode_count: Optional[int] = None
    genres: List[str] = field(default_factory=list)


@dataclass
class Album(MediaItem):
    """Music album media item."""
    artist: Optional[str] = None
    track_count: Optional[int] = None


@dataclass
class Book(MediaItem):
    """Book media item."""
    author: Optional[str] = None
    isbn: Optional[str] = None


@dataclass
class ServiceStatus:
    """Health status for a service."""
    name: str
    status: str  # "up", "down", "unknown"
    version: Optional[str] = None
    error: Optional[str] = None
    url: Optional[str] = None


@dataclass
class SearchResult:
    """API search result."""
    id: str
    title: str
    year: Optional[int] = None
    overview: Optional[str] = None
    poster_url: Optional[str] = None
    provider_ids: ProviderIds = field(default_factory=ProviderIds)
    additional_data: Dict = field(default_factory=dict)


@dataclass
class QualityProfile:
    """Quality profile configuration for ARR services."""
    id: int
    name: str


@dataclass
class RootFolder:
    """Root folder configuration for ARR services."""
    id: int
    path: str
    free_space: int = 0
    accessible: bool = True
