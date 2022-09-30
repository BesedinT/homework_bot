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
        logger.info(f'Сообщение отправлено: {message}')
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
    logger.info(f'Начинаем запрос к API {response_values["url"]} с '
                f'параметрами: {response_values["params"]}')
    try:
        response = requests.get(
            **response_values
        )
        if response.status_code != HTTPStatus.OK:
            message = (f'Ошибка при получении ответа с сервера '
                       f'{response.status_code}')
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
    except Exception as error:
        raise ConnectionError(f'Код ответа API к {response_values["url"]} с '
                              f'параметрами: {response_values["params"]}'
                              f'(ConnectionError):{error}')


def check_response(response):
    """Проверка api ответа на корректность."""
    if not isinstance(response, Dict):
        raise TypeError("homework не является словарем!")
    if 'homeworks' not in response:
        raise exceptions.EmptyAnswersAPI('Пустой ответ от API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise KeyError('homework не является списком!')
    return homeworks


def parse_status(homework):
    """Проверка статуса домашней работы."""
    logger.info('Начата проверка API на кооректность')
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('У homework нет имени')
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyError('У homework нет статуса')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Ошибка статуса homework : {homework_status}')
    logging.info(f'Новый статус {homework_status}')
    return (f'Изменился статус проверки работы "{homework_name}". '
            f'{HOMEWORK_VERDICTS.get(homework_status)}'
            f'homework_name = {homework_name}, verdict = '
            f'{HOMEWORK_VERDICTS.get(homework_status)}')


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = (
        ('Практикум токен', PRACTICUM_TOKEN),
        ('Телеграм токен', TELEGRAM_TOKEN),
        ('ID чата', TELEGRAM_TOKEN),
    )
    check = True
    for name, token in tokens:
        if not token:
            logger.critical(f'Отсутствует {name}')
            check = False
    return check


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise KeyError('Отсутствуют токены чата. Программа остановлена')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    current_report = {}
    prev_report = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            statuses = check_response(response)
            if statuses:
                status = statuses[0]
                message = parse_status(status)
                homework_status = status.get('status')
                current_report['сообщение'] = homework_status
            if current_report != prev_report:
                send_message(bot, message)
                if send_message:
                    prev_report = current_report.copy()
                    current_timestamp = response.get('current_date',
                                                     current_timestamp)
        except response is None:
            message = 'Пустой ответ от API'
            logger.info(message)
            raise exceptions.EmptyAnswersAPI(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            current_report['сообщение'] = message
            logger.exception()
            if current_report != prev_report:
                send_message(bot, message)
                if send_message:
                    prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        filename='logs.log',
        format='%(asctime)s, %(levelname)s, %(message)s,'
               '%(funcName)s, %(lineno)s',
        filemode='a',
    )
    main()
