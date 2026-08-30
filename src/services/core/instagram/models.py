"""
Instagram profile data structures.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class InstagramProfile:
    username: str
    full_name: str
    bio: str
    followers_count: int
    following_count: int
    posts_count: int
    profile_url: str
    is_business: bool
    category: Optional[str]
    phone: Optional[str]
    email: Optional[str]
