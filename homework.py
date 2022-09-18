import json
import logging
import os
import requests
import time
from typing import Dict

import telegram

from dotenv import load_dotenv
from http import HTTPStatus

import exceptions


logging.basicConfig(
    level=logging.INFO,
    filename='logs.log',
    format='%(asctime)s, %(levelname)s, %(message)s,'
           '%(funcName)s, %(lineno)s',
    filemode='a',
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Сообщение отправлено!')
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка: {error}')


def get_api_answer(current_timestamp):
    """Запрос к API."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            message = 'Ошибка при получении ответа с сервера'
            logger.error(message)
            raise exceptions.WrongResponse(message)
        logger.info('Получен ответ от сервера')
        return response.json()
    except json.decoder.JSONDecodeError:
        logger.error('Ошибка преобразования в JSON')
    except requests.RequestException as request_error:
        logger.error(f'Код ответа API (RequestException): {request_error}')
    except ValueError as value_error:
        logger.error(f'Код ответа API (ValueError): {value_error}')


def check_response(response):
    """Проверка api ответа на корректность."""
    try:
        homeworks = response['homeworks']
        if not isinstance(homeworks, list):
            raise TypeError("homework не является списком!")
    except KeyError:
        logger.error('Отсутствует ключ у homeworks')
        raise KeyError('Отсутствует ключ у homeworks')
    except IndexError:
        logger.info('Список домашних работ пуст')
        raise IndexError('Список домашних работ пуст')
    return homeworks


def parse_status(homework):
    """Проверка статуса домашней работы."""
    if not isinstance(homework, Dict):
        raise TypeError("homework не является словарем!")
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('У homework нет имени')
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyError('У homework нет статуса')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if verdict is None:
        raise KeyError(f'Ошибка статуса homework : {verdict}')
    logging.info(f'Новый статус {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        return True
    elif PRACTICUM_TOKEN is None:
        logger.critical('Отсутствует PRACTICUM_TOKEN')
        return False
    elif TELEGRAM_TOKEN is None:
        logger.critical('Отсутствует TELEGRAM_TOKEN')
        return False
    elif TELEGRAM_CHAT_ID is None:
        logger.critical('Отсутствует TELEGRAM_CHAT_ID')
        return False


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствуют токены чата'
        logger.critical(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    error_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp - RETRY_TIME)
            statuses = check_response(response)
            for status in statuses:
                message = parse_status(status)
                send_message(bot, message)
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error)
            if message != error_message:
                send_message(bot, message)
                error_message = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
