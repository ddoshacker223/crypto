import aiosqlite, asyncio
import os  # ДОБАВЬТЕ ЭТОТ ИМПОРТ
import re  # added for robust pagination parsing
import logging
from logs import logger
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta
from dotenv import load_dotenv  # ДОБАВЬТЕ ЭТОТ ИМПОРТ


load_dotenv()

# ИМПОРТ АВТО-ВЫДАЧИ
import data_base as auto_db

def validate_user_input(text: str, max_length: int = 100) -> bool:
    """Валидация пользовательского ввода"""
    if not text or len(text) > max_length:
        return False
    # Запрещаем опасные символы
    dangerous_chars = [';', '--', '/*', '*/', 'xp_', '%20', 'drop table', 'delete from', 'update ', 'insert into', 'select *']
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
        alert_msg = f"🚨 ПОДОЗРИТЕЛЬНАЯ АКТИВНОСТЬ В АДМИНКЕ\nUser: {user_id}\nAction: {action}\nDetails: {details}"
        try:
            await bot.send_message(LOG_CHAT_ID, alert_msg)
        except:
            pass
    
    logger.warning(f"Suspicious activity in admin panel", user_id=user_id, details=f"{action}: {details}")

# Тексты для уведомлений о бане/разбане
BANNED_TEXT_RU = '❌ <b>Доступ запрещен</b> ❌\n\nВы были забанены администратором и больше не можете пользоваться ботом.\n\nДля большей информации обратитесь к нашему сапорту: @ekatwa'
UNBANNED_TEXT_RU = '✅ <b>Доступ восстановлен</b> ✅\n\nВы были разбанены. Теперь вы снова можете пользоваться ботом.'

# ─── FSM STATES FOR ADMIN PANEL ─────────────────────────────────
class AdminAuth(StatesGroup):
    waiting_for_password = State()

class AddCategory(StatesGroup):
    waiting_for_category_name = State()

class AddCity(StatesGroup):
    waiting_for_city_name = State()

class AddDistrict(StatesGroup):
    waiting_for_district_name = State()

class AddProduct(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_media = State()
    waiting_for_stock = State()

class DeleteCategory(StatesGroup):
    waiting_for_category = State()
    waiting_for_confirmation = State()

class DeleteCity(StatesGroup):
    waiting_for_city = State()
    waiting_for_confirmation = State()

class DeleteProduct(StatesGroup):
    waiting_for_product = State()
    waiting_for_confirmation = State()

class EditPayments(StatesGroup):
    waiting_for_usdt = State()
    waiting_for_btc = State()
    waiting_for_card = State()

class EditCryptoWallets(StatesGroup):
    waiting_for_usdt_wallet = State()
    waiting_for_trongrid_api_key = State()

class Broadcast(StatesGroup):
    waiting_for_content = State()
    waiting_for_confirm = State()

class BanUser(StatesGroup):
    waiting_for_id = State()

class UnbanUser(StatesGroup):
    waiting_for_id = State()

class EditStock(StatesGroup):
    waiting_for_product = State()
    waiting_for_stock = State()

class AddPromoCode(StatesGroup):
    waiting_for_code = State()
    waiting_for_discount = State()
    waiting_for_limit = State()
    waiting_for_expiry = State()

class DeletePromoCode(StatesGroup):
    waiting_for_promo = State()
    waiting_for_confirmation = State()

class ViewUsers(StatesGroup):
    waiting_for_user_selection = State()

class ViewOrders(StatesGroup):
    waiting_for_order_selection = State()

# НОВОЕ: Состояния для авто-выдачи
class AutoDelivery(StatesGroup):
    waiting_for_product = State()  
    waiting_for_city = State()
    waiting_for_district = State()
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_quantity = State()  
    waiting_for_price = State()

# НОВОЕ: Состояния для управления скрытыми товарами
class ManageHiddenProducts(StatesGroup):
    waiting_for_action = State()

class DeleteDistrict(StatesGroup):
    waiting_for_city = State()
    waiting_for_district = State()
    waiting_for_confirmation = State()

class SearchAutoPoints(StatesGroup):
    waiting_for_query = State()

# НОВОЕ: Состояние для таблицы пользователей
class ViewUsersTable(StatesGroup):
    waiting_for_query = State()

# Глобальные переменные которые будут установлены из main.py
bot = None
ADMIN_IDS = set()
ADMIN_PASSWORD = ""
LOG_CHAT_ID = None

def init_admin_panel(bot_instance, admin_ids, admin_password, log_chat_id):
    global bot, ADMIN_IDS, ADMIN_PASSWORD, LOG_CHAT_ID
    bot = bot_instance
    ADMIN_IDS = admin_ids
    ADMIN_PASSWORD = admin_password
    LOG_CHAT_ID = log_chat_id

# ─── ADMIN PANEL MAIN MENU ──────────────────────────────────────
async def show_admin_panel(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    
    # Категории (группировка)
    kb.row(
        InlineKeyboardButton("➕ Категория", callback_data="add_category"),
        InlineKeyboardButton("🗑️ Удалить категорию", callback_data="delete_category")
    )
    
    # Города и районы (группировка)
    kb.row(
    InlineKeyboardButton("🏙️ Добавить город", callback_data="add_city"),
    InlineKeyboardButton("🗑️ Удалить город", callback_data="delete_city")
    )

    kb.row(
    InlineKeyboardButton("🏘️ Добавить район", callback_data="add_district"),
    InlineKeyboardButton("🗑️ Удалить район", callback_data="delete_district")
    )
    
    # Товары (группировка)
    kb.row(
        InlineKeyboardButton("🎁 Добавить товар", callback_data="add_product"),
        InlineKeyboardButton("🗑️ Удалить товар", callback_data="delete_product")
    )
    
    # Финансы и управление
    kb.row(
        InlineKeyboardButton("💳 Реквизиты", callback_data="edit_payments"),
        InlineKeyboardButton("🪙 Крипто кошельки", callback_data="edit_crypto_wallets")
    )
    kb.row(
        InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")
    )
    
    # Пользователи и заказы
    kb.row(
        InlineKeyboardButton("🔨 Бан (по ID)", callback_data="ban_user"),
        InlineKeyboardButton("🔓 Разбан (по ID)", callback_data="unban_user")
    )
    kb.row(
        InlineKeyboardButton("👥 Пользователи", callback_data="view_users_table"),  # ИЗМЕНЕНО: теперь таблица
        InlineKeyboardButton("📋 Заказы", callback_data="view_orders")
    )
    
    # Остатки и промокоды
    kb.row(
        InlineKeyboardButton("🎁 Промокоды", callback_data="manage_promos")
    )
    
    # АВТО-ВЫДАЧА - ОДНА КНОПКА ДЛЯ ВХОДА В ПАНЕЛЬ АВТО-ВЫДАЧИ
    kb.row(InlineKeyboardButton("🚚 Авто-выдача", callback_data="auto_delivery_panel"))
    
    # Розыгрыши
    kb.row(InlineKeyboardButton("🎪 Розыгрыши", callback_data="draw_panel"))

    # Статистика и выход
    kb.row(
        InlineKeyboardButton("📊 Статистика", callback_data="stats_main"),
        InlineKeyboardButton("🚪 Выход", callback_data="exit_admin")
    )
    
    # Получаем статистику для отображения (с обработкой ошибок)
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Статистика пользователей
            users_stats = await (await db.execute("""
                SELECT 
                    COUNT(*) as total_users,
                    COUNT(CASE WHEN banned = 1 THEN 1 END) as banned_users,
                    COUNT(CASE WHEN subscribed = 1 THEN 1 END) as subscribed_users
                FROM users
            """)).fetchone()
            
            # Статистика заказов
            orders_stats = await (await db.execute("""
                SELECT 
                    COUNT(*) as total_orders,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_orders,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN final_price ELSE 0 END), 0) as total_revenue
                FROM orders
            """)).fetchone()
        
        total_users, banned_users, subscribed_users = users_stats
        total_orders, completed_orders, pending_orders, total_revenue = orders_stats
        
        text = "🔐 <b>Админ-панель</b>\n\n"
        text += "📊 <b>Общая статистика:</b>\n"
        text += f"• 👥 Пользователи: {total_users} (🔴{banned_users} | ✅{subscribed_users})\n"
        text += f"• 📦 Заказы: {total_orders} (✅{completed_orders} | ⏳{pending_orders})\n"
        text += f"• 💰 Выручка: {total_revenue:.2f} €\n\n"
        
        # Статистика авто-выдачи (с обработкой ошибок)
        try:
            auto_stats = await auto_db.get_auto_delivery_stats()
            if auto_stats:
                total_points, available_points, used_points, hidden_points, total_quantity = auto_stats
                text += "🚚 <b>Авто-выдача:</b>\n"
                text += f"• 📍 Точки: {total_points} (✅{available_points} | 🔴{used_points})\n"
                text += f"• ⚖️ Общий вес: {total_quantity}г\n\n"
        except Exception as e:
            logger.error(f"Error getting auto stats: {e}")
            text += "🚚 <b>Авто-выдача:</b>\n"
            text += f"• 📍 Система обновляется...\n\n"
        
        text += "👇 <b>Выберите действие:</b>"
        
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        text = "🔐 <b>Админ-панель</b>\n\n"
        text += "❌ <i>Не удалось загрузить статистику</i>\n\n"
        text += "👇 <b>Выберите действие:</b>"
    
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

# ─── ADMIN AUTHENTICATION ───────────────────────────────────────
async def request_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id in ADMIN_IDS:
        await show_admin_panel(callback.message)
    else:
        await callback.message.answer("🔒 Введите пароль админа:")
        await AdminAuth.waiting_for_password.set()
    await callback.answer()

async def admin_command(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await show_admin_panel(message)
    else:
        await message.answer("🔒 Введите пароль админа:")
        await AdminAuth.waiting_for_password.set()

async def process_admin_password(message: types.Message, state: FSMContext):
    global ADMIN_PASSWORD
    print(f"DEBUG: Checking password. Entered: '{message.text}', Expected: '{ADMIN_PASSWORD}'")
    
    if message.text == ADMIN_PASSWORD:
        ADMIN_IDS.add(message.from_user.id)
        await message.answer("✅ Доступ разрешен!")
        await show_admin_panel(message)
    else:
        await message.answer("❌ Неверный пароль!")
    await state.finish()

# ─── CANCEL AND EXIT ───────────────────────────────────────────
async def cancel_action(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await callback.message.edit_text("❌ Действие отменено")
    await show_admin_panel(callback.message)
    await callback.answer()

async def exit_admin_panel(callback: types.CallbackQuery, state: FSMContext):
    await state.finish()
    try:
        await callback.message.edit_text("👋 Выход из админ-панели")
    except Exception:
        await callback.message.answer("👋 Выход из админ-панели")
    await callback.answer()

# ─── КАТЕГОРИИ ────────────────────────────────────────────────
async def add_category_start(callback: types.CallbackQuery):
    await callback.message.edit_text("📝 Введите название новой категории:")
    await AddCategory.waiting_for_category_name.set()
    await callback.answer()

async def add_category_name(message: types.Message, state: FSMContext):
    """Добавление категории с валидацией ввода"""
    if not validate_user_input(message.text):
        await message.answer("❌ Недопустимые символы в названии категории. Используйте только буквы, цифры и пробелы.")
        return
        
    category_name = message.text.strip()
    
    # Дополнительная проверка длины
    if len(category_name) < 2 or len(category_name) > 50:
        await message.answer("❌ Название категории должно быть от 2 до 50 символов.")
        return
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Проверяем, нет ли уже такой категории
            existing = await (await db.execute(
                "SELECT id FROM categories WHERE name = ?", (category_name,)
            )).fetchone()
            
            if existing:
                await message.answer(f"❌ Категория '{category_name}' уже существует!")
                await state.finish()
                await show_admin_panel(message)
                return
            
            await db.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (category_name,))
            await db.commit()
        
        await log_suspicious_activity(message.from_user.id, "add_category", f"Category: {category_name}")
        await message.answer(f"✅ Категория '{category_name}' добавлена!")
        
    except Exception as e:
        logger.error(f"Error adding category", user_id=message.from_user.id, details=str(e))
        await message.answer("❌ Ошибка при добавлении категории.")
    
    await state.finish()
    await show_admin_panel(message)

async def delete_category_start(callback: types.CallbackQuery):
    async with aiosqlite.connect('shop.db') as db:
        categories = await (await db.execute("SELECT id, name FROM categories")).fetchall()
    
    if not categories:
        await callback.message.answer("❌ Нет категорий для удаления")
        return
    
    kb = InlineKeyboardMarkup()
    for cat_id, cat_name in categories:
        kb.add(InlineKeyboardButton(cat_name, callback_data=f"delcat_sel_{cat_id}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text("🗑️ Выберите категорию для удаления:", reply_markup=kb)
    await DeleteCategory.waiting_for_category.set()
    await callback.answer()

async def confirm_delete_category(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect('shop.db') as db:
        cat_name = (await (await db.execute("SELECT name FROM categories WHERE id=?", (cat_id,))).fetchone())[0]
    
    await state.update_data(category_id=cat_id, category_name=cat_name)
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Да, удалить", callback_data="delcat_conf"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text(f"⚠️ Вы уверены, что хотите удалить категорию '{cat_name}'?", reply_markup=kb)
    await DeleteCategory.waiting_for_confirmation.set()
    await callback.answer()

async def execute_delete_category(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cat_id = data['category_id']
    cat_name = data['category_name']
    
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        await db.commit()
    
    await callback.message.answer(f"✅ Категория '{cat_name}' удалена!")
    await state.finish()
    await show_admin_panel(callback.message)
    await callback.answer()

# ─── ГОРОДА И РАЙОНЫ ──────────────────────────────────────────
async def add_city_start(callback: types.CallbackQuery):
    await callback.message.edit_text("🏙️ Введите название нового города:")
    await AddCity.waiting_for_city_name.set()
    await callback.answer()

async def add_city_name(message: types.Message, state: FSMContext):
    """Добавление города с валидацией ввода"""
    if not validate_user_input(message.text):
        await message.answer("❌ Недопустимые символы в названии города. Используйте только буквы, цифры и пробелы.")
        return
        
    city_name = message.text.strip()
    
    # Проверка длины
    if len(city_name) < 2 or len(city_name) > 50:
        await message.answer("❌ Название города должно быть от 2 до 50 символов.")
        return
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Проверяем, нет ли уже такого города
            existing = await (await db.execute(
                "SELECT id FROM cities WHERE name = ?", (city_name,)
            )).fetchone()
            
            if existing:
                await message.answer(f"❌ Город '{city_name}' уже существует!")
                await state.finish()
                await show_admin_panel(message)
                return
            
            await db.execute("INSERT OR IGNORE INTO cities(name) VALUES(?)", (city_name,))
            await db.commit()
        
        await log_suspicious_activity(message.from_user.id, "add_city", f"City: {city_name}")
        await message.answer(f"✅ Город '{city_name}' добавлен!")
        
    except Exception as e:
        logger.error(f"Error adding city", user_id=message.from_user.id, details=str(e))
        await message.answer("❌ Ошибка при добавлении города.")
    
    await state.finish()
    await show_admin_panel(message)

async def delete_city_start(callback: types.CallbackQuery):
    async with aiosqlite.connect('shop.db') as db:
        cities = await (await db.execute("SELECT id, name FROM cities")).fetchall()
    
    if not cities:
        await callback.message.answer("❌ Нет городов для удаления")
        return
    
    kb = InlineKeyboardMarkup()
    for city_id, city_name in cities:
        kb.add(InlineKeyboardButton(city_name, callback_data=f"delcity_sel_{city_id}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text("🗑️ Выберите город для удаления:", reply_markup=kb)
    await DeleteCity.waiting_for_city.set()
    await callback.answer()

async def confirm_delete_city(callback: types.CallbackQuery, state: FSMContext):
    city_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect('shop.db') as db:
        city_name = (await (await db.execute("SELECT name FROM cities WHERE id=?", (city_id,))).fetchone())[0]
    
    await state.update_data(city_id=city_id, city_name=city_name)
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Да, удалить", callback_data="delcity_conf"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text(f"⚠️ Вы уверены, что хотите удалить город '{city_name}'?", reply_markup=kb)
    await DeleteCity.waiting_for_confirmation.set()
    await callback.answer()

async def execute_delete_city(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    city_id = data['city_id']
    city_name = data['city_name']
    
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("DELETE FROM cities WHERE id=?", (city_id,))
        await db.commit()
    
    await callback.message.answer(f"✅ Город '{city_name}' удален!")
    await state.finish()
    await show_admin_panel(callback.message)
    await callback.answer()

async def add_district_start(callback: types.CallbackQuery):
    async with aiosqlite.connect('shop.db') as db:
        cities = await (await db.execute("SELECT id, name FROM cities")).fetchall()
    
    if not cities:
        await callback.message.answer("❌ Сначала добавьте города!")
        return
    
    kb = InlineKeyboardMarkup()
    for city_id, city_name in cities:
        kb.add(InlineKeyboardButton(city_name, callback_data=f"distcity_sel_{city_id}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text("🏘️ Выберите город для добавления района:", reply_markup=kb)
    await AddDistrict.waiting_for_district_name.set()
    await callback.answer()

async def select_city_for_district(callback: types.CallbackQuery, state: FSMContext):
    try:
        city_id = int(callback.data.split("_")[2])
        # СОХРАНЯЕМ city_id В СОСТОЯНИИ
        await state.update_data(city_id=city_id)
        await callback.message.edit_text("🏘️ Введите название района:")
        await callback.answer()
    except (ValueError, IndexError) as e:
        await callback.answer("❌ Ошибка выбора города", show_alert=True)
        await state.finish()
        await show_admin_panel(callback.message)

async def add_district_name(message: types.Message, state: FSMContext):
    """Добавление района с валидацией ввода"""
    if not validate_user_input(message.text):
        await message.answer("❌ Недопустимые символы в названии района. Используйте только буквы, цифры и пробелы.")
        return
        
    district_name = message.text.strip()
    
    # Проверка длины
    if len(district_name) < 2 or len(district_name) > 50:
        await message.answer("❌ Название района должно быть от 2 до 50 символов.")
        return
    
    data = await state.get_data()
    city_id = data.get('city_id')
    
    if not city_id:
        await message.answer("❌ Ошибка: город не выбран. Начните заново.")
        await state.finish()
        await show_admin_panel(message)
        return
        
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Проверяем, нет ли уже такого района в этом городе
            existing = await (await db.execute(
                "SELECT id FROM districts WHERE city_id = ? AND name = ?", (city_id, district_name)
            )).fetchone()
            
            if existing:
                await message.answer(f"❌ Район '{district_name}' уже существует в этом городе!")
                await state.finish()
                await show_admin_panel(message)
                return
            
            # Получаем название города для лога ПЕРЕД добавлением
            city_info = await (await db.execute("SELECT name FROM cities WHERE id=?", (city_id,))).fetchone()
            city_name = city_info[0] if city_info else "Unknown"
            
            await db.execute("INSERT INTO districts(city_id, name) VALUES(?,?)", (city_id, district_name))
            await db.commit()
        
        await log_suspicious_activity(message.from_user.id, "add_district", f"District: {district_name}, City: {city_name}")
        await message.answer(f"✅ Район '{district_name}' добавлен в город '{city_name}'!")
        
    except Exception as e:
        logger.error(f"Error adding district", user_id=message.from_user.id, details=str(e))
        await message.answer("❌ Ошибка при добавлении района.")
    
    await state.finish()
    await show_admin_panel(message)

async def delete_district_start(callback: types.CallbackQuery):
    """Начинает процесс удаления района: показывает список городов."""
    async with aiosqlite.connect('shop.db') as db:
        cities = await (await db.execute("SELECT id, name FROM cities")).fetchall()
    
    if not cities:
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("◀️ Назад", callback_data="back_admin"))
        await callback.message.edit_text("❌ Нет городов для выбора. Добавьте город сначала.", reply_markup=kb)
        await callback.answer()
        return

    kb = InlineKeyboardMarkup(row_width=1)
    for city_id, city_name in cities:
        # Используем префикс 'deldist_citysel_' для выбора города
        kb.add(InlineKeyboardButton(city_name, callback_data=f"deldist_citysel_{city_id}"))
    
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    await callback.message.edit_text("🗑️ Выберите город, из которого хотите удалить район:", reply_markup=kb)
    await DeleteDistrict.waiting_for_city.set()
    await callback.answer()

async def select_city_for_district_deletion(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор города и показывает список районов."""
    city_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect('shop.db') as db:
        city_info = await (await db.execute("SELECT name FROM cities WHERE id = ?", (city_id,))).fetchone()
        districts = await (await db.execute("SELECT id, name FROM districts WHERE city_id = ?", (city_id,))).fetchall()

    if not city_info:
        await callback.message.answer("❌ Город не найден")
        await state.finish()
        await show_admin_panel(callback.message)
        return

    city_name = city_info[0]
    await state.update_data(city_id=city_id, city_name=city_name)
    
    if not districts:
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("◀️ Назад", callback_data="delete_district"))
        await callback.message.edit_text(f"❌ В городе '{city_name}' нет районов.", reply_markup=kb)
        await state.finish()
        await callback.answer()
        return

    kb = InlineKeyboardMarkup(row_width=1)
    for district_id, district_name in districts:
        # Используем префикс 'deldist_sel_' для выбора района
        kb.add(InlineKeyboardButton(district_name, callback_data=f"deldist_sel_{district_id}"))

    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    await callback.message.edit_text(f"🗑️ Выберите район в городе '{city_name}' для удаления:", reply_markup=kb)
    await DeleteDistrict.waiting_for_district.set()
    await callback.answer()

async def confirm_delete_district(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор района и запрашивает подтверждение."""
    district_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect('shop.db') as db:
        district_info = await (await db.execute("""
            SELECT d.name, c.name 
            FROM districts d 
            JOIN cities c ON d.city_id = c.id 
            WHERE d.id = ?
        """, (district_id,))).fetchone()

    if not district_info:
        await callback.message.answer("❌ Район не найден")
        await state.finish()
        await show_admin_panel(callback.message)
        return

    district_name, city_name = district_info
    
    await state.update_data(district_id=district_id, district_name=district_name, city_name=city_name)

    kb = InlineKeyboardMarkup()
    # Используем префикс 'deldist_conf_' для подтверждения
    kb.add(InlineKeyboardButton("✅ Да, удалить", callback_data=f"deldist_conf_{district_id}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    # ВАЖНО: Предупреждение об удалении авто-точек
    await callback.message.edit_text(f"⚠️ Вы уверены, что хотите удалить район '{district_name}' из города '{city_name}'? **Все авто-точки в этом районе будут удалены!**", reply_markup=kb, parse_mode="HTML")
    await DeleteDistrict.waiting_for_confirmation.set()
    await callback.answer()

async def execute_delete_district(callback: types.CallbackQuery, state: FSMContext):
    """Выполняет удаление района и всех связанных данных."""
    data = await state.get_data()
    district_id = data.get('district_id')
    district_name = data.get('district_name', 'Неизвестный район')
    city_name = data.get('city_name', 'Неизвестный город')
    
    if not district_id:
        await callback.message.answer("❌ Ошибка: ID района не найден.")
        await state.finish()
        await show_admin_panel(callback.message)
        return
        
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Удаляем район. Благодаря 'FOREIGN KEY... ON DELETE CASCADE' в init_db,
            # все связанные авто-точки (auto_points) также будут автоматически удалены.
            await db.execute("DELETE FROM districts WHERE id = ?", (district_id,))
            await db.commit()
    except Exception as e:
        logger.error(f"Error deleting district", user_id=callback.from_user.id, details=str(e))
        await callback.message.edit_text("❌ Ошибка при удалении района.")
        
    await state.finish()
    await show_admin_panel(callback.message)
    await callback.answer()    

# ─── ТОВАРЫ ───────────────────────────────────────────────────
async def add_product_start(callback: types.CallbackQuery):
    async with aiosqlite.connect('shop.db') as db:
        categories = await (await db.execute("SELECT id, name FROM categories")).fetchall()
    
    if not categories:
        await callback.message.answer("❌ Сначала добавьте категории!")
        return
    
    kb = InlineKeyboardMarkup()
    for cat_id, cat_name in categories:
        kb.add(InlineKeyboardButton(cat_name, callback_data=f"prodcat_sel_{cat_id}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text("🎁 Выберите категорию для товара:", reply_markup=kb)
    await AddProduct.waiting_for_category.set()
    await callback.answer()

async def select_category_for_product(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=cat_id)
    await callback.message.edit_text("📝 Введите название товара:")
    await AddProduct.waiting_for_name.set()
    await callback.answer()

async def add_product_name(message: types.Message, state: FSMContext):
    """Добавление названия товара"""
    product_name = message.text.strip()
    
    if len(product_name) < 2 or len(product_name) > 100:
        await message.answer("❌ Название должно быть 2-100 символов")
        return
    
    await state.update_data(name=product_name)
    await message.answer("💶 Введите цену за 1 грамм (в €):")
    await AddProduct.waiting_for_price.set()

async def add_product_price(message: types.Message, state: FSMContext):
    """Добавление цены товара"""
    try:
        price = float(message.text.replace(',', '.'))
        
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return
        
        await state.update_data(price=price)
        await message.answer("📝 Введите описание товара:")
        await AddProduct.waiting_for_description.set()
        
    except ValueError:
        await message.answer("❌ Неверная цена. Введите число:")

async def add_product_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = None
    video_id = None
    
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.video:
        video_id = message.video.file_id
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            cursor = await db.execute(
                "INSERT INTO products(category_id, name, price, description, photo_id, video_id, stock) VALUES(?,?,?,?,?,?,?)",
                (data['category_id'], data['name'], data['price'], data['description'], photo_id, video_id, 0)
            )
            await db.commit()
            
            product_id = cursor.lastrowid
        
        product_name = data['name']
        await message.answer(
            f"✅ Товар '{product_name}' успешно добавлен!\n"
            f"🆔 ID товара: {product_id}\n\n"
            f"💰 Цена за грамм: {data['price']}€",
            parse_mode="HTML"
        )
        await state.finish()
        await show_admin_panel(message)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении товара: {e}")
        await state.finish()
        await show_admin_panel(message)

async def add_product_description(message: types.Message, state: FSMContext):
    """Добавление описания товара с валидацией"""
    description = message.text.strip()
    
    # Проверка длины описания
    if len(description) > 500:
        await message.answer("❌ Описание слишком длинное. Максимум 500 символов.")
        return
    
    # Базовая валидация опасного контента
    if not validate_user_input(description, 500):
        await message.answer("❌ Недопустимые символы в описании.")
        return
    
    await state.update_data(description=description)
    await log_suspicious_activity(message.from_user.id, "add_product_description", f"Description length: {len(description)}")
    await message.answer("🖼️ Отправьте фото или видео товара:")
    await AddProduct.waiting_for_media.set()

async def add_product_media(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = None
    video_id = None
    
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.video:
        video_id = message.video.file_id
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Сохраняем товар СКРЫТЫМ (is_hidden = 1)
            cursor = await db.execute(
                "INSERT INTO products(category_id, name, description, photo_id, video_id, stock, is_hidden) VALUES(?,?,?,?,?,?,?)",
                (data['category_id'], data['name'], data['description'], photo_id, video_id, 0, 1)  # is_hidden = 1
            )
            await db.commit()
            
            product_id = cursor.lastrowid
        
        product_name = data['name']
        await message.answer(
            f"✅ Товар '{product_name}' успешно добавлен!\n"
            f"🆔 ID товара: {product_id}\n\n"
            f"📌 <b>Товар добавлен как СКРЫТЫЙ</b>\n"
            f"🔒 Он НЕ будет виден пользователям до добавления авто-выдачи!\n\n"
            f"🚚 Теперь добавьте точки авто-выдачи:\n"
            f"1. 🔧 Админ-панель\n"
            f"2. 🚚 Авто-выдача\n" 
            f"3. 📍 Добавить точку клада\n"
            f"4. Выберите этот товар (ID: {product_id})",
            parse_mode="HTML"
        )
        await state.finish()
        await show_admin_panel(message)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении товара: {e}")
        await state.finish()
        await show_admin_panel(message)

async def fix_product_media(message: types.Message):
    """Исправить некорректные media_id для товаров"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Найти товары с некорректными file_id
            products = await (await db.execute(
                "SELECT id, name, photo_id, video_id FROM products"
            )).fetchall()
            
            fixed_count = 0
            for pid, name, photo_id, video_id in products:
                # Проверяем photo_id
                if photo_id and (len(photo_id) < 20 or '://' in photo_id):
                    await db.execute(
                        "UPDATE products SET photo_id = NULL WHERE id = ?",
                        (pid,)
                    )
                    fixed_count += 1
                    logger.info(f"Fixed photo_id for product {pid} ({name})")
                
                # Проверяем video_id
                if video_id and (len(video_id) < 20 or '://' in video_id):
                    await db.execute(
                        "UPDATE products SET video_id = NULL WHERE id = ?",
                        (pid,)
                    )
                    fixed_count += 1
                    logger.info(f"Fixed video_id for product {pid} ({name})")
            
            await db.commit()
            
            await message.answer(f"✅ Исправлено {fixed_count} некорректных медиафайлов")
            
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def delete_product_start(callback: types.CallbackQuery):
    async with aiosqlite.connect('shop.db') as db:
        products = await (await db.execute(
            "SELECT p.id, p.name, c.name FROM products p JOIN categories c ON p.category_id = c.id"
        )).fetchall()
    
    if not products:
        await callback.message.answer("❌ Нет товаров для удаления")
        return
    
    kb = InlineKeyboardMarkup()
    for prod_id, prod_name, cat_name in products:
        kb.add(InlineKeyboardButton(f"{prod_name} ({cat_name})", callback_data=f"delprod_sel_{prod_id}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text("🗑️ Выберите товар для удаления:", reply_markup=kb)
    await DeleteProduct.waiting_for_product.set()
    await callback.answer()

async def confirm_delete_product(callback: types.CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect('shop.db') as db:
        product_info = await (await db.execute(
            "SELECT p.name, c.name FROM products p JOIN categories c ON p.category_id = c.id WHERE p.id=?", (prod_id,)
        )).fetchone()
    
    if product_info:
        prod_name, cat_name = product_info
        await state.update_data(product_id=prod_id, product_name=prod_name)
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Да, удалить", callback_data="delprod_conf"))
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        await callback.message.edit_text(f"⚠️ Вы уверены, что хотите удалить товар '{prod_name}' из категории '{cat_name}'?", reply_markup=kb)
        await DeleteProduct.waiting_for_confirmation.set()
    
    await callback.answer()

async def execute_delete_product(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prod_id = data['product_id']
    prod_name = data['product_name']
    
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("DELETE FROM products WHERE id=?", (prod_id,))
        await db.commit()
    
    await callback.message.answer(f"✅ Товар '{prod_name}' удален!")
    await state.finish()
    await show_admin_panel(callback.message)
    await callback.answer()

# ─── ПЛАТЕЖИ ──────────────────────────────────────────────────
async def edit_payments_start(callback: types.CallbackQuery):
    async with aiosqlite.connect('shop.db') as db:
        payments = await (await db.execute("SELECT usdt, btc, card FROM payments WHERE id=1")).fetchone()
    
    usdt, btc, card = payments
    
    kb = InlineKeyboardMarkup(row_width=1)
    # ОСТАВЛЯЕМ ТОЛЬКО КАРТУ
    kb.add(InlineKeyboardButton("💳 Карта", callback_data="edit_card"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="cancel_action"))
    
    text = "💳 <b>Текущие реквизиты:</b>\n\n"
    text += f"💳 Карта: <code>{card or 'Не задана'}</code>\n\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

async def edit_usdt_start(callback: types.CallbackQuery):
    await callback.message.edit_text("🪙 Введите новый USDT адрес:")
    await EditPayments.waiting_for_usdt.set()
    await callback.answer()

async def edit_btc_start(callback: types.CallbackQuery):
    await callback.message.edit_text("🪙 Введите новый BTC адрес:")
    await EditPayments.waiting_for_btc.set()
    await callback.answer()

async def edit_card_start(callback: types.CallbackQuery):
    await callback.message.edit_text("💳 Введите новые данные карты:")
    await EditPayments.waiting_for_card.set()
    await callback.answer()

async def set_usdt(message: types.Message, state: FSMContext):
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("UPDATE payments SET usdt=? WHERE id=1", (message.text,))
        await db.commit()
    
    await message.answer("✅ USDT адрес обновлен!")
    await state.finish()
    await show_admin_panel(message)

async def set_btc(message: types.Message, state: FSMContext):
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("UPDATE payments SET btc=? WHERE id=1", (message.text,))
        await db.commit()
    
    await message.answer("✅ BTC адрес обновлен!")
    await state.finish()
    await show_admin_panel(message)

async def set_card(message: types.Message, state: FSMContext):
    """Установка данных карты с валидацией"""
    card_data = message.text.strip()
    
    # Базовая валидация данных карты
    if not validate_user_input(card_data, 50):
        await message.answer("❌ Недопустимые символы в данных карты.")
        return
    
    # Проверка длины
    if len(card_data) < 8 or len(card_data) > 30:
        await message.answer("❌ Данные карты должны быть от 8 до 30 символов.")
        return
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            await db.execute("UPDATE payments SET card=? WHERE id=1", (card_data,))
            await db.commit()
        
        await log_suspicious_activity(message.from_user.id, "set_card", "Card details updated")
        await message.answer("✅ Данные карты обновлены!")
        
    except Exception as e:
        logger.error(f"Error setting card", user_id=message.from_user.id, details=str(e))
        await message.answer("❌ Ошибка при обновлении данных карты.")
    
    await state.finish()
    await show_admin_panel(message)

# ─── РАССЫЛКА ────────────────────────────────────────────────
async def broadcast_start(callback: types.CallbackQuery):
    await callback.message.edit_text("📢 Отправьте сообщение для рассылки (текст, фото или видео):")
    await Broadcast.waiting_for_content.set()
    await callback.answer()

async def broadcast_content(message: types.Message, state: FSMContext):
    """Обработка контента для рассылки с валидацией"""
    # Валидация текста если есть
    if message.text and not validate_user_input(message.text, 4000):
        await message.answer("❌ Недопустимые символы в тексте рассылки.")
        return
        
    if message.caption and not validate_user_input(message.caption, 1000):
        await message.answer("❌ Недопустимые символы в подписи к медиа.")
        return
    
    content = {
        'text': message.text if message.text else None,
        'caption': message.caption if message.caption else None,
        'photo': message.photo[-1].file_id if message.photo else None,
        'video': message.video.file_id if message.video else None
    }
    
    await state.update_data(content=content)
    await log_suspicious_activity(message.from_user.id, "broadcast_prepare", f"Content type: {message.content_type}")
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Начать рассылку", callback_data="broadcast_yes"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await message.answer("⚠️ Начать рассылку всем пользователям?", reply_markup=kb)
    await Broadcast.waiting_for_confirm.set()

async def broadcast_confirm(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    content = data['content']
    
    async with aiosqlite.connect('shop.db') as db:
        users = await (await db.execute("SELECT user_id FROM users WHERE banned=0")).fetchall()
    
    success = 0
    failed = 0
    
    await callback.message.edit_text(f"📤 Рассылка начата для {len(users)} пользователей...")
    
    for user in users:
        user_id = user[0]
        try:
            if content['photo']:
                await bot.send_photo(user_id, content['photo'], caption=content['caption'])
            elif content['video']:
                await bot.send_video(user_id, content['video'], caption=content['caption'])
            else:
                await bot.send_message(user_id, content['text'])
            success += 1
        except Exception as e:
            logger.error(f"Failed to send broadcast", user_id=user_id, details=str(e))
            failed += 1
        await asyncio.sleep(0.1)
    
    await callback.message.answer(f"✅ Рассылка завершена!\nУспешно: {success}\nНе удалось: {failed}")
    await state.finish()
    await show_admin_panel(callback.message)
    await callback.answer()

# ─── ПОЛЬЗОВАТЕЛИ ────────────────────────────────────────────
async def ban_start(callback: types.CallbackQuery):
    await callback.message.edit_text("🔨 Введите ID пользователя для бана:")
    await BanUser.waiting_for_id.set()
    await callback.answer()

async def ban_enter_id(message: types.Message, state: FSMContext):
    """Бан пользователя с валидацией ID"""
    try:
        user_id = int(message.text.strip())
        
        # Проверка что это не админ
        if user_id in ADMIN_IDS:
            await message.answer("❌ Нельзя забанить администратора!")
            await state.finish()
            await show_admin_panel(message)
            return
            
        # Проверка диапазона ID
        if user_id < 1 or user_id > 9999999999:
            await message.answer("❌ Неверный ID пользователя.")
            return
        
        async with aiosqlite.connect('shop.db') as db:
            # Проверяем существует ли пользователь
            user_exists = await (await db.execute(
                "SELECT user_id FROM users WHERE user_id=?", (user_id,)
            )).fetchone()
            
            if not user_exists:
                await message.answer("❌ Пользователь с таким ID не найден.")
                await state.finish()
                await show_admin_panel(message)
                return
            
            await db.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
            await db.commit()
        
        await message.answer(f"✅ Пользователь {user_id} забанен!")
        await log_suspicious_activity(message.from_user.id, "ban_user", f"Banned user: {user_id}")
        
        # Уведомляем пользователя
        try:
            await bot.send_message(user_id, BANNED_TEXT_RU, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify user {user_id} about ban", user_id=user_id, details=str(e))
            await message.answer(f"⚠️ Не удалось уведомить пользователя {user_id}.")
            
        await state.finish()
        await show_admin_panel(message)
        
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число:")
    except Exception as e:
        logger.error(f"Error banning user", user_id=message.from_user.id, details=str(e))
        await message.answer("❌ Ошибка при бане пользователя.")
        await state.finish()
        await show_admin_panel(message)

async def unban_start(callback: types.CallbackQuery):
    await callback.message.edit_text("🔓 Введите ID пользователя для разбана:")
    await UnbanUser.waiting_for_id.set()
    await callback.answer()

async def unban_enter_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        async with aiosqlite.connect('shop.db') as db:
            await db.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
            await db.commit()
            
        await message.answer(f"✅ Пользователь {user_id} разбанен!")
        
        # Уведомляем пользователя
        try:
            await bot.send_message(user_id, UNBANNED_TEXT_RU, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to notify user about unban", user_id=user_id, details=str(e))
            await message.answer(f"⚠️ Не удалось уведомить пользователя {user_id}.")

        await state.finish()
        await show_admin_panel(message)
    except ValueError:
        await message.answer("❌ Неверный ID. Введите число:")

async def ban_user_from_details(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
        await db.commit()
    
    await callback.answer(f"Пользователь {user_id} забанен!")
    
    # Уведомляем пользователя
    try:
        await bot.send_message(user_id, BANNED_TEXT_RU, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to notify user about ban from details", user_id=user_id, details=str(e))
        await callback.answer("⚠️ Не удалось уведомить пользователя.", show_alert=True)
        
    # Обновляем сообщение с детальной информацией
    await view_user_details(callback)

async def unban_user_from_details(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
        await db.commit()
        
    await callback.answer(f"Пользователь {user_id} разбанен!")
    
    # Уведомляем пользователя
    try:
        await bot.send_message(user_id, UNBANNED_TEXT_RU, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to notify user about unban from details", user_id=user_id, details=str(e))
        await callback.answer("⚠️ Не удалось уведомить пользователя.", show_alert=True)

    # Обновляем сообщение с детальной информацией
    await view_user_details(callback)


async def view_user_details(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect('shop.db') as db:
        user_info = await (await db.execute("""
            SELECT username, lang, banned, subscribed, created_at, last_active
            FROM users WHERE user_id=?
        """, (user_id,))).fetchone()
        
        if not user_info:
            await callback.message.answer("❌ Пользователь не найден")
            return
        
        username, lang, banned, subscribed, created_at, last_active = user_info
        
        # Расширенная статистика заказов
        orders_stats = await (await db.execute("""
            SELECT 
                COUNT(*) as total_orders,
                COUNT(CASE WHEN status='completed' THEN 1 END) as completed_orders,
                COUNT(CASE WHEN status='pending' THEN 1 END) as pending_orders,
                COUNT(CASE WHEN status='cancelled' THEN 1 END) as cancelled_orders,
                COUNT(CASE WHEN status='rejected' THEN 1 END) as rejected_orders,
                COALESCE(SUM(CASE WHEN status='completed' THEN final_price ELSE 0 END), 0) as total_spent,
                COALESCE(AVG(CASE WHEN status='completed' THEN final_price ELSE NULL END), 0) as avg_order_value,
                MAX(CASE WHEN status='completed' THEN created_at ELSE NULL END) as last_order_date
            FROM orders WHERE user_id=?
        """, (user_id,))).fetchone()
        
        total_orders, completed_orders, pending_orders, cancelled_orders, rejected_orders, total_spent, avg_order_value, last_order_date = orders_stats
        
        # Статистика по географии заказов
        geography_stats = await (await db.execute("""
            SELECT c.name, COUNT(*) as order_count
            FROM orders o 
            JOIN cities c ON o.city_id = c.id 
            WHERE o.user_id=? AND o.status='completed'
            GROUP BY c.name 
            ORDER BY order_count DESC 
            LIMIT 5
        """, (user_id,))).fetchall()
        
        # Статистика по товарам
        product_stats = await (await db.execute("""
            SELECT p.name, COUNT(*) as order_count, SUM(o.quantity) as total_quantity
            FROM orders o 
            JOIN products p ON o.product_id = p.id 
            WHERE o.user_id=? AND o.status='completed'
            GROUP BY p.name 
            ORDER BY order_count DESC 
            LIMIT 5
        """, (user_id,))).fetchall()
        
        # Статистика по дням недели
        weekday_stats = await (await db.execute("""
            SELECT strftime('%w', created_at) as weekday, COUNT(*) as order_count 
            FROM orders 
            WHERE user_id=? AND status='completed' 
            GROUP BY weekday 
            ORDER BY order_count DESC
        """, (user_id,))).fetchall()
        
    username_display = f"@{username}" if username else "Без username"
    status = "🔴 Забанен" if banned else "🟢 Активен"
    subscription_status = "✅ Подписан" if subscribed else "❌ Не подписан"
    
    text = f"👤 <b>Детальная информация о пользователе</b>\n\n"
    text += f"🆔 ID: <code>{user_id}</code>\n"
    text += f"👤 Username: {username_display}\n"
    text += f"🌐 Язык: {'🇷🇺 Русский' if lang == 'ru' else '🇬🇧 English'}\n"
    text += f"📊 Статус: {status}\n"
    text += f"📢 Рассылка: {subscription_status}\n"
    text += f"📅 Регистрация: {created_at}\n"
    text += f"🕐 Последняя активность: {last_active or 'Неизвестно'}\n\n"
    
    text += f"📊 <b>Статистика заказов:</b>\n"
    text += f"• Всего заказов: {total_orders}\n"
    text += f"• Успешных: {completed_orders}\n"
    text += f"• Ожидают: {pending_orders}\n"
    text += f"• Отменено: {cancelled_orders}\n"
    text += f"• Отклонено: {rejected_orders}\n"
    text += f"• Общая сумма: {total_spent:.2f}€\n"
    text += f"• Средний чек: {avg_order_value:.2f}€\n"
    text += f"• Последний заказ: {last_order_date or 'Нет'}\n\n"
    
    if geography_stats:
        text += f"🗺️ <b>Топ городов:</b>\n"
        for city_name, order_count in geography_stats:
            text += f"• {city_name}: {order_count} зак.\n"
        text += "\n"
    
    if product_stats:
        text += f"🏪 <b>Топ товаров:</b>\n"
        for product_name, order_count, total_quantity in product_stats:
            text += f"• {product_name}: {order_count} зак. ({total_quantity}г)\n"
        text += "\n"
    
    if weekday_stats:
        weekdays = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
        text += f"📅 <b>Активность по дням:</b>\n"
        for weekday_num, order_count in weekday_stats:
            weekday_name = weekdays[int(weekday_num)]
            text += f"• {weekday_name}: {order_count} зак.\n"
    
    kb = InlineKeyboardMarkup(row_width=2)
    
    if banned:
        kb.add(InlineKeyboardButton("🔓 Разбанить", callback_data=f"unban_from_details_{user_id}"))
    
    kb.add(InlineKeyboardButton("📋 Заказы пользователя", callback_data=f"user_orders_{user_id}"))
    kb.add(InlineKeyboardButton("◀️ Назад к списку", callback_data="view_users_table"))
    kb.add(InlineKeyboardButton("🏠 В меню", callback_data="cancel_action"))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

async def show_auto_delivery_panel(callback: types.CallbackQuery):
    """Показывает панель управления авто-выдачей"""
    try:
        # Получаем статистику авто-выдачи
        stats = await auto_db.get_auto_delivery_stats()
        
        if stats:
            total_points, available_points, used_points, hidden_points, total_quantity = stats
            
            text = "🚚 <b>Панель авто-выдачи</b>\n\n"
            text += "📊 <b>Статистика:</b>\n"
            text += f"• 📍 Всего точек: {total_points}\n"
            text += f"• ✅ Доступно: {available_points}\n"
            text += f"• 🔴 Использовано: {used_points}\n"
            text += f"• 👁️ Скрыто: {hidden_points}\n"
            text += f"• ⚖️ Общий вес: {total_quantity}г\n\n"
            
        else:
            text = "🚚 <b>Панель авто-выдачи</b>\n\n"
            text += "❌ <i>Нет данных по авто-выдаче</i>\n\n"
        
        text += "👇 <b>Выберите действие:</b>"
        
        kb = InlineKeyboardMarkup(row_width=2)
        
        # Основные функции авто-выдачи
        kb.row(
            InlineKeyboardButton("📍 Добавить клад", callback_data="add_auto_point"),
            InlineKeyboardButton("📋 Список кладов", callback_data="list_auto_points")
        )
        kb.row(
            InlineKeyboardButton("🗑️ Удалить клад", callback_data="delete_auto_point"),
            InlineKeyboardButton("📊 Статистика", callback_data="auto_delivery_stats")
        )
        
        # Управление скрытыми товарами
        kb.row(
            InlineKeyboardButton("👁️ Скрытые товары", callback_data="view_hidden_products"),
            InlineKeyboardButton("🔄 Восстановить", callback_data="restore_hidden_product")
        )
        
        # Назад в главное меню админки
        kb.row(InlineKeyboardButton("◀️ Назад", callback_data="cancel_action"))
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        
    except Exception as e:
        logger.error(f"Error showing auto delivery panel: {e}")
        # Упрощенное сообщение об ошибке
        text = "🚚 <b>Панель авто-выдачи</b>\n\n"
        text += "⚠️ <i>База данных обновляется...</i>\n\n"
        text += "👇 <b>Выберите действие:</b>"
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(
            InlineKeyboardButton("📍 Добавить клад", callback_data="add_auto_point"),
            InlineKeyboardButton("📋 Список кладов", callback_data="list_auto_points")
        )
        kb.row(InlineKeyboardButton("◀️ Назад", callback_data="cancel_action"))
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    
    await callback.answer()

# ─── ЗАКАЗЫ ──────────────────────────────────────────────────
async def view_orders_start(callback: types.CallbackQuery):
    async with aiosqlite.connect('shop.db') as db:
        orders = await (await db.execute("""
            SELECT o.id, o.user_id, u.username, p.name, o.quantity, o.final_price, o.status, o.created_at
            FROM orders o
            JOIN users u ON o.user_id = u.user_id
            JOIN products p ON o.product_id = p.id
            ORDER BY o.created_at DESC
            LIMIT 50
        """)).fetchall()
    
    if not orders:
        await callback.message.answer("❌ Нет заказов в базе")
        await callback.answer()
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    text = "📋 <b>Последние 50 заказов:</b>\n\n"
    
    for order_id, user_id, username, product_name, quantity, final_price, status, created_at in orders:
        username_display = f"@{username}" if username else f"ID: {user_id}"
        status_icon = "🟢" if status == "completed" else "🟡" if status == "pending" else "🔴"
        short_date = created_at.split()[0]
        
        kb.add(InlineKeyboardButton(
            f"{status_icon} Заказ #{order_id} - {username_display} - {final_price}€ ({short_date})",
            callback_data=f"order_detail_{order_id}"
        ))

    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="cancel_action"))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

async def view_order_details(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect('shop.db') as db:
        order_info = await (await db.execute("""
            SELECT 
                o.id, o.user_id, o.product_id, o.quantity, o.final_price, o.status,
                o.payment_method, o.created_at, o.updated_at, o.city_id, o.district_id,
                u.username, p.name as product_name, c.name as city_name, d.name as district_name
            FROM orders o
            JOIN users u ON o.user_id = u.user_id
            JOIN products p ON o.product_id = p.id
            LEFT JOIN cities c ON o.city_id = c.id
            LEFT JOIN districts d ON o.district_id = d.id
            WHERE o.id=?
        """, (order_id,))).fetchone()
    
    if not order_info:
        await callback.message.answer("❌ Заказ не найден")
        return
    
    (order_id, user_id, product_id, quantity, final_price, status, 
     payment_method, created_at, updated_at, city_id, district_id,
     username, product_name, city_name, district_name) = order_info
    
    username_display = f"@{username}" if username else "Без username"
    location = f"{city_name}, {district_name}" if district_name else f"{city_name}" if city_name else "Не указано"
    
    status_icons = {
        'completed': '✅',
        'pending': '⏳', 
        'cancelled': '❌',
        'rejected': '🚫'
    }
    status_icon = status_icons.get(status, '📊')
    
    text = f"📋 <b>Детали заказа #{order_id}</b>\n\n"
    text += f"{status_icon} <b>Статус:</b> {status}\n"
    text += f"👤 <b>Пользователь:</b> {username_display}\n"
    text += f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
    text += f"🎁 <b>Товар:</b> {product_name}\n"
    text += f"⚖️ <b>Количество:</b> {quantity}г\n"
    text += f"💰 <b>Сумма:</b> {final_price}€\n"
    text += f"💳 <b>Способ оплаты:</b> {payment_method or 'Не указан'}\n"
    text += f"📍 <b>Локация:</b> {location}\n"
    text += f"📅 <b>Создан:</b> {created_at}\n"
    text += f"🕐 <b>Обновлен:</b> {updated_at}\n"
    
    kb = InlineKeyboardMarkup(row_width=2)
    
    if status == 'pending':
        kb.add(InlineKeyboardButton("✅ Завершить", callback_data=f"complete_order_{order_id}"))
        kb.add(InlineKeyboardButton("🚫 Отклонить", callback_data=f"reject_order_{order_id}"))
    elif status == 'completed':
        kb.add(InlineKeyboardButton("⏳ В ожидание", callback_data=f"pending_order_{order_id}"))
    elif status == 'rejected':
        kb.add(InlineKeyboardButton("✅ Завершить", callback_data=f"complete_order_{order_id}"))
        kb.add(InlineKeyboardButton("⏳ В ожидание", callback_data=f"pending_order_{order_id}"))
    
    kb.add(InlineKeyboardButton("📋 Все заказы пользователя", callback_data=f"user_orders_{user_id}"))
    kb.add(InlineKeyboardButton("◀️ Назад к списку", callback_data="view_orders"))
    kb.add(InlineKeyboardButton("🏠 В меню", callback_data="cancel_action"))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

async def view_user_orders(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect('shop.db') as db:
        user_info = await (await db.execute("SELECT username FROM users WHERE user_id=?", (user_id,))).fetchone()
        orders = await (await db.execute("""
            SELECT o.id, p.name, o.quantity, o.final_price, o.status, o.created_at
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.user_id=?
            ORDER BY o.created_at DESC
            LIMIT 20
        """, (user_id,))).fetchall()
    
    username = user_info[0] if user_info else "Неизвестно"
    username_display = f"@{username}" if username else f"ID: {user_id}"
    
    if not orders:
        await callback.message.answer(f"📋 У пользователя {username_display} нет заказов")
        await callback.answer()
        return
    
    text = f"📋 <b>Заказы пользователя {username_display}:</b>\n\n"
    
    for order_id, product_name, quantity, final_price, status, created_at in orders:
        status_icon = "✅" if status == "completed" else "⏳" if status == "pending" else "❌"
        short_date = created_at.split()[0]
        text += f"{status_icon} <b>Заказ #{order_id}</b>\n"
        text += f"   🎁 {product_name}\n"
        text += f"   ⚖️ {quantity}г | 💰 {final_price}€\n"
        text += f"   📅 {short_date} | 📊 {status}\n\n"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Назад к пользователю", callback_data=f"user_detail_{user_id}"))
    kb.add(InlineKeyboardButton("📋 К таблице", callback_data="view_users_table"))
    kb.add(InlineKeyboardButton("🏠 В меню", callback_data="cancel_action"))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

async def change_order_status(callback: types.CallbackQuery):
    action_parts = callback.data.split("_")
    action = action_parts[0]  # complete, reject, pending
    order_id = int(action_parts[2])
    
    new_status = {
        'complete': 'completed',
        'reject': 'rejected', 
        'pending': 'pending'
    }.get(action, 'pending')
    
    async with aiosqlite.connect('shop.db') as db:
        # УБРАТЬ ВСЮ ЛОГИКУ С STOCK
        
        await db.execute("UPDATE orders SET status=?, updated_at=datetime('now') WHERE id=?", (new_status, order_id))
        await db.commit()
    
    status_text = {
        'completed': 'завершен',
        'rejected': 'отклонен', 
        'pending': 'возвращен в ожидание'
    }.get(new_status, 'обновлен')
    
    await callback.answer(f"✅ Заказ #{order_id} {status_text}!")
    
    # Обновляем сообщение с деталями заказа
    await view_order_details(callback)

# ─── ОСТАТКИ ТОВАРОВ ─────────────────────────────────────────
async def edit_stock_start(callback: types.CallbackQuery):
    async with aiosqlite.connect('shop.db') as db:
        products = await (await db.execute("""
            SELECT p.id, p.name, c.name, p.stock 
            FROM products p 
            JOIN categories c ON p.category_id = c.id
            ORDER BY c.name, p.name
        """)).fetchall()
    
    if not products:
        await callback.message.answer("❌ Нет товаров для редактирования")
        return
    
    kb = InlineKeyboardMarkup()
    for prod_id, prod_name, cat_name, stock in products:
        kb.add(InlineKeyboardButton(
            f"{prod_name} ({cat_name}) - {stock}г", 
            callback_data=f"stock_sel_{prod_id}"
        ))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text("📦 Выберите товар для изменения остатка:", reply_markup=kb)
    await EditStock.waiting_for_product.set()
    await callback.answer()

async def select_product_for_stock(callback: types.CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[2])
    
    async with aiosqlite.connect('shop.db') as db:
        product_info = await (await db.execute("""
            SELECT p.name, c.name, p.stock 
            FROM products p 
            JOIN categories c ON p.category_id = c.id 
            WHERE p.id=?
        """, (prod_id,))).fetchone()
    
    if product_info:
        prod_name, cat_name, current_stock = product_info
        await state.update_data(product_id=prod_id, product_name=prod_name)
        
        await callback.message.edit_text(
            f"📦 Товар: <b>{prod_name}</b> ({cat_name})\n"
            f"📊 Текущий остаток: <b>{current_stock}г</b>\n\n"
            f"Введите новое количество на складе (в граммах):",
            parse_mode="HTML"
        )
        await EditStock.waiting_for_stock.set()
    
    await callback.answer()

async def set_product_stock(message: types.Message, state: FSMContext):
    try:
        new_stock = int(message.text)
        data = await state.get_data()
        prod_id = data['product_id']
        prod_name = data['product_name']
        
        async with aiosqlite.connect('shop.db') as db:
            await db.execute("UPDATE products SET stock=? WHERE id=?", (new_stock, prod_id))
            await db.commit()
        
        await message.answer(f"✅ Остаток товара '{prod_name}' изменен на {new_stock}г!")
        await state.finish()
        await show_admin_panel(message)
    except ValueError:
        await message.answer("❌ Неверное количество. Введите число:")

# ─── ПРОМОКОДЫ ──────────────────────────────────────────────
async def manage_promos_start(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Добавить промокод", callback_data="add_promo"),
        InlineKeyboardButton("🗑️ Удалить промокод", callback_data="delete_promo")
    )
    kb.add(InlineKeyboardButton("📋 Список промокодов", callback_data="list_promos"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="cancel_action"))
    
    await callback.message.edit_text("🎁 <b>Управление промокодами</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

async def add_promo_start(callback: types.CallbackQuery):
    await callback.message.edit_text("🎁 Введите код промокода:")
    await AddPromoCode.waiting_for_code.set()
    await callback.answer()

async def add_promo_code(message: types.Message, state: FSMContext):
    """Добавление промокода с валидацией"""
    code = message.text.strip().upper()
    
    # Валидация промокода
    if not validate_user_input(code, 20):
        await message.answer("❌ Недопустимые символы в промокоде. Используйте только буквы, цифры и дефисы.")
        return
    
    # Проверка длины
    if len(code) < 3 or len(code) > 20:
        await message.answer("❌ Промокод должен быть от 3 до 20 символов.")
        return
    
    # Проверка на существующий промокод
    async with aiosqlite.connect('shop.db') as db:
        existing = await (await db.execute(
            "SELECT code FROM promo_codes WHERE code=?", (code,)
        )).fetchone()
        
        if existing:
            await message.answer(f"❌ Промокод '{code}' уже существует!")
            await state.finish()
            await show_admin_panel(message)
            return
    
    await state.update_data(code=code)
    await log_suspicious_activity(message.from_user.id, "add_promo_code", f"Code: {code}")
    await message.answer("💯 Введите размер скидки (в процентах, число от 1 до 100):")
    await AddPromoCode.waiting_for_discount.set()

async def add_promo_discount(message: types.Message, state: FSMContext):
    try:
        discount = float(message.text)
        if 1 <= discount <= 100:
            await state.update_data(discount=discount)
            await message.answer("🔢 Введите лимит использований (0 = без лимита):")
            await AddPromoCode.waiting_for_limit.set()
        else:
            await message.answer("❌ Скидка должна быть от 1 до 100%. Введите снова:")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число:")

async def add_promo_limit(message: types.Message, state: FSMContext):
    try:
        usage_limit = int(message.text)
        await state.update_data(usage_limit=usage_limit)
        await message.answer("📅 Введите дату окончания действия (в формате ДД.ММ.ГГГГ или '0' для бессрочного):")
        await AddPromoCode.waiting_for_expiry.set()
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число:")

async def add_promo_expiry(message: types.Message, state: FSMContext):
    """Добавляет дату окончания промокода"""
    data = await state.get_data()
    code = data['code']
    discount = data['discount']
    usage_limit = data['usage_limit']
    
    expiry_date = None
    if message.text.strip() != '0':
        try:
            day, month, year = map(int, message.text.strip().split('.'))
            expiry_date = f"{year:04d}-{month:02d}-{day:02d} 23:59:59"
            
            # Проверяем, что дата в будущем
            expires_datetime = datetime.strptime(f"{year:04d}-{month:02d}-{day:02d}", "%Y-%m-%d")
            if expires_datetime < datetime.now():
                await message.answer("❌ Дата должна быть в будущем. Введите снова (или '0' для бессрочного):")
                return
                
        except ValueError:
            await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ или '0':")
            return
    
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Проверяем, нет ли уже такого промокода
            existing = await (await db.execute(
                "SELECT code FROM promo_codes WHERE code = ?", (code,)
            )).fetchone()
            
            if existing:
                await message.answer(f"❌ Промокод <b>{code}</b> уже существует!", parse_mode="HTML")
                await state.finish()
                await show_admin_panel(message)
                return
            
            # Вставляем промокод с discount_percent (не discount!)
            await db.execute(
                "INSERT INTO promo_codes (code, discount_percent, usage_limit, expires_at) VALUES (?, ?, ?, ?)",
                (code, discount, usage_limit, expiry_date)
            )
            await db.commit()
        
        expiry_text = f"до {message.text.strip()}" if expiry_date else "бессрочно"
        
        await message.answer(
            f"✅ Промокод <b>{code}</b> успешно добавлен!\n\n"
            f"💯 Скидка: {discount}%\n"
            f"🔢 Лимит использований: {usage_limit if usage_limit > 0 else 'без лимита'}\n"
            f"📅 Действует: {expiry_text}",
            parse_mode="HTML"
        )
        
        # Логируем действие
        await log_suspicious_activity(
            message.from_user.id, 
            "add_promo_code", 
            f"Code: {code}, Discount: {discount}%"
        )
        
    except Exception as e:
        logger.error(f"Error adding promo code: {e}")
        await message.answer(f"❌ Ошибка при добавлении промокода: {str(e)}")
    
    await state.finish()
    await show_admin_panel(message)

async def delete_promo_start(callback: types.CallbackQuery):
    async with aiosqlite.connect('shop.db') as db:
        promos = await (await db.execute("""
            SELECT code, discount_percent, usage_limit, used_count, expires_at 
            FROM promo_codes 
            ORDER BY created_at DESC
        """)).fetchall()
    
    if not promos:
        await callback.message.answer("❌ Нет промокодов для удаления")
        return
    
    kb = InlineKeyboardMarkup()
    for code, discount_percent, usage_limit, used_count, expires_at in promos:
        expiry_text = expires_at.split()[0] if expires_at else "бессрочно"
        button_text = f"{code} (-{discount_percent}%) - использовано {used_count}/{usage_limit if usage_limit > 0 else '∞'}"
        kb.add(InlineKeyboardButton(button_text, callback_data=f"delpromo_sel_{code}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text("🗑️ Выберите промокод для удаления:", reply_markup=kb)
    await DeletePromoCode.waiting_for_promo.set()
    await callback.answer()

async def confirm_delete_promo(callback: types.CallbackQuery, state: FSMContext):
    code = callback.data.split("_")[2]
    
    async with aiosqlite.connect('shop.db') as db:
        promo_info = await (await db.execute("""
            SELECT discount_percent, usage_limit, used_count, expires_at 
            FROM promo_codes WHERE code=?
        """, (code,))).fetchone()
    
    if promo_info:
        discount_percent, usage_limit, used_count, expires_at = promo_info
        expiry_text = expires_at.split()[0] if expires_at else "бессрочно"
        
        await state.update_data(promo_code=code)
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Да, удалить", callback_data="delpromo_conf"))
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        text = f"⚠️ Вы уверены, что хотите удалить промокод <b>{code}</b>?\n\n"
        text += f"💯 Скидка: {discount_percent}%\n"
        text += f"🔢 Использовано: {used_count}/{usage_limit if usage_limit > 0 else '∞'}\n"
        text += f"📅 Действует: {expiry_text}"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await DeletePromoCode.waiting_for_confirmation.set()
    
    await callback.answer()

async def execute_delete_promo(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    code = data['promo_code']
    
    async with aiosqlite.connect('shop.db') as db:
        await db.execute("DELETE FROM promo_codes WHERE code=?", (code,))
        await db.commit()
    
    await callback.message.answer(f"✅ Промокод <b>{code}</b> удален!", parse_mode="HTML")
    await state.finish()
    await show_admin_panel(callback.message)
    await callback.answer()

async def list_promos(callback: types.CallbackQuery):
    """Показывает список активных промокодов"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            promos = await (await db.execute("""
                SELECT 
                    code, 
                    discount_percent, 
                    usage_limit, 
                    used_count, 
                    expires_at, 
                    created_at
                FROM promo_codes 
                ORDER BY 
                    CASE WHEN expires_at IS NULL THEN 0 ELSE 1 END,
                    created_at DESC
            """)).fetchall()
        
        if not promos:
            await callback.message.answer(
                "📋 <b>Список промокодов</b>\n\n"
                "❌ Нет активных промокодов",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        text = "📋 <b>Список промокодов</b>\n\n"
        
        total_promos = len(promos)
        active_promos = 0
        
        for code, discount_percent, usage_limit, used_count, expires_at, created_at in promos:
            # Проверяем активность промокода
            is_active = True
            expiry_reason = ""
            
            if expires_at:
                try:
                    expires_date = datetime.fromisoformat(expires_at)
                    if expires_date < datetime.now():
                        is_active = False
                        expiry_reason = " (истек)"
                except:
                    pass
            
            if usage_limit > 0 and used_count >= usage_limit:
                is_active = False
                expiry_reason = " (лимит исчерпан)"
            
            if is_active:
                active_promos += 1
            
            # Форматируем данные
            expiry_text = expires_at.split()[0] if expires_at else "бессрочно"
            usage_text = f"{used_count}/{usage_limit}" if usage_limit > 0 else f"{used_count}/∞"
            created_text = created_at.split()[0]
            
            status_emoji = "🟢" if is_active else "🔴"
            
            text += f"{status_emoji} <b>{code}</b> (-{discount_percent}%){expiry_reason}\n"
            text += f"   🔢 Использовано: {usage_text}\n"
            text += f"   📅 Действует: {expiry_text}\n"
            text += f"   📋 Создан: {created_text}\n\n"
        
        text += f"📊 <b>Статистика:</b>\n"
        text += f"• Всего промокодов: {total_promos}\n"
        text += f"• Активных: {active_promos}\n"
        text += f"• Неактивных: {total_promos - active_promos}\n"
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("🔄 Обновить", callback_data="list_promos"),
            InlineKeyboardButton("➕ Добавить", callback_data="add_promo")
        )
        kb.add(
            InlineKeyboardButton("🗑️ Удалить", callback_data="delete_promo"),
            InlineKeyboardButton("◀️ Назад", callback_data="manage_promos")
        )
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        
    except Exception as e:
        logger.error(f"Error listing promos: {e}")
        await callback.message.answer(
            "❌ Ошибка при загрузке промокодов",
            parse_mode="HTML"
        )
    
    await callback.answer()

# ─── АВТО-ВЫДАЧА ─────────────────────────────────────────────
async def auto_delivery_start(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📍 Добавить точку клада", callback_data="add_auto_point"),
        InlineKeyboardButton("📋 Список точек кладов", callback_data="list_auto_points")
    )
    kb.add(InlineKeyboardButton("🗑️ Удалить точку клада", callback_data="delete_auto_point"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="cancel_action"))
    
    await callback.message.edit_text("🤖 <b>Управление авто-выдачей</b>", parse_mode="HTML", reply_markup=kb)
    await callback.answer()

async def add_auto_point_start(callback: types.CallbackQuery):
    """Начинает процесс добавления точки авто-выдачи"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            products = await (await db.execute('''
                SELECT p.id, p.name, c.name as category_name
                FROM products p 
                JOIN categories c ON p.category_id = c.id
                WHERE p.id NOT IN (SELECT product_id FROM hidden_products)
                ORDER BY c.name, p.name
            ''')).fetchall()
        
        if not products:
            await callback.message.answer(
                "❌ Нет доступных товаров для авто-выдачи\n\n"
                "💡 Сначала добавьте товары через меню '🎁 Добавить товар'"
            )
            return
        
        kb = InlineKeyboardMarkup()
        for prod_id, prod_name, category_name in products:
            kb.add(InlineKeyboardButton(f"{prod_name} ({category_name})", callback_data=f"autoprod_sel_{prod_id}"))
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        await callback.message.edit_text("🎁 Выберите товар для клада:", reply_markup=kb)
        await AutoDelivery.waiting_for_product.set()
        
    except Exception as e:
        logger.error(f"Error starting auto point addition: {e}")
        await callback.message.answer("❌ Ошибка при загрузке товаров")
        await show_admin_panel(callback.message)
    
    await callback.answer()

async def select_product_for_auto(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор товара для авто-выдачи"""
    try:
        product_id = int(callback.data.split("_")[2])
        
        # Сохраняем product_id в состоянии
        await state.update_data(product_id=product_id)
        
        # Получаем информацию о товаре (ТОЛЬКО ИМЯ, БЕЗ ЦЕНЫ!)
        async with aiosqlite.connect('shop.db') as db:
            product_info = await (await db.execute(
                "SELECT name FROM products WHERE id = ?", (product_id,)
            )).fetchone()
            
            if product_info:
                product_name = product_info[0]
                await state.update_data(product_name=product_name)
        
        # Получаем список городов
        async with aiosqlite.connect('shop.db') as db:
            cities = await (await db.execute("SELECT id, name FROM cities")).fetchall()
        
        if not cities:
            await callback.message.answer("❌ Сначала добавьте города!")
            await state.finish()
            await show_admin_panel(callback.message)
            return
        
        kb = InlineKeyboardMarkup()
        for city_id, city_name in cities:
            kb.add(InlineKeyboardButton(city_name, callback_data=f"autocity_sel_{city_id}"))
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        text = f"🎁 <b>Выбран товар:</b> {product_name}\n\n"
        text += "🏙️ Выберите город для клада:"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await AutoDelivery.waiting_for_city.set()
        
    except Exception as e:
        logger.error(f"Error selecting product for auto: {e}")
        await callback.message.answer("❌ Ошибка при выборе товара")
        await state.finish()
        await show_admin_panel(callback.message)
    
    await callback.answer()

async def select_city_for_auto(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор города для авто-выдачи"""
    try:
        city_id = int(callback.data.split("_")[2])
        
        # Сохраняем city_id в состоянии
        await state.update_data(city_id=city_id)
        
        # Получаем информацию о городе
        async with aiosqlite.connect('shop.db') as db:
            city_info = await (await db.execute(
                "SELECT name FROM cities WHERE id = ?", (city_id,)
            )).fetchone()
            
            if city_info:
                await state.update_data(city_name=city_info[0])
        
        # Получаем районы для этого города
        async with aiosqlite.connect('shop.db') as db:
            districts = await (await db.execute(
                "SELECT id, name FROM districts WHERE city_id = ?", (city_id,)
            )).fetchall()
        
        kb = InlineKeyboardMarkup()
        if districts:
            for dist_id, dist_name in districts:
                kb.add(InlineKeyboardButton(dist_name, callback_data=f"autodist_sel_{dist_id}"))
        kb.add(InlineKeyboardButton("❌ Без района", callback_data="autodist_sel_0"))
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        text = "🏘️ Выберите район для клада:"
        if city_info:
            text = f"🏙️ <b>Выбран город:</b> {city_info[0]}\n\n" + text
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await AutoDelivery.waiting_for_district.set()
        
    except Exception as e:
        logger.error(f"Error selecting city for auto: {e}")
        await callback.message.answer("❌ Ошибка при выборе города")
        await state.finish()
        await show_admin_panel(callback.message)
    
    await callback.answer()

async def select_district_for_auto(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор района для авто-выдачи"""
    try:
        district_id = int(callback.data.split("_")[2])
        
        if district_id == 0:
            # Без района
            await state.update_data(district_id=None, district_name=None)
            district_text = "без района"
        else:
            # С районом
            await state.update_data(district_id=district_id)
            
            # Получаем информацию о районе
            async with aiosqlite.connect('shop.db') as db:
                district_info = await (await db.execute(
                    "SELECT name FROM districts WHERE id = ?", (district_id,)
                )).fetchone()
                
                if district_info:
                    await state.update_data(district_name=district_info[0])
                    district_text = district_info[0]
        
        # Получаем данные из состояния для информационного сообщения
        data = await state.get_data()
        product_name = data.get('product_name', 'Неизвестно')
        city_name = data.get('city_name', 'Неизвестно')
        
        text = f"🎁 <b>Товар:</b> {product_name}\n"
        text += f"🏙️ <b>Город:</b> {city_name}\n"
        text += f"🏘️ <b>Район:</b> {district_text}\n\n"
        text += "📸 Отправьте фото клада (или нажмите 'Пропустить'):"
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⏭️ Пропустить фото", callback_data="skip_auto_photo"))
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await AutoDelivery.waiting_for_photo.set()
        
    except Exception as e:
        logger.error(f"Error selecting district for auto: {e}")
        await callback.message.answer("❌ Ошибка при выборе района")
        await state.finish()
        await show_admin_panel(callback.message)
    
    await callback.answer()

async def skip_auto_photo_handler(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск фото"""
    await state.update_data(photo_file_id=None)
    
    data = await state.get_data()
    product_name = data.get('product_name', 'Неизвестно')
    city_name = data.get('city_name', 'Неизвестно')
    
    text = f"🎁 <b>Товар:</b> {product_name}\n"
    text += f"🏙️ <b>Город:</b> {city_name}\n"
    text += f"📸 <b>Фото:</b> ❌ Без фото\n\n"
    text += "📝 Введите описание клада (можно пропустить, отправив '-'):"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await AutoDelivery.waiting_for_description.set()  # Прямо к описанию
    await callback.answer()

async def add_auto_photo(message: types.Message, state: FSMContext):
    """Обрабатывает фото клада"""
    try:
        if not message.photo:
            await message.answer("❌ Пожалуйста, отправьте фото или нажмите 'Пропустить':")
            return
        
        photo_file_id = message.photo[-1].file_id
        await state.update_data(photo_file_id=photo_file_id)
        
        # Получаем данные для информационного сообщения
        data = await state.get_data()
        product_name = data.get('product_name', 'Неизвестно')
        city_name = data.get('city_name', 'Неизвестно')
        
        text = f"🎁 <b>Товар:</b> {product_name}\n"
        text += f"🏙️ <b>Город:</b> {city_name}\n"
        text += f"📸 <b>Фото:</b> ✅ Получено\n\n"
        text += "📝 Введите описание клада (можно пропустить, отправив '-'):"
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        await AutoDelivery.waiting_for_description.set()  # Прямо к описанию
        
    except Exception as e:
        logger.error(f"Error processing auto photo: {e}")
        await message.answer("❌ Ошибка при обработке фото")
        await state.finish()
        await show_admin_panel(message)

async def add_auto_coordinates(message: types.Message, state: FSMContext):
    """Обрабатывает координаты клада"""
    try:
        coordinates = message.text.strip()
        
        # Простая валидация координат
        if not any(char in coordinates for char in ['.', ',']) or len(coordinates) < 5:
            await message.answer("❌ Неверный формат координат! Пример: 50.4504, 30.5245\nПопробуйте снова:")
            return
        
        await state.update_data(coordinates=coordinates)
        
        # Получаем данные для информационного сообщения
        data = await state.get_data()
        product_name = data.get('product_name', 'Неизвестно')
        city_name = data.get('city_name', 'Неизвестно')
        
        text = f"🎁 <b>Товар:</b> {product_name}\n"
        text += f"🏙️ <b>Город:</b> {city_name}\n"
        text += f"📍 <b>Координаты:</b> {coordinates}\n\n"
        text += "📝 Введите описание клада (можно пропустить, отправив '-'):"
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        await AutoDelivery.waiting_for_description.set()
        
    except Exception as e:
        logger.error(f"Error processing auto coordinates: {e}")
        await message.answer("❌ Ошибка при обработке координат")
        await state.finish()
        await show_admin_panel(message)

async def add_auto_description(message: types.Message, state: FSMContext):
    """Обрабатывает описание клада"""
    try:
        description = message.text if message.text != '-' else ""
        await state.update_data(description=description)
        
        # Получаем данные для информационного сообщения
        data = await state.get_data()
        product_name = data.get('product_name', 'Неизвестно')
        
        text = f"🎁 <b>Товар:</b> {product_name}\n"
        if description:
            text += f"📝 <b>Описание:</b> {description}\n\n"
        else:
            text += f"📝 <b>Описание:</b> Без описания\n\n"
        
        # Добавляем выбор единиц измерения
        kb = InlineKeyboardMarkup(row_width=3)
        kb.add(
            InlineKeyboardButton("⚖️ Граммы", callback_data="unit_grams"),
            InlineKeyboardButton("🔢 Штуки", callback_data="unit_pieces"),
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_action")
        )
        
        text += "📊 Выберите единицы измерения количества:"
        
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        
    except Exception as e:
        logger.error(f"Error processing auto description: {e}")
        await message.answer("❌ Ошибка при обработке описания")
        await state.finish()
        await show_admin_panel(message)

async def select_unit_for_auto(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор единиц измерения"""
    try:
        unit_type = callback.data.split("_")[1]  # grams или pieces
        
        if unit_type == "grams":
            unit_display = "граммы"
            unit_abbr = "г"
        else:  # pieces
            unit_display = "штуки"
            unit_abbr = "шт"
        
        await state.update_data(unit_type=unit_type, unit_display=unit_display, unit_abbr=unit_abbr)
        
        # Получаем данные для информационного сообщения
        data = await state.get_data()
        product_name = data.get('product_name', 'Неизвестно')
        
        text = f"🎁 <b>Товар:</b> {product_name}\n"
        text += f"📊 <b>Единицы измерения:</b> {unit_display}\n\n"
        text += f"🔢 Введите количество ({unit_abbr}):"
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await AutoDelivery.waiting_for_quantity.set()
        
    except Exception as e:
        logger.error(f"Error selecting unit for auto: {e}")
        await callback.message.answer("❌ Ошибка при выборе единиц измерения")
        await state.finish()
        await show_admin_panel(callback.message)
    
    await callback.answer()

async def list_auto_points(callback: types.CallbackQuery, state: FSMContext):
    """
    Обновлённая версия: использует helper build_auto_points_page.
    Пытается edit_message_text; если не выходит — удаляет старое и отправляет новое.
    Использует search_query из state, если он там есть.
    """
    try:
        user_id = callback.from_user.id
        raw = callback.data or ""
        logging.info(f"ENTER list_auto_points | from={user_id} data={raw!r}")
        logger.info("ENTER list_auto_points", user_id=user_id, details=f"data={raw}")

        # Определяем номер страницы
        page = 1
        if "list_auto_points_auto_page_" in raw:
            m = re.search(r"list_auto_points_auto_page_(\d+)", raw)
            if m:
                page = int(m.group(1))
        elif "auto_page_" in raw:
            m = re.search(r"auto_page_(\d+)", raw)
            if m:
                page = int(m.group(1))
        else:
            # оставляем 1 если просто "list_auto_points"
            page = 1

        # Получаем search_query из state (если есть)
        search_query = None
        try:
            st = await state.get_data()
            search_query = st.get("search_query")
        except Exception as e:
            logging.warning(f"Couldn't read state: {e}")

        header, kb, total_pages, total_items = await build_auto_points_page(search_query, page)

        # Попытка редактирования старого сообщения
        chat_id = getattr(callback.message, "chat", None).id if callback.message and callback.message.chat else None
        msg_id = getattr(callback.message, "message_id", None) if callback.message else None

        try:
            # пытаемся редактировать существующее сообщение (самый аккуратный вариант)
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=header, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
            await callback.answer()
            return
        except Exception as e:
            logging.warning(f"edit_message_text failed, will fallback to delete+send: {e}")
            logger.warning("list_auto_points edit failed", user_id=user_id, details=str(e))

        # Фолбек: удаляем старое сообщение и отправляем новое (жёсткое обновление)
        try:
            if chat_id and msg_id:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except Exception:
                    pass
            if chat_id:
                await bot.send_message(chat_id, header, reply_markup=kb, parse_mode="HTML")
            else:
                await callback.message.answer(header, reply_markup=kb, parse_mode="HTML")
            await callback.answer()
            return
        except Exception as e2:
            logging.exception(f"Fallback send failed: {e2}")
            logger.error("list_auto_points fallback send failed", user_id=user_id, details=str(e2))
            try:
                await callback.answer("❌ Ошибка при обновлении списка. Проверьте логи.", show_alert=True)
            except:
                pass
            return

    except Exception as outer:
        logging.exception(f"Unhandled exception in list_auto_points: {outer}")
        logger.error("Unhandled exception in list_auto_points", user_id=(callback.from_user.id if callback else None), details=str(outer))
        try:
            await callback.answer("❌ Внутренняя ошибка. Проверьте логи.", show_alert=True)
        except:
            pass

async def view_autopoint_detail(callback: types.CallbackQuery):
    """
    Дебаг-версия просмотра детали авто-точки.
    Логирует вход, получает данные из БД и безопасно редактирует/отправляет сообщение.
    """
    try:
        logging.info(f"ENTER view_autopoint_detail | from={callback.from_user.id} data={callback.data!r}")
        logger.info("ENTER view_autopoint_detail", user_id=callback.from_user.id, details=f"data={callback.data}")

        # Парсинг id
        try:
            parts = callback.data.split("_")
            point_id = int(parts[-1])
        except Exception as e:
            logging.exception(f"view_autopoint_detail: invalid callback.data: {callback.data} | {e}")
            await callback.answer("❌ Неверный идентификатор точки", show_alert=True)
            return

        # Получаем точку из БД
        async with aiosqlite.connect('shop.db') as db:
            row = await (await db.execute("""
                SELECT adp.id, p.name, c.name, d.name, adp.quantity_grams, 
                       adp.unit_type, adp.price, adp.is_used, adp.coordinates, 
                       adp.description, adp.photo_file_id, adp.created_at
                FROM auto_delivery_points adp
                JOIN products p ON adp.product_id = p.id
                JOIN cities c ON adp.city_id = c.id
                LEFT JOIN districts d ON adp.district_id = d.id
                WHERE adp.id = ?
            """, (point_id,))).fetchone()

        if not row:
            logging.warning(f"view_autopoint_detail: point not found id={point_id}")
            await callback.answer("❌ Клад не найден", show_alert=True)
            return

        (pid, prod, city, dist, qty, unit, price, is_used, coords, desc, photo, created) = row

        unit_disp = "шт" if unit == 'pieces' else "г"
        status = "🔴 ПРОДАН" if is_used else "🟢 АКТИВЕН"
        loc = f"{city}, {dist}" if dist else city

        text = f"📦 <b>Детали клада #{pid}</b>\n\n"
        text += f"📊 Статус: <b>{status}</b>\n"
        text += f"🎁 Товар: <b>{prod}</b>\n"
        text += f"⚖️ Вес/Кол-во: <b>{qty}{unit_disp}</b>\n"
        text += f"💰 Цена: <b>{price}€</b>\n"
        text += f"📍 Локация: <b>{loc}</b>\n"
        text += f"🗺 Координаты: <code>{coords or 'Не указаны'}</code>\n"
        text += f"📅 Создан: {created}\n"
        if desc:
            text += f"\n📝 Описание:\n<i>{desc}</i>"

        kb = types.InlineKeyboardMarkup(row_width=1)
        if not is_used:
            kb.add(types.InlineKeyboardButton("🗑️ Удалить этот клад", callback_data=f"delauto_conf_{pid}"))
        kb.add(types.InlineKeyboardButton("🔙 К списку", callback_data="list_auto_points"))

        # Попытка отредактировать старое сообщение; если не получилось — отправить новое
        chat_id = getattr(callback.message, "chat", None).id if callback.message and callback.message.chat else None
        msg_id = getattr(callback.message, "message_id", None) if callback.message else None

        try:
            logging.info(f"view_autopoint_detail: trying edit_message_text chat_id={chat_id} msg_id={msg_id}")
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
            logging.info("view_autopoint_detail: edit_message_text succeeded")
            await callback.answer()
            return
        except Exception as e:
            logging.exception(f"view_autopoint_detail: edit_message_text failed: {e}")
            logger.warning("view_autopoint_detail edit failed", user_id=callback.from_user.id, details=str(e))

        # Если есть фото — попробуем отправить фото с подписью (новое сообщение)
        if photo:
            try:
                # удаляем старое сообщение, чтобы не дублировать слишком много
                if chat_id and msg_id:
                    try:
                        await bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    except Exception:
                        pass
                await bot.send_photo(chat_id, photo, caption=text, reply_markup=kb, parse_mode="HTML")
                logging.info("view_autopoint_detail: send_photo fallback succeeded")
                await callback.answer()
                return
            except Exception as e:
                logging.exception(f"view_autopoint_detail: fallback send_photo failed: {e}")
                logger.error("view_autopoint_detail fallback photo failed", user_id=callback.from_user.id, details=str(e))

        # Последний fallback: отправить текстовое сообщение
        try:
            if chat_id:
                await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
            else:
                await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
            await callback.answer()
        except Exception as e:
            logging.exception(f"view_autopoint_detail: final fallback send failed: {e}")
            try:
                await callback.answer("❌ Ошибка при показе деталей. Смотрите логи.", show_alert=True)
            except:
                pass

    except Exception as outer_e:
        logging.exception(f"Unhandled in view_autopoint_detail: {outer_e}")
        logger.error("Unhandled in view_autopoint_detail", user_id=(callback.from_user.id if callback else None), details=str(outer_e))
        try:
            await callback.answer("❌ Внутренняя ошибка. Проверьте логи.", show_alert=True)
        except:
            pass

async def start_auto_search(callback: types.CallbackQuery, state: FSMContext):
    """
    Запускает режим поиска: просит ввести имя/город/ID и переводит в состояние ожидания.
    """
    try:
        prompt = (
            "🔍 Введите название товара, название города или ID клада для поиска:\n\n"
            "Пример: weed  или  Bratislava  или  1"
        )
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="list_auto_points"))
        # Редактируем текущее сообщение (аккуратно) или отправляем новое
        try:
            await callback.message.edit_text(prompt, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await callback.message.answer(prompt, reply_markup=kb, parse_mode="HTML")
        await SearchAutoPoints.waiting_for_query.set()
        await callback.answer()
    except Exception as e:
        logging.exception(f"start_auto_search error: {e}")
        try:
            await callback.answer("❌ Ошибка. См. логи.", show_alert=True)
        except:
            pass

async def process_search_query(message: types.Message, state: FSMContext):
    """
    Обрабатывает введённый текст поиска, сохраняет фильтр в state и выводит первую страницу результатов.
    """
    user_id = message.from_user.id
    query = message.text.strip()
    if not query:
        await message.answer("❌ Пустой запрос. Попробуйте ещё раз или нажмите Отмена.")
        return

    # Базовая валидация (безопасность)
    if not validate_user_input(query, max_length=200):
        await message.answer("❌ Недопустимые символы в запросе.")
        return

    # Сохраняем фильтр в state, чтобы пагинация его учитывала
    try:
        await state.update_data(search_query=query)
    except Exception as e:
        logging.warning(f"process_search_query: can't update state: {e}")

    # Формируем первую страницу
    header, kb, total_pages, total_items = await build_auto_points_page(query, page=1)

    # Удаляем сообщение пользователя (по желанию) чтобы не засорять чат
    try:
        await message.delete()
    except:
        pass

    # Пытаемся отредактировать предыдущий (если есть) иначе просто отправляем
    # Используем callback message — у нас нет callback здесь, поэтому просто отправляем новую
    try:
        await message.answer(header, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logging.exception(f"process_search_query: send failed: {e}")
        await message.answer("❌ Ошибка при показе результатов поиска. Проверьте логи.")

    # Состояние остаётся SearchAutoPoints.waiting_for_query (чтобы пагинация использовала его)
    # Не завершаем state тут — поиск сохраняется до явного сброса
    await SearchAutoPoints.waiting_for_query.set()

async def show_stats(callback):
    """
    Shows admin statistics pages.
    Expected callback.data format: "stats_main" or "stats_detailed"
    """
    try:
        stat_type = callback.data.split("_")[1] if "_" in callback.data else "main"

        async with aiosqlite.connect('shop.db') as db:
            if stat_type == "main":
                total_users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
                active_users = (await (await db.execute("SELECT COUNT(*) FROM users WHERE banned=0")).fetchone())[0]
                total_orders = (await (await db.execute("SELECT COUNT(*) FROM orders")).fetchone())[0]
                completed_orders = (await (await db.execute("SELECT COUNT(*) FROM orders WHERE status='completed'")).fetchone())[0]
                total_revenue = (await (await db.execute("SELECT COALESCE(SUM(final_price), 0) FROM orders WHERE status='completed'")).fetchone())[0] or 0

                today_orders = (await (await db.execute("""
                    SELECT COUNT(*), COALESCE(SUM(final_price), 0) 
                    FROM orders 
                    WHERE DATE(created_at) = DATE('now') AND status='completed'
                """)).fetchone())
                today_order_count, today_revenue = today_orders

                yesterday_orders = (await (await db.execute("""
                    SELECT COUNT(*), COALESCE(SUM(final_price), 0) 
                    FROM orders 
                    WHERE DATE(created_at) = DATE('now', '-1 day') AND status='completed'
                """)).fetchone())
                yesterday_order_count, yesterday_revenue = yesterday_orders

                text = "📊 <b>Основная статистика</b>\n\n"
                text += f"👥 <b>Пользователи:</b>\n"
                text += f"• Всего: {total_users}\n"
                text += f"• Активных: {active_users}\n\n"

                text += f"📦 <b>Заказы:</b>\n"
                text += f"• Всего: {total_orders}\n"
                text += f"• Завершено: {completed_orders}\n"
                text += f"• Конверсия: {(completed_orders/total_orders*100) if total_orders > 0 else 0:.1f}%\n\n"

                text += f"💰 <b>Финансы:</b>\n"
                text += f"• Общая выручка: {total_revenue:.2f}€\n"
                text += f"• Средний чек: {(total_revenue/completed_orders) if completed_orders > 0 else 0:.2f}€\n\n"

                text += f"📅 <b>Сегодня:</b>\n"
                text += f"• Заказов: {today_order_count}\n"
                text += f"• Выручка: {today_revenue:.2f}€\n\n"

                text += f"📅 <b>Вчера:</b>\n"
                text += f"• Заказов: {yesterday_order_count}\n"
                text += f"• Выручка: {yesterday_revenue:.2f}€\n\n"

                kb = InlineKeyboardMarkup(row_width=2)
                kb.add(
                    InlineKeyboardButton("📈 Детальная статистика", callback_data="stats_detailed"),
                    InlineKeyboardButton("🔄 Обновить", callback_data="stats_main")
                )
                kb.add(InlineKeyboardButton("◀️ Назад", callback_data="cancel_action"))

                await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

            elif stat_type == "detailed":
                product_stats = await (await db.execute("""
                    SELECT p.name, COUNT(o.id) as order_count, SUM(o.quantity) as total_quantity,
                           SUM(o.final_price) as total_revenue
                    FROM orders o
                    JOIN products p ON o.product_id = p.id
                    WHERE o.status='completed'
                    GROUP BY p.name
                    ORDER BY total_revenue DESC
                    LIMIT 10
                """)).fetchall()

                city_stats = await (await db.execute("""
                    SELECT c.name, COUNT(o.id) as order_count, SUM(o.final_price) as total_revenue
                    FROM orders o
                    JOIN cities c ON o.city_id = c.id
                    WHERE o.status='completed'
                    GROUP BY c.name
                    ORDER BY total_revenue DESC
                    LIMIT 10
                """)).fetchall()

                weekday_stats = await (await db.execute("""
                    SELECT 
                        strftime('%w', created_at) as weekday,
                        COUNT(*) as order_count,
                        SUM(final_price) as total_revenue
                    FROM orders 
                    WHERE status='completed'
                    GROUP BY weekday
                    ORDER BY weekday
                """)).fetchall()

                text = "📈 <b>Детальная статистика</b>\n\n"

                text += "🏪 <b>Топ товаров:</b>\n"
                for i, (product_name, order_count, total_quantity, total_revenue) in enumerate(product_stats, 1):
                    text += f"{i}. {product_name}\n"
                    text += f"   📦 {order_count} зак. | ⚖️ {total_quantity}г | 💰 {total_revenue:.2f}€\n"
                text += "\n"

                text += "🏙️ <b>Топ городов:</b>\n"
                for i, (city_name, order_count, total_revenue) in enumerate(city_stats, 1):
                    text += f"{i}. {city_name}\n"
                    text += f"   📦 {order_count} зак. | 💰 {total_revenue:.2f}€\n"
                text += "\n"

                text += "📅 <b>Активность по дням недели:</b>\n"
                weekdays = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
                for weekday_num, order_count, total_revenue in weekday_stats:
                    weekday_name = weekdays[int(weekday_num)]
                    text += f"• {weekday_name}: {order_count} зак. | {total_revenue:.2f}€\n"

                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("◀️ Назад к основной", callback_data="stats_main"))
                kb.add(InlineKeyboardButton("🏠 В меню", callback_data="cancel_action"))

                await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

        await callback.answer()
    except Exception as e:
        # Minimal error handling so admin_panel doesn't crash import time.
        try:
            await callback.answer("❌ Ошибка при получении статистики", show_alert=True)
        except:
            pass
        # Prefer to use logger if available in admin_panel module
        try:
            from logs import logger
            logger.error(f"Error in show_stats: {e}")
        except:
            pass

async def reset_auto_search(callback: types.CallbackQuery, state: FSMContext):
    """
    Сбрасывает фильтр поиска и показывает обычный список (страница 1).
    """
    try:
        await state.update_data(search_query=None)
    except:
        try:
            await state.reset_state(with_data=True)
        except:
            pass

    header, kb, total_pages, total_items = await build_auto_points_page(None, page=1)

    # Попытка отредактировать сообщение, иначе отправка нового
    try:
        await bot.edit_message_text(chat_id=callback.message.chat.id, message_id=callback.message.message_id, text=header, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        return
    except Exception:
        pass

    try:
        # fallback send
        await callback.message.answer(header, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
    except Exception as e:
        logging.exception(f"reset_auto_search failed: {e}")
        try:
            await callback.answer("❌ Ошибка при сбросе фильтра. Проверьте логи.", show_alert=True)
        except:
            pass

async def add_auto_quantity(message: types.Message, state: FSMContext):
    """Обрабатывает количество товара в кладе"""
    try:
        quantity = float(message.text)
        
        if quantity <= 0:
            await message.answer("❌ Количество должно быть больше 0")
            return
        
        # Сохраняем количество в состоянии
        await state.update_data(quantity=quantity)
        
        # Получаем данные для информационного сообщения
        data = await state.get_data()
        product_name = data.get('product_name', 'Неизвестно')
        unit_abbr = data.get('unit_abbr', 'г')
        
        text = f"🎁 <b>Товар:</b> {product_name}\n"
        text += f"⚖️ <b>Количество:</b> {quantity}{unit_abbr}\n\n"
        text += "💰 Введите ОБЩУЮ цену за весь клад (в €):\n"
        text += "<i>Например: 10, 20, 34.5 - это будет полная стоимость клада</i>"
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        await AutoDelivery.waiting_for_price.set()
        
    except ValueError:
        await message.answer("❌ Неверное количество. Введите число:")
    except Exception as e:
        logger.error(f"Error processing auto quantity: {e}")
        await message.answer("❌ Ошибка при обработке количества")
        await state.finish()
        await show_admin_panel(message)

async def add_auto_price(message: types.Message, state: FSMContext):
    """Обрабатывает ОБЩУЮ цену за весь клад (не за грамм!)"""
    try:
        total_price = float(message.text)
        
        if total_price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return
        
        # Сохраняем ОБЩУЮ цену в состоянии
        await state.update_data(price=total_price)
        
        # Получаем все данные для информационного сообщения
        data = await state.get_data()
        product_name = data.get('product_name', 'Неизвестно')
        quantity = data.get('quantity', 0)
        unit_abbr = data.get('unit_abbr', 'г')
        city_name = data.get('city_name', 'Неизвестно')
        district_name = data.get('district_name', 'без района')
        coordinates = data.get('coordinates', 'Не указаны')
        
        text = "✅ <b>Все данные готовы!</b>\n\n"
        text += f"🎁 <b>Товар:</b> {product_name}\n"
        text += f"🏙️ <b>Город:</b> {city_name}\n"
        text += f"🏘️ <b>Район:</b> {district_name}\n"
        text += f"📍 <b>Координаты:</b> {coordinates}\n"
        text += f"⚖️ <b>Количество:</b> {quantity}{unit_abbr}\n"
        text += f"💰 <b>Общая цена за клад:</b> {total_price}€\n"
        
        # УБИРАЕМ ВСЕ РАСЧЕТЫ ЦЕНЫ ЗА ЕДИНИЦУ
        # НЕ РАССЧИТЫВАЕМ И НЕ ПОКАЗЫВАЕМ ЦЕНУ ЗА ГРАММ/ШТУКУ
        
        if data.get('description'):
            text += f"📝 <b>Описание:</b> {data['description']}\n"
        
        if data.get('photo_file_id'):
            text += f"📸 <b>Фото:</b> ✅ Есть\n"
        else:
            text += f"📸 <b>Фото:</b> ❌ Нет\n"
        
        text += "\nДля подтверждения нажмите кнопку ниже:"
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("✅ Добавить клад", callback_data="confirm_auto_point"))
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        
    except ValueError:
        await message.answer("❌ Неверная цена. Введите число (например: 25.50):")

async def add_auto_price(message: types.Message, state: FSMContext):
    """Обрабатывает ОБЩУЮ цену за весь клад (не за грамм!)"""
    try:
        total_price = float(message.text)
        
        if total_price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return
        
        # Сохраняем ОБЩУЮ цену в состоянии
        await state.update_data(price=total_price)
        
        # Получаем все данные для информационного сообщения
        data = await state.get_data()
        product_name = data.get('product_name', 'Неизвестно')
        quantity = data.get('quantity', 0)
        unit_abbr = data.get('unit_abbr', 'г')
        city_name = data.get('city_name', 'Неизвестно')
        district_name = data.get('district_name', 'без района')
        coordinates = data.get('coordinates', 'Не указаны')
        
        text = "✅ <b>Все данные готовы!</b>\n\n"
        text += f"🎁 <b>Товар:</b> {product_name}\n"
        text += f"🏙️ <b>Город:</b> {city_name}\n"
        text += f"🏘️ <b>Район:</b> {district_name}\n"
        text += f"📍 <b>Координаты:</b> {coordinates}\n"
        text += f"⚖️ <b>Количество:</b> {quantity}{unit_abbr}\n"
        text += f"💰 <b>Общая цена за клад:</b> {total_price}€\n"
        
        # УБИРАЕМ ВСЕ РАСЧЕТЫ ЦЕНЫ ЗА ЕДИНИЦУ
        # УБИРАЕМ ЭТУ СТРОКУ: text += f"💵 <b>Общая стоимость клада:</b> {total_cost:.2f}€\n\n"
        
        if data.get('description'):
            text += f"📝 <b>Описание:</b> {data['description']}\n"
        
        if data.get('photo_file_id'):
            text += f"📸 <b>Фото:</b> ✅ Есть\n"
        else:
            text += f"📸 <b>Фото:</b> ❌ Нет\n"
        
        text += "\nДля подтверждения нажмите кнопку ниже:"
        
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("✅ Добавить клад", callback_data="confirm_auto_point"))
        kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
        
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
        
    except ValueError:
        await message.answer("❌ Неверная цена. Введите число (например: 25.50):")

async def confirm_auto_point(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение добавления точки авто-выдачи"""
    try:
        data = await state.get_data()
        
        # Проверяем наличие обязательных данных
        required_fields = ['product_id', 'city_id', 'quantity', 'unit_type', 'price']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            logger.error(f"Missing fields in state: {missing_fields}")
            logger.error(f"Current state data: {data}")
            await callback.message.answer(f"❌ Ошибка: отсутствуют данные - {', '.join(missing_fields)}")
            await state.finish()
            return
        
        async with aiosqlite.connect('shop.db') as db:
            # Сохраняем точку авто-выдачи
            cursor = await db.execute('''
                INSERT INTO auto_delivery_points 
                (product_id, city_id, district_id, photo_file_id, description, coordinates, quantity_grams, unit_type, price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['product_id'], data['city_id'], data['district_id'], 
                data.get('photo_file_id'), data.get('description'), 
                data.get('coordinates'), data['quantity'], data['unit_type'], 
                data['price']
            ))
            await db.commit()
            
            delivery_point_id = cursor.lastrowid
            
            # Получаем информацию о товаре
            product_info = await (await db.execute(
                "SELECT name FROM products WHERE id = ?", (data['product_id'],)
            )).fetchone()
            
            product_name = product_info[0] if product_info else "Неизвестный товар"
            
            # Получаем названия города и района
            city_info = await (await db.execute(
                "SELECT name FROM cities WHERE id = ?", (data['city_id'],)
            )).fetchone()
            city_name = city_info[0] if city_info else "Неизвестно"
            
            district_name = ""
            if data['district_id']:
                district_info = await (await db.execute(
                    "SELECT name FROM districts WHERE id = ?", (data['district_id'],)
                )).fetchone()
                district_name = district_info[0] if district_info else "Неизвестно"
        
        unit_display = "шт" if data['unit_type'] == 'pieces' else "г"
        
        text = f"✅ Клад успешно добавлен!\n\n"
        text += f"🎁 Товар: {product_name}\n"
        text += f"🏙️ Город: {city_name}\n"
        if district_name:
            text += f"🏘️ Район: {district_name}\n"
        text += f"⚖️ Количество: {data['quantity']}{unit_display}\n"
        text += f"💰 Цена: {data['price']}€\n"
        text += f"🆔 ID клада: {delivery_point_id}\n\n"
        text += f"📌 Товар теперь ВИДЕН пользователям!"
        
        # Создаем кнопку для возврата в админ-панель
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔙 Вернуться в админ-панель", callback_data="admin_panel"))
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        
        # Завершаем состояние
        await state.finish()
        
        
    except Exception as e:
        logger.error(f"Error confirming auto point: {e}")
        await callback.message.answer(f"❌ Ошибка при сохранении: {e}")
        await state.finish()

# ФУНКЦИЯ ДЛЯ ВОССТАНОВЛЕНИЯ СКРЫТОГО ТОВАРА
async def restore_hidden_product_start(callback: types.CallbackQuery):
    hidden_products = await auto_db.get_hidden_products()
    
    if not hidden_products:
        await callback.message.answer("❌ Нет скрытых товаров для восстановления")
        return
    
    kb = InlineKeyboardMarkup()
    for prod_id, name, price, description, hidden_at, reason in hidden_products:
        kb.add(InlineKeyboardButton(f"{name} ({price}€)", callback_data=f"restore_prod_{prod_id}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text("🔄 Выберите товар для восстановления:", reply_markup=kb)
    await callback.answer()

async def execute_restore_product(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    
    await auto_db.restore_hidden_product(product_id)
    
    await callback.message.answer("✅ Товар восстановлен и снова доступен для покупки!")
    await show_admin_panel(callback.message)
    await callback.answer()

async def delete_auto_point_start(callback: types.CallbackQuery):
    auto_points = await auto_db.get_auto_points()
    
    if not auto_points:
        await callback.message.answer("❌ Нет точек для удаления")
        return
    
    kb = InlineKeyboardMarkup()
    for point in auto_points:
        status = "🟢" if not point['is_used'] else "🔴"
        button_text = f"{status} {point['city_name']}, {point['district_name']} - {point['coordinates']}"
        kb.add(InlineKeyboardButton(button_text, callback_data=f"delauto_sel_{point['id']}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_action"))
    
    await callback.message.edit_text("🗑️ Выберите точку клада для удаления:", reply_markup=kb)
    await callback.answer()

async def confirm_delete_auto_point(callback: types.CallbackQuery):
    point_id = int(callback.data.split("_")[2])
    point = await auto_db.get_auto_point_by_id(point_id)
    
    if not point:
        await callback.answer("❌ Точка не найдена", show_alert=True)
        return
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Да, удалить", callback_data=f"delauto_conf_{point_id}"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="delete_auto_point"))
    
    text = f"⚠️ Вы уверены, что хотите удалить точку клада?\n\n"
    text += f"🏙️ Город: {point['city_name']}\n"
    text += f"🏘️ Район: {point['district_name']}\n"
    text += f"📍 Координаты: {point['coordinates']}\n"
    if point['description']:
        text += f"📝 Описание: {point['description']}\n"
    text += f"📊 Статус: {'🟢 Свободна' if not point['is_used'] else '🔴 Использована'}"
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

async def execute_delete_auto_point(callback: types.CallbackQuery, state: FSMContext):
    """Удаление точки авто-выдачи с возвратом в меню"""
    try:
        delivery_id = int(callback.data.split("_")[2])
        
        async with aiosqlite.connect('shop.db') as db:
            # Получаем информацию о точке перед удалением
            delivery_info = await (await db.execute('''
                SELECT product_id, quantity_grams, unit_type, price 
                FROM auto_delivery_points 
                WHERE id = ?
            ''', (delivery_id,))).fetchone()
            
            if not delivery_info:
                await callback.answer("❌ Точка авто-выдачи не найдена", show_alert=True)
                return
            
            product_id, quantity, unit_type, price = delivery_info
            
            # Удаляем точку
            await db.execute("DELETE FROM auto_delivery_points WHERE id = ?", (delivery_id,))
            await db.commit()
            
            # Получаем название товара
            product_info = await (await db.execute(
                "SELECT name FROM products WHERE id = ?", (product_id,)
            )).fetchone()
            
            product_name = product_info[0] if product_info else f"ID:{product_id}"
        
        unit_display = "шт" if unit_type == 'pieces' else "г"
        
        # Создаем клавиатуру для возврата
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📋 К списку точек", callback_data="list_auto_points"))
        kb.add(InlineKeyboardButton("🔙 В админ-панель", callback_data="admin_panel"))
        
        await callback.message.edit_text(
            f"✅ Точка авто-выдачи удалена!\n\n"
            f"🎁 Товар: {product_name}\n"
            f"⚖️ Количество: {quantity}{unit_display}\n"
            f"💰 Цена: {price}€\n\n"
            f"📌 Если это была последняя точка авто-выдачи, товар СКРЫТ.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        
        # Завершаем состояние
        await state.finish()
        
    except Exception as e:
        logger.error(f"Error deleting auto point: {e}")
        await callback.answer(f"❌ Ошибка при удалении: {e}", show_alert=True)
        await state.finish()

async def build_auto_points_page(search_query: str | None, page: int = 1, items_per_page: int = 8):
    offset = (page - 1) * items_per_page

    sql_count = """
        SELECT COUNT(*) 
        FROM auto_delivery_points adp
        JOIN products p ON adp.product_id = p.id
        JOIN cities c ON adp.city_id = c.id
    """
    sql_select = """
        SELECT adp.id, p.name, c.name, adp.quantity_grams, adp.unit_type, adp.price, adp.is_used
        FROM auto_delivery_points adp
        JOIN products p ON adp.product_id = p.id
        JOIN cities c ON adp.city_id = c.id
    """
    params = []
    if search_query:
        if search_query.isdigit():
            where_clause = " WHERE (adp.id = ? OR p.name LIKE ? OR c.name LIKE ?)"
            params = [int(search_query), f"%{search_query}%", f"%{search_query}%"]
        else:
            where_clause = " WHERE (p.name LIKE ? OR c.name LIKE ?)"
            params = [f"%{search_query}%", f"%{search_query}%"]
        sql_count += where_clause
        sql_select += where_clause

    sql_select += " ORDER BY adp.is_used ASC, adp.created_at DESC LIMIT ? OFFSET ?"
    params_select = params + [items_per_page, offset]

    async with aiosqlite.connect('shop.db') as db:
        total_items_row = await (await db.execute(sql_count, params)).fetchone()
        total_items = total_items_row[0] if total_items_row else 0
        points = await (await db.execute(sql_select, params_select)).fetchall()

    total_pages = 1 if total_items <= 0 else (total_items + items_per_page - 1) // items_per_page

    kb = types.InlineKeyboardMarkup(row_width=1)
    for point_id, prod_name, city, qty, unit, price, is_used in points:
        unit_display = "шт" if (unit == 'pieces') else "г"
        status_icon = "🔴" if is_used else "🟢"
        btn_text = f"[ID:{point_id}] {status_icon} {city} - {prod_name} ({qty}{unit_display}) - {price}€"
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"view_autopoint_{point_id}"))

    # pagination
    pagination_btns = []
    if page > 1:
        pagination_btns.append(types.InlineKeyboardButton("⬅️ Пред.", callback_data=f"list_auto_points_auto_page_{page-1}"))
    if page < total_pages:
        pagination_btns.append(types.InlineKeyboardButton("След. ➡️", callback_data=f"list_auto_points_auto_page_{page+1}"))
    if pagination_btns:
        kb.row(*pagination_btns)

    if search_query:
        kb.add(types.InlineKeyboardButton(f"🔎 Фильтр: {search_query} (Сбросить ❌)", callback_data="reset_auto_search"))
    else:
        kb.add(types.InlineKeyboardButton("🔍 Поиск по названию/городу/ID", callback_data="start_auto_search"))
    kb.add(types.InlineKeyboardButton("🔙 Меню авто-выдачи", callback_data="auto_delivery_panel"))

    header = "📦 <b>Список кладов</b>"
    if search_query:
        header += f" (🔍 {search_query})"
    header += f"\n📄 Страница {page} из {total_pages} (Всего: {total_items})"

    return header, kb, total_pages, total_items

# ─── СКРЫТЫЕ ТОВАРЫ ──────────────────────────────────────────
async def manage_hidden_products(callback: types.CallbackQuery):
    hidden_products = await auto_db.get_hidden_products()
    
    if not hidden_products:
        await callback.message.answer("✅ Нет скрытых товаров")
        await callback.answer()
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    text = "📦 <b>Скрытые товары (нет доступных кладов):</b>\n\n"
    
    for i, (product_id, product_name, category_name) in enumerate(hidden_products, 1):
        text += f"{i}. {product_name} ({category_name})\n"
        kb.add(InlineKeyboardButton(
            f"👁️ Показать {product_name}", 
            callback_data=f"restore_product_{product_id}"
        ))
    
    kb.add(InlineKeyboardButton("🔄 Проверить доступность", callback_data="check_delivery_availability"))
    kb.add(InlineKeyboardButton("◀️ Назад", callback_data="cancel_action"))
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

async def restore_product_handler(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    
    await auto_db.restore_product_visibility(product_id)
    await callback.answer(f"✅ Товар восстановлен!")
    
    # Обновляем список
    await manage_hidden_products(callback)

async def check_delivery_availability(callback: types.CallbackQuery):
    hidden_count = await auto_db.check_and_hide_empty_products()
    
    if hidden_count > 0:
        await callback.answer(f"🔄 Скрыто {hidden_count} товаров без кладов", show_alert=True)
    else:
        await callback.answer("✅ Все товары имеют доступные клады", show_alert=True)
    
    await manage_hidden_products(callback)

async def update_product_visibility(product_id):
    """
    Обновляет видимость товара на основе наличия авто-выдачи
    is_hidden = 0 (видимый) если есть активная авто-выдача
    is_hidden = 1 (скрытый) если нет авто-выдачи
    """
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Проверяем, есть ли активные точки авто-выдачи для товара
            cursor = await db.execute('''
                SELECT COUNT(*) 
                FROM auto_delivery_points 
                WHERE product_id = ? 
                AND is_used = 0 
                AND is_hidden = 0
            ''', (product_id,))
            
            result = await cursor.fetchone()
            has_auto_delivery = result[0] > 0 if result else False
            
            # Обновляем видимость товара
            is_hidden = 0 if has_auto_delivery else 1
            
            await db.execute(
                "UPDATE products SET is_hidden = ? WHERE id = ?",
                (is_hidden, product_id)
            )
            await db.commit()
            
            # Получаем название товара для логирования
            product_info = await (await db.execute(
                "SELECT name FROM products WHERE id = ?", (product_id,)
            )).fetchone()
            
            product_name = product_info[0] if product_info else f"ID:{product_id}"
            
            logger.info(f"🔄 Updated product visibility: {product_name} - {'🟢 VISIBLE' if not is_hidden else '🔴 HIDDEN'}")
            
    except Exception as e:
        logger.error(f"Error updating product visibility for {product_id}: {e}")

async def toggle_product_visibility(callback: types.CallbackQuery):
    """Ручное переключение видимости товара"""
    try:
        product_id = int(callback.data.split("_")[2])
        
        async with aiosqlite.connect('shop.db') as db:
            # Получаем текущий статус
            product_info = await (await db.execute(
                "SELECT name, is_hidden FROM products WHERE id = ?", (product_id,)
            )).fetchone()
            
            if not product_info:
                await callback.answer("❌ Товар не найден", show_alert=True)
                return
            
            product_name, current_hidden = product_info
            
            # Переключаем статус
            new_hidden = 0 if current_hidden == 1 else 1
            
            await db.execute(
                "UPDATE products SET is_hidden = ? WHERE id = ?",
                (new_hidden, product_id)
            )
            await db.commit()
        
        status = "🟢 ВИДИМЫЙ" if new_hidden == 0 else "🔴 СКРЫТЫЙ"
        
        await callback.message.edit_text(
            f"✅ Видимость товара обновлена!\n\n"
            f"🎁 Товар: {product_name}\n"
            f"🆔 ID: {product_id}\n"
            f"📊 Статус: {status}\n\n"
            f"⚠️ <b>Внимание:</b> Ручное изменение видимости может нарушить логику системы.",
            parse_mode="HTML"
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error toggling product visibility: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

async def show_hidden_products(callback: types.CallbackQuery):
    """Показать скрытые товары"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            products = await (await db.execute('''
                SELECT p.id, p.name, p.category_id, c.name as category_name,
                       (SELECT COUNT(*) FROM auto_delivery_points adp 
                        WHERE adp.product_id = p.id AND adp.is_used = 0) as auto_count
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.is_hidden = 1
                ORDER BY p.name
            ''')).fetchall()

        if not products:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("◀️ Назад", callback_data="admin_panel"))
            await callback.message.edit_text(
                "📦 <b>Скрытые товары</b>\n\n"
                "✅ Нет скрытых товаров! Все товары видны пользователям.",
                reply_markup=kb, parse_mode="HTML"
            )
            await callback.answer()
            return

        text = "📦 <b>Скрытые товары</b>\n\n"
        text += f"Всего скрыто: {len(products)} товаров\n\n"

        kb = InlineKeyboardMarkup(row_width=1)

        for pid, name, cat_id, cat_name, auto_count in products:
            text += f"🎁 <b>{name}</b>\n"
            text += f"   🆔 ID: {pid} | 📂 {cat_name or 'Без категории'}\n"
            text += f"   🚚 Точек авто-выдачи: {auto_count}\n\n"

            # Add toggle button to change visibility manually
            kb.add(InlineKeyboardButton(
                f"👁️ Управлять {name}",
                callback_data=f"toggle_product_{pid}"
            ))

        kb.add(InlineKeyboardButton("🔄 Проверить наличие кладов", callback_data="check_delivery_availability"))
        kb.add(InlineKeyboardButton("◀️ Назад", callback_data="admin_panel"))

        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing hidden products: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

# ─── ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ ──────────────────────────────────────
async def build_users_table_page(search_query: str | None = None, page: int = 1, items_per_page: int = 10, sort_by: str = "created_at", sort_order: str = "DESC"):
    """
    Построение таблицы пользователей с пагинацией, поиском и сортировкой
    """
    offset = (page - 1) * items_per_page
    
    # Базовый запрос
    sql_count = "SELECT COUNT(*) FROM users WHERE 1=1"
    sql_select = """
        SELECT 
            user_id, 
            username, 
            banned, 
            subscribed,
            created_at,
            (SELECT COUNT(*) FROM orders WHERE user_id = users.user_id) as total_orders,
            (SELECT COUNT(*) FROM orders WHERE user_id = users.user_id AND status = 'completed') as completed_orders,
            (SELECT COALESCE(SUM(final_price), 0) FROM orders WHERE user_id = users.user_id AND status = 'completed') as total_spent
        FROM users 
        WHERE 1=1
    """
    
    params = []
    
    # Поиск по ID или username
    if search_query:
        if search_query.isdigit():
            where_clause = " AND (user_id = ? OR username LIKE ?)"
            params = [int(search_query), f"%{search_query}%"]
        else:
            where_clause = " AND username LIKE ?"
            params = [f"%{search_query}%"]
        sql_count += where_clause
        sql_select += where_clause
    
    # Сортировка
    sort_columns = {
        "id": "user_id",
        "username": "username",
        "created": "created_at",
        "orders": "total_orders",
        "spent": "total_spent"
    }
    
    sort_column = sort_columns.get(sort_by, "created_at")
    order = "DESC" if sort_order == "DESC" else "ASC"
    
    sql_select += f" ORDER BY {sort_column} {order} LIMIT ? OFFSET ?"
    params_select = params + [items_per_page, offset]
    
    async with aiosqlite.connect('shop.db') as db:
        # Общее количество
        total_items_row = await (await db.execute(sql_count, params)).fetchone()
        total_items = total_items_row[0] if total_items_row else 0
        
        # Данные пользователей
        users = await (await db.execute(sql_select, params_select)).fetchall()
    
    # Подсчет страниц
    total_pages = 1 if total_items <= 0 else (total_items + items_per_page - 1) // items_per_page
    
    # Формирование заголовка
    header = "👥 <b>Таблица пользователей</b>"
    if search_query:
        header += f" (🔍 {search_query})"
    header += f"\n📄 Страница {page} из {total_pages} (Всего: {total_items})\n\n"
    
    # Краткая информация о статусах на странице
    banned_count = sum(1 for row in users if row[2])  # banned
    subscribed_count = sum(1 for row in users if row[3])  # subscribed
    
    header += f"📊 <b>Статистика страницы:</b>\n"
    header += f"• 🟢 Активных: {len(users) - banned_count}\n"
    header += f"• 🔴 Забанено: {banned_count}\n"
    header += f"• ✅ Подписано: {subscribed_count}\n\n"
    
    return header, total_pages, total_items, users

async def build_users_table_keyboard(search_query: str | None, page: int, total_pages: int, sort_by: str, sort_order: str, users_data: list):
    """
    Построение клавиатуры для таблицы пользователей - как в списке кладов
    """
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    # Кнопки для каждого пользователя
    for user_id, username, banned, subscribed, created_at, total_orders, completed_orders, total_spent in users_data:
        # Форматируем информацию о пользователе
        status_icon = "🔴" if banned else "🟢"
        username_display = f"@{username}" if username else f"ID:{user_id}"
        reg_date = created_at.split()[0] if created_at else "н/д"
        
        # Краткая информация: статус + имя + дата регистрации + заказы
        btn_text = f"{status_icon} {username_display} ({reg_date})"
        if total_orders > 0:
            btn_text += f" - {completed_orders}/{total_orders} зак."
            if total_spent > 0:
                btn_text += f" ({total_spent:.0f}€)"
        
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f"user_detail_{user_id}"))
    
    # Пагинация
    pagination_btns = []
    if page > 1:
        pagination_btns.append(types.InlineKeyboardButton("⬅️ Пред.", callback_data=f"users_page_{page-1}"))
    if page < total_pages:
        pagination_btns.append(types.InlineKeyboardButton("След. ➡️", callback_data=f"users_page_{page+1}"))
    if pagination_btns:
        kb.row(*pagination_btns)
    
    # Сортировка (простая строка с текущей сортировкой и кнопкой смены)
    current_sort_text = {
        "id": "🆔 ID",
        "username": "👤 Имя", 
        "created": "📅 Регистрация",
        "orders": "📦 Заказы",
        "spent": "💰 Потрачено"
    }.get(sort_by, "📅 Дата")
    
    current_order_icon = "⬆️" if sort_order == "ASC" else "⬇️"
    
    # Кнопка смены сортировки
    sort_callback = f"users_sort_{sort_by}_{('ASC' if sort_order == 'DESC' else 'DESC')}"
    kb.add(types.InlineKeyboardButton(f"📊 Сортировка: {current_sort_text} {current_order_icon}", callback_data=sort_callback))
    
    # Поиск/фильтр
    if search_query:
        kb.add(types.InlineKeyboardButton(f"🔎 Фильтр: {search_query[:15]} (Сбросить ❌)", callback_data="users_clear_search"))
    else:
        kb.add(types.InlineKeyboardButton("🔍 Поиск по ID/имени", callback_data="users_start_search"))
    
    # Кнопки действий
    kb.row(
        types.InlineKeyboardButton("📈 Статистика", callback_data="users_stats"),
        types.InlineKeyboardButton("🔄 Обновить", callback_data=f"users_page_{page}")
    )
    
    # Назад
    kb.add(types.InlineKeyboardButton("🔙 Назад в админ-панель", callback_data="view_users_table_back"))
    
    return kb

async def show_users_table(callback: types.CallbackQuery, state: FSMContext = None, page: int = 1, sort_by: str = "created_at", sort_order: str = "DESC"):
    """
    Отображение таблицы пользователей
    """
    try:
        # Получаем поисковый запрос из состояния
        search_query = None
        if state:
            try:
                user_data = await state.get_data()
                search_query = user_data.get("users_search_query")
            except:
                pass
        
        # Получаем данные страницы
        table_text, total_pages, total_items, users_data = await build_users_table_page(
            search_query=search_query,
            page=page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Создаем клавиатуру
        kb = await build_users_table_keyboard(
            search_query=search_query,
            page=page,
            total_pages=total_pages,
            sort_by=sort_by,
            sort_order=sort_order,
            users_data=users_data
        )
        
        # Сохраняем текущие параметры в состоянии
        if state:
            await state.update_data({
                "users_current_page": page,
                "users_sort_by": sort_by,
                "users_sort_order": sort_order,
                "users_search_query": search_query
            })
        
        # Пытаемся отредактировать сообщение
        try:
            await callback.message.edit_text(
                text=table_text,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception as edit_error:
            # Если не удалось отредактировать (например, callback устарел), 
            # отправляем новое сообщение
            logger.warning(f"Could not edit message, sending new: {edit_error}")
            await callback.message.answer(table_text, reply_markup=kb, parse_mode="HTML")
        
        # Всегда отвечаем на callback, даже если были ошибки
        try:
            await callback.answer()
        except:
            pass  # Игнорируем ошибки ответа на callback
        
    except Exception as e:
        logger.error(f"Error showing users table: {e}")
        # Пытаемся отправить сообщение об ошибке
        try:
            await callback.message.answer("❌ Ошибка при загрузке таблицы. Попробуйте еще раз.")
        except:
            pass

async def users_start_search(callback: types.CallbackQuery, state: FSMContext):
    """
    Начало поиска пользователей
    """
    try:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="view_users_table"))
        
        # Отправляем новое сообщение вместо редактирования
        await callback.message.answer(
            "🔍 <b>Поиск пользователей</b>\n\n"
            "Введите ID пользователя или часть username для поиска:\n\n"
            "<i>Примеры:</i>\n"
            "<code>123456789</code> - поиск по ID\n"
            "<code>ivan</code> - поиск по username\n\n"
            "<i>Для отмены нажмите кнопку ниже</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        
        await ViewUsersTable.waiting_for_query.set()
        
        # Отвечаем на callback
        try:
            await callback.answer()
        except:
            pass  # Игнорируем ошибки callback
        
    except Exception as e:
        logger.error(f"Error starting users search: {e}")
        try:
            await callback.answer("❌ Ошибка", show_alert=True)
        except:
            pass

async def process_users_search(message: types.Message, state: FSMContext):
    """
    Обработка поискового запроса пользователей
    """
    try:
        search_query = message.text.strip()
        
        if not search_query:
            await message.answer("❌ Введите текст для поиска")
            return
        
        # Базовая валидация
        if not validate_user_input(search_query, max_length=200):
            await message.answer("❌ Недопустимые символы в запросе.")
            return
        
        # Сохраняем запрос в состоянии
        await state.update_data(users_search_query=search_query)
        
        # Удаляем сообщение пользователя
        try:
            await message.delete()
        except:
            pass
        
        # Получаем данные для отображения
        search_query = search_query  # полученный запрос
        page = 1
        
        # Пытаемся отправить новое сообщение с результатами
        try:
            # Получаем данные страницы
            table_text, total_pages, total_items, users_data = await build_users_table_page(
                search_query=search_query,
                page=page,
                sort_by="created_at",
                sort_order="DESC"
            )
            
            # Создаем клавиатуру
            kb = await build_users_table_keyboard(
                search_query=search_query,
                page=page,
                total_pages=total_pages,
                sort_by="created_at",
                sort_order="DESC",
                users_data=users_data
            )
            
            # Отправляем новое сообщение с результатами
            await message.answer(table_text, reply_markup=kb, parse_mode="HTML")
            
            # Сохраняем текущие параметры в состоянии
            await state.update_data({
                "users_current_page": page,
                "users_sort_by": "created_at",
                "users_sort_order": "DESC",
                "users_search_query": search_query
            })
            
        except Exception as e:
            logger.error(f"Error showing search results: {e}")
            await message.answer(f"✅ Найдены пользователи по запросу '{search_query}'\n\nНажмите на кнопку 'Поиск' в таблице пользователей для просмотра.")
        
    except Exception as e:
        logger.error(f"Error processing users search: {e}")
        # Отправляем простое сообщение об ошибке
        try:
            await message.answer(f"✅ Поиск выполнен! Запрос сохранен: '{message.text.strip()}'\n\nПерейдите в таблицу пользователей для просмотра результатов.")
        except:
            pass

async def users_clear_search(callback: types.CallbackQuery, state: FSMContext):
    """
    Очистка поискового запроса
    """
    try:
        if state:
            await state.update_data(users_search_query=None)
        
        await show_users_table(callback, state, page=1)
        await callback.answer("🔍 Поиск очищен")
        
    except Exception as e:
        logger.error(f"Error clearing users search: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

async def users_change_sort(callback: types.CallbackQuery, state: FSMContext):
    """
    Изменение сортировки таблицы
    """
    try:
        # Получаем параметры сортировки из callback data
        # Формат: users_sort_column_order
        parts = callback.data.split("_")
        if len(parts) >= 4:
            sort_by = parts[2]
            sort_order = parts[3]
        else:
            sort_by = "created_at"
            sort_order = "DESC"
        
        # Получаем текущую страницу из состояния
        current_page = 1
        if state:
            try:
                user_data = await state.get_data()
                current_page = user_data.get("users_current_page", 1)
            except:
                pass
        
        await show_users_table(callback, state, page=current_page, sort_by=sort_by, sort_order=sort_order)
        
    except Exception as e:
        logger.error(f"Error changing sort: {e}")
        await callback.answer("❌ Ошибка сортировки", show_alert=True)

async def users_change_page(callback: types.CallbackQuery, state: FSMContext):
    """
    Изменение страницы таблицы
    """
    try:
        # Получаем номер страницы из callback data
        # Формат: users_page_N
        page = int(callback.data.split("_")[2])
        
        # Получаем параметры сортировки из состояния
        sort_by = "created_at"
        sort_order = "DESC"
        
        if state:
            try:
                user_data = await state.get_data()
                sort_by = user_data.get("users_sort_by", "created_at")
                sort_order = user_data.get("users_sort_order", "DESC")
            except:
                pass
        
        await show_users_table(callback, state, page=page, sort_by=sort_by, sort_order=sort_order)
        
    except Exception as e:
        logger.error(f"Error changing page: {e}")
        try:
            await callback.answer("❌ Ошибка пагинации", show_alert=True)
        except:
            pass

async def users_show_stats(callback: types.CallbackQuery):
    """
    Показать статистику по пользователям
    """
    try:
        async with aiosqlite.connect('shop.db') as db:
            # Общая статистика
            total_stats = await (await db.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN banned = 1 THEN 1 END) as banned,
                    COUNT(CASE WHEN subscribed = 1 THEN 1 END) as subscribed,
                    COUNT(CASE WHEN username IS NOT NULL AND username != '' THEN 1 END) as with_username
                FROM users
            """)).fetchone()
            
            # Активность по дням (последние 7 дней)
            activity_stats = await (await db.execute("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as registrations
                FROM users
                WHERE DATE(created_at) >= DATE('now', '-7 days')
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """)).fetchall()
            
            # Топ пользователей по потраченным деньгам
            top_by_spent = await (await db.execute("""
                SELECT 
                    u.user_id,
                    u.username,
                    COUNT(o.id) as order_count,
                    COALESCE(SUM(o.final_price), 0) as total_spent
                FROM users u
                LEFT JOIN orders o ON u.user_id = o.user_id AND o.status = 'completed'
                GROUP BY u.user_id
                HAVING total_spent > 0
                ORDER BY total_spent DESC
                LIMIT 5
            """)).fetchall()
            
            # Последние регистрации
            recent_users = await (await db.execute("""
                SELECT user_id, username, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT 5
            """)).fetchall()
        
        total, banned, subscribed, with_username = total_stats
        
        text = "📊 <b>Статистика пользователей</b>\n\n"
        
        text += "📈 <b>Общая статистика:</b>\n"
        text += f"• Всего пользователей: <b>{total}</b>\n"
        text += f"• 🟢 Активных: <b>{total - banned}</b>\n"
        text += f"• 🔴 Забанено: <b>{banned}</b>\n"
        text += f"• ✅ Подписано: <b>{subscribed}</b>\n"
        text += f"• 👤 С username: <b>{with_username}</b>\n\n"
        
        if activity_stats:
            text += "📅 <b>Регистрации за 7 дней:</b>\n"
            for date, count in activity_stats:
                text += f"• {date}: {count} чел.\n"
            text += "\n"
        
        if top_by_spent:
            text += "🏆 <b>Топ покупателей:</b>\n"
            for i, (user_id, username, order_count, total_spent) in enumerate(top_by_spent, 1):
                username_display = f"@{username}" if username else f"ID:{user_id}"
                text += f"{i}. {username_display}\n"
                text += f"   📦 {order_count} зак. | 💰 {total_spent:.2f}€\n"
            text += "\n"
        
        if recent_users:
            text += "🆕 <b>Последние регистрации:</b>\n"
            for user_id, username, created_at in recent_users:
                username_display = f"@{username}" if username else f"ID:{user_id}"
                reg_date = created_at.split()[0] if created_at else "н/д"
                text += f"• {username_display} ({reg_date})\n"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 К таблице", callback_data="view_users_table"))
        
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing users stats: {e}")
        await callback.answer("❌ Ошибка при загрузке статистики", show_alert=True)

async def view_users_table_back(callback: types.CallbackQuery, state: FSMContext):
    """
    Возврат из таблицы пользователей в главное меню
    """
    try:
        if state:
            await state.finish()
        await show_admin_panel(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error returning from users table: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# ─── КРИПТО КОШЕЛЬКИ (ПРЯМАЯ ОПЛАТА) ──────────────────────────
async def edit_crypto_wallets_start(callback: types.CallbackQuery):
    """Показывает меню управления крипто-кошельками"""
    try:
        from direct_payment import CRYPTO_SETTINGS
        
        text = "<b>🪙 УПРАВЛЕНИЕ КРИПТО-КОШЕЛЬКАМИ</b>\n\n"
        
        for crypto_id, settings in CRYPTO_SETTINGS.items():
            wallet = settings.get('wallet_address', 'Не установлен')
            wallet_display = f"{wallet[:8]}...{wallet[-4:]}" if len(wallet) > 20 else wallet
            status = "✅" if settings['enabled'] and wallet else "❌"
            
            text += f"{status} <b>{settings['name']}</b> ({settings['network']}) • <code>{wallet_display}</code>\n"
        
        text += "\n<b>Выберите криптовалюту для настройки:</b>"
        
        kb = InlineKeyboardMarkup(row_width=2)
        
        # Кнопки для каждой криптовалюты
        kb.row(
            InlineKeyboardButton("💰 USDT", callback_data="edit_wallet_usdt"),
            InlineKeyboardButton("₿ BTC", callback_data="edit_wallet_btc")
        )
        kb.row(
            InlineKeyboardButton("≡ ETH", callback_data="edit_wallet_eth"),
            InlineKeyboardButton("💎 TON", callback_data="edit_wallet_ton")
        )
        kb.row(
            InlineKeyboardButton("☀️ SOL", callback_data="edit_wallet_sol"),
            InlineKeyboardButton("💠 TRX", callback_data="edit_wallet_trx")
        )
        kb.row(
            InlineKeyboardButton("� LTC", callback_data="edit_wallet_ltc"),
            InlineKeyboardButton("💵 USDC", callback_data="edit_wallet_usdc_bep20")
        )
        kb.row(InlineKeyboardButton("💛 BNB", callback_data="edit_wallet_bnb"))
        kb.row(InlineKeyboardButton("◀️ Назад", callback_data="cancel_action"))
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing crypto wallets menu: {e}")
        await callback.answer("❌ Ошибка загрузки настроек", show_alert=True)


async def edit_usdt_wallet_start(callback: types.CallbackQuery):
    """Запрашивает новый USDT адрес"""
    text = """
<b>📝 ИЗМЕНИТЬ USDT TRC20 АДРЕС</b>

Введите новый адрес USDT кошелька в сети TRC20:

<b>⚠️ ВАЖНО:</b>
• Адрес должен начинаться с 'T'
• Длина: 34 символа
• Проверьте адрес несколько раз!
• Неправильный адрес = потеря средств

<b>Пример:</b>
<code>TYourWalletAddressHere123456789</code>
"""
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="edit_crypto_wallets"))
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await EditCryptoWallets.waiting_for_usdt_wallet.set()
    await callback.answer()


async def set_usdt_wallet(message: types.Message, state: FSMContext):
    """Сохраняет новый USDT адрес"""
    wallet = message.text.strip()
    
    # Валидация TRON адреса
    if not wallet.startswith('T'):
        await message.answer("❌ Адрес TRON должен начинаться с 'T'")
        return
    
    if len(wallet) != 34:
        await message.answer(f"❌ Неверная длина адреса ({len(wallet)} символов, должно быть 34)")
        return
    
    # Проверка на опасные символы
    if not wallet.isalnum():
        await message.answer("❌ Адрес содержит недопустимые символы")
        return
    
    try:
        from direct_payment import set_usdt_wallet_to_db, USDT_SETTINGS
        
        await set_usdt_wallet_to_db(wallet)
        
        await message.answer(f"""
✅ <b>USDT адрес успешно обновлен!</b>

<b>Новый адрес:</b>
<code>{wallet}</code>

<b>Сеть:</b> {USDT_SETTINGS['network']}

Теперь пользователи будут отправлять USDT на этот адрес при выборе прямой оплаты.
""", parse_mode="HTML")
        
        await state.finish()
        await show_admin_panel(message)
        
    except Exception as e:
        logger.error(f"Error setting USDT wallet: {e}")
        await message.answer("❌ Ошибка сохранения адреса")
        await state.finish()


async def edit_trongrid_api_start(callback: types.CallbackQuery):
    """Запрашивает TronGrid API ключ"""
    text = """
<b>🔑 TRONGRID API КЛЮЧ</b>

Введите ваш TronGrid API ключ:

<b>ℹ️ Зачем нужен API ключ?</b>
• Ускоряет проверку транзакций
• Увеличивает лимит запросов
• Повышает стабильность работы

<b>🔗 Где получить?</b>
1. Зайдите на https://www.trongrid.io/
2. Зарегистрируйтесь/войдите
3. Создайте API ключ
4. Скопируйте и отправьте сюда

<b>⚠️ Опционально:</b> Можно оставить пустым
Отправьте "skip" чтобы пропустить
"""
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data="edit_crypto_wallets"))
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await EditCryptoWallets.waiting_for_trongrid_api_key.set()
    await callback.answer()


async def set_trongrid_api_key(message: types.Message, state: FSMContext):
    """Сохраняет TronGrid API ключ"""
    api_key = message.text.strip()
    
    # Пропуск установки ключа
    if api_key.lower() == 'skip':
        await message.answer("⏭ API ключ не изменен")
        await state.finish()
        await show_admin_panel(message)
        return
    
    # Базовая валидация
    if len(api_key) < 10 or len(api_key) > 100:
        await message.answer("❌ Неверный формат API ключа")
        return
    
    try:
        from direct_payment import set_usdt_api_key_to_db
        
        await set_usdt_api_key_to_db(api_key)
        
        # Скрываем часть ключа
        key_display = f"{api_key[:8]}...{api_key[-4:]}"
        
        await message.answer(f"""
✅ <b>TronGrid API ключ обновлен!</b>

<b>Ключ:</b> {key_display}

Теперь проверка транзакций будет быстрее и стабильнее.
""", parse_mode="HTML")
        
        await state.finish()
        await show_admin_panel(message)
        
    except Exception as e:
        logger.error(f"Error setting TronGrid API key: {e}")
        await message.answer("❌ Ошибка сохранения API ключа")
        await state.finish()


async def test_usdt_payment(callback: types.CallbackQuery):
    """Тестирует проверку USDT платежа"""
    try:
        from direct_payment import USDT_SETTINGS
        import aiohttp
        
        await callback.answer("🧪 Тестирую подключение...", show_alert=False)
        
        # Тестовый запрос к TronGrid API
        headers = {}
        if USDT_SETTINGS.get('api_key'):
            headers['TRONGRID-API-KEY'] = USDT_SETTINGS['api_key']
        
        wallet = USDT_SETTINGS['wallet_address']
        
        async with aiohttp.ClientSession() as session:
            url = f"https://apilist.tronscanapi.com/api/account?address={wallet}"
            
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    balance_trx = data.get('balance', 0) / 1_000_000
                    
                    text = f"""
✅ <b>ТЕСТ УСПЕШЕН!</b>

<b>Адрес:</b> <code>{wallet}</code>

<b>Статус:</b> Активен ✓
<b>Баланс TRX:</b> {balance_trx:.2f} TRX

<b>API:</b> {"Ключ установлен ✓" if USDT_SETTINGS.get('api_key') else "Без ключа"}

Система готова принимать платежи!
"""
                    await callback.message.edit_text(text, parse_mode="HTML")
                else:
                    raise Exception(f"API вернул статус {resp.status}")
                    
    except asyncio.TimeoutError:
        await callback.message.edit_text("""
⏰ <b>ТАЙМАУТ</b>

Не удалось подключиться к TronScan API.
Проверьте подключение к интернету.
""", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Test USDT payment error: {e}")
        await callback.message.edit_text(f"""
❌ <b>ОШИБКА ТЕСТА</b>

{str(e)}

Проверьте:
• Правильность адреса кошелька
• API ключ (если установлен)
• Подключение к интернету
""", parse_mode="HTML")
    
    finally:
        # Добавляем кнопку возврата
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("◀️ Назад", callback_data="edit_crypto_wallets"))
        try:
            await callback.message.edit_reply_markup(reply_markup=kb)
        except:
            pass

# ─── РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ──────────────────────────────────
def register_handlers(dp):
    """Регистрирует все обработчики админ-панели"""
    dp.register_message_handler(admin_command, commands=["admin"], state="*")
    dp.register_message_handler(process_admin_password, state=AdminAuth.waiting_for_password)

    dp.register_callback_query_handler(request_admin_panel, lambda c: c.data == "admin_panel", state="*")
    dp.register_callback_query_handler(exit_admin_panel, lambda c: c.data == "exit_admin", state="*")
    dp.register_callback_query_handler(cancel_action, lambda c: c.data == "cancel_action", state="*")

    # Categories
    dp.register_callback_query_handler(add_category_start, lambda c: c.data == "add_category", state="*")
    dp.register_message_handler(add_category_name, state=AddCategory.waiting_for_category_name)
    dp.register_callback_query_handler(delete_category_start, lambda c: c.data == "delete_category", state="*")
    dp.register_callback_query_handler(confirm_delete_category, lambda c: c.data.startswith("delcat_sel_"), state=DeleteCategory.waiting_for_category)
    dp.register_callback_query_handler(execute_delete_category, lambda c: c.data == "delcat_conf", state=DeleteCategory.waiting_for_confirmation)

    # Cities and districts
    dp.register_callback_query_handler(add_city_start, lambda c: c.data == "add_city", state="*")
    dp.register_message_handler(add_city_name, state=AddCity.waiting_for_city_name)
    dp.register_callback_query_handler(delete_city_start, lambda c: c.data == "delete_city", state="*")
    dp.register_callback_query_handler(confirm_delete_city, lambda c: c.data.startswith("delcity_sel_"), state=DeleteCity.waiting_for_city)
    dp.register_callback_query_handler(execute_delete_city, lambda c: c.data == "delcity_conf", state=DeleteCity.waiting_for_confirmation)

    dp.register_callback_query_handler(add_district_start, lambda c: c.data == "add_district", state="*")
    dp.register_callback_query_handler(select_city_for_district, lambda c: c.data.startswith("distcity_sel_"), state=AddDistrict.waiting_for_district_name)
    dp.register_message_handler(add_district_name, state=AddDistrict.waiting_for_district_name)

    dp.register_callback_query_handler(delete_district_start, lambda c: c.data == "delete_district", state="*")
    dp.register_callback_query_handler(select_city_for_district_deletion, lambda c: c.data.startswith("deldist_citysel_"), state=DeleteDistrict.waiting_for_city)
    dp.register_callback_query_handler(confirm_delete_district, lambda c: c.data.startswith("deldist_sel_"), state=DeleteDistrict.waiting_for_district)
    dp.register_callback_query_handler(execute_delete_district, lambda c: c.data.startswith("deldist_conf_"), state=DeleteDistrict.waiting_for_confirmation)

    # Products
    dp.register_callback_query_handler(add_product_start, lambda c: c.data == "add_product", state="*")
    dp.register_callback_query_handler(select_category_for_product, lambda c: c.data.startswith("prodcat_sel_"), state=AddProduct.waiting_for_category)
    dp.register_message_handler(add_product_name, state=AddProduct.waiting_for_name)
    dp.register_message_handler(add_product_price, state=AddProduct.waiting_for_price)
    dp.register_message_handler(add_product_description, state=AddProduct.waiting_for_description)
    dp.register_message_handler(add_product_media, content_types=types.ContentType.ANY, state=AddProduct.waiting_for_media)

    dp.register_callback_query_handler(delete_product_start, lambda c: c.data == "delete_product", state="*")
    dp.register_callback_query_handler(confirm_delete_product, lambda c: c.data.startswith("delprod_sel_"), state=DeleteProduct.waiting_for_product)
    dp.register_callback_query_handler(execute_delete_product, lambda c: c.data == "delprod_conf", state=DeleteProduct.waiting_for_confirmation)

    # Payments
    dp.register_callback_query_handler(edit_payments_start, lambda c: c.data == "edit_payments", state="*")
    dp.register_callback_query_handler(edit_usdt_start, lambda c: c.data == "edit_usdt", state="*")
    dp.register_callback_query_handler(edit_btc_start, lambda c: c.data == "edit_btc", state="*")
    dp.register_callback_query_handler(edit_card_start, lambda c: c.data == "edit_card", state="*")
    dp.register_message_handler(set_usdt, state=EditPayments.waiting_for_usdt)
    dp.register_message_handler(set_btc, state=EditPayments.waiting_for_btc)
    dp.register_message_handler(set_card, state=EditPayments.waiting_for_card)

    # Broadcast
    dp.register_callback_query_handler(broadcast_start, lambda c: c.data == "broadcast", state="*")
    dp.register_message_handler(broadcast_content, content_types=types.ContentType.ANY, state=Broadcast.waiting_for_content)
    dp.register_callback_query_handler(broadcast_confirm, lambda c: c.data == "broadcast_yes", state=Broadcast.waiting_for_confirm)

    # Users
    dp.register_callback_query_handler(ban_start, lambda c: c.data == "ban_user", state="*")
    dp.register_message_handler(ban_enter_id, state=BanUser.waiting_for_id)
    dp.register_callback_query_handler(unban_start, lambda c: c.data == "unban_user", state="*")
    dp.register_message_handler(unban_enter_id, state=UnbanUser.waiting_for_id)
    dp.register_callback_query_handler(ban_user_from_details, lambda c: c.data.startswith("ban_from_details_"), state="*")
    dp.register_callback_query_handler(unban_user_from_details, lambda c: c.data.startswith("unban_from_details_"), state="*")
    dp.register_callback_query_handler(view_user_details, lambda c: c.data.startswith("user_detail_"), state="*")
    dp.register_callback_query_handler(view_user_orders, lambda c: c.data.startswith("user_orders_"), state="*")

    # НОВЫЕ ОБРАБОТЧИКИ ТАБЛИЦЫ ПОЛЬЗОВАТЕЛЕЙ
    dp.register_callback_query_handler(show_users_table, lambda c: c.data == "view_users_table", state="*")
    dp.register_callback_query_handler(users_start_search, lambda c: c.data == "users_start_search", state="*")
    dp.register_message_handler(process_users_search, state=ViewUsersTable.waiting_for_query)
    dp.register_callback_query_handler(users_clear_search, lambda c: c.data == "users_clear_search", state="*")
    dp.register_callback_query_handler(users_change_sort, lambda c: c.data.startswith("users_sort_"), state="*")
    dp.register_callback_query_handler(users_change_page, lambda c: c.data.startswith("users_page_"), state="*")
    dp.register_callback_query_handler(users_show_stats, lambda c: c.data == "users_stats", state="*")
    dp.register_callback_query_handler(view_users_table_back, lambda c: c.data == "view_users_table_back", state="*")

    # Orders
    dp.register_callback_query_handler(view_orders_start, lambda c: c.data == "view_orders", state="*")
    dp.register_callback_query_handler(view_order_details, lambda c: c.data.startswith("order_detail_"), state="*")
    dp.register_callback_query_handler(change_order_status, lambda c: c.data.startswith(("complete_order_", "reject_order_", "pending_order_")), state="*")

    # Stock
    dp.register_callback_query_handler(edit_stock_start, lambda c: c.data == "edit_stock", state="*")
    dp.register_callback_query_handler(select_product_for_stock, lambda c: c.data.startswith("stock_sel_"), state=EditStock.waiting_for_product)
    dp.register_message_handler(set_product_stock, state=EditStock.waiting_for_stock)

    # Promos
    dp.register_callback_query_handler(manage_promos_start, lambda c: c.data == "manage_promos", state="*")
    dp.register_callback_query_handler(add_promo_start, lambda c: c.data == "add_promo", state="*")
    dp.register_message_handler(add_promo_code, state=AddPromoCode.waiting_for_code)
    dp.register_message_handler(add_promo_discount, state=AddPromoCode.waiting_for_discount)
    dp.register_message_handler(add_promo_limit, state=AddPromoCode.waiting_for_limit)
    dp.register_message_handler(add_promo_expiry, state=AddPromoCode.waiting_for_expiry)
    dp.register_callback_query_handler(delete_promo_start, lambda c: c.data == "delete_promo", state="*")
    dp.register_callback_query_handler(confirm_delete_promo, lambda c: c.data.startswith("delpromo_sel_"), state=DeletePromoCode.waiting_for_promo)
    dp.register_callback_query_handler(execute_delete_promo, lambda c: c.data == "delpromo_conf", state=DeletePromoCode.waiting_for_confirmation)
    dp.register_callback_query_handler(list_promos, lambda c: c.data == "list_promos", state="*")

    # Auto-delivery: main panel, add, list, detail, search, delete
    dp.register_callback_query_handler(show_auto_delivery_panel, lambda c: c.data == "auto_delivery_panel", state="*")
    dp.register_callback_query_handler(add_auto_point_start, lambda c: c.data == "add_auto_point", state="*")
    dp.register_callback_query_handler(select_product_for_auto, lambda c: c.data.startswith("autoprod_sel_"), state=AutoDelivery.waiting_for_product)
    dp.register_callback_query_handler(select_city_for_auto, lambda c: c.data.startswith("autocity_sel_"), state=AutoDelivery.waiting_for_city)
    dp.register_callback_query_handler(select_district_for_auto, lambda c: c.data.startswith("autodist_sel_"), state=AutoDelivery.waiting_for_district)
    dp.register_callback_query_handler(skip_auto_photo_handler, lambda c: c.data == "skip_auto_photo", state=AutoDelivery.waiting_for_photo)
    dp.register_message_handler(add_auto_photo, content_types=types.ContentType.PHOTO, state=AutoDelivery.waiting_for_photo)
    dp.register_message_handler(add_auto_description, state=AutoDelivery.waiting_for_description)
    dp.register_callback_query_handler(select_unit_for_auto, lambda c: c.data.startswith("unit_"), state="*")
    dp.register_message_handler(add_auto_quantity, state=AutoDelivery.waiting_for_quantity)
    dp.register_message_handler(add_auto_price, state=AutoDelivery.waiting_for_price)
    dp.register_callback_query_handler(confirm_auto_point, lambda c: c.data == "confirm_auto_point", state="*")

    # List, pagination, detail, search
    dp.register_callback_query_handler(list_auto_points, lambda c: c.data == "list_auto_points" or "auto_page_" in (c.data or ""), state="*")
    dp.register_callback_query_handler(view_autopoint_detail, lambda c: c.data.startswith("view_autopoint_"), state="*")
    dp.register_callback_query_handler(start_auto_search, lambda c: c.data == "start_auto_search", state="*")
    dp.register_message_handler(process_search_query, state=SearchAutoPoints.waiting_for_query)
    dp.register_callback_query_handler(reset_auto_search, lambda c: c.data == "reset_auto_search", state="*")

    # Delete auto points
    dp.register_callback_query_handler(delete_auto_point_start, lambda c: c.data == "delete_auto_point", state="*")
    dp.register_callback_query_handler(confirm_delete_auto_point, lambda c: c.data.startswith("delauto_sel_"), state="*")
    dp.register_callback_query_handler(execute_delete_auto_point, lambda c: c.data.startswith("delauto_conf_"), state="*")

    # Hidden products & restore
    dp.register_callback_query_handler(manage_hidden_products, lambda c: c.data == "view_hidden_products", state="*")
    dp.register_callback_query_handler(restore_hidden_product_start, lambda c: c.data == "restore_hidden_product", state="*")
    dp.register_callback_query_handler(execute_restore_product, lambda c: c.data.startswith("restore_prod_"), state="*")
    dp.register_callback_query_handler(restore_product_handler, lambda c: c.data.startswith("restore_product_"), state="*")
    dp.register_callback_query_handler(check_delivery_availability, lambda c: c.data == "check_delivery_availability", state="*")
    dp.register_callback_query_handler(show_hidden_products, lambda c: c.data == "show_hidden_products", state="*")
    dp.register_callback_query_handler(toggle_product_visibility, lambda c: c.data.startswith("toggle_product_"), state="*")

    # Stats
    dp.register_callback_query_handler(show_stats, lambda c: c.data.startswith("stats_"), state="*")

    # Utilities
    dp.register_message_handler(fix_product_media, commands=['fixmedia'], state="*")