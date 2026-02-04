import telebot
import requests
from telebot import types
import random
import os

# Ключі з налаштувань Railway
TOKEN = os.getenv('BOT_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

bot = telebot.TeleBot(TOKEN)

# Назви типів
NAMES_MAP = {
    "movie": "Фільм 🎬", 
    "tv": "Серіал 📺", 
    "anime": "Аніме ⛩"
}

GENRES_MAP = {
    "movie": {"Будь-який 🎲": "any", "Бойовик 💥": 28, "Комедія 😂": 35, "Жахи 😱": 27, "Фантастика 🚀": 878},
    "tv": {"Будь-який 🎲": "any", "Детектив 🕵️‍♂️": 80, "Комедія 😂": 35, "Фентезі 🧙‍♂️": 10765},
    "anime": {"Будь-який 🎲": "any", "Екшн ⚔️": 28, "Пригоди 🗺️": 12, "Фентезі 🔮": 14}
}

# Прапори для країн
COUNTRIES_ISO = {
    "US": "США 🇺🇸", "UA": "Україна 🇺🇦", "GB": "Велика Британія 🇬🇧", 
    "FR": "Франція 🇫🇷", "DE": "Німеччина 🇩🇪", "JP": "Японія 🇯🇵", 
    "KR": "Південна Корея 🇰🇷", "IT": "Італія 🇮🇹", "ES": "Іспанія 🇪🇸"
}

user_selection = {}
seen_content = {}

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_selection[chat_id] = {}
    if chat_id not in seen_content: seen_content[chat_id] = []
    
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
    
    # Вибір типу
    if call.data.startswith("type_"):
        ctype = call.data.split("_")[1]
        user_selection[chat_id] = {'type': ctype}
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(n, callback_data=f"genre_{g_id}_{n}") for n, g_id in GENRES_MAP[ctype].items()]
        markup.add(*btns)
        
        # Відображення першого кроку вибору
        text = f"✅ **Ваш вибір:** {NAMES_MAP[ctype]}\n\n🎭 Тепер оберіть жанр:"
        bot.edit_message_text(text, chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    # Вибір жанру
    elif call.data.startswith("genre_"):
        parts = call.data.split("_")
        g_id, g_name = parts[1], parts[2]
        
        user_selection[chat_id]['genre_id'] = None if g_id == "any" else g_id
        ctype = user_selection[chat_id]['type']
        
        # Відображення повного ланцюжка вибору (не зникає!)
        final_text = f"✅ **Ваш вибір:** {NAMES_MAP[ctype]} > {g_name}"
        bot.edit_message_text(final_text, chat_id, call.message.message_id, parse_mode="Markdown")
        
        send_recommendation(chat_id)
        bot.answer_callback_query(call.id)

    elif call.data == "repeat":
        send_recommendation(chat_id)
        bot.answer_callback_query(call.id)
    elif call.data == "change":
        start(call.message)
        bot.answer_callback_query(call.id)

def send_recommendation(chat_id):
    data = user_selection.get(chat_id)
    if not data or 'type' not in data: return

    api_path = "tv" if data['type'] == "tv" else "movie"
    params = {
        'api_key': TMDB_API_KEY,
        'sort_by': 'popularity.desc',
        'vote_average.gte': 5.5,
        'vote_count.gte': 100,
        'language': 'uk-UA'
    }

    if data.get('genre_id'): params['with_genres'] = data['genre_id']
    if data['type'] == "anime":
        params.update({'with_genres': f"16,{data.get('genre_id', '')}", 'with_original_language': 'ja'})
        api_path = "movie"
    else:
        params['without_genres'] = 16

    try:
        res_pages = requests.get(f"https://api.themoviedb.org/3/discover/{api_path}", params=params).json()
        params['page'] = random.randint(1, min(res_pages.get('total_pages', 1), 15))
        res = requests.get(f"https://api.themoviedb.org/3/discover/{api_path}", params=params).json()
        results = res.get('results', [])
        
        fresh = [m for m in results if m['id'] not in seen_content.get(chat_id, []) and m.get('poster_path')]

        if fresh:
            movie = random.choice(fresh[:5])
            m_id = movie['id']
            seen_content.setdefault(chat_id, []).append(m_id)
            
            title = movie.get('title') or movie.get('name')
            year = (movie.get('release_date') or movie.get('first_air_date') or "----")[:4]
            
            # Визначаємо країну
            origin_countries = movie.get('origin_country', [])
            country_code = origin_countries[0] if origin_countries else "??"
            country_display = COUNTRIES_ISO.get(country_code, f"{country_code} 🏳️")

            overview = movie.get('overview')
            if not overview:
                eng_res = requests.get(f"https://api.themoviedb.org/3/{api_path}/{m_id}?api_key={TMDB_API_KEY}&language=en-US").json()
                overview = eng_res.get('overview') or "Опис відсутній."

            poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
            
            # Пошук трейлера на YouTube
            trailer_url = f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+трейлер+українською"

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("🎥 Пошук трейлера", url=trailer_url))
            markup.row(types.InlineKeyboardButton("🔄 Ще один", callback_data="repeat"),
                       types.InlineKeyboardButton("🎭 Меню", callback_data="change"))

            # Вся інформація в картці
            caption = (f"🌟 *{title}*\n"
                       f"🎞 Тип: {NAMES_MAP[data['type']]}\n"
                       f"⭐️ Рейтинг: {movie['vote_average']}\n"
                       f"🗓 Рік: {year}\n"
                       f"🌍 Країна: {country_display}\n\n"
                       f"📖 {overview[:450]}...")
            
            bot.send_photo(chat_id, poster, caption=caption, parse_mode="Markdown", reply_markup=markup)
    except:
        bot.send_message(chat_id, "❌ Помилка зв'язку з базою.")

bot.infinity_polling()
