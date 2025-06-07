"""
Программа, описывающая Telegram-бота.
Бот обращается к API сервиса Практикум Домашка и узнает статус работы.
"""
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from requests import RequestException
from telebot import TeleBot
from telebot.apihelper import ApiTelegramException

from exceptions import EndpointUnavailableError

load_dotenv()

PRACTICUM_TOKEN = 'y0__xCO_oYnGJG5GCDZgNOoE4HoCvjWAqmffTvfa0EId2xiprYC'
TELEGRAM_TOKEN = '7829946679:AAEVz9Sfv5829JlgtGMhZcF31UShXN8-0K4'
TELEGRAM_CHAT_ID = '7392073921'

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f"OAuth {os.getenv('PRACTICUM_TOKEN')}"}

logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s, %(levelname)s, %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    required_vars = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    missing = [name for name, value in required_vars.items() if not value]
    absence_of_variables = f'Отсутствуют переменные окружения: {missing}'
    if missing:
        logger.critical(absence_of_variables)
        raise EnvironmentError(absence_of_variables)


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат."""
    logger.debug('Начало отправки сообщения в Telegram.')
    bot.send_message(os.getenv('TELEGRAM_CHAT_ID'), message)
    logger.debug(f'Сообщение отправлено в Telegram: {message}')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    logger.debug(f'Отправка запроса к {ENDPOINT} с параметрами: {params}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка при запросе к API: {error}') from error

    if response.status_code != HTTPStatus.OK:
        raise EndpointUnavailableError(
            f'Эндпоинт {ENDPOINT} недоступен. Статус: {response.status_code}'
        )

    logger.debug('Успешно получен ответ от API')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logger.debug('Начало проверки ответа API')
    if not isinstance(response, dict):
        raise TypeError('Ожидался dict в переменной "response", '
                        f'но получен {type(response).__name__}')
    if 'homeworks' not in response:
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Ожидался list в ключе "homeworks", '
                        f'но получен {type(homeworks).__name__}')
    logger.debug('Ответ API успешно прошёл проверку')
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    logger.debug('Начало выполнения parse_status')
    required_keys = ['homework_name', 'status']
    missing_keys = [key for key in required_keys if key not in homework]
    if missing_keys:
        error_msg = ('Отсутствуют ключи в ответе API: '
                     f'{", ".join(missing_keys)}')
        raise KeyError(error_msg)
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы "{homework_name}": '
                         f'{status}')
    verdict = HOMEWORK_VERDICTS[status]
    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    logger.debug(f'Статус работы "{homework_name}" изменился: {verdict}')
    logger.debug('Завершение выполнения parse_status')
    return message


def main():
    """Основная логика работы программы."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_sent_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.debug('В ответе нет новых статусов домашних работ.')
                continue
            homework = homeworks[0]
            message = parse_status(homework)
            if message != last_sent_message:
                send_message(bot, message)
                last_sent_message = message
            else:
                logger.debug('Статус не изменился,'
                             'сообщение не отправлено.')
            timestamp = response.get('current_date', timestamp)

        except (ApiTelegramException, RequestException) as error:
            logger.exception('Ошибка при отправке сообщения в Telegram: '
                             f'{error}')

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logger.exception(error_message)

            if error_message != last_sent_message:
                try:
                    send_message(bot, error_message)
                    last_sent_message = error_message
                except (ApiTelegramException, RequestException) as send_error:
                    logger.exception('Не удалось отправить сообщение '
                                     f'об ошибке в Telegram: {send_error}')

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
