import logging
import asyncio
import aiosqlite
import json
import os
import shutil
import glob  # ДОБАВЬТЕ ЭТО
import random
from datetime import datetime, timedelta
import time
from dotenv import load_dotenv
import traceback
from aiogram.utils.exceptions import MessageNotModified, Unauthorized, InvalidQueryID, TelegramAPIError



#========== МОНКИ-ПАТЧИНГ ДЛЯ TOR ПРОКСИ ==========
import socket
import socks
socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
socket.socket = socks.socksocket
os.environ['ALL_PROXY'] = 'socks5://127.0.0.1:9050'
os.environ['HTTP_PROXY'] = 'socks5://127.0.0.1:9050' 
os.environ['HTTPS_PROXY'] = 'socks5://127.0.0.1:9050'

from aiogram import types
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext  # ДОБАВЬТЕ ЭТО
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.handler import CancelHandler

import direct_payment  # ДОБАВЬТЕ ЭТО
from admin_panel import AutoDelivery, add_auto_price, confirm_auto_point
from admin_panel import register_handlers as register_admin_handlers
from admin_panel import (
    ViewUsersTable,
    show_users_table, users_start_search, process_users_search,
    users_clear_search, users_change_sort, users_change_page,
    users_show_stats, view_users_table_back
)

import data_base as auto_db
import draw
import logs
from config import BOT_STATUS

load_dotenv()

# Настройка логирования ДО всех других операций
logs.setup_logging()
logging.info("🚀 Bot loading")

API_TOKEN = os.getenv('BOT_TOKEN')

import requests
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

import glob
import direct_payment as dp_module
import crypto_admin
from direct_payment import CRYPTO_SETTINGS, show_crypto_selection, process_direct_crypto_payment

from direct_payment import (
    CRYPTO_SETTINGS,
    USDT_SETTINGS, 
    DirectPayment,
    handle_paid_button,
    handle_tx_id_input,
    process_tx_id,
    check_direct_payment_status as check_direct_payment
)



# Aiogram автоматически использует системные настройки
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
draw.set_dp(dp)





LOG_CHAT_ID = int(os.getenv('LOG_CHAT_ID'))
ADMIN_IDS = set(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else set()
SUPPORT_WORKER_IDS = set(map(int, os.getenv('SUPPORT_WORKER_IDS', '').split(','))) if os.getenv('SUPPORT_WORKER_IDS') else set()
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')


SUPPORT_STATUS = {}

WELCOME_PHOTO_PATH = "img/WELCOME_PHOTO.jpg"
CITIES_PHOTO_PATH = "img/CITIES_PHOTO.jpg"
DISTRICTS_PHOTO_PATH = "img/DISTRICTS_PHOTO.jpg"
CATEGORIES_PHOTO_PATH = "img/CATEGORIES_PHOTO.jpg"
PROFILE_PHOTO_PATH = "img/PROFILE_PHOTO.jpg"
INFO_PHOTO_PATH = "img/INFO_PHOTO.jpg"

REQUIRED_CHANNELS = [
    {"id": -1003284608592, "name": "📢 Наш главный канал", "url": "https://t.me/+eWvldlBJGeAzNTJk"},
]

CRYPTOBOT_TOKEN = os.getenv('CRYPTOBOT_TOKEN')
CRYPTOBOT_TESTNET = os.getenv('CRYPTOBOT_TESTNET', 'False').lower() == 'true'

CRYPTOBOT_AVAILABLE = False
crypto_bot = None

try:
    from cryptobot import init_crypto_bot
    CRYPTOBOT_AVAILABLE = True
    crypto_bot = init_crypto_bot(CRYPTOBOT_TOKEN, CRYPTOBOT_TESTNET)
except ImportError as e:
    logs.log_warning(f"CryptoBot не доступен: {e}")
except Exception as e:
    logs.logger.error(f"Ошибка инициализации CryptoBot: {e}")

# Direct payment инициализируется в on_startup, не здесь

from aiogram.types import BotCommandScopeChat

async def set_bot_commands(dp: Dispatcher):
    # Команды для обычных пользователей
    user_commands = [
        BotCommand("start", "🚀 Запустить бота"),
        BotCommand("swap", "🌐 Сменить язык"),
        BotCommand("lang", "🗣️ Текущий язык")
    ]
    
    # Команды для администраторов (включая обычные + админские)
    admin_commands = user_commands + [
        BotCommand("admin", "🔐 Админ панель"),
        BotCommand("status", "🔧 Статус бота"),
        BotCommand("logs", "🔬 Логи"),
        BotCommand("tp", "👨‍💼 Панель поддержки")
    ]
    
    # Устанавливаем команды для всех пользователей (только базовые)
    try:
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    except:
        pass
    
    # Проверяем, есть ли администраторы для настройки
    if not ADMIN_IDS:
        return
    
    # Устанавливаем полный набор команд для каждого администратора
    for admin_id in ADMIN_IDS:
        try:
            chat = await bot.get_chat(admin_id)
            await bot.set_my_commands(
                admin_commands, 
                scope=BotCommandScopeChat(chat_id=admin_id)
            )
        except:
            continue

async def on_startup(dp):
    """Функция запуска при старте бота"""
    # Инициализируем базу данных
    await init_db()
    await auto_db.init_db()
    
    # Загружаем настройки криптовалют из БД
    try:
        import crypto_admin
        await crypto_admin.load_crypto_settings_from_db()
        logging.info("✅ Crypto settings loaded from database")
    except Exception as e:
        logging.error(f"Error loading crypto settings: {e}")
    
    # Загружаем настройки прямой оплаты
    try:
        await dp_module.init_direct_payment()
    except Exception as e:
        logging.error(f"Error loading direct payment settings: {e}")
    
    # Настраиваем команды бота
    await set_bot_commands(dp)
    
    logging.info("✅ Bot started")
        

@dp.message_handler(commands=['cryptotest', 'checkinvoice'])
async def admin_commands_check(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    command = message.get_command(pure=True)
    
    if command == 'cryptotest':
        await cryptotest_command(message)
    elif command == 'checkinvoice':
        await check_invoice_command(message)

@dp.callback_query_handler(lambda c: c.data.startswith("view_participants_"))
async def view_draw_participants(callback: types.CallbackQuery):
    draw_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect('shop.db') as db:
        participants = await (await db.execute('''
            SELECT username, ticket_number, joined_at 
            FROM draw_participants 
            WHERE draw_id = ? AND has_qualified = 1
            ORDER BY joined_at DESC
            LIMIT 50
        ''', (draw_id,))).fetchall()
        
        draw_info = await (await db.execute(
            "SELECT title FROM draws WHERE id = ?", (draw_id,)
        )).fetchone()
    
    if not draw_info:
        await callback.answer("❌ Розыгрыш не найден", show_alert=True)
        return
    
    title = draw_info[0]
    
    if not participants:
        text = f"🎫 <b>Участники розыгрыша</b>\n\n"
        text += f"🎁 <b>{title}</b>\n\n"
        text += "❌ Участников пока нет"
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("◀️ Назад", callback_data=f"manage_draw_{draw_id}"))
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        return
    
    text = f"🎫 <b>Участники розыгрыша</b>\n\n"
    text += f"🎁 <b>{title}</b>\n\n"
    text += f"👥 Всего участников: {len(participants)}\n\n"
    
    for i, (username, ticket_number, joined_at) in enumerate(participants, 1):
        username_display = f"@{username}" if username else "No username"
        text += f"{i}. {username_display}\n"
        text += f"   🎫 Билет: {ticket_number}\n"
        text += f"   ⏰ {joined_at[:16]}\n\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data=f"manage_draw_{draw_id}"))
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("view_referrals_"))
async def view_draw_referrals(callback: types.CallbackQuery):
    draw_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect('shop.db') as db:
        referrals = await (await db.execute('''
            SELECT dr.referred_username, dr.has_subscribed, 
                   u.username as referrer_username, dr.created_at
            FROM draw_referrals dr
            JOIN users u ON dr.referrer_id = u.user_id
            WHERE dr.draw_id = ?
            ORDER BY dr.created_at DESC
            LIMIT 50
        ''', (draw_id,))).fetchall()
        
        draw_info = await (await db.execute(
            "SELECT title FROM draws WHERE id = ?", (draw_id,)
        )).fetchone()
        
        stats = await (await db.execute('''
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN has_subscribed = 1 THEN 1 END) as subscribed
            FROM draw_referrals WHERE draw_id = ?
        ''', (draw_id,))).fetchone()
    
    if not draw_info:
        await callback.answer("❌ Розыгрыш не найден", show_alert=True)
        return
    
    title = draw_info[0]
    total_refs, subscribed_refs = stats
    
    text = f"🤝 <b>Рефералы розыгрыша</b>\n\n"
    text += f"🎁 <b>{title}</b>\n\n"
    text += f"📊 <b>Статистика:</b>\n"
    text += f"• Всего приглашено: {total_refs}\n"
    text += f"• Подписались: {subscribed_refs}\n"
    text += f"• Конверсия: {round((subscribed_refs/total_refs*100) if total_refs > 0 else 0, 1)}%\n\n"
    
    if not referrals:
        text += "❌ Рефералов пока нет"
    else:
        text += "<b>Последние рефералы:</b>\n\n"
        
        for i, (referred_username, has_subscribed, referrer_username, created_at) in enumerate(referrals, 1):
            referred_display = f"@{referred_username}" if referred_username else "No username"
            referrer_display = f"@{referrer_username}" if referrer_username else "No username"
            status = "✅ Подписан" if has_subscribed else "❌ Не подписан"
            
            text += f"{i}. {referred_display}\n"
            text += f"   👤 Пригласил: {referrer_display}\n"
            text += f"   📊 Статус: {status}\n"
            text += f"   ⏰ {created_at[:16]}\n\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data=f"manage_draw_{draw_id}"))
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("view_winners_"))
async def view_draw_winners(callback: types.CallbackQuery):
    draw_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect('shop.db') as db:
        winners = await (await db.execute('''
            SELECT username, ticket_number, won_at 
            FROM draw_winners 
            WHERE draw_id = ?
            ORDER BY won_at
        ''', (draw_id,))).fetchall()
        
        draw_info = await (await db.execute(
            "SELECT title FROM draws WHERE id = ?", (draw_id,)
        )).fetchone()
    
    if not draw_info:
        await callback.answer("❌ Розыгрыш не найден", show_alert=True)
        return
    
    title = draw_info[0]
    
    text = f"🏆 <b>Победители розыгрыша</b>\n\n"
    text += f"🎁 <b>{title}</b>\n\n"
    
    if not winners:
        text += "❌ Победителей нет"
    else:
        for i, (username, ticket_number, won_at) in enumerate(winners, 1):
            username_display = f"@{username}" if username else "No username"
            text += f"{i}. {username_display}\n"
            text += f"   🎫 Билет: {ticket_number}\n"
            text += f"   ⏰ {won_at[:16]}\n\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data=f"manage_draw_{draw_id}"))
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("end_draw_"))
async def end_draw_early(callback: types.CallbackQuery):
    draw_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect('shop.db') as db:
        draw_info = await (await db.execute(
            "SELECT title, winners_count FROM draws WHERE id = ? AND is_active = 1",
            (draw_id,)
        )).fetchone()
        
        if not draw_info:
            await callback.answer("❌ Розыгрыш не найден или уже завершен", show_alert=True)
            return
            
        title, winners_count = draw_info
        
        winners = await draw.select_winners(draw_id, winners_count)
        
        await db.execute(
            "UPDATE draws SET is_active = 0 WHERE id = ?",
            (draw_id,)
        )
        await db.commit()
    
    await draw.update_completed_draw_message(draw_id)
    
    if winners:
        winners_text_list = [f"🏆 @{username} (билет {ticket})" for _, username, ticket in winners]
        winners_text_log = "\n".join(winners_text_list)
        
        log_text = (
            f"🎉 Розыгрыш <b>«{title}»</b> завершен!\n\n"
            f"Победители:\n{winners_text_log}"
        )
    else:
        log_text = (
            f"🎉 Розыгрыш <b>«{title}»</b> завершен!\n\n"
            f"❌ Победителей нет - не было участников"
        )

    try:
        await bot.send_message(LOG_CHAT_ID, log_text, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send draw completion log to {LOG_CHAT_ID}: {e}")
    
    if winners:
        winners_text = "\n".join([f"🎫 @{username} (билет {ticket})" for _, username, ticket in winners])
        await callback.message.answer(
            f"✅ Розыгрыш <b>«{title}»</b> завершен досрочно!\n\n"
            f"🏆 Победители:\n{winners_text}",
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            f"✅ Розыгрыш <b>«{title}»</b> завершен досрочно!\n\n"
            f"❌ Победителей нет - не было участников",
            parse_mode="HTML"
        )
    
    await draw.manage_draw(callback)
    await callback.answer()

try:
    import en
except ImportError:
    class en:
        pass

import admin_panel as ap
ap.init_admin_panel(bot, ADMIN_IDS, ADMIN_PASSWORD, LOG_CHAT_ID)

async def safe_edit_message(callback: types.CallbackQuery, text: str, reply_markup=None, parse_mode="HTML", photo_path=None):
    try:
        if photo_path:
            try:
                await callback.message.delete()
            except:
                pass
            with open(photo_path, 'rb') as photo:
                await callback.message.answer_photo(
                    photo=photo,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
        elif callback.message.photo:
            await callback.message.edit_caption(
                caption=text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode
            )
        elif callback.message.video:
            await callback.message.edit_caption(
                caption=text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode
            )
        else:
            await callback.message.edit_text(
                text=text, 
                reply_markup=reply_markup, 
                parse_mode=parse_mode
            )
    except Exception as e:
        logs.logger.error(f"Error editing message", details=f"Error: {e}")
        if photo_path:
            try:
                with open(photo_path, 'rb') as photo:
                    await callback.message.answer_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=reply_markup,
                        parse_mode=parse_mode
                    )
            except Exception as photo_error:
                logs.logger.error(f"Error sending photo", details=f"Error: {photo_error}")
                await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)

class BanCheckMiddleware(BaseMiddleware):
    async def on_process_update(self, update: types.Update, data: dict):
        try:
            # Простой и безопасный подход
            user_id = None
            
            # Безопасно получаем user_id из разных типов обновлений
            if update.message:
                user_id = update.message.from_user.id if update.message.from_user else None
            elif update.callback_query:
                user_id = update.callback_query.from_user.id if update.callback_query.from_user else None
            elif update.inline_query:
                user_id = update.inline_query.from_user.id if update.inline_query.from_user else None
            elif update.edited_message:
                user_id = update.edited_message.from_user.id if update.edited_message.from_user else None
            
            if not user_id:
                return
            
            # Пропускаем админов
            if user_id in ADMIN_IDS:
                return

            # Проверяем бан
            async with aiosqlite.connect('shop.db') as db:
                cursor = await db.execute(
                    "SELECT banned FROM users WHERE user_id = ?", 
                    (user_id,)
                )
                result = await cursor.fetchone()
            
            # Если пользователь забанен
            if result and result[0] == 1:
                if update.message:
                    await update.message.answer(
                        get_text(user_id, 'USER_BANNED_MESSAGE', "Свяжитесь с поддержкой"),
                        parse_mode="HTML"
                    )
                elif update.callback_query:
                    try:
                        await update.callback_query.answer(
                            "Доступ запрещен",
                            show_alert=True
                        )
                    except:
                        pass
                
                raise CancelHandler()
                
        except Exception as e:
            if "CancelHandler" not in str(e):
                logs.logger.error(f"BanCheckMiddleware error: {str(e)[:100]}")
            raise

class BotStatusMiddleware(BaseMiddleware):
    async def on_process_update(self, update: types.Update, data: dict):
        try:
            user_id = None
            
            if update.message:
                user_id = update.message.from_user.id if update.message.from_user else None
            elif update.callback_query:
                user_id = update.callback_query.from_user.id if update.callback_query.from_user else None
            
            if not user_id:
                return
            
            # Пропускаем админов
            if user_id in ADMIN_IDS:
                return
            
            # Проверяем статус бота через config
            from config import BOT_STATUS
            
            if BOT_STATUS == "не ворк":
                # Получаем язык пользователя
                user_lang = USER_LANG.get(user_id, 'ru')
                
                if user_lang == 'en':
                    message_text = "🔴 <b>Bot is under Stop</b>\n\nWe apologize for the inconvenience. We are working on improvements."
                else:
                    message_text = "🔴 <b>Бот на технических работах</b>\n\nПриносим извинения за неудобства. Мы работаем над улучшениями."
                
                if update.message:
                    await update.message.answer(message_text, parse_mode="HTML")
                elif update.callback_query:
                    try:
                        if user_lang == 'en':
                            await update.callback_query.answer(
                                "Bot is under maintenance",
                                show_alert=True
                            )
                        else:
                            await update.callback_query.answer(
                                "Бот на технических работах",
                                show_alert=True
                            )
                    except:
                        pass
                
                raise CancelHandler()
                
        except Exception as e:
            if "CancelHandler" not in str(e):
                logs.logger.error(f"BotStatusMiddleware error: {str(e)[:100]}")
            raise

dp.middleware.setup(BanCheckMiddleware())
dp.middleware.setup(BotStatusMiddleware())


class Purchase(StatesGroup):
    waiting_for_quantity = State()
    waiting_for_payment_method = State()
    waiting_for_crypto_payment = State()
    waiting_for_proof = State()

class ManagerLog(StatesGroup):
    waiting_for_photos = State()
    

class ManagerReject(StatesGroup):
    waiting_for_reason = State()

class UserSetup(StatesGroup):
    waiting_for_language = State()
    waiting_for_subscription = State()

class PromoCode(StatesGroup):
    waiting_for_promo = State()

class CryptoBotDelivery(StatesGroup):
    pass

class SupportPanel(StatesGroup):
    waiting_for_support_message = State()

class ReviewStates(StatesGroup):
    waiting_for_review_text = State()

USER_LANG = {}

def get_text(user_id: int, key: str, *args) -> str:
    lang = USER_LANG.get(user_id, 'ru')
    
    if lang == 'en':
        text = getattr(en, key, None)
        if text is None:
            text = key
    else:
        ru_texts = {
            'MAIN_MENU': '🔹 Главное меню 🔹',
            'WELCOME_TEXT': 'Приветствуем вас в нашем шопе, вы сможете выбрать настроение на сегодня ниже',
            'CATEGORIES_BTN': '📂 Категории',
            'INFO_BTN': 'ℹ️ Информация',
            'PROFILE_BTN': '👤 Профиль',
            'ADMIN_PANEL_BTN': '🔐 Админ-панель',
            'BACK_BTN': '◀️ Назад',
            'CHOOSE_LANGUAGE': '🌐 Выберите язык:\n🌐 choose your language',
            'RUSSIAN_BTN': '🇷🇺 Русский',
            'ENGLISH_BTN': '🇬🇧 English',
            'CHOOSE_CITY': '🏙 Выберите город:',
            'CHOOSE_DISTRICT': '🏘 Выберите район:',
            'CHOOSE_CATEGORY': '📂 Выберите категорию:',
            'NO_PRODUCTS': '❌ Товаров нет.',
            'PRODUCT_NAME': '🎁 {}',
            'PRODUCT_PRICE': '💶 {} €',
            'PRODUCT_STOCK': '⚖️ На складе: {}г',
            'PRODUCT_DESCRIPTION': '📝 {}',
            'BUY_BTN': '🛒 Купить',
            'CHOOSE_QUANTITY': '⚖️ Выберите количество:',
            'CUSTOM_QUANTITY': '🔢 Другое количество',
            'MANAGER_CONTACT': '👨‍💼 Для большего количества обратитесь к менеджеру',
            'ORDER_NUMBER': '🆔 Заказ #{}',
            'USDT_ADDRESS': '🪙 USDT: <code>{}</code>',
            'BTC_ADDRESS': '🪙 BTC: <code>{}</code>',
            'CARD_DETAILS': '💳 Карта: <code>{}</code>',
            'PAYMENT_INSTRUCTIONS': '⏳ 10 мин. на оплату, после — скриншот.',
            'SCREENSHOT_SENT': '✅ Нету данных для Авто-выдачи. Скрин отправлен менеджерам, Ожидайте.',
            'PROFILE_TITLE': '👤 <b>Профиль</b>',
            'USER_ID': '🆔 ID: <code>{}</code>',
            'ORDERS_COUNT': '🔢 Заказов: {}',
            'USER_RANK': '🎖️ Ранг: {}',
            'INFO_TITLE': 'ℹ️ <b>Контакты поддержки и правила</b>',
            'QUANTITY_SELECTED': '⚖️ Выбрано: {}г\n💶 Общая стоимость: {} €',
            'ENTER_CUSTOM_QUANTITY': '🔢 Введите количество грамм:',
            'INVALID_QUANTITY': '❌ Неверное количество. Введите число:',
            'NOT_ENOUGH_STOCK': '❌ Недостаточно товара на складе. Доступно: {}г',
            'LANGUAGE_CHANGED': '🌐 Язык изменен на {}',
            'CURRENT_LANGUAGE': '🌐 Текущий язык: {}',
            'SEND_PHOTOS_PROMPT': '📸 Пришлите фото местоположения (можно несколько).',
            'SEND_COORDS_PROMPT': '📍 Теперь пришлите координаты (только текст).',
            'WAITING_FOR_MORE_PHOTOS': '📸 Фото принято! Можете отправить еще фото или нажмите "✅ Готово" чтобы завершить.',
            'PHOTOS_COMPLETED': '✅ Все фото приняты! Отправляю пользователю...',
            'SUPPORT_BTN': '📞 Поддержка',
            'RULES_BTN': '📋 Правила',
            'SUBSCRIPTION_REQUIRED': '📢 Для использования бота нужно подписаться на наш канал',
            'CHECK_SUBSCRIPTION_BTN': '✅ Проверить подписку',
            'SUBSCRIBE_BTN': '📢 Подписаться на канал',
            'SUBSCRIPTION_SUCCESS': '✅ Спасибо за подписку! Теперь вы можете использовать бота.',
            'SUBSCRIPTION_FAILED': '❌ Вы не подписаны на все необходимые каналы. Пожалуйста, подпишитесь и попробуйте снова.',
            'PROMO_CODE_BTN': '🎁 Промокод',
            'ENTER_PROMO_CODE': '🎁 Введите промокод:',
            'PROMO_CODE_APPLIED': '✅ Промокод применен! Скидка: {}%',
            'PROMO_CODE_INVALID': '❌ Неверный промокод',
            'PROMO_CODE_EXPIRED': '❌ Промокод истек',
            'PROMO_CODE_USED': '❌ Промокод уже использован',
            'ORDER_CANCELLED': '❌ Заказ #{} отменен (время оплаты истекло)',
            'DISCOUNT_APPLIED': '🎁 Скидка применена: {}%',
            'USER_BANNED_MESSAGE': '❌ <b>Доступ запрещен</b> ❌\n\nВы были забанены администратором и больше не можете пользоваться ботом.\n\nДля большей информации обратитесь к нашему сапорту: {}',
            'USER_UNBANNED_MESSAGE': '✅ <b>Доступ восстановлен</b> ✅\n\nВы были разбанены. Теперь вы снова можете пользоваться ботом.',
            'AUTO_DELIVERY_SUCCESS': '🚚 Ваш клад готов!\n\n\n✅ Заказ #{}\n🎁 Товар: {}\n⚖️ Количество: {}г\n{}❤️ Спасибо за покупку! Приятного отдыха!',
            'NEW_ORDER_LOG': '🆕 Новый заказ #{}\n👤 Пользователь: {}\n🎁 Товар: {}\n⚖️ Количество: {}г\n💰 Сумма: {} €\n📍 Локация: {}',
            'ORDER_PROCESSED_LOG': '✅ Заказ #{} обработан автоматически\n📦 Использована авто-выдача\n👤 Пользователь уведомлен с фото клада',
            'PAYMENT_METHOD_SELECTION': '💳 <b>Выберите способ оплаты:</b>',
            'CRYPTOBOT_PAYMENT_TITLE': '🤖 <b>Оплата через CryptoBot</b>',
            'EXCHANGE_RATE': '💱 Курс: 1 EUR = {:.2f} USDT',
            'AMOUNT_TO_PAY': '🪙 К оплате: {:.2f} USDT',
            'PAY_VIA_CRYPTOBOT': '💳 Оплатить через CryptoBot',
            'CHECK_PAYMENT_STATUS': '🔄 Проверить оплату',
            'CANCEL_ORDER': '❌ Отменить заказ',
            'PAYMENT_SUCCESS_ALERT': '✅ Оплата получена! Обрабатываем заказ...',
            'PAYMENT_PENDING_ALERT': '❌ Платеж еще не получен. Статус: {}',
            'CRYPTOBOT_INSTRUCTIONS': '📖 Инструкция по оплате',
            'CLICK_BELOW_TO_PAY': '👇 Нажмите кнопку ниже для оплаты:',
            'CHOOSE_PRODUCT': '🎁 Выберите товар:',
            'ADMIN_PANEL_TITLE': '🔐 <b>Админ-панель</b>',
            'ADMIN_ADD_CATEGORY': '➕ Категория',
            'ADMIN_DELETE_CATEGORY': '🗑️ Удалить категорию',
            'ADMIN_ADD_CITY': '🏙️ Добавить город',
            'ADMIN_DELETE_CITY': '🗑️ Удалить город',
            'ADMIN_ADD_DISTRICT': '🏘️ Добавить район',
            'ADMIN_ADD_PRODUCT': '🎁 Добавить товар',
            'ADMIN_DELETE_PRODUCT': '🗑️ Удалить товар',
            'ADMIN_EDIT_PAYMENTS': '💳 Реквизиты оплаты',
            'ADMIN_BROADCAST': '📢 Рассылка',
            'ADMIN_BAN_USER': '🔨 Забанить пользователя',
            'ADMIN_UNBAN_USER': '🔓 Разбанить пользователя',
            'ADMIN_EDIT_STOCK': '📦 Остатки',
            'ADMIN_STATS': '📊 Статистика',
            'ADMIN_EXIT': '🚪 Выход',
            'DRAW_PANEL': '🎁 Панель розыгрышей',
            'CREATE_DRAW': '🎫 Создать розыгрыш',
            'ACTIVE_DRAWS': '📋 Активные розыгрыши',
            'COMPLETED_DRAWS': '📊 Завершенные розыгрыши',
            'DRAW_STATS': '📈 Статистика розыгрышей',
            'DRAW_PARTICIPANTS': '👥 Участники',
            'DRAW_REFERRALS': '🤝 Рефералы',
            'DRAW_WINNERS': '🏆 Победители',
            'END_DRAW_EARLY': '⏹️ Завершить досрочно',
            'JOIN_DRAW': '🎯 Участвовать',
            'AUTO_DELIVERY_MANAGEMENT': '🚚 Авто-выдача',
            'ADD_AUTO_POINT': '📍 Добавить точку клада',
            'LIST_AUTO_POINTS': '📋 Список точек кладов',
            'DELETE_AUTO_POINT': '🗑️ Удалить точку клада',
            'ORDER_PENDING': '⏳ Ожидание',
            'ORDER_COMPLETED': '✅ Завершен',
            'ORDER_CANCELLED': '❌ Отменен',
            'ORDER_REJECTED': '🚫 Отклонен',
            'PAYMENT_CRYPTOBOT': '🤖 CryptoBot',
            'PAYMENT_CARD': '💳 Банковская карта',
            'CONFIRM_ORDER': '✅ Подтвердить',
            'REJECT_ORDER': '🚫 Отклонить',
            'SEND_PHOTOS': '📸 Отправить фото',
            'FINISH_PHOTOS': '✅ Готово (отправить фото)',
            'ENTER_COORDINATES': '📍 Ввести координаты',
            'AUTO_DELIVERY_QUANTITIES': '⚖️ Доступные клады: {}г',
        }
        text = ru_texts.get(key, key)
    
    return text.format(*args) if args else text

def get_user_rank(order_count: int, user_id: int) -> str:
    lang = USER_LANG.get(user_id, 'ru')
    
    if order_count >= 100:
        return "👑 БОГ" if lang == 'ru' else "👑 GOD"
    elif order_count >= 60:
        return "😈 Псих" if lang == 'ru' else "😈 PSYCHO"
    elif order_count >= 30:
        return "🎯 Игрок" if lang == 'ru' else "🎯 PLAYER"
    elif order_count >= 10:
        return "🔥 Начинающий" if lang == 'ru' else "🔥 BEGINNER"
    else:
        return "🎪 Новичок" if lang == 'ru' else "🎪 NOVICE"

async def check_subscription(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            chat_member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            allowed_statuses = ['member', 'administrator', 'creator']
            if chat_member.status not in allowed_statuses:
                return False
        except Exception as e:
            logs.logger.error(f"Error checking subscription", details=f"Channel: {channel['id']}, Error: {e}")
            return False
    return True

async def save_user_subscription(user_id: int):
    async with aiosqlite.connect('shop.db') as db:
        await db.execute(
            "UPDATE users SET subscribed=1 WHERE user_id=?",
            (user_id,)
        )
        await db.commit()

async def get_subscription_status(user_id: int) -> bool:
    async with aiosqlite.connect('shop.db') as db:
        result = await (await db.execute(
            "SELECT subscribed FROM users WHERE user_id = ?", 
            (user_id,)
        )).fetchone()
        return bool(result and result[0]) if result else False

async def create_subscription_keyboard(user_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    lang = USER_LANG.get(user_id, 'ru')
    
    if lang == 'en':
        channel_name = "📢 Our main channel"
        button_text = "✅ I subscribed"
    else:
        channel_name = "📢 Наш главный канал" 
        button_text = "✅ Я подписался"
    
    keyboard.add(InlineKeyboardButton(
        text=channel_name, 
        url="https://t.me/+eWvldlBJGeAzNTJk"
    ))
    
    keyboard.add(InlineKeyboardButton(
        text=button_text, 
        callback_data="check_subscription"
    ))
    
    return keyboard

def get_subscription_message(user_id: int) -> str:
    lang = USER_LANG.get(user_id, 'ru')
    
    if lang == 'en':
        return (
            "🔒 <b>Access Restricted</b>\n\n"
            "To use the bot you need to subscribe to our channel:\n\n"
            "👇 Subscribe to the channels below and click the «I subscribed» button"
        )
    else:
        return (
            "🔒 <b>Доступ ограничен</b>\n\n"
            "Для использования бота нужно подписаться на наш канал:\n\n"
            "👇 Подпишитесь на каналы ниже и нажмите кнопку «Я подписался»"
        )

async def init_db():
    """
    Инициализирует базу данных и создает все необходимые таблицы
    """
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Включаем внешние ключи
            await db.execute("PRAGMA foreign_keys = ON")
            
            # ========== ПОЛЬЗОВАТЕЛИ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    lang TEXT DEFAULT 'ru',
                    banned INTEGER DEFAULT 0,
                    subscribed INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
                    referral_code TEXT UNIQUE,
                    referred_by INTEGER,
                    total_orders INTEGER DEFAULT 0,
                    total_spent REAL DEFAULT 0
                )
            ''')
            
            # ========== КАТЕГОРИИ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ========== ГОРОДА ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS cities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ========== РАЙОНЫ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS districts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city_id INTEGER,
                    name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(city_id, name),
                    FOREIGN KEY (city_id) REFERENCES cities (id) ON DELETE CASCADE
                )
            ''')
            
            # ========== ТОВАРЫ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER,
                    name TEXT,
                    description TEXT,
                    photo_id TEXT,
                    video_id TEXT,
                    stock INTEGER DEFAULT 0,
                    is_hidden INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories (id)
                )
            ''')
            
            # ========== ЗАКАЗЫ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_display_id TEXT UNIQUE,
                    user_id INTEGER,
                    product_id INTEGER,
                    product_name TEXT,
                    quantity REAL,
                    final_price REAL,
                    status TEXT DEFAULT 'pending',
                    payment_method TEXT,
                    payment_type TEXT DEFAULT 'cryptobot',
                    city_id INTEGER,
                    district_id INTEGER,
                    promo_code TEXT,
                    discount_percent REAL DEFAULT 0,
                    invoice_id TEXT,
                    crypto_amount REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expiration_warning_sent INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (product_id) REFERENCES products (id),
                    FOREIGN KEY (city_id) REFERENCES cities (id),
                    FOREIGN KEY (district_id) REFERENCES districts (id)
                )
            ''')
            
            # Добавляем колонки если их нет
            try:
                await db.execute('ALTER TABLE orders ADD COLUMN expiration_warning_sent INTEGER DEFAULT 0')
                await db.commit()
            except:
                pass
            try:
                await db.execute('ALTER TABLE orders ADD COLUMN order_display_id TEXT UNIQUE')
                await db.commit()
            except:
                pass
            
            # ========== ПЛАТЕЖНЫЕ РЕКВИЗИТЫ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    usdt TEXT,
                    btc TEXT,
                    card TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Инициализируем таблицу payments если пуста
            payments_exist = await (await db.execute(
                "SELECT COUNT(*) FROM payments WHERE id = 1"
            )).fetchone()
            
            if payments_exist[0] == 0:
                await db.execute(
                    "INSERT INTO payments (id, usdt, btc, card) VALUES (1, NULL, NULL, NULL)"
                )
            
            # ========== НАСТРОЙКИ (для прямой оплаты USDT и др.) ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ========== ПРОМОКОДЫ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    discount_percent REAL,
                    usage_limit INTEGER DEFAULT 0,
                    used_count INTEGER DEFAULT 0,
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ========== АВТО-ВЫДАЧА ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS auto_delivery_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    city_id INTEGER,
                    district_id INTEGER,
                    photo_file_id TEXT,
                    coordinates TEXT,
                    description TEXT,
                    quantity_grams REAL,
                    unit_type TEXT DEFAULT 'grams',
                    price REAL,
                    is_used INTEGER DEFAULT 0,
                    is_hidden INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id),
                    FOREIGN KEY (city_id) REFERENCES cities (id),
                    FOREIGN KEY (district_id) REFERENCES districts (id)
                )
            ''')
            
            # ========== СКРЫТЫЕ ТОВАРЫ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS hidden_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER UNIQUE,
                    hidden_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    reason TEXT,
                    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
                )
            ''')
            
            # ========== CRYPTOBOT ИНВОЙСЫ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS crypto_invoices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT UNIQUE,
                    order_id INTEGER,
                    user_id INTEGER,
                    amount_usdt REAL,
                    status TEXT DEFAULT 'pending',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    paid_at DATETIME,
                    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # ========== ПРЯМАЯ ОПЛАТА USDT ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS direct_payment_settings (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    address TEXT,
                    api_key TEXT,
                    api_secret TEXT,
                    network TEXT DEFAULT 'TRC20',
                    is_active INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Инициализируем таблицу direct_payment_settings если пуста
            dp_settings_exist = await (await db.execute(
                "SELECT COUNT(*) FROM direct_payment_settings WHERE id = 1"
            )).fetchone()
            
            if dp_settings_exist[0] == 0:
                await db.execute(
                    "INSERT INTO direct_payment_settings (id, address, api_key, api_secret, network, is_active) VALUES (1, NULL, NULL, NULL, 'TRC20', 0)"
                )
            
            # ========== ПРЯМЫЕ ПЛАТЕЖИ USDT ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS direct_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER UNIQUE,
                    usdt_amount REAL,
                    wallet_address TEXT,
                    network TEXT DEFAULT 'TRC20',
                    tx_hash TEXT,
                    status TEXT DEFAULT 'pending',
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    confirmed_at DATETIME,
                    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
                )
            ''')
            
            # ========== РОЗЫГРЫШИ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS draws (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    description TEXT,
                    prize TEXT,
                    winners_count INTEGER DEFAULT 1,
                    max_participants INTEGER,
                    ticket_price REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    draw_date DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS draw_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draw_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    ticket_number INTEGER,
                    has_qualified INTEGER DEFAULT 0,
                    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(draw_id, user_id),
                    FOREIGN KEY (draw_id) REFERENCES draws (id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # ========== ОТЗЫВЫ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER UNIQUE,
                    user_id INTEGER,
                    username TEXT,
                    product_name TEXT,
                    rating INTEGER,
                    review_text TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS draw_winners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draw_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    ticket_number INTEGER,
                    won_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (draw_id) REFERENCES draws (id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS draw_referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draw_id INTEGER,
                    referrer_id INTEGER,
                    referred_user_id INTEGER,
                    referred_username TEXT,
                    has_subscribed INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (draw_id) REFERENCES draws (id) ON DELETE CASCADE,
                    FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                    FOREIGN KEY (referred_user_id) REFERENCES users (user_id)
                )
            ''')
            
            # ========== ЛОГИ ИНВОЙСОВ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS invoice_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT,
                    order_id INTEGER,
                    action TEXT,
                    details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE SET NULL
                )
            ''')
            
            # ========== СЕССИИ ПОКУПКИ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS purchase_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    product_id INTEGER,
                    quantity REAL,
                    final_price REAL,
                    city_id INTEGER,
                    district_id INTEGER,
                    promo_code TEXT,
                    session_data TEXT,
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (product_id) REFERENCES products (id),
                    FOREIGN KEY (city_id) REFERENCES cities (id),
                    FOREIGN KEY (district_id) REFERENCES districts (id)
                )
            ''')
            
            # ========== ПРОВЕРКА И ДОБАВЛЕНИЕ КОЛОНОК ==========
            
            # Проверяем существующие столбцы и добавляем отсутствующие
            try:
                # Проверяем наличие колонки payment_type в orders
                columns = await (await db.execute("PRAGMA table_info(orders)")).fetchall()
                column_names = [col[1] for col in columns]
                
                if 'payment_type' not in column_names:
                    await db.execute("ALTER TABLE orders ADD COLUMN payment_type TEXT DEFAULT 'cryptobot'")
                    logging.info("Added payment_type column to orders table")
                
                if 'tx_hash' not in column_names:
                    await db.execute("ALTER TABLE orders ADD COLUMN tx_hash TEXT")
                    logging.info("Added tx_hash column to orders table")
                    
                # Проверяем другие важные колонки
                if 'usdt_amount' not in column_names:
                    await db.execute("ALTER TABLE orders ADD COLUMN usdt_amount REAL")
                
                # НОВЫЕ ПОЛЯ ДЛЯ ПРЯМОЙ ОПЛАТЫ
                if 'payment_tail' not in column_names:
                    await db.execute("ALTER TABLE orders ADD COLUMN payment_tail TEXT")
                    logging.info("Added payment_tail column to orders table")
                
                if 'payment_unique_amount' not in column_names:
                    await db.execute("ALTER TABLE orders ADD COLUMN payment_unique_amount REAL")
                    logging.info("Added payment_unique_amount column to orders table")
                
                if 'payment_expires_at' not in column_names:
                    await db.execute("ALTER TABLE orders ADD COLUMN payment_expires_at DATETIME")
                    logging.info("Added payment_expires_at column to orders table")
                
                if 'payment_status' not in column_names:
                    await db.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'pending'")
                    logging.info("Added payment_status column to orders table")
                    
            except Exception as e:
                logging.warning(f"Could not check/alter orders table: {e}")
            
            # Проверяем и добавляем колонки в direct_payments
            try:
                columns = await (await db.execute("PRAGMA table_info(direct_payments)")).fetchall()
                column_names = [col[1] for col in columns]
                
                if 'confirmed_at' not in column_names:
                    await db.execute("ALTER TABLE direct_payments ADD COLUMN confirmed_at DATETIME")
                    
                if 'network' not in column_names:
                    await db.execute("ALTER TABLE direct_payments ADD COLUMN network TEXT DEFAULT 'TRC20'")
                    
            except Exception as e:
                logging.warning(f"Could not check/alter direct_payments table: {e}")
            
            # Проверяем и добавляем колонки в users
            try:
                columns = await (await db.execute("PRAGMA table_info(users)")).fetchall()
                column_names = [col[1] for col in columns]
                
                if 'total_orders' not in column_names:
                    await db.execute("ALTER TABLE users ADD COLUMN total_orders INTEGER DEFAULT 0")
                    logging.info("Added total_orders column to users table")
                
                if 'total_spent' not in column_names:
                    await db.execute("ALTER TABLE users ADD COLUMN total_spent REAL DEFAULT 0")
                    logging.info("Added total_spent column to users table")
                    
            except Exception as e:
                logging.warning(f"Could not check/alter users table: {e}")
            
            # ========== ИНДЕКСЫ ДЛЯ БЫСТРОГО ПОИСКА ==========
            
            # СНАЧАЛА проверим что колонки существуют, потом создаем индексы
            
            # Проверяем существование колонок перед созданием индексов
            try:
                # Для orders
                orders_columns = await (await db.execute("PRAGMA table_info(orders)")).fetchall()
                orders_column_names = [col[1] for col in orders_columns]
                
                # Индексы для пользователей
                await db.execute("CREATE INDEX IF NOT EXISTS idx_users_banned ON users(banned)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_users_subscribed ON users(subscribed)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at)")
                
                # Индексы для заказов (только если колонки существуют)
                if 'user_id' in orders_column_names:
                    await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
                
                if 'status' in orders_column_names:
                    await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
                
                if 'created_at' in orders_column_names:
                    await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at)")
                
                # payment_type может быть еще не добавлен, если таблица уже существовала
                # Пытаемся добавить индекс, но ловим ошибку если колонки нет
                try:
                    if 'payment_type' in orders_column_names:
                        await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_payment_type ON orders(payment_type)")
                except:
                    logging.warning("Cannot create index for payment_type - column may not exist yet")
                
                # Индексы для авто-выдачи
                await db.execute("CREATE INDEX IF NOT EXISTS idx_auto_points_product ON auto_delivery_points(product_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_auto_points_city ON auto_delivery_points(city_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_auto_points_used ON auto_delivery_points(is_used)")
                
                # Индексы для крипто инвойсов
                await db.execute("CREATE INDEX IF NOT EXISTS idx_crypto_invoices_status ON crypto_invoices(status)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_crypto_invoices_order ON crypto_invoices(order_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_crypto_invoices_user ON crypto_invoices(user_id)")
                
                # Индексы для прямых платежей
                await db.execute("CREATE INDEX IF NOT EXISTS idx_direct_payments_order ON direct_payments(order_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_direct_payments_status ON direct_payments(status)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_direct_payments_expires ON direct_payments(expires_at)")
                
                # Индексы для розыгрышей
                await db.execute("CREATE INDEX IF NOT EXISTS idx_draw_participants_draw ON draw_participants(draw_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_draw_participants_user ON draw_participants(user_id)")
                await db.execute("CREATE INDEX IF NOT EXISTS idx_draws_active ON draws(is_active)")
                
                # Проверяем существование таблицы reviews
                reviews_table_check = await (await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='reviews'"
                )).fetchone()
                
                if not reviews_table_check:
                    logging.info("Creating reviews table...")
                    await db.execute('''
                        CREATE TABLE reviews (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            order_id INTEGER UNIQUE,
                            user_id INTEGER,
                            username TEXT,
                            product_name TEXT,
                            rating INTEGER,
                            review_text TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE,
                            FOREIGN KEY (user_id) REFERENCES users (user_id)
                        )
                    ''')
                    await db.execute("CREATE INDEX IF NOT EXISTS idx_reviews_user ON reviews(user_id)")
                    await db.execute("CREATE INDEX IF NOT EXISTS idx_reviews_order ON reviews(order_id)")
                    logging.info("✅ Reviews table created successfully")
                
            except Exception as e:
                logging.warning(f"Error creating indexes: {e}")
            
            # ========== ТРИГГЕРЫ ==========
            
            try:
                # Триггер для обновления updated_at в заказах
                await db.execute('''
                    CREATE TRIGGER IF NOT EXISTS update_orders_timestamp 
                    AFTER UPDATE ON orders
                    BEGIN
                        UPDATE orders SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                ''')
                
                # Триггер для обновления статистики пользователя при новом заказе
                await db.execute('''
                    CREATE TRIGGER IF NOT EXISTS update_user_stats_on_order
                    AFTER INSERT ON orders
                    WHEN NEW.status = 'completed'
                    BEGIN
                        UPDATE users 
                        SET total_orders = total_orders + 1,
                            total_spent = total_spent + NEW.final_price,
                            last_active = CURRENT_TIMESTAMP
                        WHERE user_id = NEW.user_id;
                    END
                ''')
                
            except Exception as e:
                logging.warning(f"Could not create triggers: {e}")
            
            # ========== ЛОГИ ДЕЙСТВИЙ ПОЛЬЗОВАТЕЛЕЙ ==========
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action_type TEXT,
                    action_details TEXT,
                    page TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')
            
            await db.commit()
            
            logging.info("✅ Database initialized successfully")
            
            # Проверяем количество записей в основных таблицах
            tables_to_check = ['users', 'categories', 'cities', 'products', 'orders']
            
            for table in tables_to_check:
                try:
                    count = await (await db.execute(f"SELECT COUNT(*) FROM {table}")).fetchone()
                    logging.info(f"📊 Table {table}: {count[0]} records")
                except:
                    logging.warning(f"Table {table} may not exist yet")
                
    except Exception as e:
        logging.error(f"❌ Error initializing database: {e}")
        raise

# Также создадим функцию для создания резервной копии базы данных
async def backup_database():
    """
    Создает резервную копию базы данных
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup/shop_backup_{timestamp}.db"
        
        # Создаем папку backup если её нет
        os.makedirs("backup", exist_ok=True)
        
        async with aiosqlite.connect('shop.db') as source:
            async with aiosqlite.connect(backup_file) as backup:
                await source.backup(backup)
        
        logging.info(f"✅ Database backup created: {backup_file}")
        
        # Удаляем старые резервные копии (оставляем последние 7)
        backup_files = sorted(glob.glob("backup/shop_backup_*.db"))
        if len(backup_files) > 7:
            for old_file in backup_files[:-7]:
                os.remove(old_file)
                logging.info(f"🗑️ Removed old backup: {old_file}")
                
    except Exception as e:
        logging.error(f"❌ Error creating database backup: {e}")

# Функция для проверки целостности базы данных
async def check_database_integrity():
    """
    Проверяет целостность базы данных
    """
    try:
        async with aiosqlite.connect('shop.db') as db:
            integrity_check = await (await db.execute("PRAGMA integrity_check")).fetchone()
            
            if integrity_check[0] == "ok":
                logging.info("✅ Database integrity check passed")
                return True
            else:
                logging.error(f"❌ Database integrity check failed: {integrity_check[0]}")
                return False
                
    except Exception as e:
        logging.error(f"❌ Error checking database integrity: {e}")
        return False

# Функция для оптимизации базы данных
async def optimize_database():
    """
    Выполняет оптимизацию базы данных
    """
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Анализируем базу для лучшего плана запросов
            await db.execute("ANALYZE")
            
            # Выполняем VACUUM для освобождения места
            await db.execute("VACUUM")
            
            # Обновляем статистику
            await db.execute("PRAGMA optimize")
            
            logging.info("✅ Database optimization completed")
            
    except Exception as e:
        logging.error(f"❌ Error optimizing database: {e}")

async def log_user_action(user_id: int, action_type: str, action_details: str = "", page: str = ""):
    async with aiosqlite.connect('shop.db') as db:
        await db.execute(
            """INSERT INTO user_actions 
            (user_id, action_type, action_details, page) 
            VALUES (?, ?, ?, ?)""",
            (user_id, action_type, action_details, page)
        )
        await db.commit()

async def log_order_action(order_id: int, action: str, details: str):
    """Логирует действия с заказом"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            await db.execute(
                """INSERT INTO invoice_logs (order_id, action, details) 
                   VALUES (?, ?, ?)""",
                (order_id, action, details)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Error logging order action: {e}")

async def save_manager_photo(order_id: int, file_id: str):
    async with aiosqlite.connect('shop.db') as db:
        await db.execute(
            "INSERT INTO manager_photos(order_id, file_id) VALUES(?,?)",
            (order_id, file_id)
        )
        await db.commit()

async def get_manager_photos(order_id: int):
    async with aiosqlite.connect('shop.db') as db:
        rows = await (await db.execute(
            "SELECT file_id FROM manager_photos WHERE order_id=?", (order_id,)
        )).fetchall()
    return [row[0] for row in rows]

async def cancel_expired_orders():
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            async with aiosqlite.connect('shop.db') as db:
                # ДОБАВЬТЕ ЭТИ СТРОКИ:
                await db.execute("PRAGMA journal_mode=WAL")  # Включаем WAL режим
                await db.execute("PRAGMA busy_timeout=5000")  # Увеличьте таймаут
                
                expired_orders = await (await db.execute(
                    "SELECT id, user_id FROM orders WHERE status='pending' AND expires_at < datetime('now')"
                )).fetchall()
                
                if not expired_orders:
                    logs.log_info("No expired orders found")
                    break
                
                for order_id, user_id in expired_orders:
                    await db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
                    await log_order_action(order_id, "ORDER_CANCELLED", "Auto-cancelled due to payment timeout")
                    
                    try:
                        await bot.send_message(user_id, get_text(user_id, 'ORDER_CANCELLED', order_id))
                        logs.log_info(f"Order auto-cancelled", user_id=user_id, order_id=order_id)
                    except Exception as e:
                        logs.logger.error(f"Failed to notify user about cancelled order", user_id=user_id, order_id=order_id, details=f"Error: {e}")
                
                await db.commit()
                if expired_orders:
                    logs.log_info(f"Auto-cancelled expired orders", details=f"Count: {len(expired_orders)}")
                break
                
        except aiosqlite.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                logs.log_warning(f"Database locked, retrying", details=f"Delay: {retry_delay}s, Attempt: {attempt + 1}")
                await asyncio.sleep(retry_delay)
            else:
                logs.logger.error(f"Failed to cancel expired orders", details=f"Attempts: {attempt + 1}, Error: {e}")
                break
        except Exception as e:
            logs.logger.error(f"Error in cancel_expired_orders", details=f"Error: {e}")
            break

async def schedule_order_cancellation():
    while True:
        await asyncio.sleep(300)  # Каждые 5 минут
        try:
            await notify_payment_expiration_warning()  # Предупреждения об истечении
            await cancel_expired_orders()  # Обычные заказы
            await cancel_expired_crypto_orders()  # CryptoBot заказы
            await cancel_expired_direct_payments()  # Прямые крипто-платежи
        except Exception as e:
            logs.logger.error(f"Error in order cancellation scheduler", details=f"Error: {e}")

def generate_order_display_id() -> str:
    """Генерирует уникальный ID заказа в формате ORDERID12345678"""
    random_number = random.randint(10000000, 99999999)
    return f"ORDERID{random_number}"

async def apply_promo_code(user_id: int, promo_code: str, order_total: float) -> tuple:
    """Применяет промокод к заказу"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Ищем промокод с discount_percent (не discount!)
            promo = await (await db.execute(
                "SELECT id, discount_percent, usage_limit, used_count, expires_at FROM promo_codes WHERE code = ?",
                (promo_code.upper().strip(),)
            )).fetchone()
            
            if not promo:
                user_lang = USER_LANG.get(user_id, 'ru')
                error_msg = "❌ Invalid promo code" if user_lang == 'en' else "❌ Неверный промокод"
                return False, 0, order_total, error_msg
            
            promo_id, discount_percent, usage_limit, used_count, expires_at = promo
            
            # Проверяем срок действия
            if expires_at:
                try:
                    expires_date = datetime.fromisoformat(expires_at)
                    if expires_date < datetime.now():
                        user_lang = USER_LANG.get(user_id, 'ru')
                        error_msg = "❌ Promo code expired" if user_lang == 'en' else "❌ Промокод истек"
                        return False, 0, order_total, error_msg
                except ValueError as e:
                    logging.error(f"Error parsing expiry date: {e}")
                    user_lang = USER_LANG.get(user_id, 'ru')
                    error_msg = "❌ Promo code date error" if user_lang == 'en' else "❌ Ошибка даты промокода"
                    return False, 0, order_total, error_msg
            
            # Проверяем лимит использований
            if usage_limit is not None and used_count >= usage_limit:
                user_lang = USER_LANG.get(user_id, 'ru')
                error_msg = "❌ Promo code limit reached" if user_lang == 'en' else "❌ Лимит промокода исчерпан"
                return False, 0, order_total, error_msg
            
            # Проверяем, использовал ли уже этот пользователь этот промокод
            used = await (await db.execute(
                "SELECT id FROM used_promo_codes WHERE user_id = ? AND promo_code_id = ?",
                (user_id, promo_id)
            )).fetchone()
            
            if used:
                user_lang = USER_LANG.get(user_id, 'ru')
                error_msg = "❌ You already used this promo code" if user_lang == 'en' else "❌ Вы уже использовали этот промокод"
                return False, 0, order_total, error_msg
            
            # Рассчитываем скидку
            discount_amount = order_total * discount_percent / 100
            final_price = order_total - discount_amount
            
            # ВНИМАНИЕ: НЕ обновляем счетчик использований здесь!
            # Это будет сделано только при успешном создании заказа
            
            user_lang = USER_LANG.get(user_id, 'ru')
            if user_lang == 'en':
                message = f"✅ Promo code applied! Discount: {discount_percent}%"
            else:
                message = f"✅ Промокод применен! Скидка: {discount_percent}%"
            
            return True, discount_percent, final_price, message
            
    except Exception as e:
        logging.error(f"Error applying promo code: {e}")
        user_lang = USER_LANG.get(user_id, 'ru')
        error_message = "❌ Error applying promo code" if user_lang == 'en' else "❌ Ошибка применения промокода"
        return False, 0, order_total, error_message

async def mark_promo_code_used(user_id: int, promo_code: str, order_id: int):
    """Помечает промокод как использованный"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            await db.execute(
                "UPDATE promo_codes SET used_count = used_count + 1 WHERE code = ?",
                (promo_code,)
            )
            await db.commit()
            logger.info(f"Promo code {promo_code} marked as used by user {user_id} for order {order_id}")
    except Exception as e:
        logger.error(f"Error marking promo code as used: {e}")


async def send_main_menu(message: types.Message, user_id: int):
    from config import BOT_STATUS  # Импортируем глобальную переменную
    
    await log_user_action(user_id, "view_main_menu", "Просмотр главного меню", "main_menu")
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(get_text(user_id, 'CATEGORIES_BTN'), callback_data="show_cities"),
        types.InlineKeyboardButton(get_text(user_id, 'INFO_BTN'), callback_data="info"),
    )
    kb.add(types.InlineKeyboardButton(get_text(user_id, 'PROFILE_BTN'), callback_data="profile"))
    if user_id in ADMIN_IDS:
        kb.add(types.InlineKeyboardButton(get_text(user_id, 'ADMIN_PANEL_BTN'), callback_data="request_admin"))
    
    lang = USER_LANG.get(user_id, 'ru')
    
    # Определяем статус для отображения на нужном языке
    if lang == 'en':
        if BOT_STATUS == "ворк":
            status_display = "🟢 WORKING"
        else:
            status_display = "🔴 STOP"
    else:
        if BOT_STATUS == "ворк":
            status_display = "🟢 РАБОТАЕТ"
        else:
            status_display = "🔴 ТЕХ. РАБОТЫ"
    
    if lang == 'en':
        caption = f"""🏰 <b>Cultural House SHOP</b>
        
Status: {status_display}

Welcome to the world of quality relaxation!

✨ <b>Main Menu</b> ✨

Here every category is a new mood. Choose what suits you today:

• 🎯 For an energetic evening
• 🌙 For a calm night  
• 💫 For creative inspiration
• 🎪 For a special occasion

👇 Choose a category below and discover new dimensions of pleasure!"""
    else:
        caption = f"""🏰 <b>Cultural House SHOP</b>
        
Статус: {status_display}

Добро пожаловать в мир качественного отдыха! 

✨ <b>Главное меню</b> ✨

Здесь каждая категория — это новое настроение. Выбирайте то, что подходит именно вам сегодня:

• 🎯 Для энергичного вечера
• 🌙 Для спокойной ночи  
• 💫 Для творческого вдохновения
• 🎪 Для особого случая

👇 Выбирайте категорию ниже и откройте новые грани удовольствия!"""
    
    try:
        with open(WELCOME_PHOTO_PATH, 'rb') as photo:
            await message.answer_photo(
                photo=photo,
                caption=caption,
                reply_markup=kb,
                parse_mode="HTML"
            )
    except Exception as e:
        logging.error(f"Photo error: {e}, sending text instead.")
        await message.answer(
            caption,
            reply_markup=kb,
            parse_mode="HTML"
        )

async def show_language_selection(message: types.Message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(get_text(message.from_user.id, 'RUSSIAN_BTN'), callback_data="lang_ru"),
        types.InlineKeyboardButton(get_text(message.from_user.id, 'ENGLISH_BTN'), callback_data="lang_en")
    )
    await message.answer(get_text(message.from_user.id, 'CHOOSE_LANGUAGE'), reply_markup=kb)

async def show_subscription_required(message: types.Message):
    user_id = message.from_user.id
    user_lang = USER_LANG.get(user_id, 'ru')
    
    keyboard = await create_subscription_keyboard(user_id)
    text = get_subscription_message(user_id)
    
    try:
        await message.delete()
    except:
        pass
        
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await UserSetup.waiting_for_subscription.set()

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    # Завершаем текущее состояние если оно есть
    await state.finish()
    
    if message.text and message.text.startswith('/start draw_ref_'):
        await draw.process_referral_start(message)
        return
    
    await log_user_action(message.from_user.id, "bot_start", "Запуск бота", "start")
    
    async with aiosqlite.connect('shop.db') as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, username) VALUES(?,?)", 
            (message.from_user.id, message.from_user.username)
        )
        await db.execute(
            "UPDATE users SET username=?, last_active=CURRENT_TIMESTAMP WHERE user_id=?", 
            (message.from_user.username, message.from_user.id)
        )
        await db.commit()
        
        row = await (await db.execute(
            "SELECT lang, subscribed FROM users WHERE user_id=?", (message.from_user.id,)
        )).fetchone()
    
    if row and row[0]:
        USER_LANG[message.from_user.id] = row[0]
    
    # Проверяем реальную подписку на канал
    is_subscribed = await check_subscription(message.from_user.id)
    
    if row and row[0] and is_subscribed:
        # Обновляем статус подписки в БД
        await save_user_subscription(message.from_user.id)
        await send_main_menu(message, message.from_user.id)
    elif row and row[0]:
        await show_subscription_required(message)
    else:
        await show_language_selection(message)
        await UserSetup.waiting_for_language.set()

@dp.callback_query_handler(lambda c: c.data.startswith("lang_"), state=UserSetup.waiting_for_language)
async def choose_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_",1)[1]
    USER_LANG[callback.from_user.id] = lang
    
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, callback.from_user.id))
        await db.commit()
    
    lang_name = "Русский" if lang == 'ru' else "English"
    
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.message.answer(get_text(callback.from_user.id, 'LANGUAGE_CHANGED', lang_name))
    
    if lang == 'en':
        await show_english_subscription(callback.message)
    else:
        await show_russian_subscription(callback.message)
    
    await callback.answer()

async def show_english_subscription(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    keyboard.add(InlineKeyboardButton(
        text="📢 Our main channel", 
        url="https://t.me/+eWvldlBJGeAzNTJk"
    ))
    
    keyboard.add(InlineKeyboardButton(
        text="✅ I subscribed", 
        callback_data="check_subscription"
    ))
    
    text = (
        "🔒 <b>Access Restricted</b>\n\n"
        "To use the bot you need to subscribe to our channel:\n\n"
        "👇 Subscribe to the channels below and click the «I subscribed» button"
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await UserSetup.waiting_for_subscription.set()

async def show_russian_subscription(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    keyboard.add(InlineKeyboardButton(
        text="📢 Наш главный канал", 
        url="https://t.me/+eWvldlBJGeAzNTJk"
    ))
    
    keyboard.add(InlineKeyboardButton(
        text="✅ Я подписался", 
        callback_data="check_subscription"
    ))
    
    text = (
        "🔒 <b>Доступ ограничен</b>\n\n"
        "Для использования бота нужно подписаться на наш канал:\n\n"
        "👇 Подпишитесь на каналы ниже и нажмите кнопку «Я подписался»"
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await UserSetup.waiting_for_subscription.set()

@dp.callback_query_handler(lambda c: c.data == "check_subscription", state=UserSetup.waiting_for_subscription)
async def check_subscription_callback(callback: types.CallbackQuery, state: FSMContext):
    if await check_subscription(callback.from_user.id):
        await save_user_subscription(callback.from_user.id)
        
        lang = USER_LANG.get(callback.from_user.id, 'ru')
        success_text = "✅ Thank you for subscribing! Now you can use the bot." if lang == 'en' else "✅ Спасибо за подписку! Теперь вы можете использовать бота."
        
        await callback.message.answer(success_text)
        await state.finish()
        await send_main_menu(callback.message, callback.from_user.id)
    else:
        lang = USER_LANG.get(callback.from_user.id, 'ru')
        error_text = "❌ You are not subscribed to all required channels. Please subscribe and try again." if lang == 'en' else "❌ Вы не подписаны на все необходимые каналы. Пожалуйста, подпишитесь и попробуйте снова."
        
        await callback.answer(error_text, show_alert=True)
    
    await callback.answer()

@dp.message_handler(commands=['swap'])
async def cmd_swap(message: types.Message):
    await show_language_selection(message)

@dp.callback_query_handler(lambda c: c.data.startswith("lang_"))
async def swap_language_callback(callback: types.CallbackQuery):
    lang = callback.data.split("_",1)[1]
    USER_LANG[callback.from_user.id] = lang
    
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, callback.from_user.id))
        await db.commit()
    
    lang_name = "Русский" if lang == 'ru' else "English"
    
    await callback.message.answer(get_text(callback.from_user.id, 'LANGUAGE_CHANGED', lang_name))
    await send_main_menu(callback.message, callback.from_user.id)
    await callback.answer()

@dp.message_handler(commands=['lang'])
async def cmd_lang(message: types.Message):
    current_lang = USER_LANG.get(message.from_user.id, 'ru')
    lang_name = "Русский" if current_lang == 'ru' else "English"
    await message.answer(get_text(message.from_user.id, 'CURRENT_LANGUAGE', lang_name))

@dp.callback_query_handler(lambda c: c.data=="back_main", state="*")
async def back_main(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.answer()
    
    try:
        await callback.message.delete()
    except Exception as e:
        logs.logger.error(f"Could not delete message", user_id=callback.from_user.id, details=f"Error: {e}")
    
    await send_main_menu(callback.message, callback.from_user.id)

@dp.callback_query_handler(lambda c: c.data == "use_promo", state=Purchase.waiting_for_proof)
async def use_promo_code_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Промокод'"""
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        text = "🎁 <b>Enter promo code:</b>\n\nYou can enter a promo code for a discount."
    else:
        text = "🎁 <b>Введите промокод:</b>\n\nВы можете ввести промокод для получения скидки."
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        get_text(callback.from_user.id, 'BACK_BTN'),
        callback_data="back_without_promo"
    ))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await PromoCode.waiting_for_promo.set()
    await callback.answer()

@dp.message_handler(state=PromoCode.waiting_for_promo)
async def process_promo_code_handler(message: types.Message, state: FSMContext):
    """Обработка введенного промокода перед оплатой"""
    user_lang = USER_LANG.get(message.from_user.id, 'ru')
    promo_code = message.text.strip()
    
    # Получаем данные о покупке из состояния
    data = await state.get_data()
    total_price = data.get('total_price', 0)
    
    if total_price == 0:
        if user_lang == 'en':
            await message.answer("❌ Error: purchase data not found")
        else:
            await message.answer("❌ Ошибка: данные о покупке не найдены")
        await state.finish()
        await Purchase.waiting_for_payment_method.set()
        return
    
    # Применяем промокод
    success, discount_percent, final_price, result_message = await apply_promo_code(
        message.from_user.id, promo_code, total_price
    )
    
    await message.answer(result_message)
    
    if success:
        # Сохраняем промокод в состоянии для дальнейшего использования
        await state.update_data(
            discount_percent=discount_percent,
            final_price=final_price,
            promo_code=promo_code.upper().strip()
        )
        
        # Логируем успешное применение
        logs.logger.info(f"Promo code applied successfully", 
                       user_id=message.from_user.id,
                       details=f"Promo: {promo_code}, Discount: {discount_percent}%, Final price: {final_price}")
        
        # Возвращаемся к выбору способа оплаты с обновленными ценами
        await show_payment_methods_with_promo(message, state, discount_percent, final_price, total_price)
    else:
        # В случае неудачи возвращаем к выбору оплаты БЕЗ скидки
        await state.update_data(
            discount_percent=0,
            final_price=total_price,
            promo_code=None
        )
        await show_payment_methods_with_promo(message, state, 0, total_price, total_price)


async def show_payment_methods_with_promo(message: types.Message, state: FSMContext, discount_percent: int, final_price: float, original_price: float):
    """Показывает способы оплаты после применения промокода"""
    data = await state.get_data()
    user_lang = USER_LANG.get(message.from_user.id, 'ru')
    product_name = data.get('product_name', '')
    quantity = data.get('quantity', 0)
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    payment_methods = []
    
    async with aiosqlite.connect('shop.db') as db:
        payments = await (await db.execute("SELECT card FROM payments WHERE id=1")).fetchone()
        card = payments[0] if payments else None
    
    if card:
        payment_methods.append(("💳 Bank Card" if user_lang == 'en' else "💳 Банковская карта", "payment_card"))
    
    if CRYPTOBOT_AVAILABLE:
        payment_methods.append(("🤖 CryptoBot (Telegram)" if user_lang == 'en' else "🤖 CryptoBot (Telegram)", "payment_cryptobot"))
    
    for text, callback_data in payment_methods:
        kb.add(types.InlineKeyboardButton(text, callback_data=callback_data))
    
    # Кнопка для смены промокода
    kb.add(types.InlineKeyboardButton(
        "✏️ Change promo code" if user_lang == 'en' else "✏️ Изменить промокод", 
        callback_data="use_promo_before_payment"
    ))
    
    # Кнопка "Назад"
    kb.add(types.InlineKeyboardButton(
        get_text(message.from_user.id, 'BACK_BTN'),
        callback_data="back_from_order_confirm"
    ))
    
    if user_lang == 'en':
        text = f"<b>Purchase Confirmation</b>\n\n"
        text += f"🎁 Product: {product_name}\n"
        text += f"⚖️ Quantity: {quantity}g\n"
        
        if discount_percent > 0:
            text += f"💶 Original: {original_price:.2f} €\n"
            text += f"🎁 Discount: {discount_percent}%\n"
            text += f"💶 <b>Final price: {final_price:.2f} €</b>\n\n"
        else:
            text += f"💶 <b>Total: {original_price:.2f} €</b>\n\n"
            
        text += "<b>Choose payment method:</b>"
    else:
        text = f"<b>Подтверждение покупки</b>\n\n"
        text += f"🎁 Товар: {product_name}\n"
        text += f"⚖️ Количество: {quantity}г\n"
        
        if discount_percent > 0:
            text += f"💶 Исходная: {original_price:.2f} €\n"
            text += f"🎁 Скидка: {discount_percent}%\n"
            text += f"💶 <b>Финальная цена: {final_price:.2f} €</b>\n\n"
        else:
            text += f"💶 <b>Сумма: {original_price:.2f} €</b>\n\n"
            
        text += "<b>Выберите способ оплаты:</b>"
    
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await Purchase.waiting_for_payment_method.set()


@dp.callback_query_handler(lambda c: c.data == "back_without_promo", state=PromoCode.waiting_for_promo)
async def back_without_promo_handler(callback: types.CallbackQuery, state: FSMContext):
    """Возврат без ввода промокода"""
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        await callback.message.edit_text("✅ Continuing without promo code.")
    else:
        await callback.message.edit_text("✅ Продолжаем без промокода.")
    
    await state.finish()
    await Purchase.waiting_for_proof.set()
    await callback.answer()


@dp.message_handler(state=PromoCode.waiting_for_promo)
async def process_promo_code(message: types.Message, state: FSMContext):
    user_lang = USER_LANG.get(message.from_user.id, 'ru')
    promo_code = message.text.strip()
    
    # Получаем данные из состояния
    data = await state.get_data()
    order_id = data.get('order_id')
    original_price = data.get('original_price')
    
    if not order_id:
        if user_lang == 'en':
            await message.answer("❌ No active order to apply promo code")
        else:
            await message.answer("❌ Нет активного заказа для применения промокода")
        await state.finish()
        await Purchase.waiting_for_proof.set()
        return
    
    success, discount_percent, final_price, result_message = await apply_promo_code(
        message.from_user.id, promo_code, original_price
    )
    
    await message.answer(result_message)

    if success:
        # Сохраняем скидку в состоянии для использования в CryptoBot
        await state.update_data(
            discount_percent=discount_percent,
            final_price=final_price
        )
        
        # Обновляем заказ в базе
        async with aiosqlite.connect('shop.db') as db:
            await db.execute(
                "UPDATE orders SET discount_percent=?, final_price=? WHERE id=?", 
                (discount_percent, final_price, order_id)
            )
            await db.commit()
        
        await log_order_action(order_id, "PROMO_APPLIED", f"Discount: {discount_percent}%")
        
        async with aiosqlite.connect('shop.db') as db:
            order_info = await (await db.execute(
                "SELECT product_id, quantity FROM orders WHERE id=?", (order_id,)
            )).fetchone()
            
            if order_info:
                product_id, quantity = order_info
                product_info = await (await db.execute(
                    "SELECT name FROM products WHERE id=?", (product_id,)
                )).fetchone()
                
                if product_info:
                    product_name = product_info[0]
                    
                    if user_lang == 'en':
                        text = f"✅ <b>Promo code applied!</b>\n\n"
                        text += f"🎁 Product: {product_name}\n"
                        text += f"⚖️ Quantity: {quantity}g\n"
                        text += f"💶 Original price: {original_price:.2f} €\n"
                        text += f"🎁 Discount: {discount_percent}%\n"
                        text += f"💶 <b>Final price: {final_price:.2f} €</b>\n\n"
                        text += "⏳ Now send payment screenshot for confirmation."
                    else:
                        text = f"✅ <b>Промокод применен!</b>\n\n"
                        text += f"🎁 Товар: {product_name}\n"
                        text += f"⚖️ Количество: {quantity}г\n"
                        text += f"💶 Исходная цена: {original_price:.2f} €\n"
                        text += f"🎁 Скидка: {discount_percent}%\n"
                        text += f"💶 <b>Финальная цена: {final_price:.2f} €</b>\n\n"
                        text += "⏳ Теперь отправьте скриншот оплаты для подтверждения."
                    
                    await message.answer(text, parse_mode="HTML")
    
    await state.finish()
    await Purchase.waiting_for_proof.set()


@dp.callback_query_handler(lambda c: c.data=="profile", state="*")
async def show_profile(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await show_subscription_required(callback.message)
        await callback.answer()
        return
    
    await state.finish()
    
    await log_user_action(callback.from_user.id, "view_profile", "Просмотр профиля", "profile")
    
    async with aiosqlite.connect('shop.db') as db:
        order_count = (await (await db.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id=? AND status='completed'", 
            (callback.from_user.id,)
        )).fetchone())[0]
        
        cities = await (await db.execute("""
            SELECT c.name, COUNT(*) as order_count 
            FROM orders o 
            JOIN cities c ON o.city_id = c.id 
            WHERE o.user_id=? AND o.status='completed' 
            GROUP BY c.name 
            ORDER BY order_count DESC 
            LIMIT 3
        """, (callback.from_user.id,))).fetchall()
        
        last_week_orders = (await (await db.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id=? AND status='completed' AND created_at > datetime('now', '-7 days')",
            (callback.from_user.id,)
        )).fetchone())[0]
        
        total_spent = (await (await db.execute(
            "SELECT COALESCE(SUM(final_price), 0) FROM orders WHERE user_id=? AND status='completed'",
            (callback.from_user.id,)
        )).fetchone())[0] or 0
        
        user_info = await (await db.execute(
            "SELECT username, created_at, last_active, lang FROM users WHERE user_id=?",
            (callback.from_user.id,)
        )).fetchone()
        
        weekday_stats = await (await db.execute("""
            SELECT strftime('%w', created_at) as weekday, COUNT(*) as order_count 
            FROM orders 
            WHERE user_id=? AND status='completed' 
            GROUP BY weekday 
            ORDER BY order_count DESC
        """, (callback.from_user.id,))).fetchall()
        
        favorite_products = await (await db.execute("""
            SELECT p.name, COUNT(*) as order_count 
            FROM orders o 
            JOIN products p ON o.product_id = p.id 
            WHERE o.user_id=? AND o.status='completed' 
            GROUP BY p.name 
            ORDER BY order_count DESC 
            LIMIT 3
        """, (callback.from_user.id,))).fetchall()
    
    rank = get_user_rank(order_count, callback.from_user.id)
    
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        text = f"{get_text(callback.from_user.id, 'PROFILE_TITLE')}\n\n"
        text += f"{get_text(callback.from_user.id, 'USER_ID', callback.from_user.id)}\n"
        text += f"{get_text(callback.from_user.id, 'ORDERS_COUNT', order_count)}\n"
        text += f"{get_text(callback.from_user.id, 'USER_RANK', rank)}\n\n"
        
        text += "💰 <b>Finance:</b>\n"
        text += f"• Total spent: {total_spent:.2f} €\n"
        text += f"• Orders this week: {last_week_orders}\n\n"
        
        if user_info:
            username, created_at, last_active, user_lang_db = user_info
            if username:
                text += f"👤 <b>Information:</b>\n"
                text += f"• Username: @{username}\n"
                text += f"• Language: {'🇷🇺 Russian' if user_lang_db == 'ru' else '🇬🇧 English'}\n"
                text += f"• With us since: {created_at.split()[0]}\n"
                text += f"• Last activity: {last_active.split()[0]}\n\n"
        
        if cities:
            text += "🏙️ <b>Order geography:</b>\n"
            for city_name, city_orders in cities:
                text += f"• {city_name}: {city_orders} orders\n"
            text += "\n"
        
        if favorite_products:
            text += "🎁 <b>Favorite products:</b>\n"
            for product_name, product_orders in favorite_products:
                text += f"• {product_name}: {product_orders} times\n"
            text += "\n"
        
        if weekday_stats:
            weekday_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            text += "📅 <b>Activity by day:</b>\n"
            for weekday_num, weekday_orders in weekday_stats:
                weekday_name = weekday_names[int(weekday_num)]
                text += f"• {weekday_name}: {weekday_orders} orders\n"
    else:
        text = f"{get_text(callback.from_user.id, 'PROFILE_TITLE')}\n\n"
        text += f"{get_text(callback.from_user.id, 'USER_ID', callback.from_user.id)}\n"
        text += f"{get_text(callback.from_user.id, 'ORDERS_COUNT', order_count)}\n"
        text += f"{get_text(callback.from_user.id, 'USER_RANK', rank)}\n\n"
        
        text += "💰 <b>Финансы:</b>\n"
        text += f"• Всего потрачено: {total_spent:.2f} €\n"
        text += f"• Заказов за неделю: {last_week_orders}\n\n"
        
        if user_info:
            username, created_at, last_active, user_lang_db = user_info
            if username:
                text += f"👤 <b>Информация:</b>\n"
                text += f"• Username: @{username}\n"
                text += f"• Язык: {'🇷🇺 Русский' if user_lang_db == 'ru' else '🇬🇧 English'}\n"
                text += f"• В боте с: {created_at.split()[0]}\n"
                text += f"• Последняя активность: {last_active.split()[0]}\n\n"
        
        if cities:
            text += "🏙️ <b>География заказов:</b>\n"
            for city_name, city_orders in cities:
                text += f"• {city_name}: {city_orders} зак.\n"
            text += "\n"
        
        if favorite_products:
            text += "🎁 <b>Любимые товары:</b>\n"
            for product_name, product_orders in favorite_products:
                text += f"• {product_name}: {product_orders} раз\n"
            text += "\n"
        
        if weekday_stats:
            weekday_names = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
            text += "📅 <b>Активность по дням:</b>\n"
            for weekday_num, weekday_orders in weekday_stats:
                weekday_name = weekday_names[int(weekday_num)]
                text += f"• {weekday_name}: {weekday_orders} зак.\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопка отзывов
    if user_lang == 'en':
        kb.add(types.InlineKeyboardButton("⭐ My Reviews", callback_data="my_reviews"))
    else:
        kb.add(types.InlineKeyboardButton("⭐ Мои отзывы", callback_data="my_reviews"))
    
    kb.add(
        types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data="back_main")
    )
    
    await safe_edit_message(callback, text, reply_markup=kb, parse_mode="HTML", photo_path=PROFILE_PHOTO_PATH)
    await callback.answer()


# ══════════════════════════════════════════════════════════════
# СИСТЕМА ОТЗЫВОВ
# ══════════════════════════════════════════════════════════════

@dp.callback_query_handler(lambda c: c.data == "my_reviews", state="*")
async def show_my_reviews(callback: types.CallbackQuery, state: FSMContext):
    """Показывает список заказов для оставления отзывов"""
    await state.finish()
    user_id = callback.from_user.id
    user_lang = USER_LANG.get(user_id, 'ru')
    
    async with aiosqlite.connect('shop.db') as db:
        # Получаем завершенные заказы без отзывов
        orders_without_reviews = await (await db.execute("""
            SELECT o.id, o.product_name, o.final_price, o.created_at
            FROM orders o
            LEFT JOIN reviews r ON r.order_id = o.id
            WHERE o.user_id = ? AND o.status = 'completed' AND r.id IS NULL
            ORDER BY o.created_at DESC
            LIMIT 10
        """, (user_id,))).fetchall()
        
        # Получаем оставленные отзывы
        existing_reviews = await (await db.execute("""
            SELECT r.order_id, r.product_name, r.rating, r.review_text, r.created_at
            FROM reviews r
            WHERE r.user_id = ?
            ORDER BY r.created_at DESC
            LIMIT 5
        """, (user_id,))).fetchall()
    
    if user_lang == 'en':
        text = "⭐ <b>MY REVIEWS</b>\n\n"
        
        if existing_reviews:
            text += "📝 <b>Your reviews:</b>\n\n"
            for order_id, product_name, rating, review_text, created_at in existing_reviews:
                stars = "⭐" * (rating or 5)
                text += f"#{order_id} • {product_name}\n"
                text += f"{stars}\n"
                text += f"💬 {review_text[:100]}...\n"
                text += f"📅 {created_at.split()[0]}\n\n"
        
        if orders_without_reviews:
            text += "📦 <b>Leave review for:</b>\n\n"
        else:
            if not existing_reviews:
                text += "You have no completed orders yet.\n"
                text += "Complete an order to leave a review!"
            else:
                text += "✅ You've reviewed all your orders!"
    else:
        text = "⭐ <b>МОИ ОТЗЫВЫ</b>\n\n"
        
        if existing_reviews:
            text += "📝 <b>Ваши отзывы:</b>\n\n"
            for order_id, product_name, rating, review_text, created_at in existing_reviews:
                stars = "⭐" * (rating or 5)
                text += f"#{order_id} • {product_name}\n"
                text += f"{stars}\n"
                text += f"💬 {review_text[:100]}...\n"
                text += f"📅 {created_at.split()[0]}\n\n"
        
        if orders_without_reviews:
            text += "📦 <b>Оставить отзыв на:</b>\n\n"
        else:
            if not existing_reviews:
                text += "У вас пока нет завершенных заказов.\n"
                text += "Оформите заказ, чтобы оставить отзыв!"
            else:
                text += "✅ Вы оставили отзывы на все заказы!"
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Добавляем кнопки для заказов без отзывов
    for order_id, product_name, final_price, created_at in orders_without_reviews:
        btn_text = f"#{order_id} • {product_name} • {final_price}€"
        kb.add(InlineKeyboardButton(btn_text, callback_data=f"review_order_{order_id}"))
    
    back_text = "◀️ Back" if user_lang == 'en' else "◀️ Назад"
    kb.add(InlineKeyboardButton(back_text, callback_data="profile"))
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        # Если не удалось отредактировать (например, было фото), удаляем и отправляем новое
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("review_order_"), state="*")
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс оставления отзыва"""
    order_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    user_lang = USER_LANG.get(user_id, 'ru')
    
    # Проверяем что заказ принадлежит пользователю и завершен
    async with aiosqlite.connect('shop.db') as db:
        order = await (await db.execute("""
            SELECT product_name, final_price
            FROM orders
            WHERE id = ? AND user_id = ? AND status = 'completed'
        """, (order_id, user_id))).fetchone()
    
    if not order:
        error_text = "❌ Order not found" if user_lang == 'en' else "❌ Заказ не найден"
        await callback.answer(error_text, show_alert=True)
        return
    
    product_name, final_price = order
    
    if user_lang == 'en':
        text = f"📝 <b>LEAVE REVIEW</b>\n\n"
        text += f"Order: #{order_id}\n"
        text += f"Product: {product_name}\n"
        text += f"Amount: {final_price}€\n\n"
        text += "✍️ Write your review:\n"
        text += "Share your experience with this product!"
    else:
        text = f"📝 <b>ОСТАВИТЬ ОТЗЫВ</b>\n\n"
        text += f"Заказ: #{order_id}\n"
        text += f"Товар: {product_name}\n"
        text += f"Сумма: {final_price}€\n\n"
        text += "✍️ Напишите ваш отзыв:\n"
        text += "Поделитесь впечатлениями о товаре!"
    
    kb = InlineKeyboardMarkup()
    cancel_text = "❌ Cancel" if user_lang == 'en' else "❌ Отмена"
    kb.add(InlineKeyboardButton(cancel_text, callback_data="my_reviews"))
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await ReviewStates.waiting_for_review_text.set()
    await state.update_data(order_id=order_id, product_name=product_name)
    await callback.answer()


@dp.message_handler(state=ReviewStates.waiting_for_review_text)
async def process_review_text(message: types.Message, state: FSMContext):
    """Обрабатывает текст отзыва"""
    user_id = message.from_user.id
    user_lang = USER_LANG.get(user_id, 'ru')
    review_text = message.text.strip()
    
    if len(review_text) < 10:
        error_text = "❌ Review is too short. Minimum 10 characters." if user_lang == 'en' else "❌ Отзыв слишком короткий. Минимум 10 символов."
        await message.answer(error_text)
        return
    
    if len(review_text) > 1000:
        error_text = "❌ Review is too long. Maximum 1000 characters." if user_lang == 'en' else "❌ Отзыв слишком длинный. Максимум 1000 символов."
        await message.answer(error_text)
        return
    
    data = await state.get_data()
    order_id = data['order_id']
    product_name = data['product_name']
    username = message.from_user.username or message.from_user.first_name
    
    # Сохраняем отзыв в БД
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("""
            INSERT INTO reviews (order_id, user_id, username, product_name, rating, review_text)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, user_id, username, product_name, 5, review_text))
        await db.commit()
    
    # Отправляем отзыв в админ-чат
    try:
        admin_text = f"⭐ <b>НОВЫЙ ОТЗЫВ</b>\n\n"
        admin_text += f"👤 От: @{username} (ID: {user_id})\n"
        admin_text += f"📦 Заказ: #{order_id}\n"
        admin_text += f"🎁 Товар: {product_name}\n\n"
        admin_text += f"💬 <b>Отзыв:</b>\n{review_text}\n\n"
        admin_text += f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        await bot.send_message(LOG_CHAT_ID, admin_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send review to admin chat: {e}")
    
    # Уведомление пользователю
    if user_lang == 'en':
        success_text = "✅ <b>Thank you for your review!</b>\n\n"
        success_text += "Your feedback helps us improve our service."
    else:
        success_text = "✅ <b>Спасибо за ваш отзыв!</b>\n\n"
        success_text += "Ваш отзыв поможет нам улучшить сервис."
    
    kb = InlineKeyboardMarkup()
    back_text = "◀️ To Profile" if user_lang == 'en' else "◀️ В профиль"
    main_text = "🏠 Main Menu" if user_lang == 'en' else "🏠 Главное меню"
    kb.add(InlineKeyboardButton(back_text, callback_data="profile"))
    kb.add(InlineKeyboardButton(main_text, callback_data="back_main"))
    
    await message.answer(success_text, reply_markup=kb, parse_mode="HTML")
    await state.finish()


async def _process_admin_pw(msg: types.Message, state: FSMContext):
    await ap.process_admin_password(msg, state)

dp.register_callback_query_handler(
    ap.request_admin_panel,
    lambda c: c.data=="request_admin",
    state="*"
)
dp.register_message_handler(ap.admin_command, commands=['admin'])
dp.register_message_handler(
    _process_admin_pw,
    state=ap.AdminAuth.waiting_for_password
)

dp.register_callback_query_handler(ap.cancel_action,
    lambda c: c.data=="cancel_action", state="*")
dp.register_callback_query_handler(ap.exit_admin_panel,
    lambda c: c.data=="exit_admin", state="*")

dp.register_callback_query_handler(ap.add_category_start,
    lambda c: c.data=="add_category", state="*")
dp.register_message_handler(ap.add_category_name,
    state=ap.AddCategory.waiting_for_category_name)
dp.register_callback_query_handler(ap.delete_category_start,
    lambda c: c.data=="delete_category", state="*")
dp.register_callback_query_handler(ap.confirm_delete_category,
    lambda c: c.data.startswith("delcat_sel_"), state="*")
dp.register_callback_query_handler(ap.execute_delete_category,
    lambda c: c.data=="delcat_conf", state=ap.DeleteCategory.waiting_for_confirmation)

dp.register_callback_query_handler(ap.add_city_start,
    lambda c: c.data=="add_city", state="*")
dp.register_message_handler(ap.add_city_name,
    state=ap.AddCity.waiting_for_city_name)
dp.register_callback_query_handler(ap.delete_city_start,
    lambda c: c.data=="delete_city", state="*")
dp.register_callback_query_handler(ap.confirm_delete_city,
    lambda c: c.data.startswith("delcity_sel_"), state="*")
dp.register_callback_query_handler(ap.execute_delete_city,
    lambda c: c.data=="delcity_conf", state=ap.DeleteCity.waiting_for_confirmation)
dp.register_callback_query_handler(ap.add_district_start,
    lambda c: c.data=="add_district", state="*")
dp.register_callback_query_handler(ap.select_city_for_district,
    lambda c: c.data.startswith("distcity_sel_"), state="*")
dp.register_message_handler(ap.add_district_name,
    state=ap.AddDistrict.waiting_for_district_name)

dp.register_callback_query_handler(ap.add_product_start,
    lambda c: c.data=="add_product", state="*")
dp.register_callback_query_handler(ap.select_category_for_product,
    lambda c: c.data.startswith("prodcat_sel_"), state="*")
dp.register_message_handler(ap.add_product_name,
    state=ap.AddProduct.waiting_for_name)
dp.register_message_handler(ap.add_product_price,
   state=ap.AddProduct.waiting_for_price)
dp.register_message_handler(ap.add_product_description,
    state=ap.AddProduct.waiting_for_description)
dp.register_message_handler(ap.add_product_media,
    content_types=['photo', 'video'], state=ap.AddProduct.waiting_for_media)
dp.register_callback_query_handler(ap.delete_product_start,
    lambda c: c.data=="delete_product", state="*")
dp.register_callback_query_handler(ap.confirm_delete_product,
    lambda c: c.data.startswith("delprod_sel_"), state="*")
dp.register_callback_query_handler(ap.execute_delete_product,
    lambda c: c.data=="delprod_conf", state=ap.DeleteProduct.waiting_for_confirmation)

dp.register_callback_query_handler(ap.edit_payments_start,
    lambda c: c.data=="edit_payments", state="*")
dp.register_callback_query_handler(ap.edit_usdt_start,
    lambda c: c.data=="edit_usdt", state="*")
dp.register_callback_query_handler(ap.edit_btc_start,
    lambda c: c.data=="edit_btc", state="*")
dp.register_callback_query_handler(ap.edit_card_start,
    lambda c: c.data=="edit_card", state="*")
dp.register_message_handler(ap.set_usdt,
    state=ap.EditPayments.waiting_for_usdt)
dp.register_message_handler(ap.set_btc,
    state=ap.EditPayments.waiting_for_btc)
dp.register_message_handler(ap.set_card,
    state=ap.EditPayments.waiting_for_card)

# Крипто-кошельки (прямая оплата USDT TRC20)
dp.register_callback_query_handler(ap.edit_crypto_wallets_start,
    lambda c: c.data=="edit_crypto_wallets", state="*")
dp.register_callback_query_handler(ap.edit_usdt_wallet_start,
    lambda c: c.data=="edit_usdt_wallet", state="*")
dp.register_callback_query_handler(ap.edit_trongrid_api_start,
    lambda c: c.data=="edit_trongrid_api", state="*")
# Крипто-кошельки (прямая оплата)
dp.register_callback_query_handler(ap.edit_crypto_wallets_start,
    lambda c: c.data=="edit_crypto_wallets", state="*")

# Регистрация обработчиков для каждой криптовалюты
import crypto_admin
crypto_admin.init(bot)
for crypto in ['usdt', 'btc', 'eth', 'ton', 'sol', 'trx', 'ltc', 'usdc_bep20', 'bnb']:
    dp.register_callback_query_handler(
        lambda c, cr=crypto: crypto_admin.show_wallet_settings(c, cr),
        lambda c, cr=crypto: c.data == f"edit_wallet_{cr}",
        state="*"
    )
    dp.register_callback_query_handler(
        lambda c, state, cr=crypto: crypto_admin.request_wallet_address(c, cr, state),
        lambda c, cr=crypto: c.data == f"set_wallet_{cr}",
        state="*"
    )
    dp.register_callback_query_handler(
        lambda c, state, cr=crypto: crypto_admin.request_api_key(c, cr, state),
        lambda c, cr=crypto: c.data == f"set_api_{cr}",
        state="*"
    )
    # Статистика
    dp.register_callback_query_handler(
        lambda c, cr=crypto: crypto_admin.show_crypto_stats(c, cr),
        lambda c, cr=crypto: c.data == f"crypto_stats_{cr}",
        state="*"
    )
    # Проверка API
    dp.register_callback_query_handler(
        lambda c, cr=crypto: crypto_admin.test_crypto_api(c, cr),
        lambda c, cr=crypto: c.data == f"test_api_{cr}",
        state="*"
    )

dp.register_message_handler(
    crypto_admin.save_wallet_address,
    state=crypto_admin.EditCryptoWallet.waiting_for_wallet
)
dp.register_message_handler(
    crypto_admin.save_api_key,
    state=crypto_admin.EditCryptoWallet.waiting_for_api_key
)

dp.register_callback_query_handler(
    ap.broadcast_start,
    lambda c: c.data == "broadcast",
    state="*"
)
dp.register_message_handler(
    ap.broadcast_content,
    content_types=['text','photo','video'],
    state=ap.Broadcast.waiting_for_content
)
dp.register_callback_query_handler(
    ap.broadcast_confirm,
    lambda c: c.data == "broadcast_yes",
    state=ap.Broadcast.waiting_for_confirm
)

dp.register_callback_query_handler(ap.ban_start,
    lambda c: c.data=="ban_user", state="*")
dp.register_message_handler(ap.ban_enter_id,
    state=ap.BanUser.waiting_for_id)
dp.register_callback_query_handler(ap.unban_start,
    lambda c: c.data=="unban_user", state="*")
dp.register_message_handler(ap.unban_enter_id,
    state=ap.UnbanUser.waiting_for_id)
dp.register_callback_query_handler(ap.view_user_details,
    lambda c: c.data.startswith("user_detail_"), state="*")
dp.register_callback_query_handler(ap.ban_user_from_details,
    lambda c: c.data.startswith("ban_detail_"), state="*")
dp.register_callback_query_handler(ap.unban_user_from_details,
    lambda c: c.data.startswith("unban_detail_"), state="*")

dp.register_callback_query_handler(ap.view_orders_start,
    lambda c: c.data == "view_orders", state="*")
dp.register_callback_query_handler(ap.view_order_details,
    lambda c: c.data.startswith("order_detail_"), state="*")
dp.register_callback_query_handler(ap.view_user_orders,
    lambda c: c.data.startswith("user_orders_"), state="*")
dp.register_callback_query_handler(ap.change_order_status,
    lambda c: c.data.startswith("complete_order_") or 
              c.data.startswith("reject_order_") or 
              c.data.startswith("pending_order_"), state="*")

dp.register_callback_query_handler(ap.edit_stock_start,
    lambda c: c.data=="edit_stock", state="*")
dp.register_callback_query_handler(ap.select_product_for_stock,
    lambda c: c.data.startswith("stock_sel_"), state=ap.EditStock.waiting_for_product)
dp.register_message_handler(ap.set_product_stock,
    state=ap.EditStock.waiting_for_stock)

dp.register_callback_query_handler(ap.show_stats,
    lambda c: c.data.startswith("stats_"), state="*")

dp.register_callback_query_handler(ap.manage_promos_start,
    lambda c: c.data=="manage_promos", state="*")
dp.register_callback_query_handler(ap.add_promo_start,
    lambda c: c.data=="add_promo", state="*")
dp.register_message_handler(ap.add_promo_code,
    state=ap.AddPromoCode.waiting_for_code)
dp.register_message_handler(ap.add_promo_discount,
    state=ap.AddPromoCode.waiting_for_discount)
dp.register_message_handler(ap.add_promo_limit,
    state=ap.AddPromoCode.waiting_for_limit)
dp.register_message_handler(ap.add_promo_expiry,
    state=ap.AddPromoCode.waiting_for_expiry)
dp.register_callback_query_handler(ap.delete_promo_start,
    lambda c: c.data=="delete_promo", state="*")
dp.register_callback_query_handler(ap.confirm_delete_promo,
    lambda c: c.data.startswith("delpromo_sel_"), state="*")
dp.register_callback_query_handler(ap.execute_delete_promo,
    lambda c: c.data=="delpromo_conf", state=ap.DeletePromoCode.waiting_for_confirmation)
dp.register_callback_query_handler(ap.list_promos,
    lambda c: c.data == "list_promos", state="*")
dp.register_callback_query_handler(confirm_auto_point, lambda c: c.data == "confirm_auto_point", state=AutoDelivery.waiting_for_quantity)


dp.register_callback_query_handler(ap.auto_delivery_start,
    lambda c: c.data == "auto_delivery", state="*")
dp.register_callback_query_handler(ap.add_auto_point_start,
    lambda c: c.data == "add_auto_point", state="*")
dp.register_callback_query_handler(ap.select_city_for_auto,
    lambda c: c.data.startswith("autocity_sel_"), state=ap.AutoDelivery.waiting_for_city)
dp.register_callback_query_handler(ap.select_district_for_auto,
    lambda c: c.data.startswith("autodist_sel_"), state=ap.AutoDelivery.waiting_for_district)
dp.register_message_handler(ap.add_auto_photo,
    content_types=['photo'], state=ap.AutoDelivery.waiting_for_photo)
dp.register_message_handler(ap.add_auto_description,
    state=ap.AutoDelivery.waiting_for_description)
dp.register_callback_query_handler(ap.list_auto_points,
    lambda c: c.data == "list_auto_points", state="*")
dp.register_callback_query_handler(ap.delete_auto_point_start,
    lambda c: c.data == "delete_auto_point", state="*")
dp.register_callback_query_handler(ap.confirm_delete_auto_point,
    lambda c: c.data.startswith("delauto_sel_"), state="*")
dp.register_callback_query_handler(ap.execute_delete_auto_point,
    lambda c: c.data.startswith("delauto_conf_"), state="*")
dp.register_callback_query_handler(ap.skip_auto_photo_handler, lambda c: c.data == "skip_auto_photo", state=ap.AutoDelivery.waiting_for_photo)
dp.register_callback_query_handler(ap.select_unit_for_auto, lambda c: c.data.startswith("unit_"))

dp.register_callback_query_handler(show_users_table, lambda c: c.data == "view_users_table", state="*")
dp.register_callback_query_handler(users_start_search, lambda c: c.data == "users_start_search", state="*")
dp.register_message_handler(process_users_search, state=ViewUsersTable.waiting_for_query)
dp.register_callback_query_handler(users_clear_search, lambda c: c.data == "users_clear_search", state="*")
dp.register_callback_query_handler(users_change_sort, lambda c: c.data.startswith("users_sort_"), state="*")
dp.register_callback_query_handler(users_change_page, lambda c: c.data.startswith("users_page_"), state="*")
dp.register_callback_query_handler(users_show_stats, lambda c: c.data == "users_stats", state="*")
dp.register_callback_query_handler(view_users_table_back, lambda c: c.data == "view_users_table_back", state="*")


dp.register_callback_query_handler(
    draw.show_draw_panel,
    lambda c: c.data == "draw_panel",
    state="*"
)

dp.register_callback_query_handler(
    draw.create_draw_start,
    lambda c: c.data == "create_draw",
    state="*"
)
dp.register_message_handler(
    draw.process_channel_id,
    state=draw.CreateDraw.waiting_for_channel
)
dp.register_message_handler(
    draw.process_draw_title,
    state=draw.CreateDraw.waiting_for_title
)
dp.register_message_handler(
    draw.process_draw_description,
    state=draw.CreateDraw.waiting_for_description
)
dp.register_message_handler(
    draw.process_draw_media,
    content_types=['photo', 'video', 'animation'],
    state=draw.CreateDraw.waiting_for_media
)
dp.register_message_handler(
    draw.process_end_time,
    state=draw.CreateDraw.waiting_for_end_time
)
dp.register_message_handler(
    draw.process_winners_count,
    state=draw.CreateDraw.waiting_for_winners_count
)
dp.register_callback_query_handler(
    draw.process_referral_choice,
    lambda c: c.data in ["referral_yes", "referral_no"],
    state=draw.CreateDraw.waiting_for_referral
)
dp.register_callback_query_handler(
    draw.confirm_and_start_draw,
    lambda c: c.data == "confirm_draw",
    state=draw.CreateDraw.waiting_for_confirm
)

dp.register_callback_query_handler(
    draw.join_draw,
    lambda c: c.data.startswith("join_draw_"),
    state="*"
)

dp.register_message_handler(
    draw.process_referral_start,
    commands=['start'],
    state="*"
)

dp.register_callback_query_handler(
    draw.show_active_draws,
    lambda c: c.data == "active_draws",
    state="*"
)
dp.register_callback_query_handler(
    draw.manage_draw,
    lambda c: c.data.startswith("manage_draw_"),
    state="*"
)

dp.register_callback_query_handler(
    draw.show_draw_stats,
    lambda c: c.data == "draw_stats",
    state="*"
)

dp.register_callback_query_handler(
    draw.show_completed_draws,
    lambda c: c.data == "completed_draws",
    state="*"
)

dp.register_callback_query_handler(
    draw.end_draw_early,
    lambda c: c.data.startswith("end_draw_"),
    state="*"
)

dp.register_callback_query_handler(
    draw.handle_referral_language,
    lambda c: c.data.startswith("ref_lang_"),
    state="*"
)
# Авто-выдача - ОБНОВЛЕННЫЕ ХЭНДЛЕРЫ
dp.register_callback_query_handler(
    ap.show_auto_delivery_panel,
    lambda c: c.data == "auto_delivery_panel",
    state="*"
)
dp.register_callback_query_handler(
    ap.add_auto_point_start,
    lambda c: c.data == "add_auto_point",
    state="*"
)
dp.register_callback_query_handler(
    ap.select_product_for_auto,
    lambda c: c.data.startswith("autoprod_sel_"),
    state=ap.AutoDelivery.waiting_for_product
)
dp.register_callback_query_handler(
    ap.select_city_for_auto,
    lambda c: c.data.startswith("autocity_sel_"),
    state=ap.AutoDelivery.waiting_for_city
)
dp.register_callback_query_handler(
    ap.select_district_for_auto,
    lambda c: c.data.startswith("autodist_sel_"),
    state=ap.AutoDelivery.waiting_for_district
)
dp.register_message_handler(
    ap.add_auto_photo,
    content_types=['photo'],
    state=ap.AutoDelivery.waiting_for_photo
)

dp.register_message_handler(
    ap.add_auto_description,
    state=ap.AutoDelivery.waiting_for_description
)
dp.register_callback_query_handler(
    ap.select_unit_for_auto,
    lambda c: c.data.startswith("unit_"),
    state="*"  # Это новое состояние не определено в AutoDelivery, поэтому используем "*"
)
dp.register_message_handler(
    ap.add_auto_quantity,
    state=ap.AutoDelivery.waiting_for_quantity
)
dp.register_message_handler(
    ap.add_auto_price,
    state=ap.AutoDelivery.waiting_for_price
)
dp.register_callback_query_handler(
    ap.confirm_auto_point,
    lambda c: c.data == "confirm_auto_point",
    state=ap.AutoDelivery.waiting_for_price
)
dp.register_callback_query_handler(
    ap.list_auto_points,
    lambda c: c.data == "list_auto_points",
    state="*"
)
dp.register_callback_query_handler(
    ap.delete_auto_point_start,
    lambda c: c.data == "delete_auto_point",
    state="*"
)
dp.register_callback_query_handler(
    ap.confirm_delete_auto_point,
    lambda c: c.data.startswith("delauto_sel_"),
    state="*"
)
dp.register_callback_query_handler(
    ap.execute_delete_auto_point,
    lambda c: c.data.startswith("delauto_conf_"),
    state="*"
)
dp.register_callback_query_handler(
    ap.skip_auto_photo_handler,
    lambda c: c.data == "skip_auto_photo",
    state=ap.AutoDelivery.waiting_for_photo
)
dp.register_callback_query_handler(
    ap.cancel_action,
    lambda c: c.data == "cancel_action",
    state="*"
)

dp.register_callback_query_handler(
    use_promo_code_handler,
    lambda c: c.data == "use_promo",
    state=Purchase.waiting_for_proof
)

dp.register_message_handler(
    process_promo_code_handler,
    state=PromoCode.waiting_for_promo
)

dp.register_callback_query_handler(
    back_without_promo_handler,
    lambda c: c.data == "back_without_promo",
    state=PromoCode.waiting_for_promo
)

dp.register_callback_query_handler(
        ap.delete_district_start, 
        lambda c: c.data == "delete_district", 
        state="*"
)
    # 2. Выбор города
dp.register_callback_query_handler(
        ap.select_city_for_district_deletion, 
        lambda c: c.data.startswith("deldist_citysel_"), 
        state=ap.DeleteDistrict.waiting_for_city
)
    # 3. Выбор района
dp.register_callback_query_handler(
        ap.confirm_delete_district, 
        lambda c: c.data.startswith("deldist_sel_"), 
        state=ap.DeleteDistrict.waiting_for_district
)
    # 4. Подтверждение удаления
dp.register_callback_query_handler(
        ap.execute_delete_district, 
        lambda c: c.data.startswith("deldist_conf_"), 
        state=ap.DeleteDistrict.waiting_for_confirmation
)





@dp.callback_query_handler(lambda c: c.data=="show_cities", state="*")
async def show_cities(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await show_subscription_required(callback.message)
        await callback.answer()
        return
    
    await state.finish()
    
    await log_user_action(callback.from_user.id, "view_cities", "Просмотр списка городов", "cities")
    
    async with aiosqlite.connect('shop.db') as db:
        rows = await (await db.execute("SELECT id,name FROM cities")).fetchall()
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for cid, nm in rows:
        kb.add(types.InlineKeyboardButton(nm, callback_data=f"city_{cid}"))
    kb.add(types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data="back_main"))
    
    await safe_edit_message(callback, get_text(callback.from_user.id, 'CHOOSE_CITY'), reply_markup=kb, photo_path=CITIES_PHOTO_PATH)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("city_"), state="*")
async def show_districts(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await show_subscription_required(callback.message)
        await callback.answer()
        return
    await state.finish()
    
    cid = int(callback.data.split("_")[1])
    async with aiosqlite.connect('shop.db') as db:
        rows = await (await db.execute(
            "SELECT id,name FROM districts WHERE city_id=?", (cid,)
        )).fetchall()
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    if rows:
        for did, nm in rows:
            kb.add(types.InlineKeyboardButton(nm, callback_data=f"district_{did}"))
        kb.add(types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data="show_cities"))
        await safe_edit_message(callback, get_text(callback.from_user.id, 'CHOOSE_DISTRICT'), reply_markup=kb, photo_path=DISTRICTS_PHOTO_PATH)
    else:
        await show_categories(callback, city_id=cid)

    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("district_"), state="*")
async def show_categories_from_district(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await show_subscription_required(callback.message)
        await callback.answer()
        return
    
    await state.finish()
    
    try:
        district_id = int(callback.data.split("_")[1])
        
        # Получаем city_id из района
        async with aiosqlite.connect('shop.db') as db:
            city_info = await (await db.execute(
                "SELECT city_id FROM districts WHERE id=?", (district_id,)
            )).fetchone()
        
        if city_info:
            city_id = city_info[0]
            await show_categories(callback, city_id=city_id, district_id=district_id)
        else:
            await callback.message.answer("❌ Район не найден, выберите город заново.")
            await show_cities(callback, state)
            
    except Exception as e:
        logging.error(f"Error in show_categories_from_district: {e}", exc_info=True)
        await callback.answer("❌ Ошибка при обработке запроса")

async def show_categories(callback: types.CallbackQuery, city_id=None, district_id=None):
    await log_user_action(callback.from_user.id, "view_categories", "Просмотр категорий товаров", "categories")
    
    # Если не указаны city_id и district_id, пробуем получить из callback_data
    if city_id is None and district_id is None:
        if callback.data.startswith("city_"):
            city_id = int(callback.data.split("_")[1])
        elif callback.data.startswith("district_"):
            district_id = int(callback.data.split("_")[1])
            # Получаем city_id из района
            async with aiosqlite.connect('shop.db') as db:
                city_info = await (await db.execute(
                    "SELECT city_id FROM districts WHERE id=?", (district_id,)
                )).fetchone()
                if city_info:
                    city_id = city_info[0]
    
    if not city_id:
        await callback.message.answer("❌ Город не выбран. Начните сначала.")
        return
    
    # Получаем только те категории, в которых есть товары с доступными точками авто-выдачи
    async with aiosqlite.connect('shop.db') as db:
        query = """
            SELECT DISTINCT c.id, c.name 
            FROM categories c
            INNER JOIN products p ON p.category_id = c.id
            INNER JOIN auto_delivery_points adp ON adp.product_id = p.id
            WHERE adp.city_id = ? 
            AND (adp.district_id = ? OR ? IS NULL)
            AND adp.is_used = 0
            AND adp.is_hidden = 0
            ORDER BY c.name
        """
        categories = await (await db.execute(query, (city_id, district_id, district_id))).fetchall()
        
        if not categories:
            # Получаем названия для информационного сообщения
            city_info = await (await db.execute("SELECT name FROM cities WHERE id=?", (city_id,))).fetchone()
            city_name = city_info[0] if city_info else "Неизвестный город"
            
            if district_id:
                district_info = await (await db.execute("SELECT name FROM districts WHERE id=?", (district_id,))).fetchone()
                district_name = district_info[0] if district_info else "Неизвестный район"
                text = f"❌ В районе '{district_name}' нет доступных товаров с авто-выдачей.\n\n"
                text += f"🏙️ Город: {city_name}\n"
                text += f"🏘️ Район: {district_name}\n\n"
                text += "Пожалуйста, выберите другой район."
            else:
                text = f"❌ В городе '{city_name}' нет доступных товаров с авто-выдачей.\n\n"
                text += f"🏙️ Город: {city_name}\n\n"
                text += "Пожалуйста, выберите другой город."
    
    if not categories:
        kb = types.InlineKeyboardMarkup()
        
        if district_id:
            kb.add(types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data=f"city_{city_id}"))
        else:
            kb.add(types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data="show_cities"))
        
        await safe_edit_message(callback, text, reply_markup=kb)
        await callback.answer()
        return
    
    # Создаем клавиатуру с категориями
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    for cat_id, cat_name in categories:
        # Просто название категории без цифр
        geo_payload = f"d{district_id}" if district_id else f"c{city_id}"
        button_text = f"{cat_name}"
        kb.add(types.InlineKeyboardButton(button_text, callback_data=f"cat_{cat_id}_{geo_payload}"))
    
    # Кнопка назад
    if district_id:
        kb.add(types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data=f"city_{city_id}"))
    elif city_id:
        kb.add(types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data="show_cities"))
    else:
        kb.add(types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data="back_main"))
    
    # Получаем названия для информационного сообщения
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    async with aiosqlite.connect('shop.db') as db:
        city_info = await (await db.execute("SELECT name FROM cities WHERE id=?", (city_id,))).fetchone()
        city_name = city_info[0] if city_info else "Неизвестный город"
        
        if district_id:
            district_info = await (await db.execute("SELECT name FROM districts WHERE id=?", (district_id,))).fetchone()
            district_name = district_info[0] if district_info else "Неизвестный район"
            if user_lang == 'en':
                location_text = f"🏙️ City: {city_name}\n🏘️ District: {district_name}"
            else:
                location_text = f"🏙️ Город: {city_name}\n🏘️ Район: {district_name}"
        else:
            if user_lang == 'en':
                location_text = f"🏙️ City: {city_name}"
            else:
                location_text = f"🏙️ Город: {city_name}"
    
    if user_lang == 'en':
        text = f"📂 <b>Categories</b>\n\n"
        text += f"{location_text}\n\n"
        text += "👇 Select a category:"
    else:
        text = f"📂 <b>Категории</b>\n\n"
        text += f"{location_text}\n\n"
        text += "👇 Выберите категорию:"
    
    await safe_edit_message(callback, text, reply_markup=kb, photo_path=CATEGORIES_PHOTO_PATH)
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("cat_"), state="*")
async def show_products(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await show_subscription_required(callback.message)
        await callback.answer()
        return
    
    await state.finish()
    
    parts = callback.data.split("_")
    
    if len(parts) < 3:
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return
        
    try:
        cat_id = int(parts[1])
        geo_payload = parts[2]
    except (ValueError, IndexError) as e:
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return
    
    try:
        # Получаем city_id и district_id из geo_payload
        city_id = None
        district_id = None
        
        if geo_payload.startswith('d'):  # Район
            district_id = int(geo_payload[1:])
            async with aiosqlite.connect('shop.db') as db:
                city_info = await (await db.execute("SELECT city_id FROM districts WHERE id=?", (district_id,))).fetchone()
                if city_info:
                    city_id = city_info[0]
        elif geo_payload.startswith('c'):  # Город
            city_id = int(geo_payload[1:])
        
        # Получаем название категории
        async with aiosqlite.connect('shop.db') as db:
            cat_info = await (await db.execute("SELECT name FROM categories WHERE id=?", (cat_id,))).fetchone()
            cat_name = cat_info[0] if cat_info else "неизвестная категория"
        
        # Получаем товары с авто-выдачей
        async with aiosqlite.connect('shop.db') as db:
            query = """
                SELECT DISTINCT p.id, p.name, p.photo_id, p.video_id, p.description
                FROM products p 
                WHERE p.category_id = ? 
                AND p.id NOT IN (SELECT product_id FROM hidden_products)
                AND EXISTS (
                    SELECT 1 FROM auto_delivery_points adp
                    WHERE adp.product_id = p.id
                    AND adp.city_id = ?
                    AND (adp.district_id = ? OR ? IS NULL)
                    AND adp.is_used = 0
                    AND adp.is_hidden = 0
                )
                ORDER BY p.name
            """
            rows = await (await db.execute(query, (cat_id, city_id, district_id, district_id))).fetchall()
        
        # Получаем информацию о локации (если нужно)
        user_lang = USER_LANG.get(callback.from_user.id, 'ru')
        location_info = ""
        if city_id:
            async with aiosqlite.connect('shop.db') as db:
                city_info = await (await db.execute("SELECT name FROM cities WHERE id=?", (city_id,))).fetchone()
                city_name = city_info[0] if city_info else ("Unknown city" if user_lang == 'en' else "Неизвестный город")
                if user_lang == 'ru':
                    location_info += f"🏙️ Город: {city_name}"
                else:
                    location_info += f"🏙️ City: {city_name}"
                
                if district_id:
                    district_info = await (await db.execute("SELECT name FROM districts WHERE id=?", (district_id,))).fetchone()
                    district_name = district_info[0] if district_info else ("Unknown district" if user_lang == 'en' else "Неизвестный район")
                    if user_lang == 'ru':
                        location_info += f"\n🏘️ Район: {district_name}"
                    else:
                        location_info += f"\n🏘️ District: {district_name}"
        
        # Определяем данные для кнопки "Назад"
        if district_id:
            back_data = f"city_{city_id}"  # Возвращаем к списку районов
        elif city_id:
            back_data = "show_cities"  # Возвращаем к списку городов
        else:
            back_data = "back_main"
        
        if not rows:
            kb_back = types.InlineKeyboardMarkup()
            kb_back.add(types.InlineKeyboardButton(
                get_text(callback.from_user.id, 'BACK_BTN'), 
                callback_data=back_data
            ))
            
            user_lang = USER_LANG.get(callback.from_user.id, 'ru')
            if user_lang == 'en':
                text = f"❌ <b>No available products</b>\n\n"
                if location_info:
                    text += f"{location_info}\n\n"
                text += f"📂 Category: {cat_name}\n\n"
                text += "⚠️ <i>There are no available auto-delivery items in this category for the selected location.</i>"
            else:
                text = f"❌ <b>Нет доступных товаров</b>\n\n"
                if location_info:
                    text += f"{location_info}\n\n"
                text += f"📂 Категория: {cat_name}\n\n"
                text += "⚠️ <i>В этой категории нет доступных товаров с авто-выдачей для выбранной локации.</i>"
            
            await safe_edit_message(callback, text, reply_markup=kb_back, parse_mode="HTML")
            return
        
        # Создаем клавиатуру с товарами
        kb = types.InlineKeyboardMarkup(row_width=1)
        
        for pid, nm, ph, vid, desc in rows:
            kb.add(types.InlineKeyboardButton(
                f"{nm}", 
                callback_data=f"product_detail_{pid}_{geo_payload}"
            ))
        
        # Кнопка назад
        kb.add(types.InlineKeyboardButton(
            get_text(callback.from_user.id, 'BACK_BTN'), 
            callback_data=back_data
        ))
        
        # Формируем текст (user_lang уже определен выше)
        if user_lang == 'en':
            text = f"📂 <b>Products in category: {cat_name}</b>\n\n"
            if location_info:
                text += f"{location_info}\n\n"
            text += f"🎁 Available products: {len(rows)}\n\n"
            text += "👇 Select a product:"
        else:
            text = f"📂 <b>Товары в категории: {cat_name}</b>\n\n"
            if location_info:
                text += f"{location_info}\n\n"
            text += f"🎁 Доступно товаров: {len(rows)}\n\n"
            text += "👇 Выберите товар:"
        
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error in show_products: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при загрузке товаров", show_alert=True)
        await send_main_menu(callback.message, callback.from_user.id)


@dp.callback_query_handler(lambda c: c.data.startswith("product_detail_"), state="*")
async def show_product_detail(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await show_subscription_required(callback.message)
        await callback.answer()
        return
    
    await state.finish()
    
    parts = callback.data.split("_")
    
    if len(parts) < 4:
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return
        
    try:
        pid = int(parts[2])
        geo_payload = parts[3]
    except (ValueError, IndexError) as e:
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return

    try:
        async with aiosqlite.connect('shop.db') as db:
            product = await (await db.execute('''
                SELECT p.id, p.name, p.price, p.photo_id, p.video_id, p.description, p.category_id,
                       (SELECT COUNT(*) FROM hidden_products hp WHERE hp.product_id = p.id) as is_hidden
                FROM products p 
                WHERE p.id = ? AND p.id NOT IN (SELECT product_id FROM hidden_products)
            ''', (pid,))).fetchone()
        
        if not product:
            await callback.answer("❌ Товар не найден или временно недоступен", show_alert=True)
            return
        
        pid, nm, price, ph, vid, desc, cat_id, is_hidden = product
        
        # Проверяем, что price не None
        if price is None:
            price = 0.0
        
        # Получаем city_id и district_id из geo_payload
        city_id = None
        district_id = None
        if 'd' in geo_payload:
            district_id = int(geo_payload[1:])
            async with aiosqlite.connect('shop.db') as db:
                city_info = await (await db.execute("SELECT city_id FROM districts WHERE id=?", (district_id,))).fetchone()
                if city_info:
                    city_id = city_info[0]
        elif 'c' in geo_payload:
            city_id = int(geo_payload[1:])
        
        # Проверяем доступные количества через авто-выдачу
        available_quantities = []
        if city_id:
            available_quantities = await auto_db.get_available_quantities_for_product(city_id, district_id, pid)
        
        has_auto_delivery = len(available_quantities) > 0
        
        user_lang = USER_LANG.get(callback.from_user.id, 'ru')
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        
        if has_auto_delivery:
            kb.add(
                types.InlineKeyboardButton(get_text(callback.from_user.id, 'BUY_BTN'), callback_data=f"buy_{pid}_{geo_payload}"),
            )
        else:
            if user_lang == 'en':
                kb.add(types.InlineKeyboardButton("📞 Contact manager", url="https://t.me/Cultura_Center"))
            else:
                kb.add(types.InlineKeyboardButton("📞 Связаться с менеджером", url="https://t.me/Cultura_Center"))
        
        kb.add(types.InlineKeyboardButton(
            get_text(callback.from_user.id, 'BACK_BTN'), 
            callback_data=f"cat_{cat_id}_{geo_payload}"
        ))
        
        # Формируем текст
        if user_lang == 'en':
            text = f"<b>{get_text(callback.from_user.id, 'PRODUCT_NAME', nm)}</b>\n\n"
            
            if has_auto_delivery:
                # Получаем реальные цены из авто-выдачи
                available_prices = {}
                
                for qty in available_quantities:
                    delivery = await auto_db.get_available_delivery_for_exact_quantity(city_id, district_id, pid, qty)
                    if delivery:
                        # Распаковываем 7 значений: id, product_id, photo_file_id, coordinates, description, quantity_grams, price
                        delivery_id, delivery_product_id, photo_file_id, coordinates, description, delivery_quantity, delivery_price = delivery
                            
                        available_prices[qty] = delivery_price if delivery_price else price * qty
                
                text += f"\n⚖️ <b>Available items:</b>\n"
                for qty in sorted(available_quantities):
                    real_price = available_prices.get(qty, price * qty)
                    text += f"• {qty}g - {real_price:.2f}€\n"
            else:
                text += f"\n⚠️ <i>No auto-delivery available at the moment.</i>\n"
                text += f"📞 Contact manager for purchase."
        else:
            text = f"<b>{get_text(callback.from_user.id, 'PRODUCT_NAME', nm)}</b>\n"

            
            if has_auto_delivery:
                # Получаем реальные цены и unit_type из авто-выдачи
                available_prices = {}
                available_units = {}  # Сохраняем unit_type для каждого количества
                
                for qty in available_quantities:
                    delivery = await auto_db.get_available_delivery_for_exact_quantity(city_id, district_id, pid, qty)
                    if delivery:
                        # Распаковываем 7 значений
                        delivery_id, delivery_product_id, photo_file_id, coordinates, description, delivery_quantity, delivery_price = delivery
                            
                        available_prices[qty] = delivery_price if delivery_price else price * qty
                
                text += f"\n⚖️ <b>Доступные клады:</b>\n"
                for qty in sorted(available_quantities):
                    real_price = available_prices.get(qty, price * qty)
                    text += f"• {qty}г - {real_price:.2f}€\n"
            else:
                text += f"\n⚠️ <i>Сейчас нет авто-выдачи.</i>\n"
                text += f"📞 Для покупки свяжитесь с менеджером."
        
        if desc:
            text += f"\n📝 {desc}"
        
        # Определяем тип медиа и проверяем file_id
        media_type = None
        media_file_id = None
        
        if ph:
            # Проверяем, корректный ли photo_id
            if len(ph) > 20 and '://' not in ph:
                media_type = 'photo'
                media_file_id = ph
            else:
                logging.warning(f"Invalid photo_id for product {pid}: {ph}")
        
        if vid and not media_type:
            # Проверяем, корректный ли video_id
            if len(vid) > 20 and '://' not in vid:
                media_type = 'video'
                media_file_id = vid
            else:
                logging.warning(f"Invalid video_id for product {pid}: {vid}")
        
        # Отправляем сообщение
        try:
            if media_type == 'photo':
                await callback.message.answer_photo(
                    media_file_id, 
                    caption=text, 
                    reply_markup=kb, 
                    parse_mode="HTML"
                )
            elif media_type == 'video':
                await callback.message.answer_video(
                    media_file_id, 
                    caption=text, 
                    reply_markup=kb, 
                    parse_mode="HTML"
                )
            else:
                # Нет медиа или некорректный file_id
                await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
                
        except Exception as e:
            if "Wrong file identifier" in str(e):
                # Если file_id некорректный, отправляем текст
                logging.error(f"Invalid file_id for product {pid}, sending text only: {e}")
                await callback.message.answer(
                    f"📷 <i>(Медиафайл временно недоступен)</i>\n\n{text}", 
                    reply_markup=kb, 
                    parse_mode="HTML"
                )
            else:
                # Другая ошибка
                logging.error(f"Error sending product {pid}: {e}")
                await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        
        await callback.answer()
        
    except Exception as e:
        logging.error(f"Error in show_product_detail: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при загрузке товара", show_alert=True)



@dp.callback_query_handler(lambda c: c.data.startswith("buy_"), state="*")
async def buy_item(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await show_subscription_required(callback.message)
        await callback.answer()
        return
    
    try:
        await callback.message.delete()
    except Exception as e:
        logs.logger.error(f"Could not delete product message", user_id=callback.from_user.id, details=f"Error: {e}")

    parts = callback.data.split("_")
    
    # Проверяем корректность формата
    if len(parts) < 3:
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return
        
    try:
        pid = int(parts[1])
        geo_payload = parts[2]
    except (ValueError, IndexError) as e:
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return

    await log_user_action(callback.from_user.id, "view_product", f"Просмотр товара ID: {pid}", "product_detail")
    
    async with aiosqlite.connect('shop.db') as db:
        product_info = await (await db.execute(
            "SELECT name, category_id FROM products WHERE id=?", (pid,)
        )).fetchone()
    
    if not product_info:
        await callback.answer("❌ Товар не найден", show_alert=True)
        return
    
    product_name, category_id = product_info
    
    city_id = None
    district_id = None
    if 'd' in geo_payload:
        district_id = int(geo_payload[1:])
        async with aiosqlite.connect('shop.db') as db:
            city_id = (await (await db.execute("SELECT city_id FROM districts WHERE id=?", (district_id,))).fetchone())[0]
    elif 'c' in geo_payload:
        city_id = int(geo_payload[1:])

    # ПРОВЕРЯЕМ ДОСТУПНЫЕ КОЛИЧЕСТВА И ЦЕНЫ ИЗ АВТО-ВЫДАЧИ
    available_quantities = await auto_db.get_available_quantities_for_product(city_id, district_id, pid)
    
    if not available_quantities:
        await callback.answer("❌ Нет доступных кладов для этого товара в выбранном районе", show_alert=True)
        
        # Возвращаем к списку товаров в категории
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(
            get_text(callback.from_user.id, 'BACK_BTN'), 
            callback_data=f"cat_{category_id}_{geo_payload}"
        ))
        await callback.message.answer(
            "❌ Нет доступных кладов для этого товара в выбранном районе.\n\nПопробуйте выбрать другой товар или район.",
            reply_markup=kb
        )
        return

    # ПОЛУЧАЕМ РЕАЛЬНЫЕ ЦЕНЫ КЛАДОВ ИЗ АВТО-ВЫДАЧИ
    available_prices = {}
    
    for qty in available_quantities:
        delivery = await auto_db.get_available_delivery_for_exact_quantity(city_id, district_id, pid, qty)
        if delivery:
            # Распаковываем 7 значений: id, product_id, photo_file_id, coordinates, description, quantity_grams, price
            delivery_id, delivery_product_id, photo_file_id, coordinates, description, delivery_quantity, delivery_price = delivery
            available_prices[qty] = delivery_price if delivery_price else 0.0

    await state.update_data(
        product_id=pid,
        product_name=product_name,
        city_id=city_id,
        district_id=district_id,
        geo_payload=geo_payload,
        available_quantities=available_quantities,
        available_prices=available_prices,
        category_id=category_id
    )
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    # СОЗДАЕМ КНОПКИ С РЕАЛЬНЫМИ ЦЕНАМИ
    for qty in sorted(available_quantities):
        # Используем реальную цену из авто-выдачи
        real_price = available_prices.get(qty, 0)
        
        kb.insert(types.InlineKeyboardButton(
            f"{qty}г - {real_price:.2f}€", 
            callback_data=f"qty_{qty}"
        ))
    
    # Если нужны другие количества - перенаправляем к саппорту
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        kb.add(types.InlineKeyboardButton(
            "👨‍💼 Other quantities", 
            callback_data="contact_support"
        ))
    else:
        kb.add(types.InlineKeyboardButton(
            "👨‍💼 Другие количества", 
            callback_data="contact_support"
        ))
    
    # КНОПКА "НАЗАД" с правильным category_id
    kb.add(types.InlineKeyboardButton(
        get_text(callback.from_user.id, 'BACK_BTN'), 
        callback_data=f"cat_{category_id}_{geo_payload}"
    ))
    
    # Формируем текст с реальными ценами
    text = f"🎁 {product_name}\n\n"
    
    if user_lang == 'en':
        text += "💰 <b>Available stashes:</b>\n"
    else:
        text += "💰 <b>Доступные клады:</b>\n"
    
    for qty in sorted(available_quantities):
        real_price = available_prices.get(qty, 0)
        text += f"• {qty}g - {real_price:.2f}€\n"
    
    text += f"\n{get_text(callback.from_user.id, 'CHOOSE_QUANTITY')}"
    
    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await Purchase.waiting_for_quantity.set()
    await callback.answer()




# Обработчик contact_manager удален - теперь используется contact_support

@dp.callback_query_handler(lambda c: c.data.startswith("qty_"), state=Purchase.waiting_for_quantity)
async def process_quantity_selection(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    available_quantities = data.get('available_quantities', [])
    available_prices = data.get('available_prices', {})
    
    quantity = int(callback.data.split("_")[1])
    
    # ПРОВЕРЯЕМ, ЧТО ВЫБРАННОЕ КОЛИЧЕСТВО ЕСТЬ В ДОСТУПНЫХ
    if quantity not in available_quantities:
        await callback.answer("❌ Это количество недоступно для выбора", show_alert=True)
        return
    
    # Используем реальную цену из авто-выдачи
    total_price = available_prices.get(quantity, 0)
    
    if total_price == 0:
        await callback.answer("❌ Ошибка: цена не найдена", show_alert=True)
        return
    
    await state.update_data(
        quantity=quantity, 
        total_price=total_price
    )
    
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Confirm", callback_data="confirm_purchase"),
            types.InlineKeyboardButton("◀️ Back", callback_data=f"buy_{data['product_id']}_{data['geo_payload']}")
        )
    else:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_purchase"),
            types.InlineKeyboardButton("◀️ Назад", callback_data=f"buy_{data['product_id']}_{data['geo_payload']}")
        )
    
    text = get_text(callback.from_user.id, 'QUANTITY_SELECTED', f"{quantity}", f"{total_price:.2f}")
    await safe_edit_message(callback, text, reply_markup=kb)
    await callback.answer()



@dp.callback_query_handler(lambda c: c.data == "confirm_purchase", state=Purchase.waiting_for_quantity)
async def confirm_purchase(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    # Пока НЕ создаем заказ! Сохраняем только данные для будущего заказа
    total_price = data['total_price']
    product_name = data['product_name']
    quantity = data['quantity']
    product_id = data['product_id']
    city_id = data.get('city_id')
    district_id = data.get('district_id')
    geo_payload = data.get('geo_payload')
    category_id = data.get('category_id')
    
    # Сохраняем данные для создания заказа ПОСЛЕ выбора способа оплаты
    await state.update_data(
        total_price=total_price,
        product_name=product_name,
        quantity=quantity,
        product_id=product_id,
        city_id=city_id,
        district_id=district_id,
        geo_payload=geo_payload,
        category_id=category_id,
        discount_percent=0,  # По умолчанию без скидки
        final_price=total_price  # Начальная финальная цена = полная цена
    )
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    payment_methods = []
    
    # Получаем платежные методы
    async with aiosqlite.connect('shop.db') as db:
        payments = await (await db.execute("SELECT card FROM payments WHERE id=1")).fetchone()
        card = payments[0] if payments else None
    
    # Проверяем доступность прямой оплаты USDT
    from direct_payment import USDT_SETTINGS
    usdt_wallet = await dp_module.get_usdt_wallet_from_db()
    
    if card:
        payment_methods.append(("💳 Bank Card" if user_lang == 'en' else "💳 Банковская карта", "payment_card"))
    
    # ПРИОРИТЕТ: Прямая оплата USDT (если настроена)
    if usdt_wallet and len(usdt_wallet) == 34 and usdt_wallet.startswith('T'):
        payment_methods.append(("💰 Криптовалютой" if user_lang == 'ru' else "💰 Cryptocurrency", "payment_direct_usdt"))
    
    # Резервный вариант: CryptoBot
    if CRYPTOBOT_AVAILABLE:
        payment_methods.append(("🤖 CryptoBot" if user_lang == 'ru' else "🤖 CryptoBot", "payment_cryptobot"))
    
    for text, callback_data in payment_methods:
        kb.add(types.InlineKeyboardButton(text, callback_data=callback_data))
    
    if user_lang == 'en':
        text = f"<b>Purchase Confirmation</b>\n\n"
        text += f"🎁 Product: {product_name}\n"
        text += f"⚖️ Quantity: {quantity}g\n"
        text += f"💶 Amount: {total_price:.2f} €\n\n"
        text += "<b>Choose payment method:</b>\n"
        text += "🎁 You can apply promo code before payment"
    else:
        text = f"<b>Подтверждение покупки</b>\n\n"
        text += f"🎁 Товар: {product_name}\n"
        text += f"⚖️ Количество: {quantity}г\n"
        text += f"💶 Сумма: {total_price:.2f} €\n\n"
        text += "<b>Выберите способ оплаты:</b>\n"
        text += "🎁 Вы можете применить промокод перед оплатой"
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    if user_lang == 'en':
        kb.add(
            types.InlineKeyboardButton("💰 Cryptocurrency", callback_data="payment_direct_crypto"),
            types.InlineKeyboardButton("🤖 CryptoBot", callback_data="payment_cryptobot"),
            types.InlineKeyboardButton("🎁 Promo code", callback_data="use_promo_before_payment"),
            types.InlineKeyboardButton("◀️ Back", callback_data="back_from_order_confirm")
        )
    else:
        kb.add(
            types.InlineKeyboardButton("💰 Криптовалютой", callback_data="payment_direct_crypto"),
            types.InlineKeyboardButton("🤖 CryptoBot", callback_data="payment_cryptobot"),
            types.InlineKeyboardButton("🎁 Промокод", callback_data="use_promo_before_payment"),
            types.InlineKeyboardButton("◀️ Назад", callback_data="back_from_order_confirm")
        )
    
    await safe_edit_message(callback, text, reply_markup=kb, parse_mode="HTML")
    await Purchase.waiting_for_payment_method.set()
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "use_promo_before_payment", state=Purchase.waiting_for_payment_method)
async def use_promo_before_payment(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Промокод' перед выбором способа оплаты"""
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        text = "🎁 <b>Enter Promo Code</b>\n\n"
        text += "Enter your promo code to get a discount.\n"
        text += "The discount will be applied to your order."
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            "❌ Cancel (return to payment)",
            callback_data="cancel_promo_and_return"
        ))
    else:
        text = "🎁 <b>Введите промокод</b>\n\n"
        text += "Введите ваш промокод для получения скидки.\n"
        text += "Скидка будет применена к вашему заказу."
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            "❌ Отмена (вернуться к оплате)",
            callback_data="cancel_promo_and_return"
        ))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await PromoCode.waiting_for_promo.set()
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "cancel_promo_and_return", state=PromoCode.waiting_for_promo)
async def cancel_promo_and_return(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к выбору способа оплаты без промокода"""
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        await callback.answer("Returning to payment selection...")
    else:
        await callback.answer("Возвращаемся к выбору оплаты...")
    
    await state.finish()
    await Purchase.waiting_for_payment_method.set()
    
    # Повторно показываем меню выбора способа оплаты
    data = await state.get_data()
    total_price = data.get('total_price', 0)
    product_name = data.get('product_name', '')
    quantity = data.get('quantity', 0)
    final_price = data.get('final_price', total_price)
    discount_percent = data.get('discount_percent', 0)
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    payment_methods = []
    
    async with aiosqlite.connect('shop.db') as db:
        payments = await (await db.execute("SELECT card FROM payments WHERE id=1")).fetchone()
        card = payments[0] if payments else None
    
    if card:
        payment_methods.append(("💳 Bank Card" if user_lang == 'en' else "💳 Банковская карта", "payment_card"))
    
    if CRYPTOBOT_AVAILABLE:
        payment_methods.append(("🤖 CryptoBot (Telegram)" if user_lang == 'en' else "🤖 CryptoBot (Telegram)", "payment_cryptobot"))
    
    for text, callback_data in payment_methods:
        kb.add(types.InlineKeyboardButton(text, callback_data=callback_data))
    
    # Снова показываем кнопку промокода
    kb.add(types.InlineKeyboardButton(
        "🎁 Promo code" if user_lang == 'en' else "🎁 Промокод", 
        callback_data="use_promo_before_payment"
    ))
    
    # Кнопка "Назад"
    kb.add(types.InlineKeyboardButton(
        get_text(callback.from_user.id, 'BACK_BTN'),
        callback_data="back_from_order_confirm"
    ))
    
    if user_lang == 'en':
        text = f"<b>Purchase Confirmation</b>\n\n"
        text += f"🎁 Product: {product_name}\n"
        text += f"⚖️ Quantity: {quantity}g\n"
        
        if discount_percent > 0:
            text += f"🎁 Discount: {discount_percent}%\n"
            text += f"💶 Original: {total_price:.2f} €\n"
            text += f"💶 <b>Final price: {final_price:.2f} €</b>\n\n"
        else:
            text += f"💶 Total: {total_price:.2f} €\n\n"
            
        text += "<b>Choose payment method:</b>"
    else:
        text = f"<b>Подтверждение покупки</b>\n\n"
        text += f"🎁 Товар: {product_name}\n"
        text += f"⚖️ Количество: {quantity}г\n"
        
        if discount_percent > 0:
            text += f"🎁 Скидка: {discount_percent}%\n"
            text += f"💶 Исходная: {total_price:.2f} €\n"
            text += f"💶 <b>Финальная цена: {final_price:.2f} €</b>\n\n"
        else:
            text += f"💶 Сумма: {total_price:.2f} €\n\n"
            
        text += "<b>Выберите способ оплаты:</b>"
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()





@dp.callback_query_handler(lambda c: c.data == "back_from_order_confirm", state=Purchase.waiting_for_payment_method)
async def back_from_order_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Возврат из подтверждения заказа без его отмены"""
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    # Получаем данные о заказе
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if order_id:
        # Меняем статус заказа на "cancelled" если пользователь ушел
        async with aiosqlite.connect('shop.db') as db:
            await db.execute(
                "UPDATE orders SET status = 'cancelled', expires_at = NULL WHERE id = ? AND status = 'pending'", 
                (order_id,)
            )
            await db.commit()
            
            await log_order_action(order_id, "ORDER_CANCELLED", "User returned to menu without payment")
    
    # Возвращаем в главное меню
    await state.finish()
    
    if user_lang == 'en':
        await callback.answer("Returning to main menu...")
    else:
        await callback.answer("Возвращаемся в главное меню...")
    
    await send_main_menu(callback.message, callback.from_user.id)
    await callback.answer()



@dp.message_handler(content_types=['photo'], state=Purchase.waiting_for_proof)
async def receive_proof(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    async with aiosqlite.connect('shop.db') as db:
        order_info = await (await db.execute(
            """SELECT o.id, o.final_price, o.discount_percent, o.quantity, 
                      p.name, u.username, o.city_id, o.district_id, o.product_id,
                      c.name, d.name
               FROM orders o
               JOIN products p ON o.product_id = p.id
               JOIN users u ON o.user_id = u.user_id
               LEFT JOIN cities c ON o.city_id = c.id
               LEFT JOIN districts d ON o.district_id = d.id
               WHERE o.user_id=? AND o.status='pending' 
               ORDER BY o.id DESC LIMIT 1""",
            (message.from_user.id,)
        )).fetchone()

        if not order_info:
            await message.answer("❌ Активный заказ не найден")
            await state.finish()
            return

        order_id, final_price, discount_percent, quantity, product_name, username_db, city_id, district_id, product_id, city_name, district_name = order_info
        
        username = f"@{username_db}" if username_db else "No username"
        location = f"{city_name}, {district_name}" if district_name else f"{city_name}"

        # ИСПОЛЬЗУЕМ ТОЧНОЕ КОЛИЧЕСТВО ИЗ ЗАКАЗА ДЛЯ ПОИСКА АВТО-ВЫДАЧИ
        auto_delivery = await auto_db.get_available_delivery_for_exact_quantity(city_id, district_id, product_id, quantity)
        
        if auto_delivery:
            delivery_id, delivery_product_id, photo_file_id, coordinates, description, delivery_quantity, delivery_price = auto_delivery
            
            # Используем авто-выдачу ТОЧНО по количеству
            success = await auto_db.mark_delivery_used(delivery_id, message.from_user.id, quantity)
            
            if success:
                await db.execute(
                    "UPDATE orders SET status='completed', expires_at=NULL WHERE id=?", 
                    (order_id,)
                )
                await db.commit()
                
                # Отправляем клад пользователю
                description_text = f"📝 {description}\n" if description else ""
                caption = get_text(
                    message.from_user.id, 
                    'AUTO_DELIVERY_SUCCESS', 
                    coordinates, order_id, product_name, quantity, description_text
                )
                
                await bot.send_photo(
                    message.from_user.id, 
                    photo_file_id, 
                    caption=caption,
                    parse_mode="HTML"
                )
                
                await message.answer(get_text(message.from_user.id, 'ORDER_AUTO_PROCESSED'))
                
                # Логируем в админ-чате
                remaining = delivery_quantity - quantity
                status = "🔴 ИСПОЛЬЗОВАН" if remaining == 0 else f"🟢 Осталось: {remaining}г"
                
                log_text = (f"✅ Авто-выдача ID{order_id}\n"
                           f"👤 {username}\n"
                           f"🎁 {product_name} ({quantity}г)\n"
                           f"📍 {location}\n"
                           f"📦 {status}")
                
                await bot.send_message(LOG_CHAT_ID, log_text)
                
                await state.finish()
                return
            else:
                logs.logger.warning(f"Failed to use auto delivery for order {order_id}")
        
        # Ручная обработка (если нет авто-выдачи или не удалось использовать)
        await db.execute(
            "UPDATE orders SET expires_at=NULL WHERE id=?", (order_id,)
        )
        await db.commit()

        await log_order_action(order_id, "PAYMENT_RECEIVED", f"User {message.from_user.id} sent payment proof")
        
        log_text = f"🆕 Новый заказ ID{order_id:01d}\n👤 Пользователь: {username}\n🎁 Товар: {product_name}\n⚖️ Количество: {quantity}г\n💰 Сумма: {final_price:.2f} €\n📍 Локация: {location}\n\n❌ Требуется ручная выдача (нет авто-выдачи)"
        await bot.send_message(LOG_CHAT_ID, log_text)
        
        caption = (f"📥 Лог оплаты\n"
                   f"🆔 {message.from_user.id}\n"
                   f"{username}\n"
                   f"🎁 Товар: {product_name}\n"
                   f"⚖️ Количество: {quantity}г\n")
        
        if discount_percent and discount_percent > 0:
            try:
                original_price = final_price / (1 - discount_percent / 100)
                caption += f"💶 Исходная цена: {original_price:.2f} €\n"
            except ZeroDivisionError:
                caption += f"💶 Исходная цена: (ошибка расчета)\n"
            caption += f"🎁 Скидка: {discount_percent}%\n"
            caption += f"💶 <b>Финальная цена: {final_price:.2f} €</b>\n"
        else:
            caption += f"💶 Сумма: {final_price:.2f} €\n"
        
            caption = f"📋 ID сделки: ID{order_id:01d}"

        kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{order_id}"),
            types.InlineKeyboardButton("🚫 Отклонить",   callback_data=f"reject_{order_id}")
        )
        
        await bot.send_photo(LOG_CHAT_ID, message.photo[-1].file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
        await message.answer(get_text(message.from_user.id, 'SCREENSHOT_SENT'))
    
    await state.finish()

async def manager_confirm(callback: types.CallbackQuery, state: FSMContext):
    try:
        # ИСПРАВЛЕННЫЙ ПАРСИНГ - проверяем формат данных
        parts = callback.data.split("_")
        if len(parts) < 2:
            await callback.answer("❌ Неверный формат данных", show_alert=True)
            return
            
        # Проверяем что второй элемент - число
        try:
            order_id = int(parts[1])
        except ValueError:
            await callback.answer("❌ Неверный номер заказа", show_alert=True)
            return
    
    except Exception as e:
        await callback.answer("❌ Ошибка обработки запроса", show_alert=True)
        return
    
    async with aiosqlite.connect('shop.db') as db:
        order_info = await (await db.execute(
            "SELECT o.user_id, p.name, u.username, o.quantity, o.product_id FROM orders o "
            "JOIN products p ON o.product_id = p.id "
            "JOIN users u ON o.user_id = u.user_id "
            "WHERE o.id=?", (order_id,)
        )).fetchone()
    
    if order_info:
        user_id, product_name, username, quantity, product_id = order_info
        username = f"@{username}" if username else "No username"
        
        async with aiosqlite.connect('shop.db') as db:
            await db.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?", 
                (quantity, product_id)
            )
            await db.commit()
        
        await state.update_data(
            order_id=order_id, 
            user_id=user_id,
            product_name=product_name,
            quantity=quantity
        )
        
        text = (f"✅ Подтверждение заказа ID{order_id:01d}\n"
                f"👤 Пользователь: {username}\n\n"
                f"📦 Отправьте ОДНО фото с кладом и укажите координаты в ПОДПИСИ к фото!\n\n"
                f"📍 Пример подписи: 55.7558, 37.6173\n"
                f"📍 Или: 55.7558° N, 37.6173° E\n\n"
                f"⚠️ Отправляйте фото с координатами в одной сообщении!")
        
        await callback.message.answer(text)
        await ManagerLog.waiting_for_photos.set()
    else:
        await callback.message.answer("❌ Заказ не найден")
    
    await callback.answer()

@dp.message_handler(content_types=['photo'], state=ManagerLog.waiting_for_photos)
async def manager_receive_photo_with_coords(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['order_id']
    user_id = data['user_id']
    product_name = data['product_name']
    quantity = data['quantity']
    
    # Проверяем, есть ли подпись с координатами
    if not message.caption:
        await message.answer("❌ Отправьте фото с подписью, где указаны координаты клада!\n\nПример подписи: 55.7558, 37.6173")
        return
    
    coords = message.caption.strip()
    
    # Проверяем, что это похоже на координаты
    if not any(char in coords for char in ['.', ',', '°']) or len(coords) < 5:
        await message.answer("❌ Неверный формат координат! Укажите координаты в подписи к фото.\n\nПример: 55.7558, 37.6173")
        return
    
    file_id = message.photo[-1].file_id
    
    caption = (f"🚚 Ваш клад!\n\n"
               f"📍 Координаты: {coords}\n"
               f"✅ Оплата подтверждена для заказа ID{order_id:01d}\n"
               f"🎁 Товар: {product_name}\n"
               f"⚖️ Количество: {quantity}г\n"
               f"❤️ Спасибо за покупку! Если у вас появятся вопросы или проблемы, обратитесь к нашему менеджеру")
    
    try:
        await bot.send_photo(
            user_id, 
            file_id, 
            caption=caption,
            parse_mode="HTML"
        )
        
        async with aiosqlite.connect('shop.db') as db:
            await db.execute("UPDATE orders SET status='completed' WHERE id=?", (order_id,))
            await db.commit()
        
        await log_order_action(order_id, "ORDER_COMPLETED", f"Manager sent photo with coords: {coords}")
        
        await message.answer("✅ Фото с координатами успешно отправлено пользователю!")
        
    except Exception as e:
        logs.logger.error(f"Failed to send photo to user", user_id=user_id, order_id=order_id, details=f"Error: {e}")
        await message.answer(f"❌ Ошибка отправки пользователю: {e}")
    
    await state.finish()

@dp.message_handler(content_types=['photo'], state=ManagerLog.waiting_for_photos)
async def manager_receive_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['order_id']
    manager_photos = data.get('manager_photos', [])
    
    file_id = message.photo[-1].file_id
    manager_photos.append(file_id)
    
    await state.update_data(manager_photos=manager_photos)
    await save_manager_photo(order_id, file_id)
    
    kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("✅ Готово (к вводу координат)", callback_data="finish_photos")
    )
    
    await message.answer(get_text(message.from_user.id, 'WAITING_FOR_MORE_PHOTOS'), reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data == "finish_photos", state=ManagerLog.waiting_for_photos)
async def manager_finish_photos(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    if not data.get('manager_photos'):
        await callback.answer("❌ Вы не отправили ни одного фото!", show_alert=True)
        return
    
    await callback.message.edit_text(get_text(callback.from_user.id, 'SEND_COORDS_PROMPT'))
    await ManagerLog.waiting_for_coords.set()
    await callback.answer()

@dp.message_handler(content_types=['photo'], is_reply=True)
async def handle_cryptobot_manual_delivery_photo_with_caption(message: types.Message, state: FSMContext):
    if not message.reply_to_message or not message.reply_to_message.from_user.is_bot:
        return
    
    reply_text = message.reply_to_message.text or ""
    if "🆘 CryptoBot оплата" not in reply_text or "❌ НЕТ АВТО-ВЫДАЧИ" not in reply_text:
        return
    
    import re
    order_id_match = re.search(r'#id(\d+)', reply_text)
    if not order_id_match:
        await message.answer("❌ Не удалось определить номер заказа")
        return
    
    order_id = int(order_id_match.group(1))
    
    # Проверяем, есть ли подпись с координатами
    if not message.caption:
        await message.answer("❌ Отправьте фото с подписью, где указаны координаты клада!\n\nПример подписи: 55.7558, 37.6173")
        return
    
    coords = message.caption.strip()
    
    # Проверяем, что это похоже на координаты
    if not any(char in coords for char in ['.', ',', '°']) or len(coords) < 5:
        await message.answer("❌ Неверный формат координатов! Укажите координаты в подписи к фото.\n\nПример: 55.7558, 37.6173")
        return
    
    file_id = message.photo[-1].file_id
    
    # Получаем информацию о заказе
    async with aiosqlite.connect('shop.db') as db:
        order_info = await (await db.execute("""
            SELECT o.user_id, p.name, o.quantity, u.username 
            FROM orders o 
            JOIN products p ON o.product_id = p.id 
            JOIN users u ON o.user_id = u.user_id 
            WHERE o.id=?
        """, (order_id,))).fetchone()
    
    if not order_info:
        await message.answer("❌ Заказ не найден")
        return
    
    user_id, product_name, quantity, username = order_info
    username_display = f"@{username}" if username else "Пользователь"
    
    caption = (f"🚚 Ваш клад!\n\n"
               f"📍 Координаты: {coords}\n"
               f"✅ Оплата подтверждена для заказа ID{order_id:01d}\n"
               f"🎁 Товар: {product_name}\n"
               f"⚖️ Количество: {quantity}г\n"
               f"❤️ Спасибо за покупку! Если у вас появятся вопросы или проблемы, обратитесь к нашему менеджеру")
    
    try:
        await bot.send_photo(
            user_id, 
            file_id, 
            caption=caption,
            parse_mode="HTML"
        )
        
        async with aiosqlite.connect('shop.db') as db:
            await db.execute("UPDATE orders SET status='completed' WHERE id=?", (order_id,))
            await db.commit()
        
        await log_order_action(order_id, "MANUAL_DELIVERY_CRYPTOBOT", f"Manager sent photo with coords: {coords}")
        
        await message.answer(f"✅ Клад успешно отправлен пользователю {username_display}")
        
        try:
            await bot.edit_message_text(
                chat_id=LOG_CHAT_ID,
                message_id=message.reply_to_message.message_id,
                text=f"✅ ВЫДАНО ВРУЧНУЮ ID{order_id}\n"
                     f"👤 {username_display}\n"
                     f"🎁 {product_name} ({quantity}г)\n"
                     f"📍 Координаты: {coords}\n"
                     f"⏰ Выдано: {datetime.now().strftime('%d.%m %H:%M')}"
            )
        except Exception as e:
            logs.logger.error(f"Could not edit original message", order_id=order_id, details=f"Error: {e}")
            
    except Exception as e:
        logs.logger.error(f"Failed to send photo to user", user_id=user_id, order_id=order_id, details=f"Error: {e}")
        await message.answer(f"❌ Ошибка отправки пользователю: {e}")

@dp.callback_query_handler(lambda c: c.data == "cancel_cryptobot_delivery", state="*")
async def cancel_cryptobot_delivery(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("❌ Ручная выдача CryptoBot отменена")
    await callback.answer()

@dp.message_handler(state="waiting_cryptobot_coords")
async def handle_cryptobot_manual_delivery_coords(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('cryptobot_order_id')
    
    if not order_id:
        await message.answer("❌ Ошибка: не найден заказ")
        await state.finish()
        return
    
    coords = message.text.strip()
    
    async with aiosqlite.connect('shop.db') as db:
        order_info = await (await db.execute("""
            SELECT o.user_id, p.name, o.quantity, u.username 
            FROM orders o 
            JOIN products p ON o.product_id = p.id 
            JOIN users u ON o.user_id = u.user_id 
            WHERE o.id=?
        """, (order_id,))).fetchone()
    
    if not order_info:
        await message.answer("❌ Заказ не найден")
        await state.finish()
        return
    
    user_id, product_name, quantity, username = order_info
    username_display = f"@{username}" if username else "Пользователь"
    
    caption = (f"🚚 Ваш клад!\n\n"
               f"📍 Координаты: {coords}\n"
               f"✅ Оплата подтверждена для заказа ID{order_id:01d}\n"
               f"🎁 Товар: {product_name}\n"
               f"⚖️ Количество: {quantity}г\n"
               f"❤️ Спасибо за покупку! Если у вас появятся вопросы или проблемы, обратитесь к нашему менеджеру")
    
    photos = data.get('cryptobot_photos', [])
    if photos:
        try:
            await bot.send_photo(
                user_id, 
                photos[0], 
                caption=caption,
                parse_mode="HTML"
            )
            
            async with aiosqlite.connect('shop.db') as db:
                await db.execute("UPDATE orders SET status='completed' WHERE id=?", (order_id,))
                await db.commit()
            
            await log_order_action(order_id, "MANUAL_DELIVERY_CRYPTOBOT", f"Manager sent photo with coords: {coords}")
            
            await message.answer(f"✅ Клад успешно отправлен пользователю {username_display}")
            
            try:
                reply_message_id = data.get('reply_message_id')
                if reply_message_id:
                    await bot.edit_message_text(
                        chat_id=LOG_CHAT_ID,
                        message_id=reply_message_id,
                        text=f"✅ ВЫДАНО ВРУЧНУЮ ID{order_id}\n"
                             f"👤 {username_display}\n"
                             f"🎁 {product_name} ({quantity}г)\n"
                             f"📍 Координаты отправлены\n"
                             f"⏰ Выдано: {datetime.now().strftime('%d.%m %H:%M')}"
                    )
            except Exception as e:
                logs.logger.error(f"Could not edit original message", order_id=order_id, details=f"Error: {e}")
            
        except Exception as e:
            logs.logger.error(f"Failed to send photo to user", user_id=user_id, order_id=order_id, details=f"Error: {e}")
            await message.answer(f"❌ Ошибка отправки пользователю: {e}")
    else:
        await message.answer("❌ Не найдены фото для отправки")
    
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == "cancel_manual_delivery", state="*")
async def cancel_manual_delivery(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("❌ Ручная выдача отменена")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("reject_"), state="*")
async def manager_reject(callback: types.CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect('shop.db') as db:
        user_id_result = await (await db.execute(
            "SELECT user_id FROM orders WHERE id=?", (order_id,)
        )).fetchone()

    if not user_id_result:
        await callback.message.answer("❌ Заказ не найден в базе.")
        await callback.answer()
        return

    user_id = user_id_result[0]
    await state.update_data(order_id=order_id, user_id=user_id)
    await callback.message.answer("📝 Укажите причину отказа:")
    await ManagerReject.waiting_for_reason.set()
    await callback.answer()

@dp.message_handler(state=ManagerReject.waiting_for_reason)
async def manager_reject_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['order_id']
    user_id = data['user_id']
    
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("UPDATE orders SET status='rejected' WHERE id=?", (order_id,))
        await db.commit()
    
    await bot.send_message(user_id, f"❌ Ваш заказ ID{order_id:01d} отклонён.\nПричина: {message.text}")
    await message.answer("✅ Пользователь уведомлён об отказе")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data=="info", state="*")
async def show_info(callback: types.CallbackQuery, state: FSMContext):
    if not await check_subscription(callback.from_user.id):
        await show_subscription_required(callback.message)
        await callback.answer()
        return
    await state.finish()
    
    # Получаем список онлайн поддержки
    online_support = []
    for support_id, status in SUPPORT_STATUS.items():
        if status == "online":
            async with aiosqlite.connect('shop.db') as db:
                user_info = await (await db.execute(
                    "SELECT username FROM users WHERE user_id=?", (support_id,)
                )).fetchone()
            
            # ИСПРАВЛЕНИЕ: Используем username из базы или из Telegram
            username = user_info[0] if user_info and user_info[0] else "Unknown"
            try:
                user = await bot.get_chat(support_id)
                if user.username:
                    username = user.username
            except:
                pass
                
            online_support.append(f"👨‍💼 @{username}")
    
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        text = f"{get_text(callback.from_user.id, 'INFO_TITLE')}\n\n"
        
        if online_support:
            text += "🟢 <b>Online support:</b>\n" + "\n".join(online_support) + "\n\n"
        else:
            text += "🔴 <b>No online support at the moment</b>\n\n"
        
        text += "Here you can read our rules and contact the manager\n/swap command allows you to change the language\n/lang allows you to view the current language"
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        
        # Добавляем кнопку для связи с поддержкой только если есть онлайн поддержка
        if online_support:
            kb.add(types.InlineKeyboardButton("💬 Contact support", callback_data="contact_support"))
        
        kb.add(
            types.InlineKeyboardButton("📋 Rules", url="https://telegra.ph/"),
            types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data="back_main")
        )
    else:
        text = f"{get_text(callback.from_user.id, 'INFO_TITLE')}\n\n"
        
        if online_support:
            text += "🟢 <b>Онлайн поддержка:</b>\n" + "\n".join(online_support) + "\n\n"
        else:
            text += "🔴 <b>Сейчас нет онлайн поддержки</b>\n\n"
        
        text += "Тут вы можете прочитать наши правила и связатся с менеджером\n/swap команда позволяет изменить язык\n/lang позволяет посмотреть текущий язык"
        
        kb = types.InlineKeyboardMarkup(row_width=1)
        
        # Добавляем кнопку для связи с поддержкой только если есть онлайн поддержка
        if online_support:
            kb.add(types.InlineKeyboardButton("💬 Написать в поддержку", callback_data="contact_support"))
        
        kb.add(
            types.InlineKeyboardButton("📋 Правила", url="https://telegra.ph/"),
            types.InlineKeyboardButton(get_text(callback.from_user.id, 'BACK_BTN'), callback_data="back_main")
        )
    
    await safe_edit_message(callback, text, parse_mode="HTML", reply_markup=kb, photo_path=INFO_PHOTO_PATH)
    await callback.answer()



from direct_payment import USDT_SETTINGS, process_direct_usdt_payment, DirectPayment

@dp.callback_query_handler(lambda c: c.data.startswith("payment_"), state=Purchase.waiting_for_payment_method)
async def select_payment_method(callback: types.CallbackQuery, state: FSMContext):
    """Создает заказ только после выбора способа оплаты"""
    # Правильно извлекаем payment_method из callback.data
    payment_method = callback.data.replace("payment_", "")
    data = await state.get_data()
    
    # Получаем финальную цену (уже с промокодом если применен)
    final_price = data.get('final_price', data.get('total_price', 0))
    total_price = data.get('total_price', 0)
    discount_percent = data.get('discount_percent', 0)
    promo_code = data.get('promo_code')
    
    # Проверяем, активна ли прямая оплата USDT
    if payment_method == "direct_usdt":
        wallet = USDT_SETTINGS.get('wallet_address')
        if not wallet or len(wallet) < 30:
            await callback.answer("❌ Прямая оплата USDT временно недоступна. Установите кошелек в админ-панели.", show_alert=True)
            return
    
    # ТЕПЕРЬ создаем заказ
    expires_at = datetime.now() + timedelta(minutes=10)
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Получаем информацию о продукте и локации
            product_info = await (await db.execute(
                "SELECT name FROM products WHERE id = ?", (data['product_id'],)
            )).fetchone()
            
            city_info = await (await db.execute(
                "SELECT name FROM cities WHERE id = ?", (data.get('city_id'),)
            )).fetchone()
            
            district_info = None
            if data.get('district_id'):
                district_info = await (await db.execute(
                    "SELECT name FROM districts WHERE id = ?", (data.get('district_id'),)
                )).fetchone()
            
            product_name = product_info[0] if product_info else "Неизвестный товар"
            city_name = city_info[0] if city_info else "Неизвестный город"
            district_name = district_info[0] if district_info else None
            
            # Сохраняем в данные состояния (ID для динамической локализации)
            await state.update_data(
                product_name=product_name,
                city_name=city_name,
                district_name=district_name,
                product_id_for_lang=data['product_id'],
                city_id_for_lang=data.get('city_id'),
                district_id_for_lang=data.get('district_id')
            )
            
            # Создаем заказ с указанием типа оплаты
            payment_type = 'direct_usdt' if payment_method == 'direct_usdt' else 'cryptobot'
            
            await db.execute(
                """INSERT INTO orders(
                    user_id, product_id, city_id, district_id, quantity, 
                    total_price, discount_percent, final_price, expires_at,
                    payment_type, product_name, payment_method, status
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (callback.from_user.id, data['product_id'], data.get('city_id'), 
                 data.get('district_id'), data['quantity'], total_price, 
                 discount_percent, final_price, expires_at,
                 payment_type, product_name, payment_method.upper(), 'pending')
            )
            await db.commit()
            
            order_id = (await (await db.execute("SELECT last_insert_rowid()")).fetchone())[0]
        
        # Если был применен промокод, помечаем его как использованный
        if promo_code and discount_percent > 0:
            await mark_promo_code_used(callback.from_user.id, promo_code, order_id)
            await log_order_action(order_id, "PROMO_APPLIED", 
                                  f"Promo code: {promo_code}, Discount: {discount_percent}%")
        
        await log_order_action(order_id, "ORDER_CREATED", 
                              f"User {callback.from_user.id} created order {order_id} for {data['quantity']}г, Payment: {payment_method}")
        
        await state.update_data(order_id=order_id)
        
        # Выбираем способ оплаты
        if payment_method == "direct_usdt":
            # Прямая оплата USDT TRC20
            from direct_payment import process_direct_usdt_payment
            await process_direct_usdt_payment(
                callback, state, order_id, 
                callback.from_user.id, final_price, 
                product_name, data['quantity'], 
                city_name, district_name or "Не указан"
            )
        elif payment_method == "cryptobot":
            await process_cryptobot_payment(callback, state)
        elif payment_method == "card":
            await process_legacy_payment(callback, state, "card")
        elif payment_method == "direct_crypto":
            # Прямая крипто-оплата (выбор между USDT, BTC, ETH и т.д.)
            from direct_payment import show_crypto_selection
            await show_crypto_selection(
                callback, state, order_id,
                callback.from_user.id, final_price,
                product_name, data['quantity'],
                city_name, district_name or "Не указан"
            )
        else:
            logger.error(f"Unknown payment method: '{payment_method}' from callback.data: '{callback.data}'")
            await callback.answer("❌ Этот способ оплаты недоступен", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in select_payment_method: {e}")
        await callback.answer("❌ Ошибка при создании заказа", show_alert=True)

# ═══════════════════════════════════════════════════════
# СТАРЫЕ ДУБЛИРУЮЩИЕСЯ ФУНКЦИИ ПРЯМОЙ ОПЛАТЫ УДАЛЕНЫ
# Используются импортированные функции из direct_payment.py
# ═══════════════════════════════════════════════════════

@dp.callback_query_handler(lambda c: c.data == "choose_payment_method", state=Purchase.waiting_for_payment_method)
async def show_payment_options(callback: types.CallbackQuery, state: FSMContext):
    """Показывает доступные способы оплаты"""
    data = await state.get_data()
    final_price = data.get('final_price', 0)
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Проверяем доступность прямой оплаты USDT
    if USDT_SETTINGS.get('is_active') and USDT_SETTINGS.get('address'):
        kb.add(InlineKeyboardButton(
            "💰 Прямая оплата USDT (TRC20)", 
            callback_data="payment_direct_usdt"
        ))
    
    # CryptoBot оплата
    kb.add(InlineKeyboardButton(
        "🤖 CryptoBot (USDT/TRX/BTC)", 
        callback_data="payment_cryptobot"
    ))
    
    # Карта (старая оплата)
    kb.add(InlineKeyboardButton(
        "💳 Банковская карта", 
        callback_data="payment_card"
    ))
    
    kb.add(InlineKeyboardButton(
        "❌ Отмена", 
        callback_data="cancel_payment"
    ))
    
    text = (
        f"💳 <b>Выберите способ оплаты</b>\n\n"
        f"💰 Сумма к оплате: <b>{final_price} €</b>\n\n"
        f"<b>Доступные методы:</b>\n"
    )
    
    if USDT_SETTINGS.get('is_active'):
        text += "• <b>💰 Прямая оплата USDT</b> - прямой перевод на кошелек (рекомендуется)\n"
    text += "• <b>🤖 CryptoBot</b> - автоматическая оплата через Telegram бота\n"
    text += "• <b>💳 Банковская карта</b> - классический способ оплаты\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

# ═══════════════════════════════════════════════════════════════
# ОБРАБОТЧИКИ ПРОДОЛЖЕНЫ НИЖЕ (ДУБЛИР. КОД УДАЛЕН)
# ═══════════════════════════════════════════════════════════════

@dp.callback_query_handler(lambda c: c.data == "payment_cryptobot", state=Purchase.waiting_for_payment_method)
async def handle_cryptobot_payment(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки CryptoBot с учетом промокода"""
    await process_cryptobot_payment(callback, state)


@dp.message_handler(commands=['cryptorates'])
async def process_tx_id(message: types.Message, state: FSMContext):
    """Обработка TX ID от пользователя"""
    tx_hash = message.text.strip()
    
    # Базовая валидация TX ID
    if len(tx_hash) < 30 or len(tx_hash) > 100:
        await message.answer("❌ Неверный формат TX ID. Должно быть 30-100 символов.\nПопробуйте еще раз:")
        return
    
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        await message.answer("❌ Ошибка: не найден номер заказа")
        await state.finish()
        return
    
    # Сохраняем TX ID в базу
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Обновляем заказ
            await db.execute(
                "UPDATE orders SET tx_hash = ?, updated_at = datetime('now') WHERE id = ?",
                (tx_hash, order_id)
            )
            
            # Обновляем direct_payments
            await db.execute(
                "UPDATE direct_payments SET tx_hash = ? WHERE order_id = ?",
                (tx_hash, order_id)
            )
            
            await db.commit()
            
            # Получаем информацию о платеже
            payment_info = await (await db.execute(
                "SELECT usdt_amount FROM direct_payments WHERE order_id = ?", (order_id,)
            )).fetchone()
            
            if payment_info:
                usdt_amount = payment_info[0]
                
                # Проверяем платеж через API
                from direct_payment import check_usdt_payment
                
                wallet_address = USDT_SETTINGS.get('address')
                if wallet_address and USDT_SETTINGS.get('api_key'):
                    payment_confirmed = await check_usdt_payment(
                        tx_hash=tx_hash,
                        expected_amount=usdt_amount,
                        user_address=wallet_address
                    )
                    
                    if payment_confirmed:
                        # Платеж подтвержден
                        await complete_direct_payment(order_id, tx_hash, message.from_user.id)
                    else:
                        # Платеж не подтвержден, ожидаем ручной проверки
                        await message.answer(
                            "⏳ <b>TX ID получен!</b>\n\n"
                            "Платеж отправлен на проверку. Обычно это занимает 1-5 минут.\n"
                            "Вы получите уведомление, когда платеж будет подтвержден.\n\n"
                            "Можете продолжить покупки или ожидайте подтверждения.",
                            parse_mode="HTML"
                        )
                        
                        # Уведомляем админов
                        admin_message = (
                            f"🔍 <b>Новый TX ID для проверки</b>\n\n"
                            f"🆔 Заказ: #{order_id}\n"
                            f"👤 Пользователь: @{message.from_user.username or message.from_user.id}\n"
                            f"💰 Сумма: {usdt_amount} USDT\n"
                            f"🔗 TX ID: <code>{tx_hash}</code>\n\n"
                            f"Проверить: https://tronscan.org/#/transaction/{tx_hash}"
                        )
                        
                        for admin_id in ADMIN_IDS:
                            try:
                                await bot.send_message(admin_id, admin_message, parse_mode="HTML")
                            except:
                                pass
                else:
                    # API не настроен, ожидаем ручной проверки
                    await message.answer(
                        "✅ <b>TX ID получен!</b>\n\n"
                        "Администратор проверит платеж вручную. Это может занять некоторое время.\n"
                        "Вы получите уведомление, когда платеж будет подтвержден.",
                        parse_mode="HTML"
                    )
                    
                    # Уведомляем админов о необходимости ручной проверки
                    admin_message = (
                        f"🔍 <b>Требуется ручная проверка платежа</b>\n\n"
                        f"🆔 Заказ: #{order_id}\n"
                        f"👤 Пользователь: @{message.from_user.username or message.from_user.id}\n"
                        f"🔗 TX ID: <code>{tx_hash}</code>\n\n"
                        f"Проверить вручную: https://tronscan.org/#/transaction/{tx_hash}"
                    )
                    
                    for admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(admin_id, admin_message, parse_mode="HTML")
                        except:
                            pass
            else:
                await message.answer("❌ Ошибка: информация о платеже не найдена")
                
    except Exception as e:
        logger.error(f"Error processing TX ID: {e}")
        await message.answer("❌ Ошибка при обработке TX ID. Попробуйте еще раз или обратитесь в поддержку.")
    
    await state.finish()



@dp.callback_query_handler(lambda c: c.data.startswith("check_crypto_"), state=Purchase.waiting_for_crypto_payment)
async def check_cryptobot_payment_status(callback: types.CallbackQuery):
    """Проверка статуса CryptoBot платежа через callback check_crypto_{order_id}"""
    # Формат: check_crypto_{order_id}
    parts = callback.data.split("_")
    order_id = int(parts[2])
    
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Получаем информацию о заказе с CryptoBot инвойсом
            order_info = await (await db.execute(
                """SELECT status, payment_invoice_id, payment_method 
                   FROM orders WHERE id = ?""", 
                (order_id,)
            )).fetchone()
            
            if not order_info:
                msg = "❌ Order not found" if user_lang == 'en' else "❌ Заказ не найден"
                await callback.answer(msg, show_alert=True)
                return
            
            status, payment_invoice_id, payment_method = order_info
            
            # Проверяем что это CryptoBot платеж
            if payment_method != 'cryptobot':
                msg = "❌ This is not a CryptoBot payment" if user_lang == 'en' else "❌ Это не CryptoBot платеж"
                await callback.answer(msg, show_alert=True)
                return
            
            if status == 'completed':
                # Платеж уже подтвержден - молча выходим без уведомления
                await callback.answer()
                return
            
            if not payment_invoice_id:
                msg = "❌ Invoice not created" if user_lang == 'en' else "❌ Инвойс не создан"
                await callback.answer(msg, show_alert=True)
                return
        
        # Проверяем статус инвойса через CryptoBot API
        from cryptobot import crypto_bot
        
        if not CRYPTOBOT_AVAILABLE or crypto_bot is None:
            msg = "❌ CryptoBot temporarily unavailable" if user_lang == 'en' else "❌ CryptoBot временно недоступен"
            await callback.answer(msg, show_alert=True)
            return
        
        # Получаем статус инвойса
        invoice_status = await crypto_bot.check_invoice(payment_invoice_id)
        
        if invoice_status.get('paid'):
            # Платеж получен - завершаем заказ
            await process_successful_crypto_payment(order_id, callback.from_user.id)
            # Молча закрываем - пользователь получит уведомление от process_successful_crypto_payment
            await callback.answer()
        else:
            # Платеж еще не получен
            msg = "⏳ Payment not received yet. Please complete payment in CryptoBot." if user_lang == 'en' else "⏳ Платеж еще не получен. Пожалуйста, завершите оплату в CryptoBot."
            await callback.answer(msg, show_alert=True)
                
    except Exception as e:
        logger.error(f"Error checking CryptoBot payment status: {e}")
        msg = "❌ Error checking payment" if user_lang == 'en' else "❌ Ошибка при проверке платежа"
        await callback.answer(msg, show_alert=True)

async def complete_direct_payment(order_id: int, tx_hash: str, user_id: int):
    """Завершение прямого платежа"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Обновляем статус заказа
            await db.execute(
                """UPDATE orders SET 
                   status = 'completed', 
                   updated_at = datetime('now'),
                   tx_hash = ?
                   WHERE id = ?""",
                (tx_hash, order_id)
            )
            
            # Обновляем статус прямого платежа
            await db.execute(
                """UPDATE direct_payments SET 
                   status = 'completed',
                   confirmed_at = datetime('now')
                   WHERE order_id = ?""",
                (order_id,)
            )
            
            await db.commit()
            
            # Получаем информацию о заказе для уведомления
            order_info = await (await db.execute(
                """SELECT product_name, quantity, final_price 
                   FROM orders WHERE id = ?""",
                (order_id,)
            )).fetchone()
            
            if order_info:
                product_name, quantity, final_price = order_info
                
                # Уведомляем пользователя
                success_message = (
                    f"✅ <b>Платеж подтвержден!</b>\n\n"
                    f"🆔 Заказ: #{order_id}\n"
                    f"🎁 Товар: {product_name}\n"
                    f"⚖️ Количество: {quantity}г\n"
                    f"💰 Сумма: {final_price} €\n\n"
                    f"📦 <b>Заказ обрабатывается...</b>\n"
                    f"Ожидайте информацию о выдаче товара."
                )
                
                try:
                    await bot.send_message(user_id, success_message, parse_mode="HTML")
                except:
                    pass
                
                # Логируем
                await log_order_action(
                    order_id,
                    "DIRECT_PAYMENT_CONFIRMED",
                    f"TX Hash: {tx_hash[:20]}..., User: {user_id}"
                )
                
                # Уведомляем админов
                admin_message = (
                    f"✅ <b>Прямой платеж подтвержден</b>\n\n"
                    f"🆔 Заказ: #{order_id}\n"
                    f"👤 Пользователь: {user_id}\n"
                    f"💰 Сумма: {final_price} €\n"
                    f"🔗 TX Hash: <code>{tx_hash[:20]}...</code>\n\n"
                    f"Время: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                )
                
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id, admin_message, parse_mode="HTML")
                    except:
                        pass
                        
    except Exception as e:
        logger.error(f"Error completing direct payment: {e}")

async def check_payment_expiry(order_id: int):
    """Проверка истечения времени оплаты"""
    await asyncio.sleep(15 * 60)  # 15 минут
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Проверяем статус заказа
            order_info = await (await db.execute(
                "SELECT status FROM orders WHERE id = ?", (order_id,)
            )).fetchone()
            
            if order_info and order_info[0] == 'pending':
                # Обновляем статус на отмененный
                await db.execute(
                    "UPDATE orders SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?",
                    (order_id,)
                )
                
                # Обновляем статус прямого платежа
                await db.execute(
                    "UPDATE direct_payments SET status = 'expired' WHERE order_id = ?",
                    (order_id,)
                )
                
                await db.commit()
                
                logger.info(f"Order #{order_id} expired - marked as cancelled")
                
    except Exception as e:
        logger.error(f"Error checking payment expiry for order #{order_id}: {e}")


@dp.callback_query_handler(lambda c: c.data == "choose_payment_method", state=Purchase.waiting_for_payment_method)
async def show_payment_options(callback: types.CallbackQuery, state: FSMContext):
    """Показывает доступные способы оплаты"""
    data = await state.get_data()
    final_price = data.get('final_price', 0)
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Проверяем доступность прямой оплаты USDT
    if USDT_SETTINGS.get('is_active') and USDT_SETTINGS.get('address'):
        kb.add(InlineKeyboardButton(
            "💰 Прямая оплата USDT (TRC20)", 
            callback_data="payment_direct_usdt"
        ))
    
    # CryptoBot оплата
    kb.add(InlineKeyboardButton(
        "🤖 CryptoBot (USDT/TRX/BTC)", 
        callback_data="payment_cryptobot"
    ))
    
    # Карта (старая оплата)
    kb.add(InlineKeyboardButton(
        "💳 Банковская карта", 
        callback_data="payment_card"
    ))
    
    kb.add(InlineKeyboardButton(
        "❌ Отмена", 
        callback_data="cancel_payment"
    ))
    
    text = (
        f"💳 <b>Выберите способ оплаты</b>\n\n"
        f"💰 Сумма к оплате: <b>{final_price} €</b>\n\n"
        f"<b>Доступные методы:</b>\n"
    )
    
    if USDT_SETTINGS.get('is_active'):
        text += "• <b>💰 Прямая оплата USDT</b> - быстрая оплата через блокчейн Tron\n"
    
    text += "• <b>🤖 CryptoBot</b> - автоматическая оплата через Telegram бота\n"
    text += "• <b>💳 Банковская карта</b> - классический способ оплаты\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

async def process_cryptobot_payment(callback: types.CallbackQuery, state: FSMContext):
    """Обработка оплаты через CryptoBot"""
    if not CRYPTOBOT_AVAILABLE or crypto_bot is None:
        await callback.answer("❌ CryptoBot temporarily unavailable", show_alert=True)
        return
    
    data = await state.get_data()
    order_id = data['order_id']
    
    # Получаем актуальную цену из базы (уже с промокодом если применен)
    async with aiosqlite.connect('shop.db') as db:
        order_info = await (await db.execute(
            "SELECT final_price, discount_percent FROM orders WHERE id = ?", 
            (order_id,)
        )).fetchone()
    
    if not order_info:
        await callback.answer("❌ Order not found", show_alert=True)
        return
    
    final_price, discount_percent = order_info
    product_name = data['product_name']
    quantity = data['quantity']
    
    # Проверяем, не создан ли уже инвойс
    async with aiosqlite.connect('shop.db') as db:
        existing_invoice = await (await db.execute(
            "SELECT payment_invoice_id FROM orders WHERE id = ? AND payment_invoice_id IS NOT NULL", 
            (order_id,)
        )).fetchone()
        
        if existing_invoice:
            await callback.answer("⚠️ Invoice already created", show_alert=True)
            return
    
    description = f"Order #{order_id}: {product_name} - {quantity}g"
    
    try:
        # Создаем инвойс на текущую цену
        result = await crypto_bot.create_invoice(final_price, "EUR", description)
        if not result.get("success", False):
            error_msg = result.get("error", "Unknown error")
            raise Exception(error_msg)
            
    except Exception as e:
        logs.logger.error(f"CryptoBot invoice error - order_id: {order_id}, Error: {str(e)}")
        await callback.message.answer(f"❌ Payment creation error: {e}\nTry another payment method.")
        return
    
    # Сохраняем инвойс
    async with aiosqlite.connect('shop.db') as db:
        await db.execute(
            "UPDATE orders SET payment_method='cryptobot', payment_invoice_id=? WHERE id=?",
            (result["invoice_id"], order_id)
        )
        await db.commit()
    
    expires_at = datetime.now() + timedelta(minutes=15)
    expires_time = expires_at.strftime("%d.%m %H:%M")
    
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        text = f"🤖 <b>CryptoBot Payment</b>\n\n"
        text += f"🎁 Product: {product_name}\n"
        text += f"⚖️ Quantity: {quantity}g\n"
        text += f"💶 Amount: {final_price:.2f} €\n"
        
        if discount_percent and discount_percent > 0:
            original_price = final_price / (1 - discount_percent / 100)
            text += f"🎁 Discount: {discount_percent}%\n"
            text += f"💶 Original: {original_price:.2f} € → Final: {final_price:.2f} €\n"
        
        text += f"💱 Exchange rate: {result.get('exchange_rate', 1.24):.2f}\n"
        text += f"🪙 To pay: {result['amount_usdt']:.2f} USDT\n\n"
        text += f"⏰ Payment deadline: until {expires_time} (15 minutes)\n\n"
        text += f"👇 Click below to pay:"
    else:
        text = f"🤖 <b>Оплата через CryptoBot</b>\n\n"
        text += f"🎁 Товар: {product_name}\n"
        text += f"⚖️ Количество: {quantity}г\n"
        text += f"💶 Сумма: {final_price:.2f} €\n"
        
        if discount_percent and discount_percent > 0:
            original_price = final_price / (1 - discount_percent / 100)
            text += f"🎁 Скидка: {discount_percent}%\n"
            text += f"💶 Исходная: {original_price:.2f} € → Финальная: {final_price:.2f} €\n"
        
        text += f"💱 Курс: {result.get('exchange_rate', 1.24):.2f}\n"
        text += f"🪙 К оплате: {result['amount_usdt']:.2f} USDT\n\n"
        text += f"⏰ Срок оплаты: до {expires_time} (15 минут)\n\n"
        text += f"👇 Нажмите ниже для оплаты:"
    
    if hasattr(crypto_bot, 'instructions_url'):
        text += f"\n📖 <a href='{crypto_bot.instructions_url}'>INSTRUCTION</a>"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "💳 Pay via CryptoBot", 
        url=result["pay_url"]
    ))
    kb.add(types.InlineKeyboardButton(
        "🔄 Check payment", 
        callback_data=f"check_crypto_{order_id}"
    ))
    kb.add(types.InlineKeyboardButton(
        "❌ Cancel order", 
        callback_data="cancel_order"
    ))
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await Purchase.waiting_for_crypto_payment.set()
    
    await log_order_action(order_id, "CRYPTOBOT_INVOICE_CREATED", 
                          f"Invoice ID: {result['invoice_id']}, Price: {final_price} €")
    
    # Отправляем лог
    await send_cryptobot_log(
        order_id, 
        callback.from_user.id, 
        final_price, 
        result['amount_usdt'], 
        result['invoice_id'],
        "created"
    )
    
    await callback.answer()




@dp.callback_query_handler(lambda c: c.data == "payment_cryptobot", state=Purchase.waiting_for_payment_method)
async def handle_cryptobot_payment(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки CryptoBot с учетом промокода"""
    await process_cryptobot_payment(callback, state)


@dp.message_handler(commands=['cryptorates'])
async def crypto_rates_command(message: types.Message):
    from cryptobot import crypto_bot
    
    if crypto_bot is None:
        await message.answer("❌ CryptoBot не инициализирован")
        return
    
    try:
        rates_message = await crypto_bot.get_network_rates_message()
        await message.answer(rates_message, parse_mode='HTML')
    except Exception as e:
        await message.answer(f"❌ Ошибка получения курсов: {str(e)}")

@dp.message_handler(commands=['cryptotest'])
async def cryptotest_command(message: types.Message):
    from cryptobot import crypto_bot
    
    if crypto_bot is None:
        await message.answer("❌ CryptoBot не инициализирован")
        return
    
    result = await crypto_bot.create_invoice(10.0, "EUR", "Test invoice")
    
    if result["success"]:
        text = f"✅ <b>Тестовый инвойс создан!</b>\n\n"
        text += f"💰 <b>Сумма:</b> {result['amount_eur']} EUR\n"
        text += f"💵 <b>В USDT:</b> {result['amount_usdt']:.2f} USDT\n\n"
        text += f"💱 <b>Курсы:</b>\n"
        
        for asset, amount in result['crypto_amounts'].items():
            if asset != "USDT":  # USDT уже показали выше
                text += f"• {asset}: {amount:.6f}\n"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("💳 Оплатить тест", url=result["pay_url"]))
        kb.add(types.InlineKeyboardButton("📊 Все курсы", callback_data="show_rates"))
        
        await message.answer(text, reply_markup=kb, parse_mode='HTML')
    else:
        await message.answer(f"❌ Ошибка: {result.get('error', 'Unknown error')}")

async def process_legacy_payment(callback: types.CallbackQuery, state: FSMContext, method: str):
    data = await state.get_data()
    order_id = data['order_id']
    
    async with aiosqlite.connect('shop.db') as db:
        payments = await (await db.execute("SELECT usdt,btc,card FROM payments WHERE id=1")).fetchone()
    
    usdt, btc, card = payments
    
    text = f"<b>{get_text(callback.from_user.id, 'ORDER_NUMBER', order_id)}</b>\n"
    text += f"🎁 Товар: {data['product_name']}\n"
    text += f"⚖️ Количество: {data['quantity']}г\n"
    text += f"💶 Общая стоимость: {data['total_price']:.2f} €\n\n"
    
    if method == "card" and card:
        text += f"{get_text(callback.from_user.id, 'CARD_DETAILS', card)}\n"
        payment_method = "CARD"
    else:
        await callback.answer("❌ Этот способ оплаты временно недоступен", show_alert=True)
        return
    
    text += f"\n{get_text(callback.from_user.id, 'PAYMENT_INSTRUCTIONS')}"
    
    async with aiosqlite.connect('shop.db') as db:
        await db.execute(
            "UPDATE orders SET payment_method=? WHERE id=?",
            (payment_method, order_id)
        )
        await db.commit()
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(get_text(callback.from_user.id, 'PROMO_CODE_BTN'), callback_data="use_promo"))
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await Purchase.waiting_for_proof.set()
    await callback.answer()

@dp.message_handler(commands=['checkinvoice'])
async def check_invoice_command(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        invoice_id = int(message.get_args())
    except:
        await message.answer("Usage: /checkinvoice <invoice_id>")
        return
    
    from cryptobot import crypto_bot
    if crypto_bot is None:
        await message.answer("❌ CryptoBot not initialized")
        return
    
    result = await crypto_bot.check_invoice(invoice_id)
    await message.answer(f"Invoice #{invoice_id}:\n```{json.dumps(result, indent=2)}```", parse_mode="Markdown")

@dp.message_handler(commands=['logs'])
async def send_logs_file(message: types.Message):
    """Отправка файла с логами админам"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    log_file = 'logs.txt'
    
    try:
        # Проверяем существование файла
        if not os.path.exists(log_file):
            await message.answer("❌ Файл логов не найден")
            return
        
        # Проверяем размер файла
        file_size = os.path.getsize(log_file)
        if file_size == 0:
            await message.answer("📝 Файл логов пуст")
            return
        
        # Отправляем файл
        with open(log_file, 'rb') as file:
            await message.answer_document(
                document=file,
                caption=f"📊 Логи бота\n📁 Размер: {file_size} байт\n⏰ Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        logs.logger.info("Logs file sent", user_id=message.from_user.id, details="Admin requested logs")
        
    except Exception as e:
        error_msg = f"❌ Ошибка при отправке логов: {e}"
        await message.answer(error_msg)
        logs.logger.errorr(f"Error sending logs file", user_id=message.from_user.id, details=f"Error: {e}")
@dp.message_handler(commands=['tp'])
async def support_panel_command(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем доступ (админы и воркеры)
    if user_id not in ADMIN_IDS and user_id not in SUPPORT_WORKER_IDS:
        await message.answer("❌ У вас нет доступа к этой команде")
        return
    
    await show_support_panel(message)

@dp.message_handler(commands=['status'])
async def status_command_handler(message: types.Message):
    """Обработчик команды /status для админов"""
    from bot_status import handle_status_command
    await handle_status_command(message)

@dp.callback_query_handler(lambda c: c.data.startswith("set_status_"))
async def status_callback_handler(callback: types.CallbackQuery):
    """Обработчик кнопок изменения статуса"""
    from bot_status import set_bot_status
    await set_bot_status(callback)

async def show_support_panel(message_or_callback):
    """Универсальная функция для показа панели поддержки"""
    if hasattr(message_or_callback, 'message'):
        # Это CallbackQuery
        user_id = message_or_callback.from_user.id
        message = message_or_callback.message
    else:
        # Это Message
        user_id = message_or_callback.from_user.id
        message = message_or_callback
    
    current_status = SUPPORT_STATUS.get(user_id, "offline")
    user_lang = USER_LANG.get(user_id, 'ru')
    
    kb = InlineKeyboardMarkup(row_width=2)
    
    if user_lang == 'en':
        if current_status == "offline":
            kb.add(InlineKeyboardButton("🟢 Go Online", callback_data="support_online"))
        else:
            kb.add(InlineKeyboardButton("🔴 Go Offline", callback_data="support_offline"))
        
        kb.add(InlineKeyboardButton("📊 Support Status", callback_data="support_status"))
        kb.add(InlineKeyboardButton("◀️ Back", callback_data="back_main"))
        
        text = "👨‍💼 <b>Support Panel</b>\n\n"
        text += f"📊 Your current status: {'🟢 Online' if current_status == 'online' else '🔴 Offline'}\n\n"
        text += "Choose action:"
    else:
        if current_status == "offline":
            kb.add(InlineKeyboardButton("🟢 Стать онлайн", callback_data="support_online"))
        else:
            kb.add(InlineKeyboardButton("🔴 Стать оффлайн", callback_data="support_offline"))
        
        kb.add(InlineKeyboardButton("📊 Статус поддержки", callback_data="support_status"))
        kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back_main"))
        
        text = "👨‍💼 <b>Панель техподдержки</b>\n\n"
        text += f"📊 Ваш текущий статус: {'🟢 Онлайн' if current_status == 'online' else '🔴 Оффлайн'}\n\n"
        text += "Выберите действие:"
    
    # Отправляем или редактируем сообщение в зависимости от типа
    if hasattr(message_or_callback, 'message'):
        # CallbackQuery - используем safe_edit_message
        await safe_edit_message(message_or_callback, text, reply_markup=kb, parse_mode="HTML")
    else:
        # Message - отправляем новое сообщение
        await message.answer(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query_handler(lambda c: c.data == "contact_support", state="*")
async def contact_support_start(callback: types.CallbackQuery):
    # Проверяем есть ли онлайн поддержка
    online_support = [uid for uid, status in SUPPORT_STATUS.items() if status == "online"]
    
    if not online_support:
        if USER_LANG.get(callback.from_user.id, 'ru') == 'en':
            await callback.answer("❌ No online support at the moment", show_alert=True)
        else:
            await callback.answer("❌ Сейчас нет онлайн поддержки", show_alert=True)
        return
    
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        text = "💬 <b>Contact Support</b>\n\n"
        text += "Write your message and it will be sent to online support.\n"
        text += "You can send text or photo with problem description."
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_support_message"))
    else:
        text = "💬 <b>Написать в поддержку</b>\n\n"
        text += "Напишите ваше сообщение, и оно будет отправлено онлайн поддержке.\n"
        text += "Вы можете отправить текст или фото с описанием проблемы."
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Отменить", callback_data="cancel_support_message"))
    
    await safe_edit_message(callback, text, reply_markup=kb, parse_mode="HTML")
    await SupportPanel.waiting_for_support_message.set()
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "cancel_support_message", state=SupportPanel.waiting_for_support_message)
async def cancel_support_message(callback: types.CallbackQuery, state: FSMContext):
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        await callback.answer("❌ Message sending cancelled")
    else:
        await callback.answer("❌ Отправка сообщения отменена")
    
    await state.finish()
    await show_info(callback, state)

@dp.message_handler(content_types=['text', 'photo'], state=SupportPanel.waiting_for_support_message)
async def process_support_message(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Получаем информацию о пользователе
    async with aiosqlite.connect('shop.db') as db:
        user_info = await (await db.execute(
            "SELECT username, lang FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
    
    username = user_info[0] if user_info else "Unknown"
    user_lang = user_info[1] if user_info and user_info[1] else 'ru'
    
    # Получаем онлайн поддержку
    online_support = [uid for uid, status in SUPPORT_STATUS.items() if status == "online"]
    
    if not online_support:
        if user_lang == 'en':
            await message.answer("❌ Unfortunately, there is no online support at the moment. Try again later.")
        else:
            await message.answer("❌ К сожалению, сейчас нет онлайн поддержки. Попробуйте позже.")
        await state.finish()
        return
    
    # Отправляем сообщение всем онлайн воркерам
    success_sent = 0
    
    for support_id in online_support:
        try:
            # Текст уведомления для воркера
            if user_lang == 'en':
                notification_text = f"🆘 <b>New support request</b>\n\n"
            else:
                notification_text = f"🆘 <b>Новый запрос в поддержку</b>\n\n"
            
            notification_text += f"👤 User: @{username} (ID: {user_id})\n"
            notification_text += f"🌐 Language: {'English' if user_lang == 'en' else 'Russian'}\n\n"
            
            if message.content_type == 'text':
                notification_text += f"📝 Message:\n{message.text}"
                
                # Кнопка для ответа
                kb = InlineKeyboardMarkup()
                if user_lang == 'en':
                    kb.add(InlineKeyboardButton("💬 Reply to user", url=f"tg://user?id={user_id}"))
                else:
                    kb.add(InlineKeyboardButton("💬 Ответить пользователю", url=f"tg://user?id={user_id}"))
                
                await bot.send_message(support_id, notification_text, reply_markup=kb, parse_mode="HTML")
                success_sent += 1
                
            elif message.content_type == 'photo':
                notification_text += f"📷 Photo message"
                
                # Кнопка для ответа
                kb = InlineKeyboardMarkup()
                if user_lang == 'en':
                    kb.add(InlineKeyboardButton("💬 Reply to user", url=f"tg://user?id={user_id}"))
                else:
                    kb.add(InlineKeyboardButton("💬 Ответить пользователю", url=f"tg://user?id={user_id}"))
                
                await bot.send_photo(
                    support_id, 
                    message.photo[-1].file_id, 
                    caption=notification_text, 
                    reply_markup=kb,
                    parse_mode="HTML"
                )
                success_sent += 1
                
        except Exception as e:
            logging.error(f"Failed to send support message to {support_id}: {e}")
    
    # Уведомляем пользователя
    if success_sent > 0:
        if user_lang == 'en':
            await message.answer(f"✅ Your message has been sent to {success_sent} support specialist(s). They will contact you soon.")
        else:
            await message.answer(f"✅ Ваше сообщение отправлено {success_sent} специалисту(ам) поддержки. С вами свяжутся в ближайшее время.")
    else:
        if user_lang == 'en':
            await message.answer("❌ Failed to send message to support. Please try again later.")
        else:
            await message.answer("❌ Не удалось отправить сообщение в поддержку. Попробуйте позже.")
    
    await state.finish()
    await send_main_menu(message, user_id)

@dp.callback_query_handler(lambda c: c.data == "back_support_panel", state="*")
async def back_to_support_panel(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await show_support_panel(callback)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("support_"))
async def handle_support_actions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    action = callback.data
    
    if action == "support_online":
        await set_support_online(callback)
    elif action == "support_offline":
        await set_support_offline(callback)
    elif action == "support_status":
        await show_support_status(callback)
    
    await callback.answer()

async def set_support_online(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    SUPPORT_STATUS[user_id] = "online"
    
    # Получаем информацию о пользователе
    async with aiosqlite.connect('shop.db') as db:
        user_info = await (await db.execute(
            "SELECT username FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
    
    # ИСПРАВЛЕНИЕ: Используем username из callback если нет в базе
    username = user_info[0] if user_info and user_info[0] else callback.from_user.username
    username_display = f"@{username}" if username else f"ID: {user_id}"
    worker_lang = USER_LANG.get(user_id, 'ru')
    
    # Рассылка ВСЕМ пользователям бота
    async with aiosqlite.connect('shop.db') as db:
        users = await (await db.execute(
            "SELECT user_id, lang FROM users WHERE subscribed = 1"
        )).fetchall()
    
    success_count = 0
    for user_id, lang in users:
        try:
            if lang == 'en':
                notification_text = f"🟢 <b>Support is now available!</b>\n\nSupport worker {username_display} is online and ready to help you."
            else:
                notification_text = f"🟢 <b>Поддержка теперь доступна!</b>\n\nВоркер поддержки {username_display} онлайн и готов вам помочь."
            
            await bot.send_message(user_id, notification_text, parse_mode="HTML")
            success_count += 1
        except Exception as e:
            # Пропускаем ошибки (пользователь заблокировал бота и т.д.)
            continue
    
    # Логируем результат рассылки
    logs.logger.info(f"Support online notification sent", 
                  user_id=callback.from_user.id, 
                  details=f"Sent to {success_count} users")
    
    # Обновляем меню
    await show_support_panel(callback)
    
    # Ответ пользователю в зависимости от его языка
    if worker_lang == 'en':
        await callback.answer("🟢 You are now online! Notification sent to all users.")
    else:
        await callback.answer("🟢 Вы теперь онлайн! Уведомление отправлено всем пользователям.")

async def set_support_offline(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    SUPPORT_STATUS[user_id] = "offline"
    
    # Получаем информацию о пользователе
    async with aiosqlite.connect('shop.db') as db:
        user_info = await (await db.execute(
            "SELECT username FROM users WHERE user_id=?", (user_id,)
        )).fetchone()
    
    # ИСПРАВЛЕНИЕ: Используем username из callback если нет в базе
    username = user_info[0] if user_info and user_info[0] else callback.from_user.username
    username_display = f"@{username}" if username else f"ID: {user_id}"
    worker_lang = USER_LANG.get(user_id, 'ru')
    
    # Рассылка ВСЕМ пользователям бота
    async with aiosqlite.connect('shop.db') as db:
        users = await (await db.execute(
            "SELECT user_id, lang FROM users WHERE subscribed = 1"
        )).fetchall()
    
    success_count = 0
    for user_id, lang in users:
        try:
            if lang == 'en':
                notification_text = f"🔴 <b>Support is now offline</b>\n\nSupport worker {username_display} is now offline. You can still leave a message."
            else:
                notification_text = f"🔴 <b>Поддержка теперь оффлайн</b>\n\nВоркер поддержки {username_display} теперь оффлайн. Вы все еще можете оставить сообщение."
            
            await bot.send_message(user_id, notification_text, parse_mode="HTML")
            success_count += 1
        except Exception as e:
            continue
    
    # Логируем результат рассылки
    logs.logger.info(f"Support offline notification sent", 
                  user_id=callback.from_user.id, 
                  details=f"Sent to {success_count} users")
    
    # Обновляем меню
    await show_support_panel(callback)
    
    # Ответ пользователю в зависимости от его языка
    if worker_lang == 'en':
        await callback.answer("🔴 You are now offline! All users have been notified.")
    else:
        await callback.answer("🔴 Вы теперь оффлайн! Все пользователи уведомлены.")

@dp.callback_query_handler(lambda c: c.data == "support_status", state="*")
async def show_support_status(callback: types.CallbackQuery):
    online_support = []
    
    for support_id, status in SUPPORT_STATUS.items():
        if status == "online":
            async with aiosqlite.connect('shop.db') as db:
                user_info = await (await db.execute(
                    "SELECT username FROM users WHERE user_id=?", (support_id,)
                )).fetchone()
            
            # ИСПРАВЛЕНИЕ: Используем username из базы или из Telegram
            username = user_info[0] if user_info and user_info[0] else "Unknown"
            try:
                # Пытаемся получить информацию о пользователе через Telegram API
                user = await bot.get_chat(support_id)
                if user.username:
                    username = user.username
            except:
                pass
                
            online_support.append(f"👨‍💼 @{username}")
    
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    if user_lang == 'en':
        text = "📊 <b>Support Status</b>\n\n"
        
        if online_support:
            text += "🟢 <b>Currently online:</b>\n" + "\n".join(online_support)
        else:
            text += "🔴 <b>No online support at the moment</b>\n"
            text += "Leave a message and we will reply later."
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("◀️ Back", callback_data="back_support_panel"))
    else:
        text = "📊 <b>Статус поддержки</b>\n\n"
        
        if online_support:
            text += "🟢 <b>Сейчас онлайн:</b>\n" + "\n".join(online_support)
        else:
            text += "🔴 <b>Сейчас нет онлайн поддержки</b>\n"
            text += "Оставьте сообщение, и мы ответим вам позже."
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("◀️ Назад", callback_data="back_support_panel"))
    
    await safe_edit_message(callback, text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "clear_old_invoices")
async def clear_old_invoices(callback: types.CallbackQuery):
    try:
        async with aiosqlite.connect('shop.db') as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cryptobot_logs (
                    order_id INTEGER PRIMARY KEY,
                    log_message_id INTEGER,
                    invoice_id INTEGER,
                    amount_eur REAL,
                    amount_usdt REAL,
                    user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            result = await db.execute("DELETE FROM cryptobot_logs WHERE created_at < datetime('now', '-1 day')")
            deleted_count = result.rowcount
            await db.commit()
        
        await callback.answer(f"✅ Удалено {deleted_count} старых записей")
        await callback.message.edit_text(f"✅ Таблица инвойсов очищена. Удалено записей: {deleted_count}")
        
    except Exception as e:
        logging.error(f"Error clearing old invoices: {e}")
        await callback.answer("❌ Ошибка при очистке", show_alert=True)

async def process_successful_crypto_payment(order_id: int, user_id: int):
    async with aiosqlite.connect('shop.db') as db:
        # Включаем WAL режим для избежания блокировок
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        
        # Получаем информацию о инвойсе
        invoice_info = await (await db.execute(
            "SELECT payment_invoice_id FROM orders WHERE id=?", (order_id,)
        )).fetchone()
        
        # Получаем полную информацию о заказе
        order_info = await (await db.execute("""
            SELECT o.quantity, o.city_id, o.district_id, p.name as product_name, 
                   u.username, o.final_price, o.product_id, 
                   c.name as city_name, d.name as district_name,
                   o.discount_percent
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN users u ON o.user_id = u.user_id
            LEFT JOIN cities c ON o.city_id = c.id
            LEFT JOIN districts d ON o.district_id = d.id
            WHERE o.id=?
        """, (order_id,))).fetchone()
        
        if not order_info:
            logs.logger.error(f"Order not found - order_id: {order_id}")
            return
        
        quantity, city_id, district_id, product_name, username, final_price, product_id, city_name, district_name, discount_percent = order_info
        username_display = f"@{username}" if username else "Пользователь"
        location = f"{city_name}, {district_name}" if district_name else f"{city_name}" if city_name else "Не указано"
        
        # Обновляем статус заказа
        await db.execute(
            "UPDATE orders SET status='completed', expires_at=NULL WHERE id=?", 
            (order_id,)
        )
        await db.commit()
    
    # Обновляем сообщение в логах об оплате
    if invoice_info and invoice_info[0]:
        try:
            await send_cryptobot_log(
                order_id, 
                user_id, 
                final_price, 
                0, 
                invoice_info[0], 
                "paid"
            )
        except Exception as log_error:
            logs.logger.error(f"Error updating paid cryptobot log", 
                            order_id=order_id, details=f"Error: {str(log_error)}")
    
    # Поиск авто-выдачи с правильным количеством
    auto_delivery = None
    if city_id and product_id:
        try:
            auto_delivery = await auto_db.get_available_delivery_for_exact_quantity(
                city_id, district_id, product_id, quantity
            )
        except Exception as e:
            logs.logger.error(f"Error getting auto delivery", 
                            order_id=order_id, details=f"Error: {e}")
    
    if auto_delivery:
        try:
            # Распаковываем 7 значений: id, product_id, photo_file_id, coordinates, description, quantity_grams, price
            delivery_id, delivery_product_id, photo_file_id, coordinates, description, delivery_quantity, delivery_price = auto_delivery
            
            # Координаты находятся в description/caption фото, не в отдельном поле
            # Поэтому не проверяем их наличие здесь
            
            # Помечаем авто-выдачу как использованную
            success = await auto_db.mark_delivery_used(delivery_id, user_id, quantity)
            
            if success:
                # Формируем сообщение для пользователя
                # Координаты находятся в description (подпись к фото)
                coords_to_show = coordinates if coordinates else ""
                description_text = f"📝 {description}\n" if description else ""
                
                # Формируем caption
                user_lang = USER_LANG.get(user_id, 'ru')
                if user_lang == 'en':
                    caption = f"🚚 <b>Your Order!</b>\n\n"
                    caption += f"✅ Payment confirmed for order #ORDER{order_id}\n"
                    caption += f"🎁 Product: {product_name}\n"
                    caption += f"⚖️ Quantity: {quantity}g\n\n"
                    if coords_to_show:
                        caption += f"📍 Coordinates: {coords_to_show}\n"
                    caption += description_text
                    caption += "❤️ Thank you for your purchase!"
                else:
                    caption = f"🚚 <b>Ваш заказ!</b>\n\n"
                    caption += f"✅ Оплата подтверждена для заказа #ORDER{order_id}\n"
                    caption += f"🎁 Товар: {product_name}\n"
                    caption += f"⚖️ Количество: {quantity}г\n\n"
                    if coords_to_show:
                        caption += f"📍 Координаты: {coords_to_show}\n"
                    caption += description_text
                    caption += "❤️ Спасибо за покупку!"
                
                # Отправляем фото или текст
                if photo_file_id and len(photo_file_id) > 20:
                    try:
                        await bot.send_photo(
                            user_id, 
                            photo_file_id, 
                            caption=caption,
                            parse_mode="HTML"
                        )
                    except Exception as photo_error:
                        # Если не удалось отправить фото, отправляем текст
                        logs.logger.warning(f"Failed to send photo, sending text", 
                                          user_id=user_id, order_id=order_id,
                                          details=f"Error: {photo_error}")
                        await bot.send_message(user_id, caption, parse_mode="HTML")
                else:
                    # Если нет фото, отправляем только текст
                    await bot.send_message(user_id, caption, parse_mode="HTML")
                
                # Не отправляем дополнительное сообщение - вся информация уже в caption
                
                # Логируем в админ-чате
                remaining = delivery_quantity - quantity
                status = "🔴 ИСПОЛЬЗОВАН" if remaining == 0 else f"🟢 Осталось: {remaining}г"
                
                log_text = (f"✅ CryptoBot оплата #ORDER{order_id}\n"
                           f"👤 {username_display}\n"
                           f"🎁 {product_name} ({quantity}г)\n"
                           f"💰 {final_price:.2f} €\n")
                
                if discount_percent and discount_percent > 0:
                    original_price = final_price / (1 - discount_percent / 100)
                    log_text += f"🎁 Скидка: {discount_percent}%\n"
                    log_text += f"💶 Исходная: {original_price:.2f} €\n"
                
                log_text += f"📍 {location}\n"
                log_text += f"🚚 АВТО-ВЫДАЧА: Клад #{delivery_id} ({status})"
                
                await bot.send_message(LOG_CHAT_ID, log_text)
                await log_order_action(order_id, "CRYPTOBOT_AUTO_DELIVERY", f"Auto-delivery ID: {delivery_id}")
                
            else:
                # Если не удалось использовать авто-выдачу
                logs.logger.warning(f"Failed to use auto delivery for order", 
                                  order_id=order_id, user_id=user_id)
                await process_manual_crypto_delivery(order_id, user_id, username_display, product_name, quantity, final_price, location, discount_percent)
                
        except Exception as auto_error:
            logs.logger.error(f"Auto delivery processing error", 
                            order_id=order_id, user_id=user_id,
                            details=f"Error: {auto_error}")
            await process_manual_crypto_delivery(order_id, user_id, username_display, product_name, quantity, final_price, location, discount_percent)
            
    else:
        # Нет подходящей авто-выдачи - ручная обработка
        await process_manual_crypto_delivery(order_id, user_id, username_display, product_name, quantity, final_price, location, discount_percent)
    
    # Также обновляем сообщение у пользователя (если оно еще висит)
    try:
        await bot.send_message(user_id, 
                             f"✅ Заказ #ORDER{order_id} успешно оплачен и обработан!\n\n"
                             f"🎁 {product_name} - {quantity}г\n"
                             f"💰 {final_price:.2f} €",
                             parse_mode="HTML")
    except Exception as e:
        logs.logger.warning(f"Failed to send confirmation to user", 
                          user_id=user_id, order_id=order_id, details=f"Error: {e}")

async def process_manual_crypto_delivery(order_id: int, user_id: int, username: str, product_name: str, quantity: int, final_price: float, location: str, discount_percent: int = 0):
    """
    Обрабатывает ручную выдачу для CryptoBot платежей
    """
    log_text = (f"🆘 CryptoBot оплата #ORDER{order_id}\n"
               f"👤 {username}\n"
               f"🎁 {product_name} ({quantity}г)\n"
               f"💰 {final_price:.2f} €\n"
               f"📍 {location}\n\n"
               f"❌ НЕТ АВТО-ВЫДАЧИ!\n"
               f"🚨 СРОЧНО ВЫДАЙТЕ ВРУЧНУЮ!\n"
               f"<b>Ответьте на это сообщение фотографией с кладом!!!</b>")

    await bot.send_message(
        LOG_CHAT_ID,
        log_text,
        parse_mode="HTML"
    )
    
    await bot.send_message(
        user_id, 
        "✅ Оплата получена! Менеджер скоро свяжется с вами для выдачи заказа."
    )
    
    await log_order_action(order_id, "CRYPTOBOT_MANUAL_DELIVERY_NEEDED", "Waiting for manual delivery")

async def check_crypto_payments():
    """Проверка платежей CryptoBot в фоновом режиме"""
    if not CRYPTOBOT_AVAILABLE or crypto_bot is None:
        logs.log_warning("CryptoBot не доступен, проверка платежей остановлена")
        return
        
    logs.log_info("Запущена проверка платежей CryptoBot")
    
    while True:
        try:
            async with aiosqlite.connect('shop.db') as db:
                cursor = await db.execute("PRAGMA table_info(orders)")
                columns = await cursor.fetchall()
                column_names = [column[1] for column in columns]
                
                if 'payment_invoice_id' not in column_names:
                    await asyncio.sleep(60)
                    continue
                
                pending_orders = await (await db.execute("""
                    SELECT o.id, o.payment_invoice_id, o.user_id, o.quantity, o.city_id, o.district_id, o.product_id
                    FROM orders o 
                    WHERE status='pending' AND payment_method='cryptobot' AND payment_invoice_id IS NOT NULL
                """)).fetchall()
            
            for order in pending_orders:
                order_id, invoice_id, user_id, quantity, city_id, district_id, product_id = order
                if invoice_id:
                    try:
                        result = await crypto_bot.check_invoice(invoice_id)
                        
                        if result["paid"]:
                            logs.log_info(f"Платеж CryptoBot подтвержден", order_id=order_id)
                            await process_successful_crypto_payment(order_id, user_id)
                        elif result["status"] == "error":
                            logs.logger.error(f"Ошибка проверки инвойса", order_id=order_id, details=f"Инвойс: {invoice_id}, Ошибка: {result.get('error', 'Неизвестно')}")
                    except Exception as e:
                        logs.logger.error(f"Ошибка проверки инвойса", order_id=order_id, details=f"Инвойс: {invoice_id}, Ошибка: {e}")
                        continue
            
            await asyncio.sleep(30)  # Проверяем каждые 30 секундов
            
        except Exception as e:
            logs.logger.error(f"Ошибка в проверке платежей", details=f"Ошибка: {e}")
            await asyncio.sleep(60)

async def get_location_name(city_id: int, district_id: int) -> str:
    async with aiosqlite.connect('shop.db') as db:
        if district_id:
            location_info = await (await db.execute("""
                SELECT c.name, d.name 
                FROM cities c, districts d 
                WHERE c.id = ? AND d.id = ?
            """, (city_id, district_id))).fetchone()
            if location_info:
                return f"{location_info[0]}, {location_info[1]}"
        else:
            city_name = await (await db.execute("SELECT name FROM cities WHERE id=?", (city_id,))).fetchone()
            if city_name:
                return city_name[0]
    return "Неизвестно"

# В функции cancel_crypto_order ЗАМЕНИТЕ блок после отмены заказа:

@dp.callback_query_handler(lambda c: c.data == "cancel_order", state=[Purchase.waiting_for_payment_method, Purchase.waiting_for_crypto_payment, DirectPayment.waiting_for_payment, DirectPayment.waiting_for_tx_id, DirectPayment.checking_payment, "*"])
async def cancel_crypto_order(callback: types.CallbackQuery, state: FSMContext):
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    # Запрашиваем подтверждение
    if user_lang == 'ru':
        text = "❓ <b>Вы точно хотите отменить платеж?</b>\n\nЗаказ будет отменён и данные удалены."
        yes_btn = "✅ Да, отменить"
        no_btn = "❌ Нет, вернуться"
    else:
        text = "❓ <b>Are you sure you want to cancel payment?</b>\n\nOrder will be cancelled and data deleted."
        yes_btn = "✅ Yes, cancel"
        no_btn = "❌ No, go back"
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(yes_btn, callback_data="confirm_cancel_order"),
        InlineKeyboardButton(no_btn, callback_data="back_to_payment")
    )
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "confirm_cancel_order", state=[Purchase.waiting_for_crypto_payment, DirectPayment.waiting_for_payment, DirectPayment.waiting_for_tx_id, DirectPayment.checking_payment, "*"])
async def confirm_cancel_order(callback: types.CallbackQuery, state: FSMContext):
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if order_id:
        async with aiosqlite.connect('shop.db') as db:
            # Получаем информацию о заказе перед отменой
            order_info = await (await db.execute(
                "SELECT final_price, payment_invoice_id, product_name, quantity FROM orders WHERE id=?", (order_id,)
            )).fetchone()
            
            invoice_info = await (await db.execute(
                "SELECT payment_invoice_id FROM orders WHERE id=?", (order_id,)
            )).fetchone()
            
            await db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
            await db.commit()
        
        if order_info:
            final_price, invoice_id, product_name, quantity = order_info
            
            # Логируем отмену в админ-чат
            try:
                from datetime import datetime
                cancelled_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                log_msg = f"""
🚫 <b>ЗАКАЗ ОТМЕНЕН #{order_id}</b>

👤 <b>Пользователь:</b> {callback.from_user.username or callback.from_user.first_name} (ID: {callback.from_user.id})
📦 <b>Товар:</b> {product_name}
⚖️ <b>Количество:</b> {quantity}г
💰 <b>Сумма:</b> {final_price} €
⏰ <b>Отменен:</b> {cancelled_time}
"""
                await bot.send_message(LOG_CHAT_ID, log_msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to send order cancellation log to admin chat: {e}")
            
            if invoice_id:
                try:
                    logs.logger.info(f"Order cancelled - order_id: {order_id}, invoice_id: {invoice_id}")
                    
                    # Обновляем сообщение в логах
                    await send_cryptobot_log(
                        order_id, 
                        callback.from_user.id, 
                        final_price, 
                        0, 
                        invoice_id, 
                        "cancelled"
                    )
                        
                except Exception as e:
                    logs.logger.error(f"Error processing invoice cancellation - order_id: {order_id}, Error: {str(e)}")
        
        await log_order_action(order_id, "ORDER_CANCELLED", f"User cancelled order {order_id}")
    
    if user_lang == 'ru':
        await callback.message.edit_text("❌ Заказ отменен")
    else:
        await callback.message.edit_text("❌ Order cancelled")
    await state.finish()
    await send_main_menu(callback.message, callback.from_user.id)
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "back_from_crypto_selection", state=Purchase.waiting_for_payment_method)
async def back_from_crypto_selection(callback: types.CallbackQuery, state: FSMContext):
    """Возврат из выбора криптовалюты к выбору метода оплаты"""
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    data = await state.get_data()
    
    # Возвращаемся к экрану выбора метода оплаты
    product_name = data.get('product_name', '')
    quantity = data.get('quantity', 1)
    city_name = data.get('city_name', '')
    district_name = data.get('district_name', '')
    final_price = data.get('final_price', 0)
    discount_percent = data.get('discount_percent', 0)
    original_price = data.get('original_price', final_price)
    
    # Показываем меню выбора метода оплаты
    if user_lang == 'ru':
        text = f"""
<b>Подтверждение покупки</b>

🎁 <b>Товар:</b> {product_name}
⚖️ <b>Количество:</b> {quantity}г
"""
        if discount_percent > 0:
            text += f"💰 <b>Сумма без скидки:</b> <s>{original_price:.2f} €</s>\n"
            text += f"🎁 <b>Скидка:</b> {discount_percent}%\n"
            text += f"💵 <b>Итого:</b> {final_price:.2f} €\n\n"
        else:
            text += f"💶 <b>Сумма:</b> {final_price:.2f} €\n\n"
        
        text += "<b>Выберите способ оплаты:</b>\n"
        text += "🎁 Вы можете применить промокод перед оплатой"
    else:
        text = f"""
<b>Purchase Confirmation</b>

🎁 <b>Product:</b> {product_name}
⚖️ <b>Quantity:</b> {quantity}g
"""
        if discount_percent > 0:
            text += f"💰 <b>Amount without discount:</b> <s>{original_price:.2f} €</s>\n"
            text += f"🎁 <b>Discount:</b> {discount_percent}%\n"
            text += f"💵 <b>Total:</b> {final_price:.2f} €\n\n"
        else:
            text += f"💶 <b>Amount:</b> {final_price:.2f} €\n\n"
        
        text += "<b>Choose payment method:</b>\n"
        text += "🎁 You can apply promo code before payment"
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    if user_lang == 'ru':
        kb.add(
            InlineKeyboardButton("💰 Криптовалютой", callback_data="payment_direct_crypto"),
            InlineKeyboardButton("🤖 CryptoBot", callback_data="payment_cryptobot"),
            InlineKeyboardButton("🎁 Промокод", callback_data="use_promo_before_payment"),
            InlineKeyboardButton("◀️ Назад", callback_data="back_from_order_confirm")
        )
    else:
        kb.add(
            InlineKeyboardButton("💰 Cryptocurrency", callback_data="payment_direct_crypto"),
            InlineKeyboardButton("🤖 CryptoBot", callback_data="payment_cryptobot"),
            InlineKeyboardButton("🎁 Promo code", callback_data="use_promo_before_payment"),
            InlineKeyboardButton("◀️ Back", callback_data="back_from_order_confirm")
        )
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "back_to_payment", state=[Purchase.waiting_for_payment_method, Purchase.waiting_for_crypto_payment, DirectPayment.waiting_for_payment])
async def back_to_payment(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к экрану оплаты"""
    user_lang = USER_LANG.get(callback.from_user.id, 'ru')
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        if user_lang == 'ru':
            await callback.answer("❌ Заказ не найден", show_alert=True)
        else:
            await callback.answer("❌ Order not found", show_alert=True)
        return
    
    # Получаем информацию о платеже
    async with aiosqlite.connect('shop.db') as db:
        payment_data = await (await db.execute(
            "SELECT payment_method FROM orders WHERE id=?", (order_id,)
        )).fetchone()
    
    if payment_data:
        payment_method = payment_data[0]
        
        # Возвращаем пользователя к соответствующему экрану оплаты
        if payment_method and payment_method.startswith('direct_'):
            # Прямая крипто-оплата
            crypto = payment_method.replace('direct_', '')
            from direct_payment import show_payment_details
            
            try:
                await show_payment_details(callback, order_id, crypto, user_lang)
            except Exception as e:
                logs.logger.error(f"Error returning to payment: {e}")
                if user_lang == 'ru':
                    await callback.answer("❌ Ошибка возврата к платежу", show_alert=True)
                else:
                    await callback.answer("❌ Error returning to payment", show_alert=True)
        else:
            # CryptoBot оплата - просто уведомление
            if user_lang == 'ru':
                await callback.answer("✅ Возврат к оплате")
            else:
                await callback.answer("✅ Returned to payment")
    else:
        if user_lang == 'ru':
            await callback.answer("❌ Заказ не найден", show_alert=True)
        else:
            await callback.answer("❌ Order not found", show_alert=True)


async def notify_payment_expiration_warning():
    """Уведомляет пользователей за 15 минут до автоотмены заказа"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=10000")
            
            # Находим заказы, у которых осталось 15 минут до истечения
            # И которые еще не получили предупреждение
            warning_orders = await (await db.execute("""
                SELECT id, user_id, payment_method, payment_expires_at,
                       product_name, quantity, final_price
                FROM orders 
                WHERE status='pending' 
                AND payment_method LIKE 'direct_%'
                AND payment_expires_at IS NOT NULL
                AND datetime(payment_expires_at, '-15 minutes') <= datetime('now')
                AND payment_expires_at > datetime('now')
                AND (expiration_warning_sent IS NULL OR expiration_warning_sent = 0)
            """)).fetchall()
            
            for order_id, user_id, payment_method, expires_at, product_name, quantity, final_price in warning_orders:
                try:
                    # Вычисляем оставшееся время
                    expires_dt = datetime.fromisoformat(expires_at)
                    time_left = expires_dt - datetime.now()
                    minutes_left = int(time_left.total_seconds() / 60)
                    
                    if minutes_left <= 0:
                        continue
                    
                    user_lang = USER_LANG.get(user_id, 'ru')
                    
                    if user_lang == 'en':
                        warning_msg = f"""
⚠️ <b>PAYMENT REMINDER</b>

📦 Order #{order_id}
💰 Amount: {final_price} €
⏰ <b>Time left: {minutes_left} minutes</b>

❗️ If payment is not received, the order will be automatically cancelled in {minutes_left} minutes.

Please complete the payment as soon as possible!
"""
                    else:
                        warning_msg = f"""
⚠️ <b>НАПОМИНАНИЕ ОБ ОПЛАТЕ</b>

📦 Заказ #{order_id}
💰 Сумма: {final_price} €
⏰ <b>Осталось времени: {minutes_left} минут</b>

❗️ Если оплата не будет получена, заказ будет автоматически отменен через {minutes_left} минут.

Пожалуйста, завершите оплату как можно скорее!
"""
                    
                    await bot.send_message(user_id, warning_msg, parse_mode="HTML")
                    
                    # Помечаем, что предупреждение отправлено
                    await db.execute(
                        "UPDATE orders SET expiration_warning_sent = 1 WHERE id = ?",
                        (order_id,)
                    )
                    await db.commit()
                    
                    logs.logger.info(f"Expiration warning sent - order_id: {order_id}, user_id: {user_id}, minutes_left: {minutes_left}")
                    
                except Exception as e:
                    logs.logger.error(f"Failed to send expiration warning - order_id: {order_id}, Error: {str(e)}")
                    
    except Exception as e:
        logs.logger.error(f"Error in notify_payment_expiration_warning - Error: {str(e)}")


async def cancel_expired_direct_payments():
    """Автоматически отменяет просроченные прямые крипто-платежи"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            async with aiosqlite.connect('shop.db') as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA busy_timeout=10000")
                
                # Находим просроченные прямые платежи
                expired_orders = await (await db.execute("""
                    SELECT id, user_id, payment_method
                    FROM orders 
                    WHERE status='pending' 
                    AND payment_method LIKE 'direct_%'
                    AND payment_expires_at IS NOT NULL
                    AND payment_expires_at < datetime('now')
                """)).fetchall()
                
                if not expired_orders:
                    if attempt == 0:
                        logs.logger.info("No expired direct payment orders found")
                    break
                
                for order_id, user_id, payment_method in expired_orders:
                    # Получаем информацию о заказе для лога
                    order_details = await (await db.execute("""
                        SELECT o.product_name, o.quantity, o.final_price, 
                               u.username, c.name, d.name
                        FROM orders o
                        JOIN users u ON o.user_id = u.user_id
                        LEFT JOIN cities c ON o.city_id = c.id
                        LEFT JOIN districts d ON o.district_id = d.id
                        WHERE o.id = ?
                    """, (order_id,))).fetchone()
                    
                    await db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
                    await log_order_action(order_id, "DIRECT_PAYMENT_EXPIRED", f"Auto-cancelled due to payment timeout - {payment_method}")
                    
                    # Логируем отмену в админ-чат
                    if order_details:
                        product_name, quantity, final_price, username, city_name, district_name = order_details
                        username_display = f"@{username}" if username else "Пользователь"
                        location = f"{city_name}, {district_name}" if district_name else city_name or "Не указано"
                        
                        try:
                            cancel_msg = f"""
❌ <b>ЗАКАЗ ОТМЕНЕН (ПРОСРОЧЕН)</b> #{order_id}

👤 <b>Пользователь:</b> {username_display} (ID: {user_id})
📦 <b>Товар:</b> {product_name}
⚖️ <b>Количество:</b> {quantity}г
💰 <b>Сумма:</b> {final_price} €
🏙️ <b>Локация:</b> {location}
💳 <b>Метод:</b> {payment_method}
⏱️ <b>Причина:</b> Время оплаты истекло
⏰ <b>Отменен:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""
                            await bot.send_message(LOG_CHAT_ID, cancel_msg, parse_mode="HTML")
                        except Exception as e:
                            logs.logger.error(f"Failed to send cancellation log to admin chat: {e}")
                    
                    try:
                        if user_id in USER_LANG and USER_LANG[user_id] == 'en':
                            await bot.send_message(
                                user_id, 
                                f"❌ Your order #{order_id} has been cancelled because payment was not received within the time limit."
                            )
                        else:
                            await bot.send_message(
                                user_id, 
                                f"❌ Ваш заказ #{order_id} отменен, так как оплата не была получена в течение отведенного времени."
                            )
                        logs.logger.info(f"Direct payment order auto-cancelled - user_id: {user_id}, order_id: {order_id}, method: {payment_method}")
                    except Exception as e:
                        logs.logger.error(f"Failed to notify user about cancelled direct payment - user_id: {user_id}, order_id: {order_id}, Error: {str(e)}")
                
                await db.commit()
                if expired_orders:
                    logs.logger.info(f"Auto-cancelled expired direct payment orders - count: {len(expired_orders)}")
                break
                
        except aiosqlite.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logs.logger.error(f"Failed to cancel expired direct payments - attempts: {attempt + 1}, Error: {str(e)}")
                break
        except Exception as e:
            logs.logger.error(f"Error in cancel_expired_direct_payments - Error: {str(e)}")
            break


async def cancel_expired_crypto_orders():
    """Отменяет просроченные CryptoBot заказы"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            async with aiosqlite.connect('shop.db') as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA busy_timeout=10000")
                
                # Находим заказы с CryptoBot оплатой, которые просрочены более 15 минут
                expired_orders = await (await db.execute("""
                    SELECT id, user_id, payment_invoice_id, final_price 
                    FROM orders 
                    WHERE status='pending' 
                    AND payment_method='cryptobot' 
                    AND payment_invoice_id IS NOT NULL
                    AND created_at < datetime('now', '-15 minutes')
                """)).fetchall()
                
                if not expired_orders:
                    if attempt == 0:
                        logs.logger.info("No expired crypto orders found")
                    break
                
                for order_id, user_id, invoice_id, final_price in expired_orders:
                    await db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (order_id,))
                    await log_order_action(order_id, "CRYPTO_ORDER_CANCELLED", "Auto-cancelled due to payment timeout (15min)")
                    
                    # Обновляем сообщение в логах
                    try:
                        await send_cryptobot_log(order_id, user_id, final_price, 0, invoice_id, "expired")
                    except Exception as log_error:
                        logs.logger.error(f"Error updating cryptobot log - order_id: {order_id}, Error: {str(log_error)}")
                    
                    try:
                        await bot.send_message(
                            user_id, 
                            f"❌ Ваш заказ #{order_id} отменен, так как оплата не была получена в течение 15 минут."
                        )
                        logs.logger.info(f"Crypto order auto-cancelled - user_id: {user_id}, order_id: {order_id}")
                    except Exception as e:
                        logs.logger.error(f"Failed to notify user about cancelled crypto order - user_id: {user_id}, order_id: {order_id}, Error: {str(e)}")
                
                await db.commit()
                if expired_orders:
                    logs.logger.info(f"Auto-cancelled expired crypto orders - count: {len(expired_orders)}")
                break
                
        except aiosqlite.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logs.logger.error(f"Failed to cancel expired crypto orders - attempts: {attempt + 1}, Error: {str(e)}")
                break
        except Exception as e:
            logs.logger.error(f"Error in cancel_expired_crypto_orders - Error: {str(e)}")
            break

async def send_cryptobot_log(order_id: int, user_id: int, amount_eur: float, amount_usdt: float, invoice_id: int, action: str = "created"):
    """
    Отправляет/обновляет сообщение в логах CryptoBot
    """
    try:
        # Сначала обновляем структуру таблицы
        await update_cryptobot_logs_table()
        
        # Определяем текст в зависимости от действия
        if action == "created":
            emoji = "🆕"
            status_text = "создан"
            expiry_time = (datetime.now() + timedelta(hours=24)).strftime('%d.%m %H:%M')
        elif action == "paid":
            emoji = "✅"
            status_text = "оплачен"
            expiry_time = "Оплачено"
        elif action == "expired":
            emoji = "❌"
            status_text = "отменен"
            expiry_time = "Истек"
        elif action == "cancelled":
            emoji = "❌"
            status_text = "отменен"
            expiry_time = "Отменен"
        else:
            emoji = "📊"
            status_text = action
            expiry_time = "Неизвестно"
        
        # Получаем информацию о пользователе
        async with aiosqlite.connect('shop.db') as db:
            user_info = await (await db.execute(
                "SELECT username FROM users WHERE user_id = ?", (user_id,)
            )).fetchone()
        
        username = f"@{user_info[0]}" if user_info and user_info[0] else f"ID: {user_id}"
        
        # Формируем текст сообщения
        text = (f"{emoji} CryptoBot инвойс {status_text} #ORDER{order_id}\n"
                f"👤 Пользователь: {username}\n"
                f"💰 Сумма: {amount_eur:.2f} € | {amount_usdt:.2f} USDT\n"
                f"🆔 Инвойс: #{invoice_id}\n"
                f"⏰ Статус: {expiry_time}")
        
        async with aiosqlite.connect('shop.db') as db:
            # Создаем таблицу если не существует
            await db.execute("""
                CREATE TABLE IF NOT EXISTS cryptobot_logs (
                    order_id INTEGER PRIMARY KEY,
                    log_message_id INTEGER,
                    invoice_id INTEGER UNIQUE,
                    amount_eur REAL,
                    amount_usdt REAL,
                    user_id INTEGER,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # ПРОСТОЙ ПОДХОД: всегда ищем по order_id
            existing = await (await db.execute(
                "SELECT log_message_id FROM cryptobot_logs WHERE order_id = ?", (order_id,)
            )).fetchone()
            
            if existing and existing[0]:
                message_id = existing[0]
                try:
                    # Пытаемся отредактировать существующее сообщение
                    await bot.edit_message_text(
                        chat_id=LOG_CHAT_ID,
                        message_id=message_id,
                        text=text
                    )
                    
                    # Обновляем запись в базе
                    await db.execute("""
                        UPDATE cryptobot_logs 
                        SET invoice_id = ?, amount_eur = ?, amount_usdt = ?, user_id = ?, status = ?, updated_at = datetime('now')
                        WHERE order_id = ?
                    """, (invoice_id, amount_eur, amount_usdt, user_id, action, order_id))
                    await db.commit()
                    
                    logs.logger.info(f"CryptoBot log UPDATED - order_id: {order_id}, action: {action}")
                    return True
                    
                except Exception as e:
                    error_msg = str(e)
                    if "message to edit not found" in error_msg:
                        logs.logger.warning(f"Message not found, will create new - order_id: {order_id}")
                        # Удаляем старую запись и создаем новую
                        await db.execute("DELETE FROM cryptobot_logs WHERE order_id = ?", (order_id,))
                        await db.commit()
                    else:
                        logs.logger.warning(f"Edit failed, will create new - order_id: {order_id}, error: {error_msg}")
            
            # Создаем новое сообщение
            message = await bot.send_message(LOG_CHAT_ID, text)
            
            # Сохраняем в базу
            await db.execute("""
                INSERT OR REPLACE INTO cryptobot_logs 
                (order_id, log_message_id, invoice_id, amount_eur, amount_usdt, user_id, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id, message.message_id, invoice_id, amount_eur, amount_usdt, user_id, action))
            await db.commit()
            
            logs.logger.info(f"CryptoBot log CREATED - order_id: {order_id}, action: {action}")
            return True
            
    except Exception as e:
        logs.logger.error(f"Error in send_cryptobot_log - order_id: {order_id}, Error: {str(e)}")
        
        # Резервный вариант - просто отправить сообщение
        try:
            await bot.send_message(LOG_CHAT_ID, text)
            return True
        except Exception as fallback_error:
            logs.logger.error(f"Fallback also failed - order_id: {order_id}, Fallback error: {str(fallback_error)}")
            return False

async def update_cryptobot_logs_table():
    """
    Простое обновление структуры таблицы cryptobot_logs
    """
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Проверяем существующие колонки
            cursor = await db.execute("PRAGMA table_info(cryptobot_logs)")
            columns = await cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            # Добавляем недостающие колонки
            if 'status' not in column_names:
                await db.execute("ALTER TABLE cryptobot_logs ADD COLUMN status TEXT")
                logs.logger.info("Added status column to cryptobot_logs")
            
            if 'updated_at' not in column_names:
                await db.execute("ALTER TABLE cryptobot_logs ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                logs.logger.info("Added updated_at column to cryptobot_logs")
            
            await db.commit()
            return True
    except Exception as e:
        logs.logger.error(f"Error updating cryptobot_logs table: {e}")
        return False


# =============================================
# ДОБАВИТЬ ЭТИ ФУНКЦИИ В MAIN.PY
# =============================================

import os
import aiohttp
import re
from logs import logger

async def safe_return_to_menu(message_or_callback, user_id: int, state: FSMContext = None, error_message: str = None):
    """
    Безопасный возврат в главное меню из любого состояния
    """
    try:
        # Завершаем состояние если оно есть
        if state:
            try:
                await state.finish()
            except:
                pass
        
        # Показываем сообщение об ошибке если есть
        if error_message:
            try:
                if hasattr(message_or_callback, 'message'):
                    await message_or_callback.message.answer(error_message)
                else:
                    await message_or_callback.answer(error_message)
            except:
                pass
        
        # Возвращаем в главное меню
        try:
            if hasattr(message_or_callback, 'message'):
                await send_main_menu(message_or_callback.message, user_id)
            else:
                await send_main_menu(message_or_callback, user_id)
        except Exception as e:
            # Последняя попытка отправить сообщение
            try:
                error_text = "🚫 Произошла ошибка. Используйте /start для перезапуска бота."
                if hasattr(message_or_callback, 'message'):
                    await message_or_callback.message.answer(error_text)
                else:
                    await message_or_callback.answer(error_text)
            except:
                pass
                
    except Exception as e:
        logs.logger.error(f"Error in safe_return_to_menu", user_id=user_id, details=str(e))

def validate_user_input(text: str, max_length: int = 100) -> bool:
    """Валидация пользовательского ввода"""
    if not text or len(text) > max_length:
        return False
    # Запрещаем опасные символы
    dangerous_chars = [';', '--', '/*', '*/', 'xp_', '%20', 'drop table', 'delete from', 'update ', 'insert into']
    text_lower = text.lower()
    return not any(char in text_lower for char in dangerous_chars)

async def log_suspicious_activity(user_id: int, action: str, details: str):
    """Логирование подозрительной активности"""
    suspicious_patterns = [
        "DROP TABLE", "DELETE FROM", "UPDATE users", 
        "INSERT INTO users", "SELECT * FROM", "UNION SELECT",
        "drop table", "delete from", "update users", "insert into"
    ]
    
    is_suspicious = any(pattern in details.upper() for pattern in suspicious_patterns)
    
    if is_suspicious:
        alert_msg = f"🚨 ПОДОЗРИТЕЛЬНАЯ АКТИВНОСТЬ\nUser: {user_id}\nAction: {action}\nDetails: {details}"
        try:
            await bot.send_message(LOG_CHAT_ID, alert_msg)
        except:
            pass
    
    logs.logger.warning(f"Suspicious activity", user_id=user_id, details=f"{action}: {details}")

async def backup_database():
    """
    Создает резервную копию базы данных
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup/shop_backup_{timestamp}.db"
        
        # Создаем папку backup если её нет
        os.makedirs("backup", exist_ok=True)
        
        async with aiosqlite.connect('shop.db') as source:
            async with aiosqlite.connect(backup_file) as backup:
                await source.backup(backup)
        
        logging.info(f"✅ Database backup created: {backup_file}")
        
        # Удаляем старые резервные копии (оставляем последние 7)
        try:
            backup_files = sorted(glob.glob("backup/shop_backup_*.db"))
            if len(backup_files) > 7:
                for old_file in backup_files[:-7]:
                    os.remove(old_file)
                    logging.info(f"🗑️ Removed old backup: {old_file}")
        except Exception as e:
            logging.error(f"Error cleaning old backups: {e}")
                
    except Exception as e:
        logging.error(f"❌ Error creating database backup: {e}")

async def schedule_backups():
    """Планировщик бэкапов"""
    while True:
        await asyncio.sleep(6 * 60 * 60)  # Каждые 6 часов
        await backup_database()

async def safe_db_execute(query: str, params: tuple = ()):
    """Безопасное выполнение SQL запросов"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Включаем foreign keys и другие настройки безопасности
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA secure_delete = ON")
            result = await db.execute(query, params)
            await db.commit()
            return result
    except Exception as e:
        logs.logger.error(f"Database error: {e}")
        return None

async def security_audit():
    """Проверка безопасности при запуске"""
    try:
        checks = [
            os.getenv('BOT_TOKEN') != '7747179125:AAE7dTDtI6l8j-eX_aCNF0XVoaIvP2Yu-70',
            os.getenv('ADMIN_PASSWORD') != 'jopa1337',
            len(os.getenv('ADMIN_PASSWORD', '')) >= 8,
            'BOT_TOKEN' in os.environ,
            'ADMIN_PASSWORD' in os.environ
        ]
        
        security_score = sum(checks)
        
        if security_score < len(checks):
            alert = f"⚠️ ВНИМАНИЕ: Проблемы с безопасностью! Score: {security_score}/{len(checks)}"
            try:
                await bot.send_message(LOG_CHAT_ID, alert)
            except:
                pass
            logs.logger.warning(f"Security audit failed", details=f"Score: {security_score}/{len(checks)}")
        else:
            logs.logger.info("Security audit passed")
            
    except Exception as e:
        logs.logger.error(f"Security audit error: {e}")

async def validate_payment_screenshot(photo_file_id: str, amount_eur: float) -> dict:
    """
    Проверяет скриншот платежа на валидность
    """
    try:
        # В реальном проекте здесь должна быть интеграция с OCR
        # Сейчас используем заглушку
        
        # Ключевые слова для EUR
        eur_keywords = ['eur', '€', 'euro', 'евро', 'євро']
        # Ключевые слова для UAH (гривна)
        uah_keywords = ['uah', '₴', 'грн', 'грив', 'hryvnia', 'гривня']
        # Ключевые слова для Monobank
        monobank_keywords = ['monobank', 'mono', 'mono bank', 'монобанк', 'монобанк']
        # Ключевые слова для PrivatBank
        privatbank_keywords = ['privatbank', 'privat', 'privat bank', 'приватбанк', 'приват']
        
        # Заглушка для OCR результата
        ocr_result = {
            'text': 'example payment screenshot text',
            'confidence': 0.8
        }
        
        text_lower = ocr_result.get('text', '').lower()
        
        # Проверяем валюту
        has_eur = any(keyword in text_lower for keyword in eur_keywords)
        has_uah = any(keyword in text_lower for keyword in uah_keywords)
        
        # Проверяем банки
        has_monobank = any(keyword in text_lower for keyword in monobank_keywords)
        has_privatbank = any(keyword in text_lower for keyword in privatbank_keywords)
        
        # Определяем валюту платежа
        currency = None
        if has_eur:
            currency = "EUR"
        elif has_uah:
            currency = "UAH"
        
        # Определяем банк
        bank = None
        if has_monobank:
            bank = "Monobank"
        elif has_privatbank:
            bank = "PrivatBank"
        
        # Упрощенная проверка суммы (в реальном проекте нужно извлекать из OCR)
        amount_found = amount_eur  # Заглушка
        
        # Валидация в зависимости от валюты
        if currency == "EUR":
            is_amount_valid = True
            validation_message = "✅ EUR платеж проверен"
        elif currency == "UAH":
            exchange_rate = await get_uah_to_eur_rate()
            amount_eur_equivalent = amount_found / exchange_rate
            is_amount_valid = abs(amount_eur_equivalent - amount_eur) <= (amount_eur * 0.1)
            validation_message = f"✅ UAH платеж проверен (курс: {exchange_rate:.2f} UAH/EUR)"
        else:
            is_amount_valid = False
            validation_message = "❌ Не удалось определить валюту платежа"
        
        return {
            'is_valid': is_amount_valid and (has_eur or has_uah),
            'currency': currency,
            'bank': bank,
            'amount_found': amount_found,
            'amount_expected': amount_eur,
            'validation_message': validation_message,
            'confidence': ocr_result.get('confidence', 0)
        }
        
    except Exception as e:
        logger.error(f"Error validating payment screenshot: {e}")
        return {
            'is_valid': False,
            'validation_message': f'❌ Ошибка проверки: {str(e)}',
            'confidence': 0
        }

async def get_uah_to_eur_rate() -> float:
    """
    Получает актуальный курс UAH к EUR
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.privatbank.ua/p24api/pubinfo?json&exchange&coursid=5') as response:
                if response.status == 200:
                    data = await response.json()
                    for rate in data:
                        if rate['ccy'] == 'EUR':
                            return float(rate['sale'])
        
        # Резервный курс если API недоступно
        return 42.0
        
    except Exception as e:
        logger.error(f"Error getting UAH rate: {e}")
        return 42.0

@dp.callback_query_handler(lambda c: c.data.startswith("pay_crypto_"), state=Purchase.waiting_for_payment_method)
async def process_crypto_payment(callback: types.CallbackQuery, state: FSMContext):
    try:
        order_id = int(callback.data.split("_")[2])
        
        async with aiosqlite.connect('shop.db') as db:
            order_info = await (await db.execute(
                "SELECT final_price, product_id, quantity FROM orders WHERE id=?", 
                (order_id,)
            )).fetchone()
            
        if not order_info:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            await safe_return_to_menu(callback, callback.from_user.id, state)
            return
            
        final_price, product_id, quantity = order_info
        
        # Получаем информацию о товаре
        async with aiosqlite.connect('shop.db') as db:
            product_info = await (await db.execute(
                "SELECT name FROM products WHERE id=?", (product_id,)
            )).fetchone()
            
        product_name = product_info[0] if product_info else "Неизвестный товар"
        
        # Создаем инвойс через CryptoBot
        if not CRYPTOBOT_AVAILABLE or crypto_bot is None:
            await callback.answer("❌ CryptoBot временно недоступен", show_alert=True)
            await safe_return_to_menu(callback, callback.from_user.id, state)
            return
            
        invoice_result = await crypto_bot.create_invoice(
            final_price, 
            description=f"Заказ #{order_id}: {product_name} ({quantity}г)"
        )
        
        if not invoice_result["success"]:
            error_msg = invoice_result.get("error", "Неизвестная ошибка")
            await callback.message.answer(
                f"❌ Ошибка создания платежа: {error_msg}\n\n"
                f"Пожалуйста, попробуйте другой способ оплаты или обратитесь в поддержку."
            )
            await safe_return_to_menu(callback, callback.from_user.id, state)
            return
        
        # Сохраняем информацию об инвойсе
        async with aiosqlite.connect('shop.db') as db:
            await db.execute(
                "UPDATE orders SET payment_method='cryptobot', payment_invoice_id=? WHERE id=?",
                (invoice_result["invoice_id"], order_id)
            )
            await db.commit()
        
        # Показываем инструкции по оплате
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("💳 Оплатить", url=invoice_result["pay_url"]),
            InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_crypto_{order_id}")
        )
        kb.add(InlineKeyboardButton("❌ Отменить заказ", callback_data=f"cancel_order_{order_id}"))
        kb.add(InlineKeyboardButton("🏠 В главное меню", callback_data="back_main"))
        
        text = f"🤖 <b>Оплата через CryptoBot</b>\n\n"
        text += f"💶 Сумма: {final_price} €\n"
        text += f"🪙 К оплате: ~{invoice_result['amount_usdt']:.2f} USDT\n"
        text += f"⏰ Время на оплату: 15 минут\n\n"
        text += f"👇 Нажмите кнопку ниже для оплаты:"
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await Purchase.waiting_for_crypto_payment.set()
        
    except Exception as e:
        logs.logger.error(f"Error in crypto payment process", user_id=callback.from_user.id, details=str(e))
        await callback.message.answer(
            "❌ Произошла ошибка при создании платежа. Пожалуйста, попробуйте другой способ оплаты."
        )
        await safe_return_to_menu(callback, callback.from_user.id, state)
    
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("check_crypto_"), state=Purchase.waiting_for_crypto_payment)
async def check_crypto_payment(callback: types.CallbackQuery, state: FSMContext):
    try:
        order_id = int(callback.data.split("_")[2])
        
        async with aiosqlite.connect('shop.db') as db:
            order_info = await (await db.execute(
                "SELECT payment_invoice_id, user_id FROM orders WHERE id=?", 
                (order_id,)
            )).fetchone()
            
        if not order_info:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            await safe_return_to_menu(callback, callback.from_user.id, state)
            return
            
        invoice_id, user_id = order_info
        
        if not CRYPTOBOT_AVAILABLE or crypto_bot is None:
            await callback.answer("❌ CryptoBot временно недоступен", show_alert=True)
            await safe_return_to_menu(callback, callback.from_user.id, state)
            return
            
        # Проверяем статус платежа
        payment_status = await crypto_bot.check_invoice(invoice_id)
        
        if payment_status.get("paid"):
            await callback.answer("✅ Оплата получена! Обрабатываем заказ...", show_alert=True)
            # Здесь должна быть дальнейшая обработка успешного платежа
            # Пока просто возвращаем в меню
            await safe_return_to_menu(callback, callback.from_user.id, state)
        else:
            status = payment_status.get("status", "unknown")
            await callback.answer(f"❌ Платеж еще не получен. Статус: {status}", show_alert=True)
            
    except Exception as e:
        logs.logger.error(f"Error checking crypto payment", user_id=callback.from_user.id, details=str(e))
        await callback.answer("❌ Ошибка проверки платежа", show_alert=True)
        await safe_return_to_menu(callback, callback.from_user.id, state)

@dp.callback_query_handler(lambda c: c.data.startswith("pay_uah_"), state=Purchase.waiting_for_payment_method)
async def process_uah_payment(callback: types.CallbackQuery, state: FSMContext):
    try:
        order_id = int(callback.data.split("_")[2])
        
        async with aiosqlite.connect('shop.db') as db:
            order_info = await (await db.execute(
                "SELECT final_price FROM orders WHERE id=?", (order_id,)
            )).fetchone()
            
        if not order_info:
            await callback.answer("❌ Заказ не найден", show_alert=True)
            await safe_return_to_menu(callback, callback.from_user.id, state)
            return
            
        final_price = order_info[0]
        uah_rate = await get_uah_to_eur_rate()
        amount_uah = final_price * uah_rate
        
        user_lang = USER_LANG.get(callback.from_user.id, 'ru')
        
        if user_lang == 'en':
            text = f"₴ <b>Payment in Ukrainian Hryvnia (UAH)</b>\n\n"
            text += f"💶 Amount in EUR: {final_price} €\n"
            text += f"💱 Exchange rate: 1 EUR = {uah_rate:.2f} UAH\n"
            text += f"₴ <b>Amount to pay: {amount_uah:.2f} UAH</b>\n\n"
            text += "<b>Supported banks:</b>\n"
            text += "• Monobank\n"
            text += "• PrivatBank\n"
            text += "• Other Ukrainian banks\n\n"
            text += "👇 <b>Please send screenshot after payment</b>"
        else:
            text = f"₴ <b>Оплата в гривнах (UAH)</b>\n\n"
            text += f"💶 Сумма в EUR: {final_price} €\n"
            text += f"💱 Курс обмена: 1 EUR = {uah_rate:.2f} UAH\n"
            text += f"₴ <b>Сумма к оплате: {amount_uah:.2f} UAH</b>\n\n"
            text += "<b>Поддерживаемые банки:</b>\n"
            text += "• Monobank\n"
            text += "• PrivatBank\n"
            text += "• Другие украинские банки\n\n"
            text += "👇 <b>Отправьте скриншот после оплаты</b>"
        
        # Обновляем способ оплаты в базе
        async with aiosqlite.connect('shop.db') as db:
            await db.execute(
                "UPDATE orders SET payment_method='uah_bank' WHERE id=?",
                (order_id,)
            )
            await db.commit()
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            get_text(callback.from_user.id, 'BACK_BTN'), 
            callback_data="back_main"
        ))
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await Purchase.waiting_for_proof.set()
        
    except Exception as e:
        logger.error(f"Error processing UAH payment: {e}")
        await callback.answer("❌ Ошибка при обработке платежа", show_alert=True)
        await safe_return_to_menu(callback, callback.from_user.id, state)
    
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "force_back_main", state="*")
async def force_back_to_main(callback: types.CallbackQuery, state: FSMContext):
    """Принудительный возврат в главное меню из любого состояния"""
    await safe_return_to_menu(callback, callback.from_user.id, state)


# Хэндлер для неизвестных команд
# Хэндлер для любого текста (не команды)
@dp.message_handler(content_types=types.ContentType.TEXT, state="*")
async def handle_any_text(message: types.Message, state: FSMContext):
    """Обработка любого текстового сообщения"""
    
    # Пропускаем сообщения из чата логов
    if message.chat.id == LOG_CHAT_ID:
        return
    
    user_id = message.from_user.id
    
    # Пропускаем для администраторов - они могут писать что угодно
    if user_id in ADMIN_IDS:
        return
    
    # Пропускаем если это состояние ожидания ввода
    current_state = await state.get_state()
    if current_state:
        return  # Пусть другие хэндлеры обрабатывают состояния
    
    # Пропускаем если сообщение слишком длинное (возможно, это не "белеберта")
    if len(message.text) > 50:
        await safe_return_to_menu(message, user_id, state, 
            "📝 Ваше сообщение слишком длинное. Возвращаю в главное меню." if USER_LANG.get(user_id, 'ru') == 'ru' 
            else "📝 Your message is too long. Returning to main menu."
        )
        return
    
    await log_user_action(user_id, "random_text", f"Text: {message.text}", "unknown")
    
    # Получаем язык пользователя
    user_lang = USER_LANG.get(user_id, 'ru')
    
    if user_lang == 'en':
        text = "🤨 <b>What did you write? Return to the menu!</b>\n\n" \
               "If you need help, use the buttons below 👇"
    else:
        text = "🤨 <b>Че ты написал? Вернись в меню!</b>\n\n" \
               "Если нужна помощь - используй кнопки ниже 👇"
    
    kb = InlineKeyboardMarkup(row_width=2)
    
    if user_lang == 'en':
        kb.add(
            InlineKeyboardButton("🏠 Main menu", callback_data="back_main"),
            InlineKeyboardButton("💬 Support", callback_data="contact_support")
        )
        kb.add(
            InlineKeyboardButton("📋 Rules", url="https://telegra.ph/"),
            InlineKeyboardButton("🔄 Change language", callback_data="swap_lang_from_text")
        )
    else:
        kb.add(
            InlineKeyboardButton("🏠 Главное меню", callback_data="back_main"),
            InlineKeyboardButton("💬 Поддержка", callback_data="contact_support")
        )
        kb.add(
            InlineKeyboardButton("📋 Правила", url="https://telegra.ph/"),
            InlineKeyboardButton("🔄 Сменить язык", callback_data="swap_lang_from_text")
        )
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

# Хэндлер для любых других типов контента (фото, видео и т.д.)
@dp.message_handler(content_types=[types.ContentType.PHOTO, types.ContentType.VIDEO, 
                                  types.ContentType.DOCUMENT, types.ContentType.STICKER, 
                                  types.ContentType.VOICE, types.ContentType.VIDEO_NOTE], state="*")
async def handle_other_content(message: types.Message, state: FSMContext):
    """Обработка другого контента (не текст)"""
    
    # Пропускаем сообщения из чата логов
    if message.chat.id == LOG_CHAT_ID:
        return
    
    user_id = message.from_user.id
    
    # Пропускаем если это состояние ожидания ввода
    current_state = await state.get_state()
    if current_state:
        return
    
    await log_user_action(user_id, "random_content", f"Content type: {message.content_type}", "unknown")
    
    user_lang = USER_LANG.get(user_id, 'ru')
    
    if user_lang == 'en':
        text = "📎 <b>I don't understand what you sent</b>\n\n" \
               "Please use the menu buttons for navigation 👇"
    else:
        text = "📎 <b>Я не понимаю, что ты отправил</b>\n\n" \
               "Пожалуйста, используй кнопки меню для навигации 👇"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        "🏠 Главное меню" if user_lang == 'ru' else "🏠 Main menu", 
        callback_data="back_main"
    ))
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

# Хэндлер для неизвестных команд
@dp.message_handler(commands=[], state="*")
async def unknown_command(message: types.Message):
    """Обработка неизвестных команд"""
    
    # Пропускаем сообщения из чата логов
    if message.chat.id == LOG_CHAT_ID:
        return
    
    user_id = message.from_user.id
    await log_user_action(user_id, "unknown_command", f"Command: {message.text}", "unknown")
    
    # Получаем язык пользователя
    user_lang = USER_LANG.get(user_id, 'ru')
    
    if user_lang == 'en':
        text = "❌ <b>Command not recognized</b>\n\n" \
               "Available commands:\n" \
               "/start - Start bot\n" \
               "/swap - Change language\n" \
               "/lang - Current language"
    else:
        text = "❌ <b>Команда не распознана</b>\n\n" \
               "Доступные команды:\n" \
               "/start - Запустить бота\n" \
               "/swap - Сменить язык\n" \
               "/lang - Текущий язык"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        "🏠 Главное меню" if user_lang == 'ru' else "🏠 Main menu", 
        callback_data="back_main"
    ))
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@dp.errors_handler()
async def global_error_handler(update: types.Update, exception: Exception):
    """Глобальный обработчик ошибок"""
    try:
        # Получаем информацию о пользователе
        user_id = None
        update_type = None
        
        if update.message:
            user_id = update.message.from_user.id
            update_type = "message"
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
            update_type = "callback_query"
        elif update.inline_query:
            user_id = update.inline_query.from_user.id
            update_type = "inline_query"
        
        # Используем исправленный логгер
        logs.logger.error(
            f"Global Python Error Handler | Type: {update_type}", 
            user_id=user_id, 
            details=f"Error: {str(exception)}",
            exc_info=True
        )
        
    except Exception as e:
        # Если даже обработчик ошибок сломался
        logging.critical(f"Error handler failed: {e}", exc_info=True)
    
    return True


# =============================================
# КОНЕЦ ДОБАВЛЯЕМЫХ ФУНКЦИЙ
# =============================================


dp.register_callback_query_handler(
    use_promo_before_payment,
    lambda c: c.data == "use_promo_before_payment",
    state=Purchase.waiting_for_payment_method
)

dp.register_callback_query_handler(
    cancel_promo_and_return,
    lambda c: c.data == "cancel_promo_and_return",
    state=PromoCode.waiting_for_promo
)

register_admin_handlers(dp)

# Регистрируем обработчики прямой оплаты (делаем это вручную)

# Обработчик выбора криптовалюты
async def handle_crypto_selection(callback: types.CallbackQuery, state: FSMContext):
    crypto = callback.data.split("_")[1]
    await process_direct_crypto_payment(callback, state, crypto)

dp.register_callback_query_handler(
    handle_crypto_selection,
    lambda c: c.data.startswith("crypto_"),
    state="*"
)

# Обработчики для кнопок "Я оплатил" и "Проверить"
dp.register_callback_query_handler(
    handle_paid_button, 
    lambda c: c.data.startswith("paid_") and "_" in c.data[5:], 
    state="*"
)
dp.register_callback_query_handler(
    check_direct_payment,
    lambda c: c.data.startswith("check_") and "_" in c.data[6:],
    state="*"
)
dp.register_callback_query_handler(
    handle_tx_id_input, 
    lambda c: c.data.startswith("manual_tx_"), 
    state="*"
)

dp.register_message_handler(
    process_tx_id, 
    state=DirectPayment.waiting_for_tx_id
)

# Регистрируем обработчики розыгрышей

if __name__ == '__main__':
    try:
        from aiogram import executor
        executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
    except Exception as e:
        logging.critical(f"Failed to start bot: {e}")
        raise
