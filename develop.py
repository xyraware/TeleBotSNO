
import requests
import settings
import telebot
from telebot import types
import os
import discord_webhook
import vk_api

TOKEN = settings.telegram_settings['token']
BOT_NAME = settings.telegram_settings['bot_name']
VK_ACCESS_TOKEN = settings.vk_settings['access_token']

bot_telegram = telebot.TeleBot(TOKEN)
vk_session = vk_api.VkApi(token=VK_ACCESS_TOKEN)

# Список действий в режиме постинга
actions = ['Отправить текст и фото', 'Отправить только текст', 'Отмена']

posting_mode = False


@bot_telegram.message_handler(commands=['start'])
def start_handler(message):
    """
        Обработчик команды /start. Отправляет приветственное сообщение и инструкции пользователю.

        :param message: Объект сообщения от пользователя.
    """
    start_post_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    start_post_keyboard.add(types.KeyboardButton('/start'), types.KeyboardButton('/post'))
    # Отправить приветственное сообщение и инструкции
    bot_telegram.send_message(message.chat.id,
                              'Привет! Я бот для автопостинга в канале. Для начала работы введите команду /post.',
                              reply_markup=start_post_keyboard)


# Обработчик команды /post
@bot_telegram.message_handler(commands=['post'])
def post_handler(message):
    """
        Обработчик команды /post, который отправляет сообщение с инструкциями по автопостингу
        и создает клавиатуру с действиями для выбора пользователем.

        :param message: Объект сообщения, полученного от Telegram API.
    """
    # Создать клавиатуру с действиями
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(*[types.KeyboardButton(action) for action in actions])

    # Отправить сообщение с инструкциями и клавиатурой
    bot_telegram.send_message(message.chat.id, 'Выберите действие:', reply_markup=keyboard)


# Обработчик текстовых сообщений в режиме постинга
@bot_telegram.message_handler(
    func=lambda message: posting_mode and message.text not in ['/post', 'Отправить текст и фото',
                                                               'Отправить только текст',
                                                               'Отмена', 'False'])
# Обработчик нажатия на кнопки в режиме постинга
@bot_telegram.message_handler(func=lambda message: message.text in actions)
def action_handler(message):
    """
    Обработчик текстовых сообщений в режиме постинга.

    :param message: Объект сообщения, полученного от Telegram API
    """
    # Получить выбранное действие
    action = message.text

    # Выбрать действие
    if action == 'Отправить текст и фото':
        # Перейти в режим ожидания текста
        bot_telegram.send_message(message.chat.id, 'Введите текст:')
        bot_telegram.register_next_step_handler(message, wait_text)
    elif action == 'Отправить только текст':
        # Перейти в режим ожидания текста без фото
        bot_telegram.send_message(message.chat.id, 'Введите текст:')
        bot_telegram.register_next_step_handler(message, send_text_only)
    elif action == 'Отмена':
        # Выйти из режима постинга
        bot_telegram.send_message(message.chat.id, 'Режим постинга завершен.', reply_markup=types.ReplyKeyboardRemove())
    else:
        # Неизвестное действие
        bot_telegram.send_message(message.chat.id, 'Неизвестное действие. Попробуйте еще раз.')


# Обработчик ожидания текста в режиме постинга
def wait_text(message):
    """
    Сохраняет текст сообщения для дальнейшей обработки и переводит бота в режим ождиания фотографии,
    вызывая функцию send_with_photo при получении следующего сообщения.
    :param message: сообщение от пользователя
    """
    # Сохранить текст для дальнейшей обработки
    bot_telegram.waiting_text = message.text

    # Перейти в режим ожидания фото
    bot_telegram.send_message(message.chat.id, 'Отправьте фото:')
    bot_telegram.register_next_step_handler(message, send_with_photo)


# Обработчик ожидания текста без фото в режиме постинга
def send_text_only(message):
    """
    Обрабатывает сообщения, содержащие только текст, отправляя их в канал в Discord,
    на стену группы ВКонтакте возвращая подтверждение об успешной отправке
    :param message: сообщение от пользователя
    """
    # Отправить текст в канал
    bot_telegram.send_message(BOT_NAME, message.text)
    webhook = discord_webhook.DiscordWebhook(
        url=settings.discord_webhook_settings['url'],
        content=f'{message.text}')
    response = webhook.execute()
    # Отправить подтверждение
    bot_telegram.send_message(message.chat.id, 'Текст успешно отправлен в канал.')

    vk_session.method('wall.post', {
        'owner_id': -int(settings.vk_settings['group_id']),
        'from_group': 1,
        'message': message.text
    })

    # Выход из режима постинга
    global posting_mode
    posting_mode = False


# Обработчик ожидания фото в режиме постинга
def send_with_photo(message):
    """
    Обрабатывает сообщения, содержащие фотографию и текст, отправляя их в канал на платформе Telegram,
    на канал на платформе Discord и на стену группы ВКонтакте и возвращая подтверждение о успешной отправке.

    :param message: сообщение от пользователя
    """
    if message.photo:
        # Скачать фото
        file_info = bot_telegram.get_file(message.photo[-1].file_id)
        downloaded_file = bot_telegram.download_file(file_info.file_path)
        url = f'https://api.telegram.org/file/bot{settings.telegram_settings["token"]}/{file_info.file_path}'

        # Получить расширение файла
        file_extension = os.path.splitext(file_info.file_path)[1]

        # Сохранить фото во временную папку
        temp_file_path = f'temp{file_extension}'
        with open(temp_file_path, 'wb') as f:
            f.write(downloaded_file)

        # Отправить фото в канал из временной папки
        with open(temp_file_path, 'rb') as f:
            bot_telegram.send_photo(BOT_NAME, f)

            # Отправить текст вместе с фото
        bot_telegram.send_message(BOT_NAME, bot_telegram.waiting_text)

        if settings.discord_webhook_settings['url']:
            payload = {
                'content': f'{bot_telegram.waiting_text}',
                'embeds': [
                    {
                        'image': {
                            'url': url
                        }
                    }
                ]
            }
            response = requests.post(settings.discord_webhook_settings['url'], json=payload)

        photo_response = vk_session.method('photos.getWallUploadServer', {'group_id': settings.vk_settings['group_id']})
        photo_upload_url = photo_response['upload_url']
        photo_file = {'photo': ('photo.jpg', requests.get(url).content)}
        photo_upload_response = requests.post(photo_upload_url, files=photo_file).json()

        photo_save_response = vk_session.method('photos.saveWallPhoto', {
            'group_id': settings.vk_settings['group_id'],
            'photo': photo_upload_response['photo'],
            'server': photo_upload_response['server'],
            'hash': photo_upload_response['hash']
        })

        # публикуем фотографию и текст на стене группы
        vk_session.method('wall.post', {
            'owner_id': -int(settings.vk_settings['group_id']),
            'from_group': 1,
            'message': bot_telegram.waiting_text,
            'attachments': 'photo{}_{}'.format(
                photo_save_response[0]['owner_id'],
                photo_save_response[0]['id']
            )
        })

        # Отправить подтверждение
        bot_telegram.send_message(message.chat.id, 'Фото и текст успешно отправлены в каналы.')

        # Удалить временный файл
        os.remove(temp_file_path)

    else:
        bot_telegram.send_message(message.chat.id, 'Не удалось загрузить фото, попробуйте еще раз.')

    # Выход из режима постинга
    global posting_mode
    posting_mode = False


def main():
    """
    Запускает бота Telegram и начинает его работу
    """
    print('Telegram is running')
    bot_telegram.polling()


if __name__ == '__main__':
    main()
