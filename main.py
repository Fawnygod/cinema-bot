import telebot
import requests
from telebot import types
import random
import os

TOKEN = os.getenv('BOT_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

bot = telebot.TeleBot(TOKEN)

# Словник жанрів для кнопок
GENRES_MAP = {
    "movie": {"Будь-який 🎲": "any", "Бойовик 💥": 28, "Комедія 😂": 35, "Жахи 😱": 27, "Фантастика 🚀": 878},
    "tv": {"Будь-який 🎲": "any", "Детектив 🕵️‍♂️": 80, "Комедія 😂": 35, "Фентезі 🧙‍♂️": 10765},
    "anime": {"Будь-який 🎲": "any", "Екшн ⚔️": 28, "Пригоди 🗺️": 12, "Фентезі 🔮": 14}
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
    bot.send_message(chat_id, "🎬 **Оберіть категорію:**", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    
    if call.data.startswith("type_"):
        ctype = call.data.split("_")[1]
        user_selection[chat_id] = {'type': ctype}
        markup = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(n, callback_data=f"genre_{i}") for n, i in GENRES_MAP[ctype].items()]
        markup.add(*btns)
        bot.edit_message_text("🎭 **Тепер оберіть жанр:**", chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("genre_"):
        g_id = call.data.split("_")[1]
        user_selection[chat_id]['genre_id'] = None if g_id == "any" else g_id
        bot.send_message(chat_id, "📅 **Введіть рік (напр. 2026):**\nАбо надішліть будь-що для пошуку за весь час")
        bot.answer_callback_query(call.id)

    elif call.data == "repeat":
        send_recommendation(chat_id)
        bot.answer_callback_query(call.id)
    elif call.data == "change":
        start(call.message)
        bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.chat.id in user_selection and 'genre_id' in user_selection[message.chat.id])
def handle_year(message):
    user_selection[message.chat.id]['year'] = message.text if message.text.isdigit() else None
    send_recommendation(message.chat.id)

def send_recommendation(chat_id):
    data = user_selection.get(chat_id)
    if not data: return

    target_year = data.get('year')
    is_new = target_year and int(target_year) >= 2025
    
    # Визначаємо шлях: якщо аніме - шукаємо і в movie, і в tv по черзі
    # Для простоти коду виберемо рандомно тип контенту для кожного запиту аніме
    if data['type'] == "anime":
        api_path = random.choice(["movie", "tv"])
    else:
        api_path = "tv" if data['type'] == "tv" else "movie"

    base_url = f"https://api.themoviedb.org/3/discover/{api_path}"
    
    params = {
        'api_key': TMDB_API_KEY,
        'sort_by': 'popularity.desc',
        'vote_count.gte': 0 if is_new else 20, # Для новинок 0+ голосів
        'page': random.randint(1, 5) if not is_new else 1
    }

    if target_year:
        params['primary_release_year' if api_path == "movie" else 'first_air_date_year'] = target_year

    # Налаштування категорій
    if data['type'] == "anime":
        params['with_genres'] = f"16,{data['genre_id']}" if data.get('genre_id') else "16"
        params['with_original_language'] = 'ja'
    else:
        params['without_genres'] = 16
        if data.get('genre_id'): params['with_genres'] = data['genre_id']

    try:
        res = requests.get(base_url, params=params).json()
        results = res.get('results', [])
        
        # Якщо результатів мало, пробуємо інший тип (якщо було movie - беремо tv)
        if len(results) < 5 and data['type'] == "anime":
            api_path = "tv" if api_path == "movie" else "movie"
            # повторний запит...
            
        fresh = [m for m in results if m['id'] not in seen_content.get(chat_id, []) and m.get('poster_path')]

        if fresh:
            movie = random.choice(fresh[:10])
            seen_content.setdefault(chat_id, []).append(movie['id'])
            
            title = movie.get('title') or movie.get('name')
            poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
            
            # Трейлер
            v_res = requests.get(f"https://api.themoviedb.org/3/{api_path}/{movie['id']}/videos?api_key={TMDB_API_KEY}").json()
            trailer = f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+anime+trailer"
            for v in v_res.get('results', []):
                if v['site'] == 'YouTube' and v['type'] == 'Trailer':
                    trailer = f"https://www.youtube.com/watch?v={v['key']}"
                    break

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Ще один", callback_data="repeat"),
                       types.InlineKeyboardButton("🎭 Меню", callback_data="change"))

            bot.send_photo(chat_id, poster, caption=f"🌟 *{title}*\n⭐️ Рейтинг: {movie['vote_average']}\n🗓 Рік: {target_year or 'Всі'}\n\n🎥 [Трейлер]({trailer})", parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, "🔍 Більше нічого не знайдено за цими параметрами.")
    except Exception as e:
        bot.send_message(chat_id, "❌ Сталася помилка при пошуку.")

print("Бот запущений з фільтром проти аніме у фільмах!")
bot.infinity_polling()