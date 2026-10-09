import sqlite3
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "8544092871:AAFyd2vw8s1NoTpHaC4tJ6-6SNPTYiXBw6A"
ADMIN_ID = 7175300475

logging.basicConfig(level=logging.INFO)
router = Router()

def init_db():
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            photo TEXT,
            name TEXT,
            price TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

class AddProductState(StatesGroup):
    waiting_for_category = State()
    waiting_for_photo = State()
    waiting_for_info = State()

class OrderState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_address = State()

def main_menu_keyboard(user_id):
    keyboard = [
        [InlineButton(text="🛍 Каталог товаров", callback_data="show_categories")],
        [InlineButton(text="🛒 Корзина", callback_data="show_cart")]
    ]
    if user_id == ADMIN_ID:
        keyboard.append([InlineButton(text="➕ [Админ] Добавить товар", callback_data="admin_add_product")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def categories_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineButton(text="👩 Женские вещи", callback_data="cat_women")],
        [InlineButton(text="👨 Мужские вещи", callback_data="cat_men")],
        [InlineButton(text="👥 Парные костюмы", callback_data="cat_pairs")],
        [InlineButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await state.update_data(cart=[])
    await message.answer(
        "👋 Добро пожаловать в наш интернет-магазин одежды!\nВыберите интересующий вас раздел:",
        reply_markup=main_menu_keyboard(message.from_user.id)
    )

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.answer(
        "Главное меню:",
        reply_markup=main_menu_keyboard(callback.from_user.id)
    )
    try:
        await callback.message.delete()
    except:
        pass

@router.callback_query(F.data == "admin_add_product")
async def admin_start_add(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав администратора!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineButton(text="👩 Женские вещи", callback_data="setcat_women")],
        [InlineButton(text="👨 Мужские вещи", callback_data="setcat_men")],
        [InlineButton(text="👥 Парные костюмы", callback_data="setcat_pairs")],
        [InlineButton(text="❌ Отмена", callback_data="back_to_main")]
    ])
    await callback.message.answer("📂 Выберите категорию, в которую хотите добавить товар:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("setcat_"))
async def admin_chose_category(callback: CallbackQuery, state: FSMContext):
    cat_code = callback.data.split("_")[1]
    cat_names = {
        "women": "Женские вещи",
        "men": "Мужские вещи",
        "pairs": "Парные костюмы"
    }
    
    await state.update_data(category=cat_names.get(cat_code, "Общее"))
    await state.set_state(AddProductState.waiting_for_photo)
    
    await callback.message.answer(f"📸 Отправьте фотографию товара для категории: <b>{cat_names.get(cat_code)}</b>", parse_mode="HTML")
    await callback.answer()

@router.message(AddProductState.waiting_for_photo, F.photo)
async def admin_get_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await state.set_state(AddProductState.waiting_for_info)
    await message.answer("✍️ Теперь отправьте текст товара (название, размеры, цвета, цена):", parse_mode="HTML")

@router.message(AddProductState.waiting_for_info)
async def admin_get_info(message: Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    photo_id = data.get("photo")
    info_text = message.text

    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (category, photo, name, price) VALUES (?, ?, ?, ?)", 
                   (category, photo_id, info_text, info_text))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"✅ Товар успешно добавлен в раздел «{category}»!", reply_markup=main_menu_keyboard(message.from_user.id))

@router.callback_query(F.data == "show_categories")
async def show_categories(callback: CallbackQuery):
    await callback.message.answer("📂 Выберите интересующий вас раздел:", reply_markup=categories_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def show_products_by_category(callback: CallbackQuery):
    cat_code = callback.data.split("_")[1]
    cat_names = {
        "women": "Женские вещи",
        "men": "Мужские вещи",
        "pairs": "Парные костюмы"
    }
    selected_category = cat_names.get(cat_code)

    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, photo, name FROM products WHERE category = ?", (selected_category,))
    products = cursor.fetchall()
    conn.close()

    if not products:
        await callback.message.answer(f"В разделе «{selected_category}» пока нет товаров.", reply_markup=categories_keyboard())
        await callback.answer()
        return

    await callback.message.answer(f"📦 Товары в разделе «{selected_category}»:")
    for prod in products:
        prod_id, photo_id, name = prod[0], prod[1], prod[2]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineButton(text="🛒 Добавить в корзину", callback_data=f"add_{prod_id}")]
        ])
        if callback.from_user.id == ADMIN_ID:
            keyboard.inline_keyboard.append([InlineButton(text="🗑 Удалить товар", callback_data=f"del_{prod_id}")])

        await callback.message.answer_photo(photo=photo_id, caption=name, reply_markup=keyboard)
    
    await callback.answer()

@router.callback_query(F.data.startswith("del_"))
async def delete_product(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    prod_id = int(callback.data.split("_")[1])
    
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()

    await callback.answer("🗑 Товар удален!")
    try:
        await callback.message.delete()
    except:
        pass

@router.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[1])
    
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM products WHERE id = ?", (prod_id,))
    prod = cursor.fetchone()
    conn.close()

    if prod:
        data = await state.get_data()
        cart = data.get("cart", [])
        cart.append(prod[0])
        await state.update_data(cart=cart)
        await callback.answer("✅ Товар добавлен в корзину!")
    else:
        await callback.answer("Товар не найден.", show_alert=True)

@router.callback_query(F.data == "show_cart")
async def show_cart(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", [])

    if not cart:
        await callback.message.answer("🛒 Ваша корзина пуста.", reply_markup=main_menu_keyboard(callback.from_user.id))
        await callback.answer()
        return

    text = "🛒 <b>Ваша корзина:</b>\n\n"
    for i, item in enumerate(cart, 1):
        text += f"{i}. {item}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineButton(text="🚀 Оформить заказ", callback_data="start_checkout")],
        [InlineButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
        [InlineButton(text="🔙 В меню", callback_data="back_to_main")]
    ])
    await callback.message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery, state: FSMContext):
    await state.update_data(cart=[])
    await callback.message.answer("🗑 Корзина очищена.", reply_markup=main_menu_keyboard(callback.from_user.id))

@router.callback_query(F.data == "start_checkout")
async def start_checkout(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderState.waiting_for_phone)
    await callback.message.answer("📱 Пожалуйста, введите ваш номер телефона для связи:")
    await callback.answer()

@router.message(OrderState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(OrderState.waiting_for_address)
    await message.answer("📍 Укажите адрес доставки или пункт выдачи:")

@router.message(OrderState.waiting_for_address)
async def process_address_final(message: Message, state: FSMContext):
    address = message.text
    data = await state.get_data()
    phone = data.get("phone")
    cart = data.get("cart", [])

    order_text = f"🚨 <b>Новый заказ от клиента!</b>\n\n📱 Телефон: {phone}\n📍 Адрес: {address}\n\n🛒 <b>Товары:</b>\n"
    for item in cart:
        order_text += f"- {item}\n"

    await message.bot.send_message(ADMIN_ID, order_text, parse_mode="HTML")
    await message.answer("🎉 Спасибо за заказ! Администратор скоро свяжется с вами.", reply_markup=main_menu_keyboard(message.from_user.id))
    await state.clear()

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
