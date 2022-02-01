import pytest
from mock import patch

from app.huntflow_api import AsyncClient

pytestmark = pytest.mark.asyncio

client = AsyncClient('http://localhost', 'TOKEN')


async def test_request_batch():
    with patch('app.huntflow_api.AsyncClient.request_get') as request_mock:
        request_mock.return_value = {'items': [0, 1, 2]}
        assert [0, 1, 2] == [num async for num in client.request_batch('some/path')]


async def test_request_chunks():
    with patch('app.huntflow_api.AsyncClient.request_get') as request_mock:
        items = {'items': [1, 2], 'total': 3}
        request_mock.return_value = items
        assert [[1, 2], [1, 2], [1, 2]] == [
            data['items'] async for data in client._request_pages('some/path', None)  # pylint: disable=protected-access
        ]


async def test_request_batch_with_chunks():
    def f():
        yield 1
        yield 2
        yield 3

    with patch('app.huntflow_api.AsyncClient.request_get') as request_mock:
        items = {'items': f(), 'total': 3}
        request_mock.return_value = items
        assert [1, 2, 3] == [num async for num in client.request_batch('some/path')]
