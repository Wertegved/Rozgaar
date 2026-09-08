from app.core.config import Settings, get_settings
from app.db.session import get_db


def settings_dependency() -> Settings:
    return get_settings()