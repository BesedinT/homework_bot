
class WrongResponse(Exception):
    """Код ответа не равен 200."""

    pass


class RequestError():
    """Ошибка запроса."""

    pass


class JSONDecodeError():
    """Ошибка преобразования в JSOND."""

    pass


class EmptyAnswersAPI():
    """Пустой ответ API."""

    pass
