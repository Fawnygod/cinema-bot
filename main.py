import telebot
import requests
from telebot import types
import random
import os

TOKEN = os.getenv('BOT_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

bot = telebot.TeleBot(TOKEN)

NAMES_MAP = {"movie": "Фільм 🎬", "tv": "Серіал 📺", "anime": "Аніме ⛩"}

# РОЗШИРЕНІ ЖАНРИ
GENRES_MAP = {
    "movie": {
        "Будь-який 🎲": "any", 
        "Бойовик 💥": 28, 
        "Комедія 😂": 35, 
        "Жахи 😱": 27, 
        "Фантастика 🚀": 878,
        "Трилер 🔪": 53,
        "Драма 🎭": 18,
        "Кримінал ⚖️": 80,
        "Сімейний 👨‍👩‍👧": 10751,
        "Мультфільм 🧸": 16
    },
    "tv": {
        "Будь-який 🎲": "any", 
        "Детектив 🕵️‍♂️": 80, 
        "Комедія 😂": 35, 
        "Фентезі 🧙‍♂️": 10765,
        "Драма 🎭": 18,
        "Кримінал ⚖️": 80,
        "Пригоди 🧭": 10759,
        "Sci-Fi 🤖": 10765
    },
    "anime": {
        "Будь-який 🎲": "any",
        "Екшн ⚔️": 28, 
        "Пригоди 🗺️": 12, 
        "Фентезі 🔮": 14,
        "Комедія 😂": 35,
        "Драма 🎭": 18,
        "Романтика ❤️": 10749
    }
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
    
    if call.data.startswith("type_"):
        ctype = call.data.split("_")[1]
        user_selection[chat_id] = {'type': ctype}
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(n, callback_data=f"genre_{g_id}_{n}") for n, g_id in GENRES_MAP[ctype].items()]
        markup.add(*btns)
        bot.edit_message_text(f"✅ **Ваш вибір:** {NAMES_MAP[ctype]}\n\n🎭 Тепер оберіть жанр:", chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("genre_"):
        parts = call.data.split("_")
        g_id, g_name = parts[1], parts[2]
        user_selection[chat_id]['genre_id'] = None if g_id == "any" else g_id
        ctype = user_selection[chat_id]['type']
        bot.edit_message_text(f"✅ **Ваш вибір:** {NAMES_MAP[ctype]} > {g_name}", chat_id, call.message.message_id, parse_mode="Markdown")
        send_recommendation(chat_id)

    elif call.data == "repeat":
        send_recommendation(chat_id)
    elif call.data == "change":
        start(call.message)

def send_recommendation(chat_id):
    data = user_selection.get(chat_id)
    if not data: return
    
    # Визначаємо шлях пошуку (для аніме випадковий вибір між кіно та тб)
    if data['type'] == "anime":
        api_path = random.choice(["tv", "movie"])
        with_genres = f"16,{data.get('genre_id', '')}" if data.get('genre_id') else "16"
        with_lang = "ja"
    else:
        api_path = "tv" if data['type'] == "tv" else "movie"
        with_genres = data.get('genre_id') if data.get('genre_id') else ""
        with_lang = ""

    params = {
        'api_key': TMDB_API_KEY,
        'sort_by': 'popularity.desc',
        'vote_average.gte': 5.5,
        'vote_count.gte': 100,
        'language': 'uk-UA',
        'with_genres': with_genres,
        'with_original_language': with_lang
    }

    try:
        res_pages = requests.get(f"https://api.themoviedb.org/3/discover/{api_path}", params=params).json()
        params['page'] = random.randint(1, min(res_pages.get('total_pages', 1), 15))
        res = requests.get(f"https://api.themoviedb.org/3/discover/{api_path}", params=params).json()
        results = res.get('results', [])
        
        filtered = [m for m in results if m.get('poster_path') and m['id'] not in seen_content.get(chat_id, [])]
        if not filtered:
            bot.send_message(chat_id, "❌ Нічого нового не знайдено за цими параметрами.")
            return

        movie = random.choice(filtered[:10])
        m_id = movie['id']
        seen_content.setdefault(chat_id, []).append(m_id)

        # Детальний запит
        details = requests.get(f"https://api.themoviedb.org/3/{api_path}/{m_id}?api_key={TMDB_API_KEY}&language=uk-UA").json()
        
        countries = details.get('production_countries', [])
        country_name = countries[0].get('name', "Невідомо") if countries else "Невідомо"
        
        title = details.get('title') or details.get('name')
        year = (details.get('release_date') or details.get('first_air_date') or "----")[:4]
        rating = round(details.get('vote_average', 0), 1)
        
        poster = f"https://image.tmdb.org/t/p/w500{details['poster_path']}"
        trailer_url = f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+трейлер+українською"

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🎥 Пошук трейлера", url=trailer_url))
        markup.row(types.InlineKeyboardButton("🔄 Ще один", callback_data="repeat"),
                   types.InlineKeyboardButton("🎭 Меню", callback_data="change"))

        caption = (f"🌟 *{title}*\n"
                   f"🎞 Тип: {NAMES_MAP[data['type']]}\n"
                   f"⭐️ Рейтинг: {rating}\n"
                   f"🗓 Рік: {year}\n"
                   f"🌍 Країна: {country_name}\n\n"
                   f"📖 {details.get('overview', 'Опис відсутній')[:450]}...")
        
        bot.send_photo(chat_id, poster, caption=caption, parse_mode="Markdown", reply_markup=markup)
    except:
        bot.send_message(chat_id, "❌ Помилка завантаження.")

bot.infinity_polling()
        
