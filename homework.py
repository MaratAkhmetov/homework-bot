"""
Программа, описывающая Telegram-бота.
Бот обращается к API сервиса Практикум Домашка и узнает статус работы.
"""
import logging
import sys
import os
import time
import requests

from dotenv import load_dotenv
from telebot import TeleBot
from requests import RequestException
from telebot.apihelper import ApiTelegramException

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
    if missing:
        logger.critical(f'Отсутствуют переменные окружения: {missing}')
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram-чат. Возвращает True/False."""
    try:
        bot.send_message(os.getenv('TELEGRAM_CHAT_ID'), message)
        logger.debug(f'Сообщение отправлено в Telegram: {message}')
        return True
    except (ApiTelegramException, RequestException) as error:
        logger.error(f'Ошибка при отправке сообщения в Telegram: {error}')
        return False


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            logger.error(f'Недоступность эндпоинта: '
                         f'статус {response.status_code}')
            raise Exception(f'Недоступность эндпоинта: '
                            f'статус {response.status_code}')
        return response.json()
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к API: {error}')
        raise Exception(f'Ошибка при запросе к API: {error}') from error


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.error('Ответ API не является словарём')
        raise TypeError('Ответ API не является словарём')
    if 'homeworks' not in response or 'current_date' not in response:
        logger.error('Отсутствуют ожидаемые ключи в ответе API')
        raise KeyError('Отсутствуют ожидаемые ключи в ответе API')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logger.error('Ключ "homeworks" не содержит список')
        raise TypeError('Ключ "homeworks" не содержит список')
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if 'homework_name' not in homework:
        logger.error('Отсутствует ключ "homework_name" в домашней работе')
        raise KeyError('Ключ "homework_name" отсутствует в ответе API')
    homework_name = homework['homework_name']
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        logger.error(f'Неожиданный статус домашней работы: {status}')
        raise ValueError(f'Неизвестный статус работы '
                         f'"{homework_name}": {status}')
    verdict = HOMEWORK_VERDICTS[status]
    logger.debug(f'Статус работы "{homework_name}" изменился: {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы программы."""
    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения.'
                        'Программа остановлена.')
        sys.exit(1)
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ''
    last_status_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                message = parse_status(homework)
                if message != last_status_message:
                    send_message(bot, message)
                    last_status_message = message
                else:
                    logger.debug('Статус не изменился,'
                                 'сообщение не отправлено.')
            else:
                logger.debug('В ответе нет новых статусов домашних работ.')
            timestamp = response.get('current_date', timestamp)
            last_error_message = ''

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logger.error(error_message)
            if error_message != last_error_message:
                try:
                    send_message(bot, error_message)
                    last_error_message = error_message
                except Exception as send_error:
                    logger.error(
                        f'Не удалось отправить сообщение об ошибке в Telegram:'
                        f' {send_error}'
                    )

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
