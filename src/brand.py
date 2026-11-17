"""Formation logos for every document header: Corps of Signals 'Jimmy' top left, MCTE formation sign top right."""
import base64
from pathlib import Path

LOGO_DIR = Path(__file__).resolve().parents[1] / "assets" / "logos"
JIMMY = LOGO_DIR / "jimmy_sm.png"
MCTE = LOGO_DIR / "mcte_sm.png"


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def brand_row(inner_html: str, height_mm: float = 20) -> str:
    """Wrap a title block so the two logos sit at its top-left and top-right corners."""
    img = f"height:{height_mm}mm;width:auto;flex:none;align-self:flex-start"
    return (f'<div style="display:flex;align-items:flex-start;gap:5mm">'
            f'<img alt="Corps of Signals" src="{data_uri(JIMMY)}" style="{img}"/>'
            f'<div style="flex:1;min-width:0">{inner_html}</div>'
            f'<img alt="MCTE formation sign" src="{data_uri(MCTE)}" style="{img}"/></div>')


def brand_corners(height_mm: float = 17) -> str:
    """Two absolutely positioned logos; the parent needs position:relative and side padding."""
    st = f"position:absolute;top:0;height:{height_mm}mm;width:auto"
    return (f'<img alt="Corps of Signals" src="{data_uri(JIMMY)}" style="{st};left:0"/>'
            f'<img alt="MCTE formation sign" src="{data_uri(MCTE)}" style="{st};right:0"/>')
