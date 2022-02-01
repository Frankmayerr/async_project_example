import asyncio
import logging
import typing as t
from urllib.parse import urljoin

import aiohttp
from tenacity import before_sleep_log
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_fixed

import settings

logger = logging.getLogger(__name__)


class UploadFileException(Exception):
    pass


class CandidateException(Exception):
    pass


class UnknownRejectionReason(Exception):
    pass


class AsyncClient:
    PAGES_PROCESSING_AMOUNT = 5

    _rejection_reasons: t.Dict[int, str] = {}

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self._session: t.Optional[aiohttp.ClientSession] = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={'Authorization': 'Bearer ' + self.token},
            )
        return self._session

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), before_sleep=before_sleep_log(logger, logging.DEBUG))
    async def request_get(self, path: str, params: t.Optional[t.Any] = None) -> t.Any:
        if params is None:
            params = {}
        url = urljoin(self.base_url, path)
        async with self.session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2), before_sleep=before_sleep_log(logger, logging.DEBUG))
    async def request_post(self, path: str, data: t.Optional[t.Dict[str, t.Any]] = None) -> t.Any:
        url = urljoin(self.base_url, path)
        async with self.session.post(url, json=data) as response:
            response.raise_for_status()
            return await response.json()

    async def push_candidate_to_vacancy(
        self,
        candidate_id: int,
        status_id: int = settings.HUNTFLOW_CANDIDATE_INIT_STATUS,
        comment: str = '',
        files_ids: t.Optional[t.List[int]] = None
    ) -> int:
        vacancy_data = {
            'vacancy': settings.HUNTFLOW_REFERRAL_VACANCY,
            'status': status_id,
            'comment': comment,
            'files': [{'id': id_} for id_ in files_ids or []],
            'rejection_reason': None
        }
        vacancy_result = await self.request_post(
            f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants/{candidate_id}/vacancy',
            vacancy_data
        )

        logger.info(
            'Pushed candidate %s to vacancy with status id %s and comment %s',
            str(candidate_id), str(status_id), comment
        )
        return int(vacancy_result['status'])

    async def push_candidate(
        self,
        first_name: str,
        last_name: str,
        phone: str,
        specialization: str,
        body: str,
        files_ids: t.Optional[t.List[int]] = None
    ) -> int:

        result_candidate = await self.request_post(
            f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants',
            {
                'first_name': first_name,
                'last_name': last_name,
                'phone': phone,
                'position': specialization,
                'externals': [
                    {
                        'data': {
                            'body': body
                        },
                        'auth_type': 'NATIVE',
                        'files': [{'id': id_} for id_ in files_ids or []],
                        'account_source': settings.HUNTFLOW_RECOMMENDATION_ACCOUNT_SOURCE
                    },
                ]
            }
        )
        logger.info('Pushed candidate %s %s, got id: %s', first_name, last_name, result_candidate['id'])
        return int(result_candidate['id'])

    async def _request_pages(self, path: str, params: t.Optional[t.Any]) -> t.Any:
        if params is None:
            params = {}
        data = await self.request_get(path, params)
        yield data
        semaphore = asyncio.Semaphore(self.PAGES_PROCESSING_AMOUNT)

        async def request_semaphore(ind: int) -> t.Any:
            async with semaphore:
                return await self.request_get(path, dict({'page': ind}, **params))  # type:ignore

        tasks = [request_semaphore(i) for i in range(2, data.get('total', 1) + 1)]

        for result in await asyncio.gather(*tasks):
            yield result

    async def request_batch(self, path: str, params: t.Optional[t.Any] = None) -> t.Any:
        async for data in self._request_pages(path, params):
            for item in data.get('items', []):
                yield item

    async def get_vacancy_status_applicants(self, vacancy_id: int, status_id: int) -> t.Any:
        return self.request_batch(
            f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants',
            {'vacancy': vacancy_id, 'status': status_id}
        )

    async def get_applicant_log(self, applicant_id: int) -> t.Any:
        return self.request_batch(
            f'/account/{settings.HUNTFLOW_ACCOUNT}/applicants/{applicant_id}/log'
        )

    async def get_rejection_reason(self, id_: int) -> t.Any:
        if not self._rejection_reasons:
            self._rejection_reasons = {
                reason['id']: reason['name'] async for reason in
                self.request_batch(f'/account/{settings.HUNTFLOW_ACCOUNT}/rejection_reasons')
            }

        if id_ not in self._rejection_reasons:
            raise UnknownRejectionReason(id_)

        return self._rejection_reasons[id_]

    async def account_upload_files(self, files: t.List[bytes]) -> t.List[t.Dict[str, t.Any]]:
        return [
            resp for resp in await asyncio.gather(
                *[self.account_upload_file(file) for file in files]
            )
        ]

    async def account_upload_file(self, file: bytes) -> t.Any:
        url = urljoin(self.base_url, f'/account/{settings.HUNTFLOW_ACCOUNT}/upload')
        try:
            async with self.session.post(url, data={'file': file}) as resp:
                return await resp.json()
        except Exception as e:
            raise UploadFileException(e)


huntflow_client: AsyncClient = AsyncClient(settings.HUNTFLOW_API, settings.HUNTFLOW_TOKEN)
