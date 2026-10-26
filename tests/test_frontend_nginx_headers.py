"""Static checks for the headers emitted by the frontend nginx server."""

from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "frontend" / "nginx.conf.template"

SECURITY_HEADERS = (
    'add_header Content-Security-Policy "frame-ancestors \'self\' https://unicorncommander.ai https://*.unicorncommander.ai https://magicunicorn.dev https://*.magicunicorn.dev" always;',
    'add_header X-Content-Type-Options "nosniff" always;',
    'add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
    'add_header Permissions-Policy "camera=(), microphone=(self), geolocation=()" always;',
)


def _render_template() -> str:
    """Render the same envsubst-compatible template with no runtime values."""
    return Template(TEMPLATE.read_text()).safe_substitute()


def _location_bodies(config: str) -> list[str]:
    """Return each nginx location body, including nested braces if present."""
    bodies = []
    marker = 0
    while True:
        start = config.find("location ", marker)
        if start == -1:
            return bodies
        opening = config.find("{", start)
        depth = 0
        for index in range(opening, len(config)):
            if config[index] == "{":
                depth += 1
            elif config[index] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(config[opening + 1 : index])
                    marker = index + 1
                    break
        else:
            raise AssertionError("unclosed nginx location block")


def test_rendered_nginx_locations_emit_all_security_headers():
    rendered = _render_template()
    locations = _location_bodies(rendered)

    assert len(locations) == 5
    for location in locations:
        for header in SECURITY_HEADERS:
            assert header in location


def test_frame_policy_allows_only_the_known_cross_origin_parent():
    rendered = _render_template()

    assert "https://unicorncommander.ai" in rendered
    assert "https://ops-center" not in rendered
    assert "add_header X-Frame-Options" not in rendered
