import json
import logging
import os
import requests
import sys
import time
from typing import Dict

import telegram

from dotenv import load_dotenv
from http import HTTPStatus

import exceptions


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'telegram_bot.log')

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        filename='logs.log',
        format='%(asctime)s, %(levelname)s, %(message)s,'
               '%(funcName)s, %(lineno)s',
        filemode='a',
    )

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler_file = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s -'
                              '%(funcName)s - %(lineno)s')
handler.setFormatter(formatter)
handler_file.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(handler_file)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(f'Начата отправка сообщения: {message}')
        return True
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка: {error}')
        return False


def get_api_answer(current_timestamp):
    """Запрос к API."""
    params = {'from_date': current_timestamp}
    response_values = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params,
    }
    logger.info(f'Начинаем запрос к API с параметрами: {response_values}')
    try:
        response = requests.get(
            url=response_values.get('url'),
            headers=response_values.get('headers'),
            params=response_values.get('params')
        )
        if response.status_code != HTTPStatus.OK:
            message = 'Ошибка при получении ответа с сервера'
            raise exceptions.WrongResponse(message)
        logger.info('Получен ответ от сервера')
        return response.json()
    except json.decoder.JSONDecodeError:
        raise exceptions.JSONDecodeError('Ошибка преобразования в JSON')
    except requests.RequestException as request_error:
        raise exceptions.RequestError(f'Код ответа API (RequestException): '
                                      f'{request_error}')
    except ValueError as value_error:
        logger.error(f'Код ответа API (ValueError): {value_error}')
    except ConnectionError as error:
        raise requests.exceptions.ConnectionError(f'Код ответа API '
                                                  f'(ConnectionError):{error}')


def check_response(response):
    """Проверка api ответа на корректность."""
    if 'homeworks' not in response:
        raise exceptions.EmptyAnswersAPI('Пустой ответ от API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise KeyError('homework не является списком!')
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
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if homework_status not in HOMEWORK_VERDICTS.keys():
        raise ValueError(f'Ошибка статуса homework : {homework_status}')
    logging.info(f'Новый статус {homework_status}')
    return (f'Изменился статус проверки работы "{homework_name}". {verdict}'
            f'homework_name = {homework_name}, verdict = {verdict}')


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = (
        ('Практикум токен', PRACTICUM_TOKEN),
        ('Телеграм токен', TELEGRAM_TOKEN),
        ('ID чата', TELEGRAM_TOKEN),
    )
    check = True
    for name, token in tokens:
        if token is None:
            logger.critical(f'Отсутствует {name}')
            check = False
    return check


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        telegram.Update.stop()
        raise KeyError('Отсутствуют токены чата')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    current_report = {}
    prev_report = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            statuses = check_response(response)
            if statuses:
                message = parse_status(statuses[0])
                homework_name = statuses[0].get('homework_name')
                homework_status = statuses[0].get('status')
                current_report[homework_name] = homework_status
            if current_report != prev_report:
                send_message(bot, message)
                prev_report = current_report.copy()
                current_timestamp = response.get('current_date',
                                                 current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            current_report['error'] = message
            logger.error(error)
            if current_report != prev_report:
                send_message(bot, message)
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
