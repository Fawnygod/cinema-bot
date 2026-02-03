import telebot
import requests
from telebot import types
import random
import os

# --- НАЛАШТУВАННЯ ---
TOKEN = os.getenv('BOT_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

bot = telebot.TeleBot(TOKEN)

# Карта назв для інтерфейсу
NAMES_MAP = {
    "movie": "Фільм 🎬", 
    "tv": "Серіал 📺", 
    "anime": "Аніме ⛩"
}

# Жанри
GENRES_MAP = {
    "movie": {"Будь-який 🎲": "any", "Бойовик 💥": 28, "Комедія 😂": 35, "Жахи 😱": 27, "Фантастика 🚀": 878, "Драма 🎭": 18},
    "tv": {"Будь-який 🎲": "any", "Детектив 🕵️‍♂️": 80, "Комедія 😂": 35, "Фентезі 🧙‍♂️": 10765, "Пригоди 🧭": 10759},
    "anime": {"Будь-який 🎲": "any", "Екшн ⚔️": 28, "Пригоди 🗺️": 12, "Фентезі 🔮": 14, "Сай-фай 🤖": 878}
}

user_selection = {}
seen_content = {}

# --- ОБРОБНИКИ КОМАНД ---

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_selection[chat_id] = {}
    if chat_id not in seen_content: 
        seen_content[chat_id] = []
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("Фільми 🎬", callback_data="type_movie"),
        types.InlineKeyboardButton("Серіали 📺", callback_data="type_tv"),
        types.InlineKeyboardButton("Аніме ⛩", callback_data="type_anime")
    )
    bot.send_message(chat_id, "🎬 **Що сьогодні подивимось?**", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    
    # Вибір типу (Фільм/Серіал/Аніме)
    if call.data.startswith("type_"):
        ctype = call.data.split("_")[1]
        user_selection[chat_id] = {'type': ctype}
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(n, callback_data=f"genre_{g_id}_{n}") for n, g_id in GENRES_MAP[ctype].items()]
        markup.add(*btns)
        
        text = f"✅ **Ваш вибір:** {NAMES_MAP[ctype]}\n\n🎭 Тепер оберіть жанр:"
        bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    # Вибір жанру
    elif call.data.startswith("genre_"):
        parts = call.data.split("_")
        g_id, g_name = parts[1], parts[2]
        
        user_selection[chat_id]['genre_id'] = None if g_id == "any" else g_id
        ctype = user_selection[chat_id]['type']
        
        # Відображаємо фінальний вибір текстом
        bot.edit_message_text(f"✅ **Ваш вибір:** {NAMES_MAP[ctype]} > {g_name}", chat_id, call.message.message_id, parse_mode="Markdown")
        
        send_recommendation(chat_id)
        bot.answer_callback_query(call.id)

    # Повтор пошуку
    elif call.data == "repeat":
        send_recommendation(chat_id)
        bot.answer_callback_query(call.id)
        
    # Повернення в меню
    elif call.data == "change":
        start(call.message)
        bot.answer_callback_query(call.id)

# --- ЛОГІКА РЕКОМЕНДАЦІЇ ---

def send_recommendation(chat_id):
    data = user_selection.get(chat_id)
    if not data or 'type' not in data: 
        return

    api_path = "tv" if data['type'] == "tv" else "movie"
    content_label = NAMES_MAP[data['type']]
    
    # Фільтрація: рейтинг 5.5+ та хоча б 100 голосів
    params = {
        'api_key': TMDB_API_KEY,
        'sort_by': 'popularity.desc',
        'vote_average.gte': 5.5,
        'vote_count.gte': 100,
        'language': 'uk-UA'
    }

    if data.get('genre_id'): 
        params['with_genres'] = data['genre_id']

    # Специфіка для Аніме
    if data['type'] == "anime":
        params['with_genres'] = f"16,{data['genre_id']}" if data.get('genre_id') else "16"
        params['with_original_language'] = 'ja'
        api_path = "movie"
    else:
        params['without_genres'] = 16

    try:
        # 1. Рахуємо сторінки
        check_res = requests.get(f"https://api.themoviedb.org/3/discover/{api_path}", params=params).json()
        total_pages = min(check_res.get('total_pages', 1), 15)
        
        # 2. Рандомимо сторінку
        params['page'] = random.randint(1, total_pages)
        res = requests.get(f"https://api.themoviedb.org/3/discover/{api_path}", params=params).json()
        results = res.get('results', [])
        
        # Прибираємо дублікати
        fresh = [m for m in results if m['id'] not in seen_content.get(chat_id, []) and m.get('poster_path')]

        if fresh:
            movie = random.choice(fresh[:10])
            m_id = movie['id']
            seen_content.setdefault(chat_id, []).append(m_id)
            
            title = movie.get('title') or movie.get('name')
            year = (movie.get('release_date') or movie.get('first_air_date') or "----")[:4]
            overview = movie.get('overview')

            # Fallback на англійський опис, якщо немає UA
            if not overview:
                eng_res = requests.get(f"https://api.themoviedb.org/3/{api_path}/{m_id}?api_key={TMDB_API_KEY}&language=en-US").json()
                overview = eng_res.get('overview') or "Опис відсутній."

            poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
            
            # Посилання на плеєри
            url_1 = f"https://vidsrc.cc/v2/embed/{'tv' if data['type'] == 'tv' else 'movie'}/{m_id}"
            url_2 = f"https://www.2embed.cc/embed/{m_id}"

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🇺🇦 Дивитися (Варіант 1)", url=url_1),
                types.InlineKeyboardButton("🎬 Дивитися (Варіант 2)", url=url_2)
            )
            markup.row(
                types.InlineKeyboardButton("🔄 Ще один", callback_data="repeat"),
                types.InlineKeyboardButton("🎭 Меню", callback_data="change")
            )

            caption = (f"🌟 *{title}*\n"
                       f"🎞 Тип: {content_label}\n"
                       f"⭐️ Рейтинг: {movie['vote_average']}\n"
                       f"🗓 Рік: {year}\n\n"
                       f"📖 {overview[:400]}...\n\n"
                       f"💡 _Порада: якщо мова не та, змініть варіант або налаштування плеєра (⚙️)._")
            
            bot.send_photo(chat_id, poster, caption=caption, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, "🔍 Контент закінчився. Спробуйте інший жанр!")
    except Exception as e:
        print(f"Error: {e}")
        bot.send_message(chat_id, "❌ Помилка зв'язку з базою.")

# --- ЗАПУСК ---
if __name__ == "__main__":
    print("Бот запущений...")
    bot.infinity_polling()
