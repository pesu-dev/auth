import inspect
import re

import pytest

from app.app import _build_arg_parser
from app.exceptions.base import PESUAcademyError


def _subclasses(cls):
    for subclass in cls.__subclasses__():
        yield subclass
        yield from _subclasses(subclass)


@pytest.fixture
def docs(repository_root):
    return repository_root / "docs"


@pytest.mark.parametrize("error", list(_subclasses(PESUAcademyError)), ids=lambda error: error.__name__)
def test_the_architecture_doc_lists_every_error_with_its_status(docs, error):
    """The error table is written by hand, so a new exception class, or a changed status, needs a row."""
    table = (docs / "architecture.md").read_text()
    # Every subclass sets its status in __init__; the ones that need an argument get a placeholder
    arguments = {
        name: ""
        for name, parameter in inspect.signature(error).parameters.items()
        if parameter.default is parameter.empty
    }
    status = error(**arguments).status_code
    assert re.search(rf"^\| `{error.__name__}` +\| `{status}` +\|", table, flags=re.MULTILINE), error.__name__


def test_the_development_doc_lists_every_command_line_option(docs):
    table = (docs / "development.md").read_text()
    options = [option for action in _build_arg_parser()._actions for option in action.option_strings]
    for option in options:
        if option not in ("-h", "--help"):
            assert f"| `{option}`" in table, option


def test_the_development_doc_lists_every_environment_variable(docs, repository_root):
    """The application must read nothing from the environment that the configuration table leaves out."""
    table = (docs / "development.md").read_text()
    source = "".join(path.read_text() for path in (repository_root / "app").rglob("*.py"))
    variables = set(re.findall(r"""os\.(?:environ\.get|getenv)\(\s*["'](\w+)["']""", source))
    assert variables, "found no environment variables; the pattern no longer matches how the app reads them"
    for variable in variables:
        assert f"`{variable}`" in table, variable


def test_every_path_the_docs_name_exists(docs, repository_root):
    """The docs point at files and directories by path; a rename must not leave them pointing at nothing."""
    for page in docs.glob("*.md"):
        for path in re.findall(r"`((?:app|tests|scripts|\.github|docs)/[^`<>*{} ]*)`", page.read_text()):
            assert (repository_root / path).exists(), f"{page.name} names {path}, which does not exist"
