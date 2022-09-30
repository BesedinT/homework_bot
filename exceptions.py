
class WrongResponse(Exception):
    """Код ответа не равен 200."""

    pass


class RequestError(Exception):
    """Ошибка запроса."""

    pass


class JSONDecodeError(Exception):
    """Ошибка преобразования в JSOND."""

    pass


class EmptyAnswersAPI(Exception):
    """Пустой ответ API."""

    pass
