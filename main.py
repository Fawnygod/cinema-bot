import telebot
import requests
from telebot import types
import random
import os

# Отримуємо токени з налаштувань сервера (Variables на Railway)
TOKEN = os.getenv('BOT_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

bot = telebot.TeleBot(TOKEN)

# База жанрів
GENRES_MAP = {
    "movie": {"Будь-який 🎲": "any", "Бойовик 💥": 28, "Комедія 😂": 35, "Жахи 😱": 27, "Фантастика 🚀": 878, "Драма 🎭": 18},
    "tv": {"Будь-який 🎲": "any", "Детектив 🕵️‍♂️": 80, "Комедія 😂": 35, "Фентезі 🧙‍♂️": 10765, "Кримінал ⚖️": 80},
    "anime": {"Будь-який 🎲": "any", "Екшн ⚔️": 28, "Пригоди 🗺️": 12, "Комедія 😂": 35, "Фентезі 🔮": 14}
}

user_selection = {}
seen_content = {}

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
    # Примусово видаляємо старе нижнє меню за допомогою ReplyKeyboardRemove
    bot.send_message(chat_id, "Оберіть категорію:", reply_markup=markup)

# Обробник для старих кнопок нижнього меню (якщо вони ще активні у юзера)
@bot.message_handler(func=lambda message: message.text in ["Фільми 🎬", "Серіали 📺", "Аніме ⛩"])
def legacy_buttons(message):
    start(message)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    
    if call.data.startswith("type_"):
        ctype = call.data.split("_")[1]
        user_selection[chat_id] = {'type': ctype}
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(n, callback_data=f"genre_{i}") for n, i in GENRES_MAP[ctype].items()]
        markup.add(*btns)
        bot.edit_message_text("🎭 **Оберіть жанр:**", chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("genre_"):
        g_id = call.data.split("_")[1]
        user_selection[chat_id]['genre_id'] = None if g_id == "any" else g_id
        bot.send_message(chat_id, "📅 **Напишіть рік (напр. 2025):**\nАбо надішліть будь-що інше для пошуку за весь час")
        bot.answer_callback_query(call.id)

    elif call.data == "repeat":
        send_recommendation(chat_id)
        bot.answer_callback_query(call.id)
        
    elif call.data == "change":
        start(call.message)
        bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.chat.id in user_selection and 'genre_id' in user_selection[message.chat.id])
def handle_year_input(message):
    chat_id = message.chat.id
    user_selection[chat_id]['year'] = message.text if message.text.isdigit() else None
    send_recommendation(chat_id)

def send_recommendation(chat_id):
    data = user_selection.get(chat_id)
    if not data or 'type' not in data: return

    target_year = data.get('year')
    is_new = target_year and int(target_year) >= 2025
    
    # Визначаємо шлях для аніме (змішуємо movie/tv) чи стандарт
    if data['type'] == "anime":
        api_path = random.choice(["movie", "tv"])
    else:
        api_path = "tv" if data['type'] == "tv" else "movie"

    base_url = f"https://api.themoviedb.org/3/discover/{api_path}"
    
    # Спершу дізнаємося к-сть сторінок для безпечного рандому
    params = {
        'api_key': TMDB_API_KEY,
        'sort_by': 'popularity.desc',
        'vote_count.gte': 5 if is_new else 20
    }
    
    if target_year:
        params['primary_release_year' if api_path == "movie" else 'first_air_date_year'] = target_year
    
    if data['type'] == "anime":
        params['with_genres'] = f"16,{data['genre_id']}" if data.get('genre_id') and data.get('genre_id') != 'any' else "16"
        params['with_original_language'] = 'ja'
    else:
        params['without_genres'] = 16 # ВИКЛЮЧАЄМО АНІМАЦІЮ
        if data.get('genre_id') and data.get('genre_id') != 'any':
            params['with_genres'] = data['genre_id']

    try:
        # Робимо тестовий запит
        check = requests.get(base_url, params=params).json()
        total_p = min(check.get('total_pages', 1), 10)
        params['page'] = random.randint(1, total_p)
        
        # Фінальний запит
        res = requests.get(base_url, params=params).json()
        results = res.get('results', [])
        
        fresh = [m for m in results if m['id'] not in seen_content.get(chat_id, []) and m.get('poster_path')]

        if fresh:
            movie = random.choice(fresh[:10])
            seen_content.setdefault(chat_id, []).append(movie['id'])
            
            title = movie.get('title') or movie.get('name')
            poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
            
            v_res = requests.get(f"https://api.themoviedb.org/3/{api_path}/{movie['id']}/videos?api_key={TMDB_API_KEY}").json()
            trailer = f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+трейлер"
            for v in v_res.get('results', []):
                if v['site'] == 'YouTube' and v['type'] == 'Trailer':
                    trailer = f"https://www.youtube.com/watch?v={v['key']}"
                    break

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Ще один", callback_data="repeat"),
                       types.InlineKeyboardButton("🎭 Меню", callback_data="change"))

            bot.send_photo(chat_id, poster, caption=f"🌟 *{title}*\n⭐️ Рейтинг: {movie['vote_average']}\n🗓 Рік: {target_year or 'Всі'}\n\n🎥 [Трейлер]({trailer})", parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, "🔍 Варіанти закінчилися. Спробуйте змінити рік!")
    except:
        bot.send_message(chat_id, "❌ Помилка зв'язку.")

bot.infinity_polling()

