import importlib
import importlib.util


def test_orchestrator_has_no_run_single_target():
    import pythonarchtesting.runner_multi.orchestrator as m

    assert not hasattr(m, "run_single_target")


def test_state_does_not_export_project_state():
    import pythonarchtesting.state as s

    assert not hasattr(s, "ProjectState")


def test_report_api_has_no_single_target_builders():
    import pythonarchtesting.report.api as a

    for name in (
        "build_report",
        "build_report_document",
        "generate_single_target_report_from_run_target",
        "build_single_target_report_from_run_target",
    ):
        assert not hasattr(a, name)


def test_markdown_renderer_module_does_not_exist():
    spec = importlib.util.find_spec("pythonarchtesting.report.renderers.markdown")
    assert spec is None
