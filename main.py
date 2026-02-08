import telebot
import requests
from telebot import types
import random
import os

TOKEN = os.getenv('BOT_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

bot = telebot.TeleBot(TOKEN)

NAMES_MAP = {"movie": "Фільм 🎬", "tv": "Серіал 📺", "anime": "Аніме ⛩"}

GENRES_MAP = {
    "movie": {
        "Будь-який 🎲": "any", "Бойовик 💥": 28, "Комедія 😂": 35, "Жахи 😱": 27, 
        "Фантастика 🚀": 878, "Трилер 🔪": 53, "Драма 🎭": 18, "Кримінал ⚖️": 80, 
        "Сімейний 👨‍👩‍👧": 10751, "Мультфільм 🧸": 16, "Пригоди 🧭": 12, "Містика 🔮": 9648
    },
    "tv": {
        "Будь-який 🎲": "any", "Детектив 🕵️‍♂️": 80, "Комедія 😂": 35, "Фентезі 🧙‍♂️": 10765,
        "Драма 🎭": 18, "Кримінал ⚖️": 80, "Пригоди 🧭": 10759, "Sci-Fi 🤖": 10765,
        "Мультсеріал 🐥": 16, "Бойовик ⚔️": 10759, "Трилер ⛓️": 80
    },
    "anime": {
        "Будь-який 🎲": "any", "Екшн ⚔️": 28, "Пригоди 🗺️": 12, "Фентезі 🔮": 14,
        "Комедія 😂": 35, "Драма 🎭": 18, "Романтика ❤️": 10749, "Психологія 🧠": 9648,
        "Сай-фай 🤖": 878, "Надприродне 👻": 9648  # Покращено мапінг жанру
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
        user_selection[chat_id]['genre_id'] = None if parts[1] == "any" else parts[1]
        bot.edit_message_text(f"✅ **Ваш вибір:** {NAMES_MAP[user_selection[chat_id]['type']]} > {parts[2]}", chat_id, call.message.message_id, parse_mode="Markdown")
        send_recommendation(chat_id)

    elif call.data == "repeat":
        send_recommendation(chat_id)
    elif call.data == "change":
        start(call.message)

def get_content(api_path, params, chat_id):
    """Допоміжна функція для пошуку на декількох сторінках"""
    for _ in range(3): # Пробуємо до 3 різних випадкових сторінок
        res = requests.get(f"https://api.themoviedb.org/3/discover/{api_path}", params=params).json()
        results = res.get('results', [])
        filtered = [m for m in results if m.get('poster_path') and m['id'] not in seen_content.get(chat_id, [])]
        if filtered:
            return random.choice(filtered), api_path
        if res.get('total_pages', 1) > 1:
            params['page'] = random.randint(1, min(res['total_pages'], 20))
        else:
            break
    return None, None

def send_recommendation(chat_id):
    data = user_selection.get(chat_id)
    if not data: return
    
    is_anime = data['type'] == "anime"
    with_genres = f"16,{data.get('genre_id', '')}" if is_anime and data.get('genre_id') else ("16" if is_anime else data.get('genre_id', ""))
    
    params = {
        'api_key': TMDB_API_KEY,
        'sort_by': 'popularity.desc',
        'vote_average.gte': 5.0,
        'vote_count.gte': 20,
        'language': 'uk-UA',
        'with_genres': with_genres.strip(','),
        'with_original_language': 'ja' if is_anime else ""
    }

    # ЛОГІКА ПОШУКУ АНІМЕ (TV -> Movie)
    if is_anime:
        movie_data, final_path = get_content("tv", params, chat_id)
        if not movie_data:
            movie_data, final_path = get_content("movie", params, chat_id)
    else:
        api_path = "tv" if data['type'] == "tv" else "movie"
        movie_data, final_path = get_content(api_path, params, chat_id)

    if not movie_data:
        bot.send_message(chat_id, "❌ Нічого не знайдено. Спробуйте інший жанр!")
        return

    m_id = movie_data['id']
    seen_content.setdefault(chat_id, []).append(m_id)

    try:
        details = requests.get(f"https://api.themoviedb.org/3/{final_path}/{m_id}?api_key={TMDB_API_KEY}&language=uk-UA").json()
        title = details.get('title') or details.get('name')
        year = (details.get('release_date') or details.get('first_air_date') or "----")[:4]
        country = details.get('production_countries', [{}])[0].get('name', "Невідомо")
        
        poster = f"https://image.tmdb.org/t/p/w500{details['poster_path']}"
        rezka_url = f"https://rezka.ag/search/?do=search&subaction=search&q={title.replace(' ', '+')}"
        trailer_url = f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+трейлер+українською"

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🍿 Дивитися на Rezka", url=rezka_url),
            types.InlineKeyboardButton("🎥 Пошук трейлера", url=trailer_url)
        )
        markup.row(types.InlineKeyboardButton("🔄 Ще один", callback_data="repeat"),
                   types.InlineKeyboardButton("🎭 Меню", callback_data="change"))

        caption = (f"🌟 *{title}*\n🎞 Тип: {NAMES_MAP[data['type']]}\n⭐️ Рейтинг: {round(details.get('vote_average', 0), 1)}\n"
                   f"🗓 Рік: {year}\n🌍 Країна: {country}\n\n📖 {details.get('overview', 'Опис відсутній')[:450]}...")
        
        bot.send_photo(chat_id, poster, caption=caption, parse_mode="Markdown", reply_markup=markup)
    except:
        bot.send_message(chat_id, "❌ Помилка завантаження даних.")

bot.infinity_polling()
