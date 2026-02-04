import os

env = os.getenv("DJANGO_ENV", "local").lower()

if env in ("prod", "production"):
    from .production import *  # noqa
else:
    from .local import *  # noqa
