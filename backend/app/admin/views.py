from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.branding import branding
from app.i18n import t

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
TEMPLATES.env.globals.update(t=t, branding=branding)
