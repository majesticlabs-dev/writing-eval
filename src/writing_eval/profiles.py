"""Compatibility facade for named style profiles."""

from .profile_analysis import _STOPWORDS, build_style_gap
from .profile_io import build_profile, list_profiles, load_profile
from .profile_models import Profile, ProfileError

__all__ = [
    "Profile",
    "ProfileError",
    "build_profile",
    "build_style_gap",
    "list_profiles",
    "load_profile",
]
