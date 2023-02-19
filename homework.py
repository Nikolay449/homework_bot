import os
import logging
import requests
import time
import telegram
import sys

from http import HTTPStatus
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    logging.info('Проверка наличия всех токенов')
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot: telegram.Bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug('Попытка отправки сообщения в telegram')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение. {message}')
    except Exception as error:
        logging.error(f'Не удалось отправить сообщение. {error}')
        return f'Не удалось отправить сообщение. {error}'


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logging.debug('Отправлен запрос к эндпоинту API-сервиса')
    except Exception as error:
        logging.error(f'Ошибка при запросе к эндпоинту API-сервиса: {error}')
        raise Exception(f'Ошибка при запросе к эндпоинту API-сервиса: {error}')
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Ошибка {response.status_code}')
        raise Exception(f'Ошибка {response.status_code}')
    try:
        return response.json()
    except ValueError:
        logging.error('Сервер вернул невалидный ответ')
        raise ValueError('Сервер вернул невалидный ответ')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logging.info('Проверка ответа API на корректность')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является dict')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('Нет ключа homeworks в ответе API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Homeworks не в виде списка')
    return homeworks


def parse_status(homework):
    """Извлекает из информацию, статус конкретной домашней работе."""
    logging.info('Проводим проверки и извлекаем статус работы')
    if 'homework_name' not in homework:
        raise KeyError('Нет ключа homework_name в ответе API')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы - {homework_status}')
    return ('Изменился статус проверки работы "{homework_name}". {verdict}'
            ).format(homework_name=homework_name,
                     verdict=HOMEWORK_VERDICTS[homework_status]
                     )


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Отсутствует токен!'
        logging.critical(message)
        sys.exit(message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    start_message = 'Бот начал работу'
    send_message(bot, start_message)
    logging.info(start_message)
    prev_msg = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = 'Нет новых статусов'
            if message != prev_msg:
                send_message(bot, message)
                prev_msg = message
            else:
                logging.info(message)
            current_timestamp = response.get('current_date')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            if message != prev_msg:
                send_message(bot, message)
                prev_msg = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        filename='program.log',
        format='%(asctime)s, %(levelname)s, %(message)s',
        level=logging.DEBUG,
        encoding='UTF-8'
    )
    main()
