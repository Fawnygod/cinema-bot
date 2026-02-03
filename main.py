import telebot
import requests
from telebot import types
import random
import os

# Ключі з налаштувань Railway
TOKEN = os.getenv('BOT_TOKEN')
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

bot = telebot.TeleBot(TOKEN)

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
        btns = [types.InlineKeyboardButton(n, callback_data=f"genre_{i}") for n, i in GENRES_MAP[ctype].items()]
        markup.add(*btns)
        bot.edit_message_text("🎭 **Оберіть жанр:**", chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("genre_"):
        g_id = call.data.split("_")[1]
        user_selection[chat_id]['genre_id'] = None if g_id == "any" else g_id
        
        bot.delete_message(chat_id, call.message.message_id)
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
        'vote_count.gte': 40,
        'language': 'uk-UA' # Спочатку шукаємо українською
    }

    if data.get('genre_id'): params['with_genres'] = data['genre_id']

    if data['type'] == "anime":
        params['with_genres'] = f"16,{data['genre_id']}" if data.get('genre_id') else "16"
        params['with_original_language'] = 'ja'
        api_path = "movie"
    else:
        params['without_genres'] = 16

    try:
        # КРОК 1: Рахуємо сторінки
        check_res = requests.get(f"https://api.themoviedb.org/3/discover/{api_path}", params=params).json()
        total_pages = min(check_res.get('total_pages', 1), 20)
        
        # КРОК 2: Рандомимо та отримуємо список
        params['page'] = random.randint(1, total_pages)
        res = requests.get(f"https://api.themoviedb.org/3/discover/{api_path}", params=params).json()
        results = res.get('results', [])
        
        fresh = [m for m in results if m['id'] not in seen_content.get(chat_id, []) and m.get('poster_path')]

        if fresh:
            movie = random.choice(fresh[:10])
            seen_content.setdefault(chat_id, []).append(movie['id'])
            
            # ЛОГІКА ПЕРЕВІРКИ ОПИСУ
            title = movie.get('title') or movie.get('name')
            overview = movie.get('overview')

            # Якщо опису українською немає, робимо запит за англійським
            if not overview:
                eng_res = requests.get(f"https://api.themoviedb.org/3/{api_path}/{movie['id']}?api_key={TMDB_API_KEY}&language=en-US").json()
                overview = eng_res.get('overview') or "Опис відсутній обома мовами."

            poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}"
            
            # Трейлер
            v_res = requests.get(f"https://api.themoviedb.org/3/{api_path}/{movie['id']}/videos?api_key={TMDB_API_KEY}").json()
            trailer = f"https://www.youtube.com/results?search_query={title.replace(' ', '+')}+трейлер"
            for v in v_res.get('results', []):
                if v['site'] == 'YouTube' and v['type'] == 'Trailer':
                    trailer = f"https://www.youtube.com/watch?v={v['key']}"
                    break

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Ще один", callback_data="repeat"),
                       types.InlineKeyboardButton("🎭 Меню", callback_data="change"))

            caption = f"🌟 *{title}*\n⭐️ Рейтинг: {movie['vote_average']}\n\n📖 {overview[:500]}...\n\n🎥 [Трейлер на YouTube]({trailer})"
            bot.send_photo(chat_id, poster, caption=caption, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(chat_id, "🔍 Спробуйте інший жанр або натисніть /start")
    except:
        bot.send_message(chat_id, "❌ Помилка зв'язку з базою.")

bot.infinity_polling()
