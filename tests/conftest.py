import os

import pytest

from aquawatch import db
from aquawatch.pipeline import bootstrap
from aquawatch.synthetic import generate


@pytest.fixture
def engine(tmp_path):
    # PostgreSQL integration uses a dedicated test database supplied explicitly by CI.
    url = os.getenv("TEST_DATABASE_URL", f"sqlite:///{(tmp_path / 'test.sqlite').as_posix()}")
    value = db.make_engine(url)
    if os.getenv("TEST_DATABASE_URL"):
        assert value.url.database == "aquawatch_test", "Refusing to reset a non-test database"
        db.metadata.drop_all(value)
    db.metadata.create_all(value)
    yield value
    value.dispose()


@pytest.fixture
def seeded(engine):
    fixture = generate()
    bootstrap(engine, fixture)
    return engine, fixture
