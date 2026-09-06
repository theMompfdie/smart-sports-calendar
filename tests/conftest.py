from functools import partial
from pathlib import Path

import pytest

from tests.catalog_support import (
    CatalogInitializer,
    build_catalog,
    initialize_from_template,
)


@pytest.fixture(scope="session")
def catalog_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A session-local template, rebuilt from the current source on every run."""
    template = tmp_path_factory.mktemp("catalog-template") / "catalog.db"
    build_catalog(template)
    return template


@pytest.fixture
def initialize_test_catalog(catalog_template: Path) -> CatalogInitializer:
    """Each caller supplies its own path; no mutable database is shared."""
    return partial(initialize_from_template, catalog_template)
