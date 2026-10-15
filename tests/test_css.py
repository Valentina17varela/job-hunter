"""Guards for the stylesheet system (spec 24, slice 1): tokens in one place, one rule each."""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "jobhunter" / "web" / "static"
TEMPLATES = STATIC.parent / "templates"
STYLE = (STATIC / "style.css").read_text()
TOKENS = (STATIC / "tokens.css").read_text()


def _strip(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _blocks(css: str, context: str = ""):
    """(context, selector-list, body) for every rule; @media bodies are walked recursively."""
    css = _strip(css)
    pos = 0
    while True:
        match = re.compile(r"\s*([^{};]+)\{").search(css, pos)
        if not match:
            return
        head, start, depth, i = match.group(1).strip(), match.end() - 1, 0, match.end() - 1
        while True:
            depth += css[i] == "{"
            depth -= css[i] == "}"
            if depth == 0:
                break
            i += 1
        body = css[start + 1 : i]
        if head.startswith("@media"):
            yield from _blocks(body, head)
        elif head.startswith("@"):
            yield context, head, body
        else:
            yield context, head, body
        pos = i + 1


def test_every_selector_is_declared_once_per_context():
    seen: dict[tuple[str, str], int] = {}
    for context, head, _ in _blocks(STYLE):
        if head.startswith("@"):
            continue
        for selector in (s.strip() for s in head.split(",")):
            key = (context, " ".join(selector.split()))
            seen[key] = seen.get(key, 0) + 1
    repeated = sorted(f"{c or 'base'}: {s}" for (c, s), n in seen.items() if n > 1)
    assert not repeated, f"merge these into one block each (no layered overrides): {repeated}"


def test_style_css_has_no_color_or_shadow_literals():
    css = _strip(STYLE)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", css), "colors belong in tokens.css"
    assert not re.findall(r"rgba?\(", css), "colors, glows and overlays are tokens"
    assert not re.findall(r"box-shadow:[^;]*\d+px[^;]*rgba", css)
    assert "z-index: " not in re.sub(r"z-index: var\(--z-[a-z]+\)", "", css), "layers are tokens"


def test_every_var_used_is_defined_in_tokens():
    defined = set(re.findall(r"(--[\w-]+)\s*:", _strip(TOKENS)))
    used = set(re.findall(r"var\((--[\w-]+)", _strip(STYLE)))
    for template in TEMPLATES.glob("*.html"):
        used |= set(re.findall(r"var\((--[\w-]+)", template.read_text()))
    # set inline or by component rules on purpose: --size/--pct (rings, avatars, bars),
    # --rc (rings), --stage (board columns)
    local = {"--size", "--pct", "--rc", "--w", "--stage"}
    missing = sorted(used - defined - local)
    assert not missing, f"undefined custom properties: {missing}"


def test_dark_overrides_only_existing_tokens_and_both_themes_declare_color_scheme():
    root = re.search(r":root\s*\{(.*?)\n\}", _strip(TOKENS), re.S).group(1)
    dark = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\n\}', _strip(TOKENS), re.S).group(1)
    light_names = set(re.findall(r"(--[\w-]+)\s*:", root))
    dark_names = set(re.findall(r"(--[\w-]+)\s*:", dark))
    assert dark_names <= light_names, f"dark-only tokens: {sorted(dark_names - light_names)}"
    assert "color-scheme: light" in root and "color-scheme: dark" in dark


def test_scale_tokens_exist():
    for name in (
        "--text-xs", "--text-base", "--text-3xl", "--space-1", "--space-8", "--weight-regular",
        "--weight-extrabold", "--z-dock", "--z-notice", "--shadow-float", "--shadow-modal",
        "--scrim", "--r-full", "--btn-border",
    ):  # fmt: skip
        assert f"{name}:" in TOKENS, name


# --- surface language (spec 24, slice 3) ---------------------------------------------------

APP = (STATIC.parent / "app.py").read_text()


def test_every_posting_status_and_stage_has_a_style_rule():
    statuses = re.search(r"STATUS_LABELS = \{(.*?)\}", APP, re.S).group(1)
    for name in re.findall(r'"(\w+)":', statuses):
        assert f".st-{name}" in STYLE, f"no .st-{name} rule: a status must not fall back silently"
    stages = re.search(r"STAGE_LABELS = \{(.*?)\}", APP, re.S).group(1)
    for name in re.findall(r'"(\w+)":', stages):
        assert f".chip.stage-{name}" in STYLE, f"no chip rule for stage {name}"


def test_orange_is_not_the_default_tint():
    """Neutral by default: avatars, badges, tags, filter chips and tiles use neutral tokens."""
    for selector in (".avatar", ".badge", ".tag", ".afchip", ".kpi-ic", ".step-n", ".empty-ic"):
        block = STYLE.split(f"\n{selector} {{")[1].split("}")[0]
        assert "badge-soft" not in block and "orange" not in block, selector
    assert "--surface-neutral:" in TOKENS and "--ink-neutral:" in TOKENS


def test_type_scale_and_weights_are_tokens_not_literals():
    css = _strip(STYLE)
    sizes = re.findall(r"font-size:\s*([\d.]+rem)", css)
    assert not sizes, f"font sizes come from --text-*: {sorted(set(sizes))}"
    assert not re.findall(r"font-weight:\s*\d", css), "weights come from --weight-*"
    assert "text-wrap: balance" in css and "text-wrap: pretty" in css


def test_all_caps_is_reserved_for_micro_labels():
    allowed = {".eyebrow", ".verdict", ".fb-sel > span"}
    for _context, head, body in _blocks(STYLE):
        if "text-transform: uppercase" in body:
            assert set(s.strip() for s in head.split(",")) <= allowed, head


def test_no_text_glyph_icons_in_templates_or_scripts():
    glyphs = re.compile("[★☆✕◐◑]")
    for path in [*TEMPLATES.glob("*.html"), STATIC / "app.js", STATIC.parent / "app.py"]:
        assert not glyphs.search(path.read_text()), f"{path.name} still uses a glyph as an icon"
    sprite = (TEMPLATES / "base.html").read_text()
    for icon in ("gear", "sun", "moon", "info", "star", "star-fill", "x", "minus"):
        assert f'id="i-{icon}"' in sprite, icon
    gear = re.search(r'<symbol id="i-gear".*?</symbol>', sprite, re.S).group(0)
    assert "M12 2v3" not in gear, "the settings icon must not be the sun's rays"


def test_board_stage_bars_do_not_use_crescent_borders():
    assert "border-top: 4px" not in STYLE and '.column[class*="stage-"]::before' in STYLE
    assert "fieldset.field" in STYLE  # native fieldset chrome is neutralised


def test_one_transition_token_and_pressed_state():
    css = STYLE
    assert "transition: .12s" not in css and "transition: opacity" not in css
    assert "--transition:" in TOKENS
    assert ".btn:active" in css
    assert "@view-transition" in css
