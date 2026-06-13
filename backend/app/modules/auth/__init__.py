"""Auth module — answers "who is the user making this request?"

Public surface (what other modules may import):
  * `get_current_user` — the dependency every protected route uses.
  * `router`           — the module's /auth/me endpoints, included by main.py.
"""
from .dependencies import get_current_user
from .router import router

__all__ = ["get_current_user", "router"]
