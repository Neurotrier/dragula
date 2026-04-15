from pathlib import Path

from dragula.composition import build_application, build_describe_symbol_use_case
from dragula.application.use_cases import DescribeSymbolUseCase
from tests.support import create_project, write_default_test_config


def test_build_application_wires_shared_dependencies(tmp_path: Path) -> None:
    project = create_project(tmp_path)
    write_default_test_config(project)

    container = build_application(project)

    assert container.settings.project_root == Path(project).resolve()
    assert container.index_project.symbol_writer is container.repository
    assert container.index_project.vector_index is container.vector_index
    assert container.list_symbols.symbol_reader is container.repository
    assert container.get_symbol_details.symbol_reader is container.repository
    assert container.describe_symbol.symbol_reader is container.repository
    assert container.describe_symbol.description_cache is container.repository
    assert container.delete_symbol_descriptions.symbol_reader is container.repository
    assert (
        container.delete_symbol_descriptions.description_cache
        is container.repository
    )


def test_build_describe_symbol_use_case_uses_repository_and_settings(
    tmp_path: Path,
) -> None:
    project = create_project(tmp_path)
    write_default_test_config(project)

    container = build_application(project)
    describe_symbol = build_describe_symbol_use_case(
        container.settings,
        container.repository,
        vector_index=container.vector_index,
    )

    assert isinstance(describe_symbol, DescribeSymbolUseCase)
    assert describe_symbol.symbol_reader is container.repository
    assert describe_symbol.description_cache is container.repository
    assert describe_symbol.top_k == container.settings.top_k
