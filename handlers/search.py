from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database import db
from config import ADMIN_IDS
from keyboards.inline import search_results_kb, main_menu_kb

router = Router()

# Simple flag-based search: user taps 🔍 then types
# We'll treat any text message (not a command) as a search if it's short
SEARCHING_USERS = set()


@router.message(Command("search"))
async def search_command(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        query = args[1].strip()
        await perform_search(message, query)
    else:
        SEARCHING_USERS.add(message.from_user.id)
        await message.answer(
            "🔍 <b>ရှာဖွေလိုသော သီချင်းအမည် ရိုက်ထည့်ပါ:</b>",
            parse_mode="HTML",
        )


@router.message(F.text)
async def handle_text_message(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # If user is in search mode, treat text as search query
    if user_id in SEARCHING_USERS:
        SEARCHING_USERS.discard(user_id)
        await perform_search(message, text)
        return


async def perform_search(message: Message, query: str):
    if not query:
        await message.answer("❌ ရှာဖွေရန် အမည် ထည့်ပါ။")
        return

    songs = await db.search_songs(query)
    if not songs:
        await message.answer(
            f"😔 '{query}' နှင့် ကိုက်ညီသော သီချင်း မတွေ့ပါ။\n"
            "အခြားအမည် စမ်းကြည့်ပါ။",
            reply_markup=main_menu_kb(message.from_user.id in ADMIN_IDS),
        )
        return

    await message.answer(
        f"🔍 <b>'{query}' အတွက် ရလဒ် ({len(songs)}):</b>",
        parse_mode="HTML",
        reply_markup=search_results_kb(songs),
    )
