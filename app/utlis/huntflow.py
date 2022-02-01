import typing as t


def get_files_ids(files: t.List[t.Dict[str, t.Any]]) -> t.List[int]:
    """
    Функция выбирает id каждого из файлов.
    Если id какого-либо файла не найдено, то бросается исключение
    """
    file_ids = []
    for file in files:
        file_id = file.get('id')
        if not file_id:
            raise Exception({'detail': 'Отсутствует id в ответе', 'files': files})
        file_ids.append(file_id)
    return file_ids
