from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Help type-checkers and IDEs resolve the real Django AppConfig when available
    from django.apps import AppConfig  # pragma: no cover
else:
    # Fallback minimal AppConfig for environments where Django isn't installed
    class AppConfig:  # type: ignore
        """Minimal stand-in to satisfy linters when Django isn't installed."""
        pass


class AccountsConfig(AppConfig):
    name = 'accounts'
    default_auto_field = 'django.db.models.BigAutoField'
 