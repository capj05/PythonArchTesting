import textwrap
from pathlib import Path

from src.entities_extraction import extract_entities_from_source
from src.validation_scope import filter_entities_for_scope, is_template_logical_view


def _extract_entities(source: str):
    return extract_entities_from_source(
        textwrap.dedent(source).strip() + "\n",
        Path("views.py"),
        Path("."),
        None,
        role="target",
        include_nested_functions=False,
    )


def test_logical_view_scope_keeps_only_template_backed_views():
    entities = _extract_entities("""
        def show_page(request):
            return render(request, "pages/home.html", {})

        def compute_total(items):
            return sum(items)
        """)

    scoped = filter_entities_for_scope(entities, "logical-views")

    assert [entity.name for entity in scoped] == ["show_page"]


def test_template_logical_view_detects_flask_render_template():
    entities = _extract_entities("""
        def dashboard():
            return render_template("dashboard.html", value=1)
        """)

    dashboard = next(entity for entity in entities if entity.name == "dashboard")

    assert is_template_logical_view(dashboard) is True
