import os
import logging
import requests
import time
import json
import telegram

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


logging.basicConfig(
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s',
    level=logging.DEBUG
)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    logging.critical('Проверка наличия всех токенов')
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot: telegram.Bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug('Попытка отправки сообщения в telegram')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот отправил сообщение. {message}')
    except Exception as error:
        logging.error(f'Не удалось отправить сообщение. {error}')
        raise f'Не удалось отправить сообщение. {error}'


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        logging.debug('Попытка отправки запроса к эндпоинту API-сервиса')
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logging.debug('Отправлен запрос к эндпоинту API-сервиса')
    except requests.ConnectionError:
        logging.error('Подключение к Интернету отсутствует')
        raise ConnectionError('Подключение к Интернету отсутствует')
    except Exception as error:
        logging.error(f'Эндпоинт недоступен.Ошибка от сервера: {error}')
        send_message(f'Эндпоинт недоступен. Ошибка от сервера: {error}')
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Код ответа не 200: {response.status_code}')
        raise requests.exceptions.RequestException(
            f'Код ответа не 200: {response.status_code}'
        )
    try:
        return response.json()
    except json.JSONDecodeError:
        logging.error('Сервер вернул невалидный ответ')
        send_message('Сервер вернул невалидный ответ')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    try:
        homework = response['homeworks']
    except KeyError as error:
        logging.error(f'Ошибка доступа по ключу homeworks: {error}')
    if not isinstance(homework, list):
        logging.error('Homeworks не в виде списка')
        raise TypeError('Homeworks не в виде списка')
    return homework


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
    if check_tokens():
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())

        while True:
            try:
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)
                quantity_of_works = len(homeworks)
                while quantity_of_works > 0:
                    message = parse_status(homeworks[quantity_of_works - 1])
                    send_message(bot, message)
                    quantity_of_works -= 1
                current_timestamp = int(time.time())
                time.sleep(RETRY_PERIOD)

            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
