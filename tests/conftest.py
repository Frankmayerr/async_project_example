import pytest
import sqlalchemy

from app.models import metadata
from settings import DB_DSN


@pytest.fixture(autouse=True, scope='function')
def test_database():
    engine = sqlalchemy.create_engine(DB_DSN)
    metadata.drop_all(engine)
    metadata.create_all(engine)
    yield
    metadata.drop_all(engine)
