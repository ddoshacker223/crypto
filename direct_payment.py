"""
Модуль прямой оплаты через USDT TRC20
Проверка платежей через TronGrid API с уникальными суммами (хвостиками)
"""

import os
import aiosqlite
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import aiohttp
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from logs import logger

# ══════════════════════════════════════════════════════════════
# УТИЛИТА ДЛЯ РАБОТЫ С ЯЗЫКОМ
# ══════════════════════════════════════════════════════════════

async def get_user_lang(user_id: int) -> str:
    """Получает язык пользователя из БД"""
    try:
        async with aiosqlite.connect('shop.db') as db:
            cursor = await db.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return row[0] if row and row[0] else 'ru'
    except:
        return 'ru'

# ══════════════════════════════════════════════════════════════
# НАСТРОЙКИ ПРЯМОЙ КРИПТО-ОПЛАТЫ
# ══════════════════════════════════════════════════════════════

CRYPTO_SETTINGS = {
    'usdt': {
        'enabled': True,
        'name': '💰 USDT',
        'wallet_address': 'TBG9U4C2kDRKjyyGBSBPfQmYt2NBK8Z1ip',
        'network': 'TRC20',
        'contract': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
        'required_confirmations': 19,
        'payment_timeout_minutes': 30,
        'api_key': os.getenv('TRONGRID_API_KEY', ''),
        'decimals': 6,
    },
    'btc': {
        'enabled': False,  # Отключено: настройте адрес через админ-панель
        'name': '₿ BTC',
        'wallet_address': '',  # Установите через админ-панель
        'network': 'Bitcoin',
        'required_confirmations': 3,
        'payment_timeout_minutes': 30,
        'api_key': '',
        'decimals': 8,
    },
    'eth': {
        'enabled': False,  # Отключено: настройте адрес через админ-панель
        'name': '≡ ETH',
        'wallet_address': '',  # Установите через админ-панель
        'network': 'Ethereum',
        'required_confirmations': 12,
        'payment_timeout_minutes': 20,
        'api_key': os.getenv('ETHERSCAN_API_KEY', ''),
        'decimals': 18,
    },
    'ton': {
        'enabled': False,  # Отключено: настройте адрес через админ-панель
        'name': '💎 TON',
        'wallet_address': '',  # Установите через админ-панель
        'network': 'TON',
        'required_confirmations': 1,
        'payment_timeout_minutes': 10,
        'api_key': os.getenv('TON_API_KEY', ''),
        'decimals': 9,
    },
    'sol': {
        'enabled': False,  # Отключено: настройте адрес через админ-панель
        'name': '☀️ SOL',
        'wallet_address': '',  # Установите через админ-панель
        'network': 'Solana',
        'required_confirmations': 32,
        'payment_timeout_minutes': 30,
        'api_key': os.getenv('SOLANA_API_KEY', ''),
        'decimals': 9,
    },
    'trx': {
        'enabled': True,
        'name': '💠 TRX',
        'wallet_address': 'TBG9U4C2kDRKjyyGBSBPfQmYt2NBK8Z1ip',
        'network': 'TRON',
        'required_confirmations': 19,
        'payment_timeout_minutes': 30,
        'api_key': os.getenv('TRONGRID_API_KEY', ''),
        'decimals': 6,
    },
    'ltc': {
        'enabled': False,  # Отключено: настройте адрес через админ-панель
        'name': '🔷 LTC',
        'wallet_address': '',  # Установите через админ-панель
        'network': 'Litecoin',
        'required_confirmations': 6,
        'payment_timeout_minutes': 30,
        'api_key': '',  # SoChain API не требует ключа
        'decimals': 8,
    },
    'usdc_bep20': {
        'enabled': False,  # Отключено: настройте адрес через админ-панель
        'name': '💵 USDC',
        'wallet_address': '',  # Установите через админ-панель
        'network': 'BEP-20',
        'contract': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d',  # USDC контракт на BSC
        'required_confirmations': 15,
        'payment_timeout_minutes': 30,
        'api_key': os.getenv('ETHERSCAN_API_KEY', ''),  # Используем Etherscan API V2
        'decimals': 18,
    },
    'bnb': {
        'enabled': False,  # Отключено: настройте адрес через админ-панель
        'name': '💛 BNB',
        'wallet_address': '',  # Установите через админ-панель
        'network': 'BEP-20',
        'required_confirmations': 15,
        'payment_timeout_minutes': 30,
        'api_key': os.getenv('ETHERSCAN_API_KEY', ''),  # Используем Etherscan API V2
        'decimals': 18,
    }
}

# Для обратной совместимости
USDT_SETTINGS = CRYPTO_SETTINGS['usdt']

# API endpoints
TRONGRID_API = 'https://api.trongrid.io'
TRONSCAN_API = 'https://apilist.tronscanapi.com/api'
ETHERSCAN_API = 'https://api.etherscan.io/api'
BSCSCAN_API = 'https://api.bscscan.com/api'
TONAPI = 'https://tonapi.io/v2'
SOLSCAN_API = 'https://api.solscan.io'
BLOCKCHAIN_INFO_API = 'https://blockchain.info'
SOCHAIN_API = 'https://sochain.com/api/v2'

# ══════════════════════════════════════════════════════════════
# FSM СОСТОЯНИЯ
# ══════════════════════════════════════════════════════════════

class DirectPayment(StatesGroup):
    waiting_for_payment = State()
    waiting_for_tx_id = State()
    checking_payment = State()


# ══════════════════════════════════════════════════════════════
# УТИЛИТЫ ДЛЯ РАБОТЫ С "ХВОСТИКАМИ"
# ══════════════════════════════════════════════════════════════

def generate_unique_amount(base_amount: float) -> tuple[float, str]:
    """
    Генерирует уникальную сумму с 'хвостиком' для отслеживания платежа
    
    Args:
        base_amount: Базовая сумма (например, 10.00)
        
    Returns:
        (unique_amount, tail): Уникальная сумма и хвостик
        
    Пример: 10.00 -> (10.0234, "0234")
    """
    # Генерируем 4-значный хвостик
    tail = str(random.randint(1000, 9999))
    
    # Добавляем хвостик к сумме
    unique_amount = float(f"{base_amount:.2f}") + float(f"0.{tail}")
    
    return round(unique_amount, 4), tail


async def save_payment_tail(order_id: int, tail: str, unique_amount: float):
    """Сохраняет хвостик платежа в БД"""
    async with aiosqlite.connect('shop.db') as db:
        await db.execute('''
            UPDATE orders 
            SET payment_tail = ?, 
                payment_unique_amount = ?,
                payment_expires_at = ?
            WHERE id = ?
        ''', (
            tail, 
            unique_amount, 
            datetime.now() + timedelta(minutes=USDT_SETTINGS['payment_timeout_minutes']),
            order_id
        ))
        await db.commit()


async def get_payment_info(order_id: int) -> Optional[Dict[str, Any]]:
    """Получает информацию о платеже из БД"""
    async with aiosqlite.connect('shop.db') as db:
        cursor = await db.execute('''
            SELECT payment_tail, payment_unique_amount, payment_expires_at, 
                   final_price, tx_hash, payment_status
            FROM orders WHERE id = ?
        ''', (order_id,))
        row = await cursor.fetchone()
        
        if row:
            return {
                'tail': row[0],
                'unique_amount': row[1],
                'expires_at': row[2],
                'base_amount': row[3],
                'tx_hash': row[4],
                'status': row[5]
            }
        return None


async def update_order_payment_status(order_id: int, status: str, tx_hash: str = None):
    """Обновляет статус платежа в заказе"""
    async with aiosqlite.connect('shop.db') as db:
        if tx_hash:
            await db.execute('''
                UPDATE orders 
                SET payment_status = ?, tx_hash = ?
                WHERE id = ?
            ''', (status, tx_hash, order_id))
        else:
            await db.execute('''
                UPDATE orders 
                SET payment_status = ?
                WHERE id = ?
            ''', (status, order_id))
        await db.commit()


# ══════════════════════════════════════════════════════════════
# ПРОВЕРКА ПЛАТЕЖЕЙ ЧЕРЕЗ TRONGRID API
# ══════════════════════════════════════════════════════════════

async def check_usdt_transaction(tx_hash: str, expected_amount: float, wallet_address: str) -> Dict[str, Any]:
    """
    Проверяет USDT TRC20 транзакцию через TronGrid API
    
    Args:
        tx_hash: Хеш транзакции
        expected_amount: Ожидаемая сумма (с хвостиком)
        wallet_address: Адрес получателя
        
    Returns:
        dict: {
            'valid': bool,
            'amount': float,
            'confirmations': int,
            'status': str,
            'error': str (если есть)
        }
    """
    try:
        logger.info(f"Checking USDT transaction: {tx_hash}, expected: {expected_amount}, wallet: {wallet_address}")
        
        headers = {}
        if USDT_SETTINGS.get('api_key'):
            headers['TRON-PRO-API-KEY'] = USDT_SETTINGS['api_key']
            logger.info("Using TronGrid API key")
        else:
            logger.warning("No TronGrid API key configured")
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Получаем информацию о транзакции
            url = f"{TRONGRID_API}/wallet/gettransactionbyid"
            
            async with session.post(url, json={'value': tx_hash}, headers=headers) as resp:
                if resp.status != 200:
                    return {'valid': False, 'error': 'Transaction not found' if USDT_SETTINGS.get('api_key') else 'Транзакция не найдена'}
                
                tx_data = await resp.json()
                
                # Проверяем, что это TRC20 транзакция
                if not tx_data.get('raw_data'):
                    return {'valid': False, 'error': 'Invalid transaction' if USDT_SETTINGS.get('api_key') else 'Некорректная транзакция'}
                
                # Получаем информацию о транзакции через TronScan для деталей
                tronscan_url = f"{TRONSCAN_API}/transaction-info?hash={tx_hash}"
                async with session.get(tronscan_url) as tronscan_resp:
                    if tronscan_resp.status == 200:
                        tronscan_data = await tronscan_resp.json()
                        
                        # Проверяем TRC20 токен трансфер
                        if 'trc20TransferInfo' in tronscan_data:
                            transfer_info = tronscan_data['trc20TransferInfo']
                            
                            # Проверяем адрес получателя
                            to_address = transfer_info[0].get('to_address', '')
                            if to_address.lower() != wallet_address.lower():
                                return {'valid': False, 'error': 'Wrong recipient address' if USDT_SETTINGS.get('api_key') else 'Неверный адрес получателя'}
                            
                            # Получаем сумму (USDT имеет 6 decimals)
                            amount_raw = int(transfer_info[0].get('amount_str', '0'))
                            amount = amount_raw / 1_000_000  # Конвертируем из SUN в USDT
                            
                            # Проверяем сумму (допускаем погрешность 0.0001)
                            if abs(amount - expected_amount) > 0.0001:
                                error_msg = f'Wrong amount. Expected: {expected_amount} USDT, received: {amount} USDT' if USDT_SETTINGS.get('api_key') else f'Неверная сумма. Ожидалось: {expected_amount} USDT, получено: {amount} USDT'
                                return {'valid': False, 'error': error_msg}
                            
                            # Получаем количество подтверждений
                            confirmations = tronscan_data.get('confirmations', 0)
                            confirmed = tronscan_data.get('confirmed', False)
                            
                            return {
                                'valid': True,
                                'amount': amount,
                                'confirmations': confirmations,
                                'confirmed': confirmed,
                                'status': 'confirmed' if confirmed else 'pending',
                                'error': None
                            }
                
                return {'valid': False, 'error': 'Failed to get transaction details' if USDT_SETTINGS.get('api_key') else 'Не удалось получить детали транзакции'}
                
    except Exception as e:
        logger.error(f"Ошибка проверки USDT транзакции: {e}")
        return {'valid': False, 'error': f'API error: {str(e)}' if USDT_SETTINGS.get('api_key') else f'Ошибка API: {str(e)}'}


async def verify_payment_by_amount(wallet_address: str, expected_amount: float, time_from: datetime) -> Optional[str]:
    """
    Ищет входящую транзакцию по точной сумме
    
    Args:
        wallet_address: Адрес кошелька
        expected_amount: Ожидаемая сумма с хвостиком
        time_from: Время создания заказа
        
    Returns:
        str: Хеш транзакции если найдена, иначе None
    """
    try:
        # Конвертируем timestamp в миллисекунды
        min_timestamp = int(time_from.timestamp() * 1000)
        
        timeout = aiohttp.ClientTimeout(total=60)  # Увеличен timeout до 60 секунд
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Используем TronGrid API для получения TRC20 транзакций
            # Фильтруем сразу по контракту USDT
            url = f"{TRONGRID_API}/v1/accounts/{wallet_address}/transactions/trc20"
            
            headers = {}
            if USDT_SETTINGS.get('api_key'):
                headers['TRON-PRO-API-KEY'] = USDT_SETTINGS['api_key']
            
            params = {
                'limit': 50,
                'contract_address': USDT_SETTINGS['contract'],  # Фильтр по контракту USDT
                'only_to': 'true'  # Только входящие
            }
            
            logger.info(f"Searching for USDT transaction: amount={expected_amount}, min_timestamp={min_timestamp}")
            logger.info(f"Request URL: {url}, contract: {USDT_SETTINGS['contract']}")
            
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"TronGrid API error: {resp.status}")
                    # Fallback на TronScan API
                    return await _verify_payment_tronscan(wallet_address, expected_amount, min_timestamp, session)
                
                data = await resp.json()
                transactions = data.get('data', [])
                logger.info(f"Found {len(transactions)} USDT transactions")
                
                # Ищем транзакцию с нужной суммой
                for tx in transactions:
                    # Проверяем timestamp
                    tx_timestamp = tx.get('block_timestamp', 0)
                    if tx_timestamp < min_timestamp:
                        continue
                    
                    # Получаем сумму
                    amount_raw = int(tx.get('value', '0'))
                    amount = amount_raw / 1_000_000  # USDT имеет 6 decimals
                    
                    # Проверяем адрес получателя
                    to_address = tx.get('to', '')
                    if to_address.lower() != wallet_address.lower():
                        continue
                    
                    tx_hash = tx.get('transaction_id')
                    logger.info(f"Checking USDT TX: {tx_hash}, amount={amount}, to={to_address}")
                    
                    # Проверяем сумму с погрешностью
                    if abs(amount - expected_amount) < 0.0001:
                        logger.info(f"✅ Found matching USDT transaction: {tx_hash}, amount={amount}")
                        return tx_hash
                
                logger.warning(f"No matching USDT transaction found for amount {expected_amount}")
                return None
                
    except Exception as e:
        logger.error(f"Ошибка поиска транзакции: {e}", exc_info=True)
        return None


async def _verify_payment_tronscan(wallet_address: str, expected_amount: float, min_timestamp: int, session) -> Optional[str]:
    """Fallback метод поиска через TronScan API"""
    try:
        url = f"{TRONSCAN_API}/contract/events"
        params = {
            'address': wallet_address,
            'start': 0,
            'limit': 50,
            'min_timestamp': min_timestamp
        }
        
        logger.info(f"Using TronScan API fallback")
        
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                logger.error(f"TronScan API error: {resp.status}")
                return None
            
            data = await resp.json()
            events = data.get('data', [])
            logger.info(f"TronScan: Found {len(events)} events")
            
            # Ищем транзакцию с нужной суммой
            for event in events:
                # Проверяем, что это USDT транзакция по контракту
                token_info = event.get('tokenInfo', {})
                contract_address = token_info.get('tokenId', '')
                
                # Проверяем контракт USDT
                if contract_address.lower() != USDT_SETTINGS['contract'].lower():
                    continue
                
                if token_info.get('tokenAbbr') == 'USDT':
                    amount_raw = int(event.get('value', '0'))
                    amount = amount_raw / 1_000_000
                    
                    tx_hash = event.get('transactionId')
                    logger.info(f"TronScan: Checking USDT TX: {tx_hash}, amount={amount}")
                    
                    # Проверяем сумму с погрешностью
                    if abs(amount - expected_amount) < 0.0001:
                        logger.info(f"✅ TronScan: Found matching transaction: {tx_hash}")
                        return tx_hash
            
            logger.warning(f"TronScan: No matching transaction found")
            return None
            
    except Exception as e:
        logger.error(f"TronScan fallback error: {e}")
        return None


# ══════════════════════════════════════════════════════════════
# ОБРАБОТЧИКИ ПРЯМОЙ ОПЛАТЫ
# ══════════════════════════════════════════════════════════════

async def show_crypto_selection(callback: types.CallbackQuery, state: FSMContext, order_id: int,
                                user_id: int, final_price: float, product_name: str,
                                quantity: int, city_name: str, district_name: str):
    """Показывает меню выбора криптовалюты"""
    
    # Получаем язык пользователя из БД
    lang = await get_user_lang(callback.from_user.id)
    
    # Формируем текст в зависимости от языка
    if lang == 'en':
        text = f"""
<b>💳 DIRECT CRYPTO PAYMENT</b>

📦 Product: {product_name}
⚖️ Weight: {quantity}g
🏙️ City: {city_name}
🏘️ District: {district_name}

💰 Total amount: {final_price:.2f} €

<b>Select cryptocurrency:</b>
"""
        btn_back = "◀️ Back"
    else:
        text = f"""
<b>💳 ПРЯМАЯ КРИПТО-ОПЛАТА</b>

📦 Товар: {product_name}
⚖️ Вес: {quantity}г
🏙️ Город: {city_name}
🏘️ Район: {district_name}

💰 Общая сумма: {final_price:.2f} €

<b>Выберите криптовалюту:</b>
"""
        btn_back = "◀️ Назад"
    
    kb = InlineKeyboardMarkup(row_width=2)
    
    # Добавляем доступные криптовалюты
    crypto_buttons = []
    for crypto_id, settings in CRYPTO_SETTINGS.items():
        if settings['enabled'] and settings.get('wallet_address'):
            crypto_buttons.append(
                InlineKeyboardButton(
                    settings['name'],
                    callback_data=f"crypto_{crypto_id}_{order_id}"
                )
            )
    
    # Размещаем кнопки по 2 в ряд
    for i in range(0, len(crypto_buttons), 2):
        if i + 1 < len(crypto_buttons):
            kb.row(crypto_buttons[i], crypto_buttons[i + 1])
        else:
            kb.row(crypto_buttons[i])
    
    kb.row(InlineKeyboardButton(btn_back, callback_data="back_from_crypto_selection"))
    
    # Сохраняем данные заказа в state
    await state.update_data(
        order_id=order_id,
        user_id=user_id,
        final_price=final_price,
        product_name=product_name,
        quantity=quantity,
        city_name=city_name,
        district_name=district_name
    )
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


async def process_direct_crypto_payment(callback: types.CallbackQuery, state: FSMContext, crypto: str):
    """Обработка прямой крипто-оплаты для выбранной валюты"""
    
    # Получаем язык пользователя из БД
    lang = await get_user_lang(callback.from_user.id)
    
    # Получаем данные заказа из state
    data = await state.get_data()
    order_id = data['order_id']
    order_display_id = data.get('order_display_id', str(order_id))
    user_id = data['user_id']
    final_price = data['final_price']
    product_name = data['product_name']
    quantity = data['quantity']
    city_name = data['city_name']
    district_name = data['district_name']
    
    settings = CRYPTO_SETTINGS[crypto]
    
    # Генерируем уникальную сумму с хвостиком
    unique_amount, tail = generate_unique_amount(final_price)
    
    # Сохраняем хвостик в БД
    await save_payment_tail(order_id, tail, unique_amount)
    
    # Время истечения
    expires_at = datetime.now() + timedelta(minutes=settings['payment_timeout_minutes'])
    
    # Подготовка переменных для форматирования
    expires_time_str = expires_at.strftime('%d/%m %H:%M')
    timeout_min = settings['payment_timeout_minutes']
    network = settings['network']
    wallet = settings['wallet_address']
    
    # Формируем сообщение в зависимости от языка
    if lang == 'en':
        payment_text = f"""
💳 <b>PAYMENT • {crypto.upper()} ({network})</b>

📦 {product_name} • {quantity}g
📍 {city_name}, {district_name}
⏰ Until: {expires_time_str} ({timeout_min} min)

💰 <b>Amount:</b> <code>{unique_amount:.4f}</code> {crypto.upper()}
📱 <b>Address:</b>
<code>{wallet}</code>

⚠️ <b>IMPORTANT:</b>
• Send <b>EXACT amount</b> {unique_amount:.4f} {crypto.upper()}
• Use only <b>{network}</b> network
• Click "I paid" after sending

🔢 Order ID: #{order_display_id}
"""
        btn_paid = "✅ I paid"
        btn_check = "🔍 Check payment"
        btn_cancel = "❌ Cancel order"
    else:
        payment_text = f"""
💳 <b>ОПЛАТА • {crypto.upper()} ({network})</b>

📦 {product_name} • {quantity}г
📍 {city_name}, {district_name}
⏰ До: {expires_time_str} ({timeout_min} мин)

💰 <b>Сумма:</b> <code>{unique_amount:.4f}</code> {crypto.upper()}
📱 <b>Адрес:</b>
<code>{wallet}</code>

⚠️ <b>ВАЖНО:</b>
• Переведите <b>ТОЧНУЮ сумму</b> {unique_amount:.4f} {crypto.upper()}
• Используйте только сеть <b>{network}</b>
• После отправки нажмите "Я оплатил"

🔢 ID заказа: #{order_display_id}
"""
        btn_paid = "✅ Я оплатил"
        btn_check = "🔍 Проверить"
        btn_cancel = "❌ Отмена"
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(btn_paid, callback_data=f"paid_{crypto}_{order_id}"),
        InlineKeyboardButton(btn_check, callback_data=f"check_{crypto}_{order_id}"),
        InlineKeyboardButton(btn_cancel, callback_data="cancel_order")
    )
    
    try:
        await callback.message.edit_text(payment_text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.answer(payment_text, reply_markup=kb, parse_mode="HTML")
    
    # Логируем создание заказа в админ-чат
    from main import bot, LOG_CHAT_ID
    try:
        created_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        log_msg = f"""
🆕 <b>НОВЫЙ ЗАКАЗ #{order_display_id}</b>

👤 <b>Пользователь:</b> {callback.from_user.username or callback.from_user.first_name} (ID: {user_id})
📦 <b>Товар:</b> {product_name}
⚖️ <b>Количество:</b> {quantity}г
💰 <b>Сумма:</b> {final_price} €
🪙 <b>К оплате:</b> {unique_amount:.4f} {crypto.upper()}
🏙️ <b>Город:</b> {city_name}
🏘️ <b>Район:</b> {district_name}
💳 <b>Метод:</b> Прямая оплата {settings['name']}
⏱️ <b>Статус:</b> ⏳ Ожидание оплаты
⏰ <b>Создан:</b> {created_time}
"""
        await bot.send_message(LOG_CHAT_ID, log_msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send order creation log to admin chat: {e}")
    
    await DirectPayment.waiting_for_payment.set()
    await state.update_data(
        order_id=order_id,
        unique_amount=unique_amount,
        crypto=crypto
    )
    
    # Обновляем статус заказа
    async with aiosqlite.connect('shop.db') as db:
        await db.execute('''
            UPDATE orders 
            SET payment_method = ?,
                payment_status = 'awaiting',
                payment_expires_at = ?
            WHERE id = ?
        ''', (f'direct_{crypto}', expires_at, order_id))
        await db.commit()


async def show_payment_details(callback: types.CallbackQuery, order_id: int, crypto: str, user_lang: str):
    """Показывает детали платежа (для возврата из подтверждения отмены)"""
    
    # Получаем данные заказа из БД
    async with aiosqlite.connect('shop.db') as db:
        order_data = await (await db.execute("""
            SELECT o.product_name, o.quantity, c.name as city_name, d.name as district_name, 
                   o.final_price, o.payment_unique_amount, o.payment_expires_at, o.created_at,
                   o.order_display_id
            FROM orders o
            LEFT JOIN cities c ON o.city_id = c.id
            LEFT JOIN districts d ON o.district_id = d.id
            WHERE o.id = ?
        """, (order_id,))).fetchone()
    
    if not order_data:
        if user_lang == 'ru':
            await callback.answer("❌ Заказ не найден", show_alert=True)
        else:
            await callback.answer("❌ Order not found", show_alert=True)
        return
    
    product_name, quantity, city_name, district_name, final_price, unique_amount, expires_at_str, created_at_str, order_display_id = order_data
    
    # Если order_display_id пустой, используем order_id
    if not order_display_id:
        order_display_id = str(order_id)
    
    settings = CRYPTO_SETTINGS[crypto]
    expires_at = datetime.fromisoformat(expires_at_str)
    
    # Подготовка переменных для форматирования
    expires_time_str = expires_at.strftime('%d/%m %H:%M')
    timeout_min = settings['payment_timeout_minutes']
    network = settings['network']
    wallet = settings['wallet_address']
    
    # Формируем сообщение в зависимости от языка
    if user_lang == 'ru':
        payment_text = f"""
💳 <b>ОПЛАТА • {crypto.upper()} ({network})</b>

📦 {product_name} • {quantity}г
📍 {city_name}, {district_name}
⏰ До: {expires_time_str} ({timeout_min} мин)

💰 <b>Сумма:</b> <code>{unique_amount:.4f}</code> {crypto.upper()}
📱 <b>Адрес:</b>
<code>{wallet}</code>

⚠️ <b>ВАЖНО:</b>
• Переведите <b>ТОЧНУЮ сумму</b> {unique_amount:.4f} {crypto.upper()}
• Используйте только сеть <b>{network}</b>
• После отправки нажмите "Я оплатил"

🔢 ID заказа: #{order_display_id}
"""
        btn_paid = "✅ Я оплатил"
        btn_check = "🔍 Проверить платеж"
        btn_cancel = "❌ Отменить заказ"
    else:
        payment_text = f"""
💳 <b>PAYMENT • {crypto.upper()} ({network})</b>

📦 {product_name} • {quantity}g
📍 {city_name}, {district_name}
⏰ Until: {expires_time_str} ({timeout_min} min)

💰 <b>Amount:</b> <code>{unique_amount:.4f}</code> {crypto.upper()}
📱 <b>Address:</b>
<code>{wallet}</code>

⚠️ <b>IMPORTANT:</b>
• Send <b>EXACT amount</b> {unique_amount:.4f} {crypto.upper()}
• Use only <b>{network}</b> network
• Click "I paid" after sending

🔢 Order ID: #{order_display_id}
"""
        btn_paid = "✅ I paid"
        btn_check = "🔍 Check payment"
        btn_cancel = "❌ Cancel order"
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(btn_paid, callback_data=f"paid_{crypto}_{order_id}"),
        InlineKeyboardButton(btn_check, callback_data=f"check_{crypto}_{order_id}"),
        InlineKeyboardButton(btn_cancel, callback_data="cancel_order")
    )
    
    await callback.message.edit_text(payment_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


async def process_direct_usdt_payment(callback: types.CallbackQuery, state: FSMContext, order_id: int, 
                                     user_id: int, final_price: float, product_name: str, 
                                     quantity: int, city_name: str, district_name: str):
    """Обработка прямой USDT оплаты (для обратной совместимости)"""
    await show_crypto_selection(callback, state, order_id, user_id, final_price,
                                product_name, quantity, city_name, district_name)


async def handle_paid_button(callback: types.CallbackQuery, state: FSMContext):
    """Обработка нажатия 'Я оплатил' - автоматическая проверка по сумме"""
    # Формат: paid_{crypto}_{order_id}
    parts = callback.data.split("_")
    crypto = parts[1]
    order_id = int(parts[2])
    
    # Получаем язык пользователя из БД
    lang = await get_user_lang(callback.from_user.id)
    
    # Получаем настройки для выбранной криптовалюты
    settings = CRYPTO_SETTINGS.get(crypto)
    if not settings:
        if lang == 'en':
            await callback.answer("❌ Cryptocurrency not supported", show_alert=True)
        else:
            await callback.answer("❌ Криптовалюта не поддерживается", show_alert=True)
        return
    
    payment_info = await get_payment_info(order_id)
    
    if not payment_info:
        if lang == 'en':
            await callback.answer("❌ Order not found", show_alert=True)
        else:
            await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Проверяем, не истекло ли время
    expires_at = datetime.fromisoformat(payment_info['expires_at'])
    if datetime.now() > expires_at:
        if lang == 'en':
            await callback.answer("⏰ Payment time expired. Order cancelled.", show_alert=True)
        else:
            await callback.answer("⏰ Время оплаты истекло. Заказ отменен.", show_alert=True)
        await state.finish()
        return
    
    # Отправляем сообщение о проверке
    if lang == 'en':
        await callback.answer("🔄 Checking payment...", show_alert=False)
        checking_msg = await callback.message.edit_text(
            f"🔄 <b>Searching for transaction...</b>\n\n"
            f"💰 Expected amount: <code>{payment_info['unique_amount']:.4f}</code> {crypto.upper()}\n"
            f"📬 To address: <code>{settings['wallet_address']}</code>\n\n"
            f"⏳ This may take a few seconds...",
            parse_mode="HTML"
        )
    else:
        await callback.answer("🔄 Проверяю платеж...", show_alert=False)
        checking_msg = await callback.message.edit_text(
            f"🔄 <b>Ищу транзакцию...</b>\n\n"
            f"💰 Ожидаемая сумма: <code>{payment_info['unique_amount']:.4f}</code> {crypto.upper()}\n"
            f"📬 На адрес: <code>{settings['wallet_address']}</code>\n\n"
            f"⏳ Это может занять несколько секунд...",
            parse_mode="HTML"
        )
    
    # Время создания заказа - ищем транзакции после этого времени
    # Вычитаем 30 минут чтобы охватить период оплаты
    time_from = datetime.now() - timedelta(minutes=30)
    
    # Ищем транзакцию по сумме
    tx_hash = await verify_payment_by_amount(
        settings['wallet_address'],
        payment_info['unique_amount'],
        time_from
    )
    
    if not tx_hash:
        # Транзакция не найдена
        if lang == 'en':
            text = f"""
❌ <b>TRANSACTION NOT FOUND</b>

Could not find transaction with exact amount <code>{payment_info['unique_amount']:.4f}</code> {crypto.upper()}.

<b>Possible reasons:</b>
• Transaction not yet in blockchain (wait 1-2 minutes)
• Wrong amount sent (must be EXACTLY {payment_info['unique_amount']:.4f})
• Sent to wrong address

<b>💡 What to do:</b>
1. Check that you sent EXACT amount: <code>{payment_info['unique_amount']:.4f}</code>
2. Check address: <code>{settings['wallet_address']}</code>
3. Wait 1-2 minutes and click "🔍 Check payment" again
4. Or enter transaction hash manually
"""
            btn_check_again = "🔄 Check again"
            btn_enter_hash = "✍️ Enter hash manually"
            btn_cancel = "❌ Cancel"
        else:
            text = f"""
❌ <b>ТРАНЗАКЦИЯ НЕ НАЙДЕНА</b>

Не удалось найти транзакцию с точной суммой <code>{payment_info['unique_amount']:.4f}</code> {crypto.upper()}.

<b>Возможные причины:</b>
• Транзакция еще не попала в блокчейн (подождите 1-2 минуты)
• Отправлена неверная сумма (должна быть ТОЧНО {payment_info['unique_amount']:.4f})
• Отправлена на неверный адрес

<b>💡 Что делать:</b>
1. Проверьте, что отправили ТОЧНУЮ сумму: <code>{payment_info['unique_amount']:.4f}</code>
2. Проверьте адрес: <code>{settings['wallet_address']}</code>
3. Подождите 1-2 минуты и нажмите "🔍 Проверить" снова
4. Или введите хеш транзакции вручную
"""
            btn_check_again = "🔄 Проверить снова"
            btn_enter_hash = "✍️ Ввести хеш вручную"
            btn_cancel = "❌ Отмена"
        
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(
            InlineKeyboardButton(btn_check_again, callback_data=f"paid_{crypto}_{order_id}"),
            InlineKeyboardButton(btn_enter_hash, callback_data=f"manual_tx_{crypto}_{order_id}"),
            InlineKeyboardButton(btn_cancel, callback_data="cancel_order")
        )
        await checking_msg.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        return
    
    # Транзакция найдена! Проверяем её
    result = await check_usdt_transaction(
        tx_hash, 
        payment_info['unique_amount'],
        settings['wallet_address']
    )
    
    if result['valid']:
        if result.get('confirmed'):
            # Транзакция подтверждена
            if lang == 'en':
                await checking_msg.edit_text(f"""
✅ <b>PAYMENT CONFIRMED!</b>

💵 <b>Amount:</b> {result['amount']} {crypto.upper()}
🔗 <b>Hash:</b> <code>{tx_hash}</code>
✔️ <b>Confirmations:</b> {result['confirmations']}

⏳ Processing your order...
""", parse_mode="HTML")
            else:
                await checking_msg.edit_text(f"""
✅ <b>ПЛАТЕЖ ПОДТВЕРЖДЕН!</b>

💵 <b>Сумма:</b> {result['amount']} {crypto.upper()}
🔗 <b>Хеш:</b> <code>{tx_hash}</code>
✔️ <b>Подтверждений:</b> {result['confirmations']}

⏳ Обрабатываю заказ...
""", parse_mode="HTML")
            
            # Обновляем статус заказа
            await update_order_payment_status(order_id, 'paid', tx_hash)
            
            # Получаем user_id из callback
            user_id = callback.from_user.id
            
            # Обрабатываем доставку товара
            try:
                await process_direct_payment_delivery(order_id, user_id, tx_hash, crypto)
            except Exception as e:
                logger.error(f"Error processing delivery: {e}", exc_info=True)
                if lang == 'en':
                    await callback.message.answer(
                        "✅ Payment confirmed!\n"
                        "❗ An error occurred while processing delivery. The administrator has been notified and will contact you shortly."
                    )
                else:
                    await callback.message.answer(
                        "✅ Платеж подтвержден!\n"
                        "❗ Произошла ошибка при обработке доставки. Администратор уведомлен и скоро свяжется с вами."
                    )
            
            await state.finish()
            
        else:
            # Транзакция найдена, но еще не подтверждена
            if lang == 'en':
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("🔄 Check again", callback_data=f"paid_{crypto}_{order_id}"))
                kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_order"))
                
                await checking_msg.edit_text(f"""
⏳ <b>TRANSACTION FOUND</b>

Your transaction has been found but has not yet received enough confirmations.

💵 <b>Amount:</b> {result['amount']} {settings['name']}
🔗 <b>Hash:</b> <code>{tx_hash}</code>
✔️ <b>Confirmations:</b> {result['confirmations']}/{settings['required_confirmations']}

⏱ <b>Expected time:</b> ~{(settings['required_confirmations'] - result['confirmations']) * 3} seconds

Click "Check again" in a minute.
""", reply_markup=kb, parse_mode="HTML")
            else:
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("🔄 Проверить снова", callback_data=f"paid_{crypto}_{order_id}"))
                kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_order"))
                
                await checking_msg.edit_text(f"""
⏳ <b>ТРАНЗАКЦИЯ НАЙДЕНА</b>

Ваша транзакция найдена, но еще не набрала достаточно подтверждений.

💵 <b>Сумма:</b> {result['amount']} {settings['name']}
🔗 <b>Хеш:</b> <code>{tx_hash}</code>
✔️ <b>Подтверждений:</b> {result['confirmations']}/{settings['required_confirmations']}

⏱ <b>Ожидаемое время:</b> ~{(settings['required_confirmations'] - result['confirmations']) * 3} секунд

Нажмите "Проверить снова" через минуту.
""", reply_markup=kb, parse_mode="HTML")
    else:
        # Транзакция найдена, но невалидна
        if lang == 'en':
            text = f"""
❌ <b>VERIFICATION ERROR</b>

{result.get('error', 'Unknown error')}

<b>Found transaction:</b> <code>{tx_hash}</code>

Please check payment parameters or contact support.
"""
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔄 Check again", callback_data=f"paid_{crypto}_{order_id}"))
            kb.add(InlineKeyboardButton("❌ Cancel", callback_data="cancel_order"))
        else:
            text = f"""
❌ <b>ОШИБКА ПРОВЕРКИ</b>

{result.get('error', 'Неизвестная ошибка')}

<b>Найденная транзакция:</b> <code>{tx_hash}</code>

Пожалуйста, проверьте параметры оплаты или обратитесь в поддержку.
"""
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔄 Проверить снова", callback_data=f"paid_{crypto}_{order_id}"))
            kb.add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_order"))
        
        await checking_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")


async def process_direct_payment_delivery(order_id: int, user_id: int, tx_hash: str, crypto: str = 'usdt'):
    """
    Обработка доставки товара после успешной оплаты через Direct Crypto
    Аналог process_successful_crypto_payment из main.py
    """
    # Импортируем необходимые функции из main.py
    from main import (
        bot, LOG_CHAT_ID, get_text, log_order_action, 
        auto_db, send_cryptobot_log, process_manual_crypto_delivery
    )
    from logs import logger as logs
    
    async with aiosqlite.connect('shop.db') as db:
        # Включаем WAL режим для избежания блокировок
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        
        # Получаем полную информацию о заказе
        order_info = await (await db.execute("""
            SELECT o.quantity, o.city_id, o.district_id, p.name as product_name, 
                   u.username, o.final_price, o.product_id, 
                   c.name as city_name, d.name as district_name,
                   o.discount_percent, o.order_display_id
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN users u ON o.user_id = u.user_id
            LEFT JOIN cities c ON o.city_id = c.id
            LEFT JOIN districts d ON o.district_id = d.id
            WHERE o.id=?
        """, (order_id,))).fetchone()
        
        if not order_info:
            logs.error(f"Order not found - order_id: {order_id}")
            return
        
        quantity, city_id, district_id, product_name, username, final_price, product_id, city_name, district_name, discount_percent, order_display_id = order_info
        username_display = f"@{username}" if username else "Пользователь"
        location = f"{city_name}, {district_name}" if district_name else f"{city_name}" if city_name else "Не указано"
        
        # Если order_display_id пустой, используем order_id
        if not order_display_id:
            order_display_id = str(order_id)
        
        # Обновляем статус заказа
        await db.execute(
            "UPDATE orders SET status='completed', expires_at=NULL WHERE id=?", 
            (order_id,)
        )
        await db.commit()
    
    # Логируем действие
    await log_order_action(order_id, f"DIRECT_{crypto.upper()}_PAYMENT", f"TX: {tx_hash}")
    
    # Логируем успешную оплату в админ-чат
    try:
        crypto_name = CRYPTO_SETTINGS.get(crypto, {}).get('name', 'USDT').replace('💰 ', '').replace('💵 ', '').replace('💠 ', '')
        success_msg = f"""
✅ <b>ОПЛАТА ПОЛУЧЕНА</b> #order{order_display_id}

👤 <b>Пользователь:</b> {username_display} (ID: {user_id})
📦 <b>Товар:</b> {product_name}
⚖️ <b>Количество:</b> {quantity}г
💰 <b>Сумма:</b> {final_price} €
🏙️ <b>Локация:</b> {location}
🪙 <b>Криптовалюта:</b> {crypto_name}
🔗 <b>TX Hash:</b> <code>{tx_hash}</code>
⏱️ <b>Статус:</b> ✅ Успешно оплачен
⏰ <b>Оплачен:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""
        await bot.send_message(LOG_CHAT_ID, success_msg, parse_mode="HTML")
    except Exception as e:
        logs.error(f"Failed to send payment success log to admin chat: {e}")
    
    # Поиск авто-выдачи
    auto_delivery = None
    if city_id and product_id:
        try:
            auto_delivery = await auto_db.get_available_delivery_for_exact_quantity(
                city_id, district_id, product_id, quantity
            )
        except Exception as e:
            logs.error(f"Error getting auto delivery", 
                            order_id=order_id, details=f"Error: {e}")
    
    if auto_delivery:
        try:
            # Распаковываем 7 значений
            delivery_id, delivery_product_id, photo_file_id, coordinates, description, delivery_quantity, delivery_price = auto_delivery
            
            # Помечаем авто-выдачу как использованную
            success = await auto_db.mark_delivery_used(delivery_id, user_id, quantity)
            
            if success:
                # Получаем язык пользователя для локализации сообщения из БД
                lang = await get_user_lang(user_id)
                
                # Формируем сообщение для пользователя
                if lang == 'en':
                    user_message = f"""
✅ <b>PAYMENT CONFIRMED!</b>

📦 <b>Order:</b> #{order_display_id}
🎁 <b>Product:</b> {product_name}
⚖️ <b>Quantity:</b> {quantity}g
💰 <b>Paid:</b> {final_price} €

"""
                    if description:
                        user_message += f"📝 <b>Instructions:</b>\n{description}\n\n"
                    
                    user_message += "❤️ Thank you for your purchase!"
                else:
                    user_message = f"""
✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>

📦 <b>Заказ:</b> #{order_display_id}
🎁 <b>Товар:</b> {product_name}
⚖️ <b>Количество:</b> {quantity}г
💰 <b>Оплачено:</b> {final_price} €

"""
                    if description:
                        user_message += f"📝 <b>Инструкция:</b>\n{description}\n\n"
                    
                    user_message += "❤️ Спасибо за покупку!"
                
                # Отправляем фото или текст
                if photo_file_id and len(photo_file_id) > 20:
                    try:
                        await bot.send_photo(
                            user_id, 
                            photo_file_id, 
                            caption=user_message,
                            parse_mode="HTML"
                        )
                        logs.info(f"Sent auto-delivery photo", user_id=user_id, order_id=order_id)
                    except Exception as photo_error:
                        logs.warning(f"Failed to send photo, sending text", 
                                          user_id=user_id, order_id=order_id,
                                          details=f"Error: {photo_error}")
                        await bot.send_message(user_id, user_message, parse_mode="HTML")
                else:
                    await bot.send_message(user_id, user_message, parse_mode="HTML")
                
                # Логируем в админ-чате
                remaining = delivery_quantity - quantity
                status = "🔴 ИСПОЛЬЗОВАН" if remaining == 0 else f"🟢 Осталось: {remaining}г"
                
                crypto_name_display = CRYPTO_SETTINGS.get(crypto, {}).get('name', 'USDT').replace('💰 ', '').replace('💵 ', '').replace('💠 ', '')
                log_text = (f"✅ {crypto_name_display} оплата ID{order_display_id}\n"
                           f"👤 {username_display}\n"
                           f"🎁 {product_name} ({quantity}г)\n"
                           f"💰 {final_price:.2f} {crypto_name_display}\n")
                
                if discount_percent and discount_percent > 0:
                    original_price = final_price / (1 - discount_percent / 100)
                    log_text += f"🎁 Скидка: {discount_percent}%\n"
                    log_text += f"💶 Исходная: {original_price:.2f} {crypto_name_display}\n"
                
                log_text += f"📍 {location}\n"
                log_text += f"🔗 TX: {tx_hash}\n"
                log_text += f"🚚 АВТО-ВЫДАЧА: Клад #{delivery_id} ({status})"
                
                await bot.send_message(LOG_CHAT_ID, log_text)
                await log_order_action(order_id, f"DIRECT_{crypto.upper()}_AUTO_DELIVERY", f"Auto-delivery ID: {delivery_id}")
                
            else:
                # Если не удалось использовать авто-выдачу
                logs.warning(f"Failed to use auto delivery for order", 
                                  order_id=order_id, user_id=user_id)
                await process_manual_crypto_delivery(order_id, user_id, username_display, product_name, quantity, final_price, location, discount_percent)
                
        except Exception as auto_error:
            logs.error(f"Auto delivery processing error", 
                            order_id=order_id, user_id=user_id,
                            details=f"Error: {auto_error}")
            await process_manual_crypto_delivery(order_id, user_id, username_display, product_name, quantity, final_price, location, discount_percent)
    else:
        # Нет авто-выдачи, используем ручную доставку
        await process_manual_crypto_delivery(order_id, user_id, username_display, product_name, quantity, final_price, location, discount_percent)


async def handle_tx_id_input(callback: types.CallbackQuery, state: FSMContext):
    """Перенаправление на ввод TX ID вручную"""
    # Получаем язык из БД
    lang = await get_user_lang(callback.from_user.id)
    
    # Формат: manual_tx_{crypto}_{order_id}
    parts = callback.data.split("_")
    crypto = parts[2]
    order_id = int(parts[3])
    
    settings = CRYPTO_SETTINGS.get(crypto)
    if not settings:
        if lang == 'en':
            await callback.answer("❌ Cryptocurrency not supported", show_alert=True)
        else:
            await callback.answer("❌ Криптовалюта не поддерживается", show_alert=True)
        return
    
    payment_info = await get_payment_info(order_id)
    
    if not payment_info:
        if lang == 'en':
            await callback.answer("❌ Order not found", show_alert=True)
        else:
            await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Получаем имя криптовалюты без эмодзи для чистого отображения
    crypto_name_clean = settings['name'].replace('💰 ', '').replace('💵 ', '').replace('💠 ', '')
    
    if lang == 'en':
        text = f"""
<b>✍️ ENTER HASH MANUALLY</b>

Enter <b>transaction hash</b> (Transaction ID):

You can find it in your wallet or blockchain explorer.

<b>Expected amount:</b> <code>{payment_info['unique_amount']:.4f}</code> {crypto_name_clean}
<b>Recipient address:</b> <code>{settings['wallet_address']}</code>
<b>Network:</b> {settings['network']}
"""
        btn_back = "◀️ Back"
    else:
        text = f"""
<b>✍️ ВВОД ХЕША ВРУЧНУЮ</b>

Введите <b>хеш транзакции</b> (Transaction ID):

Вы можете найти его в вашем кошельке или блокчейн-эксплорере.

<b>Ожидаемая сумма:</b> <code>{payment_info['unique_amount']:.4f}</code> {crypto_name_clean}
<b>Адрес получателя:</b> <code>{settings['wallet_address']}</code>
<b>Сеть:</b> {settings['network']}
"""  
        btn_back = "◀️ Назад"
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(btn_back, callback_data=f"paid_{crypto}_{order_id}"))
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
    await DirectPayment.waiting_for_tx_id.set()
    await state.update_data(order_id=order_id, crypto=crypto)
    await callback.answer()



async def process_tx_id(message: types.Message, state: FSMContext):
    """Обработка введенного TX ID"""
    # Получаем язык из БД
    lang = await get_user_lang(message.from_user.id)
    
    tx_hash = message.text.strip()
    
    # Проверяем формат хеша (64 символа hex для TRON)
    if len(tx_hash) != 64 or not all(c in '0123456789abcdefABCDEF' for c in tx_hash):
        if lang == 'en':
            await message.answer("❌ Invalid transaction hash format.\nHash must be 64 characters (0-9, a-f).\n\nExample: 0aaa45685121c01425d9d43b995acb6c0a0bbc93d02ce2c904f002e5b6f743bc")
        else:
            await message.answer("❌ Неверный формат хеша транзакции.\nХеш должен состоять из 64 символов (0-9, a-f).\n\nПример: 0aaa45685121c01425d9d43b995acb6c0a0bbc93d02ce2c904f002e5b6f743bc")
        return
    
    data = await state.get_data()
    order_id = data.get('order_id')
    crypto = data.get('crypto', 'usdt')
    
    if not order_id:
        if lang == 'en':
            await message.answer("❌ Error: order not found")
        else:
            await message.answer("❌ Ошибка: заказ не найден")
        await state.finish()
        return
    
    logger.info(f"Processing manual TX hash: {tx_hash} for order {order_id}, crypto: {crypto}")
    
    payment_info = await get_payment_info(order_id)
    
    if not payment_info:
        if lang == 'en':
            await message.answer("❌ Error: payment information not found")
        else:
            await message.answer("❌ Ошибка: информация о платеже не найдена")
        await state.finish()
        return
    
    settings = CRYPTO_SETTINGS.get(crypto, USDT_SETTINGS)
    crypto_name_clean = settings['name'].replace('💰 ', '').replace('💵 ', '').replace('💠 ', '')
    
    # Отправляем сообщение о проверке
    if lang == 'en':
        checking_msg = await message.answer(
            f"🔄 <b>Checking transaction...</b>\n\n"
            f"🔗 TX: <code>{tx_hash}</code>\n"
            f"💰 Expected amount: {payment_info['unique_amount']:.4f} {crypto_name_clean}\n\n"
            f"⏳ This may take a few seconds...",
            parse_mode="HTML"
        )
    else:
        checking_msg = await message.answer(
            f"🔄 <b>Проверяю транзакцию...</b>\n\n"
            f"🔗 TX: <code>{tx_hash}</code>\n"
            f"💰 Ожидаемая сумма: {payment_info['unique_amount']:.4f} {crypto_name_clean}\n\n"
            f"⏳ Это может занять несколько секунд...",
            parse_mode="HTML"
        )
    
    # Проверяем транзакцию
    result = await check_usdt_transaction(
        tx_hash, 
        payment_info['unique_amount'],
        settings['wallet_address']
    )
    
    logger.info(f"Transaction check result: {result}")
    
    if result['valid']:
        if result.get('confirmed'):
            # Транзакция подтверждена
            if lang == 'en':
                await checking_msg.edit_text(f"""
✅ <b>PAYMENT CONFIRMED!</b>

💰 Amount: {result['amount']} {crypto_name_clean}
🔗 TX: <code>{tx_hash}</code>
✔️ Confirmations: {result['confirmations']}

⏳ Processing your order...
""", parse_mode="HTML")
            else:
                await checking_msg.edit_text(f"""
✅ <b>ПЛАТЕЖ ПОДТВЕРЖДЕН!</b>

💰 Сумма: {result['amount']} {crypto_name_clean}
🔗 TX: <code>{tx_hash}</code>
✔️ Подтверждений: {result['confirmations']}

⏳ Обрабатываю заказ...
""", parse_mode="HTML")
            
            # Сохраняем TX хеш и обновляем статус
            await update_order_payment_status(order_id, 'paid', tx_hash)
            
            # Обрабатываем доставку товара
            user_id = message.from_user.id
            try:
                await process_direct_payment_delivery(order_id, user_id, tx_hash, crypto)
            except Exception as e:
                logger.error(f"Error processing delivery: {e}", exc_info=True)
                if lang == 'en':
                    await message.answer(
                        "✅ Payment confirmed!\n"
                        "❗ An error occurred while processing delivery. The administrator has been notified and will contact you shortly."
                    )
                else:
                    await message.answer(
                        "✅ Платеж подтвержден!\n"
                        "❗ Произошла ошибка при обработке доставки. Администратор уведомлен и скоро свяжется с вами."
                    )
            
            await state.finish()
            
        else:
            # Транзакция найдена, но не подтверждена
            if lang == 'en':
                await checking_msg.edit_text(f"""
⏳ <b>TRANSACTION FOUND</b>

💰 Amount: {result['amount']} {crypto_name_clean}
🔗 TX: <code>{tx_hash}</code>
⏱ Confirmations: {result['confirmations']}/{settings['required_confirmations']}

Waiting for network confirmation...
Usually it takes 1-3 minutes.
""", parse_mode="HTML")
            else:
                await checking_msg.edit_text(f"""
⏳ <b>ТРАНЗАКЦИЯ НАЙДЕНА</b>

💰 Сумма: {result['amount']} {crypto_name_clean}
🔗 TX: <code>{tx_hash}</code>
⏱ Подтверждений: {result['confirmations']}/{settings['required_confirmations']}

Ожидайте подтверждения сети...
Обычно это занимает 1-3 минуты.
""", parse_mode="HTML")
            
            # Сохраняем TX и ставим статус pending
            async with aiosqlite.connect('shop.db') as db:
                await db.execute('''
                    UPDATE orders 
                    SET tx_hash = ?, 
                        payment_status = 'pending'
                    WHERE id = ?
                ''', (tx_hash, order_id))
                await db.commit()
            
            await state.finish()
    else:
        # Ошибка проверки
        error_text = result.get('error', 'Unknown error')
        logger.error(f"Transaction validation failed: {error_text}")
        if lang == 'en':
            await checking_msg.edit_text(f"""
❌ <b>VERIFICATION ERROR</b>

{error_text}

🔗 Hash: <code>{tx_hash}</code>

<b>Check:</b>
• Correct transaction hash
• Transfer amount ({payment_info['unique_amount']:.4f} {crypto_name_clean})
• Network (must be {settings['network']})
• Recipient address

Try again or contact support.
""", parse_mode="HTML")
        else:
            await checking_msg.edit_text(f"""
❌ <b>ОШИБКА ПРОВЕРКИ</b>

{error_text}

🔗 Хеш: <code>{tx_hash}</code>

<b>Проверьте:</b>
• Правильность хеша транзакции
• Сумму перевода ({payment_info['unique_amount']:.4f} {crypto_name_clean})
• Сеть (должна быть {settings['network']})
• Адрес получателя

Попробуйте еще раз или обратитесь в поддержку.
""", parse_mode="HTML")


async def check_direct_payment_status(callback: types.CallbackQuery, state: FSMContext):
    """Автоматическая проверка платежа по сумме"""
    # Формат: check_{crypto}_{order_id}
    parts = callback.data.split("_")
    crypto = parts[1]
    order_id = int(parts[2])
    
    # Получаем язык пользователя из БД
    lang = await get_user_lang(callback.from_user.id)
    
    settings = CRYPTO_SETTINGS.get(crypto, USDT_SETTINGS)
    payment_info = await get_payment_info(order_id)
    
    if not payment_info:
        if lang == 'en':
            await callback.answer("❌ Order not found", show_alert=True)
        else:
            await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    # Проверяем срок действия
    expires_at = datetime.fromisoformat(payment_info['expires_at'])
    if datetime.now() > expires_at:
        if lang == 'en':
            await callback.answer("⏰ Payment time expired", show_alert=True)
        else:
            await callback.answer("⏰ Время оплаты истекло", show_alert=True)
        return
    
    if lang == 'en':
        await callback.answer("🔍 Searching transaction...", show_alert=False)
    else:
        await callback.answer("🔍 Ищу транзакцию...", show_alert=False)
    
    # Ищем транзакцию по сумме
    created_at = expires_at - timedelta(minutes=settings['payment_timeout_minutes'])
    tx_hash = await verify_payment_by_amount(
        settings['wallet_address'],
        payment_info['unique_amount'],
        created_at
    )
    
    if tx_hash:
        # Проверяем найденную транзакцию
        result = await check_usdt_transaction(
            tx_hash,
            payment_info['unique_amount'],
            settings['wallet_address']
        )
        
        crypto_name_clean = settings['name'].replace('💰 ', '').replace('💵 ', '').replace('💠 ', '')
        
        if result['valid'] and result.get('confirmed'):
            # Получаем order_display_id из БД
            async with aiosqlite.connect('shop.db') as db:
                cursor = await db.execute('SELECT order_display_id FROM orders WHERE id = ?', (order_id,))
                row = await cursor.fetchone()
                order_display_id = row[0] if row and row[0] else str(order_id)
            
            # Сообщение пользователю
            if lang == 'en':
                await callback.message.edit_text(
                    f"✅ <b>PAYMENT AUTOMATICALLY CONFIRMED!</b>\n\n"
                    f"💰 <b>Amount:</b> {result['amount']} {crypto_name_clean}\n"
                    f"🔗 TX: <code>{tx_hash}</code>\n\n"
                    f"Your order #{order_display_id} accepted for processing!", 
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    f"✅ <b>ПЛАТЕЖ АВТОМАТИЧЕСКИ НАЙДЕН И ПОДТВЕРЖДЕН!</b>\n\n"
                    f"💰 <b>Сумма:</b> {result['amount']} {crypto_name_clean}\n"
                    f"🔗 TX: <code>{tx_hash}</code>\n\n"
                    f"Ваш заказ #{order_display_id} принят в обработку!", 
                    parse_mode="HTML"
                )
            
            # Обновляем статус в БД
            async with aiosqlite.connect('shop.db') as db:
                await db.execute('''
                    UPDATE orders 
                    SET tx_hash = ?, 
                        payment_status = 'confirmed'
                    WHERE id = ?
                ''', (tx_hash, order_id))
                await db.commit()
            
            # Уведомление в админ-чат
            from main import bot, LOG_CHAT_ID
            try:
                confirmed_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
                log_msg = f"""
✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА #{order_display_id}</b>

💰 <b>Сумма:</b> {result['amount']} {crypto_name_clean}
🔗 <b>TX:</b> <code>{tx_hash}</code>
👤 <b>Пользователь ID:</b> {callback.from_user.id}
🪙 <b>Криптовалюта:</b> {crypto_name_clean}
⏰ <b>Подтверждено:</b> {confirmed_time}
"""
                await bot.send_message(LOG_CHAT_ID, log_msg, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Failed to send payment confirmation log to admin chat: {e}")
            
            await state.finish()
        else:
            if lang == 'en':
                await callback.answer("⏳ Transaction found, awaiting confirmation", show_alert=True)
            else:
                await callback.answer("⏳ Транзакция найдена, ожидает подтверждения", show_alert=True)
    else:
        if lang == 'en':
            await callback.answer("❌ Transaction not found. Make sure you sent the exact amount.", show_alert=True)
        else:
            await callback.answer("❌ Транзакция не найдена. Убедитесь, что отправили точную сумму.", show_alert=True)


# ══════════════════════════════════════════════════════════════
# НАСТРОЙКИ ЧЕРЕЗ АДМИН-ПАНЕЛЬ
# ══════════════════════════════════════════════════════════════

async def get_usdt_wallet_from_db() -> str:
    """Получает USDT адрес из БД"""
    async with aiosqlite.connect('shop.db') as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'usdt_wallet'")
        row = await cursor.fetchone()
        return row[0] if row else USDT_SETTINGS['wallet_address']


async def set_usdt_wallet_to_db(wallet: str):
    """Сохраняет USDT адрес в БД"""
    async with aiosqlite.connect('shop.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO settings (key, value) VALUES ('usdt_wallet', ?)
        ''', (wallet,))
        await db.commit()
    
    # Обновляем глобальные настройки
    USDT_SETTINGS['wallet_address'] = wallet


async def get_usdt_api_key_from_db() -> str:
    """Получает TronGrid API ключ из БД"""
    async with aiosqlite.connect('shop.db') as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'trongrid_api_key'")
        row = await cursor.fetchone()
        return row[0] if row else ''


async def set_usdt_api_key_to_db(api_key: str):
    """Сохраняет TronGrid API ключ в БД"""
    async with aiosqlite.connect('shop.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO settings (key, value) VALUES ('trongrid_api_key', ?)
        ''', (api_key,))
        await db.commit()
    
    USDT_SETTINGS['api_key'] = api_key


# Инициализация при загрузке модуля
async def init_direct_payment():
    """Инициализация настроек из БД"""
    wallet = await get_usdt_wallet_from_db()
    api_key = await get_usdt_api_key_from_db()
    
    USDT_SETTINGS['wallet_address'] = wallet
    USDT_SETTINGS['api_key'] = api_key