"""Authenticated personal Hermes workbench routes."""

from open_webui.utils.auth import get_verified_user
from open_webui.utils.hermes import create_router

router = create_router(get_verified_user)
