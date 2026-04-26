from telegram.constants import ParseMode
from telegram import Update, BotCommand
from telegram.ext import ContextTypes
async def command_suggestions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = [
        '/start - Plan a new JB trip',
        '/help - Show help menu',
        '/cancel - Cancel current planning',
    ]
    await update.message.reply_text(
        "Available commands:\n" + '\n'.join(commands),
        parse_mode=ParseMode.MARKDOWN
    )
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *JB Trip Planner Bot Help*\n\n"
        "*Commands:*\n"
        "/start — Plan a new JB trip\n"
        "/cancel — Cancel current planning\n"
        "/help — Show this message\n\n"
        "*What I'll ask you:*\n"
        "• Trip duration (1–5 days)\n"
        "• Start time (8am–12pm)\n"
        "• Travel vibe (Adventure, Foodie, Culture, etc.)\n"
        "• Who you're travelling with\n"
        "• Your travel pace (slow / balanced / packed)\n"
        "• Any must-visit places (optional — or let AI surprise you!)\n"
        "• Cuisine preferences\n\n"
        "*Each itinerary includes:*\n"
        "📍 Location + Google Maps hint for every stop\n"
        "🥐 Breakfast + 🍽️ Lunch + 🌙 Dinner — different cuisines per day\n"
        "💰 Cost estimates in MYR & SGD\n"
        "💸 Full trip budget summary\n"
        "🌟 Local JB pro tips\n\n"
        "*After generation, you can:*\n"
        "• 😕 Swap any activity or meal\n"
        "• 🔄 Regenerate the whole itinerary\n"
        "• ✅ Finalise & save a clean copy\n"
        "• 📤 Share with your travel group"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
import os
from dotenv import load_dotenv
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
import google.generativeai as genai


# Load environment variables from .env file
load_dotenv()

GOOGLE_GEMINI_API_KEY = os.environ.get("GOOGLE_GEMINI_API_KEY", "YOUR_GOOGLE_GEMINI_API_KEY")
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
GOOGLE_GEMINI_API_KEY = os.environ.get("GOOGLE_GEMINI_API_KEY", "YOUR_GOOGLE_GEMINI_API_KEY")


# Conversation states
(
    ASK_DAYS, ASK_START_TIME, ASK_VIBE, ASK_GROUP,
    ASK_PACE, ASK_MUSTHAVE, ASK_FOOD_PREF, SHOW_ITINERARY, HANDLE_REJECTION
) = range(9)

VIBES = {
    "🏃 Adventure": "adventure",
    "🛍️ Shopaholic": "shopping",
    "🍜 Foodie": "foodie",
    "🏛️ Culture & History": "culture",
    "🌿 Nature & Chill": "nature",
    "🎉 Party & Nightlife": "nightlife",
}

PACE = {
    "🐢 Slow & Easy": "slow",
    "⚖️ Balanced": "balanced",
    "⚡ Pack it in!": "packed",
}

# Updated: Japanese & Korean added, Indian & Vegetarian removed
FOOD_PREFS = {
    "🍜 Local Malay": "malay",
    "🥢 Chinese Hawker": "chinese_hawker",
    "🍣 Japanese": "japanese",
    "🥩 Korean BBQ": "korean",
    "🍔 Western & Cafés": "western",
    "🦞 Seafood": "seafood",
}

GROUP_TYPES = {
    "👤 Solo": "solo",
    "💑 Couple": "couple",
    "👨‍👩‍👧‍👦 Family with Kids": "family",
    "👯 Friends Group": "friends",
}


def build_keyboard(options: dict, selected: set, cols=2, done_label="✅ Done!", show_done=True):
    buttons = []
    items = list(options.items())
    for i in range(0, len(items), cols):
        row = []
        for label, key in items[i:i+cols]:
            tick = "✅ " if key in selected else ""
            row.append(InlineKeyboardButton(f"{tick}{label}", callback_data=f"toggle_{key}"))
        buttons.append(row)
    if show_done:
        buttons.append([InlineKeyboardButton(done_label, callback_data="confirm")])
    return InlineKeyboardMarkup(buttons)


def build_single_keyboard(options: dict, prefix="pick"):
    buttons = []
    for label, key in options.items():
        buttons.append([InlineKeyboardButton(label, callback_data=f"{prefix}_{key}")])
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "🇲🇾 *Welcome to Sihui JB Trip Planner Bot!* 🇲🇾\n\n"
        "I'm your personal AI travel guide to *Johor Bahru, Malaysia!* \n\n"
        "I'll craft a personalised itinerary with *activities, 3 meals a day, "
        "Google Maps locations & cost estimates in MYR and SGD* — "
        "and you can swap anything you don't fancy! Let's go! \n\n"
        "Firstly! how many days is your JB trip? (e.g. type `1`, `2`, or `3`)",
        parse_mode="Markdown"
    )
    return ASK_DAYS


async def ask_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        if days < 1 or days > 5:
            raise ValueError
        context.user_data["days"] = days
        await update.message.reply_text(
            f" *{days} day(s)* — brilliant!\n\n"
            " What time do you plan to *start your day* in JB?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Early Bird (8am)", callback_data="time_08:00"),
                    InlineKeyboardButton("Morning (9am)", callback_data="time_09:00"),
                ],
                [
                    InlineKeyboardButton("Mid-Morning (10am)", callback_data="time_10:00"),
                    InlineKeyboardButton("Late Morning (11am)", callback_data="time_11:00"),
                ],
                [
                    InlineKeyboardButton("Noon (12pm)", callback_data="time_12:00"),
                ],
            ])
        )
        return ASK_START_TIME
    except ValueError:
        await update.message.reply_text("Please enter a number between 1 and 5 🙏")
        return ASK_DAYS


async def ask_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_val = query.data.replace("time_", "")
    context.user_data["start_time"] = time_val
    context.user_data["selected_vibes"] = set()

    await query.edit_message_text(
        f"⏰ Starting at *{time_val}* — let's lock in your vibe!\n\n"
        "🎭 *What's the mood for this trip?*\n_(Pick one or more)_",
        parse_mode="Markdown",
        reply_markup=build_keyboard(VIBES, set())
    )
    return ASK_VIBE


async def handle_vibe_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm":
        if not context.user_data.get("selected_vibes"):
            await query.answer("Pick at least one vibe! 😄", show_alert=True)
            return ASK_VIBE
        await query.edit_message_text(
            "👥 *Who are you travelling with?*",
            parse_mode="Markdown",
            reply_markup=build_single_keyboard(GROUP_TYPES, prefix="group")
        )
        return ASK_GROUP

    key = query.data.replace("toggle_", "")
    selected = context.user_data.setdefault("selected_vibes", set())
    selected.discard(key) if key in selected else selected.add(key)
    await query.edit_message_reply_markup(reply_markup=build_keyboard(VIBES, selected))
    return ASK_VIBE


async def ask_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    group = query.data.replace("group_", "")
    context.user_data["group"] = group

    await query.edit_message_text(
        "🏃 *What's your travel pace?*\n\n"
        "This helps me decide how many stops to fit in each day.",
        parse_mode="Markdown",
        reply_markup=build_single_keyboard(PACE, prefix="pace")
    )
    return ASK_PACE


async def ask_pace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pace = query.data.replace("pace_", "")
    context.user_data["pace"] = pace

    pace_labels = {"slow": "Slow & Easy 🐢", "balanced": "Balanced ⚖️", "packed": "Pack it in! ⚡"}
    label = pace_labels.get(pace, pace)

    await query.edit_message_text(
        f"Got it — *{label}* it is!\n\n"
        "📌 *Any must-visit places or things in JB?*\n\n"
        "Type anything specific — a place, food, experience, or area "
        "you definitely want included. Or tap *Skip* and I'll surprise you! 😄",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Surprise me! Skip →", callback_data="musthave_skip")]
        ])
    )
    return ASK_MUSTHAVE


async def handle_musthave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text must-have input."""
    text = update.message.text.strip()
    context.user_data["must_have"] = text
    context.user_data["selected_food"] = set()

    await update.message.reply_text(
        f"📌 Noted: *{text}*\n\n"
        "🍽️ *What cuisines do you enjoy?*\n\n"
        "_(Pick all that apply — I'll spread different cuisines across your "
        "breakfast, lunch & dinner each day!)_",
        parse_mode="Markdown",
        reply_markup=build_keyboard(FOOD_PREFS, set())
    )
    return ASK_FOOD_PREF


async def handle_musthave_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle skip button on must-have step."""
    query = update.callback_query
    await query.answer()
    context.user_data["must_have"] = None
    context.user_data["selected_food"] = set()

    await query.edit_message_text(
        "🍽️ *What cuisines do you enjoy?*\n\n"
        "_(Pick all that apply — I'll spread different cuisines across your "
        "breakfast, lunch & dinner each day!)_",
        parse_mode="Markdown",
        reply_markup=build_keyboard(FOOD_PREFS, set())
    )
    return ASK_FOOD_PREF


async def handle_food_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm":
        await query.edit_message_text(
            "🤖 *Generating your personalised JB itinerary...*\n\n"
            "📍 Adding locations, costs in MYR & SGD, 3 meals per day...\n"
            "✨ Hang tight — good things take a moment!",
            parse_mode="Markdown"
        )
        await generate_and_send_itinerary(query, context)
        return SHOW_ITINERARY

    key = query.data.replace("toggle_", "")
    selected = context.user_data.setdefault("selected_food", set())
    selected.discard(key) if key in selected else selected.add(key)
    await query.edit_message_reply_markup(reply_markup=build_keyboard(FOOD_PREFS, selected))
    return ASK_FOOD_PREF


def build_preferences_summary(context: ContextTypes.DEFAULT_TYPE) -> str:
    ud = context.user_data
    days = ud.get("days", 1)
    start_time = ud.get("start_time", "10:00")
    group = ud.get("group", "friends")
    pace = ud.get("pace", "balanced")
    vibes = list(ud.get("selected_vibes", set()))
    food = list(ud.get("selected_food", set()))
    must_have = ud.get("must_have")

    pace_labels = {"slow": "Slow & Easy (2–3 stops/day)", "balanced": "Balanced (3–4 stops/day)", "packed": "Packed (5+ stops/day)"}
    vibe_labels = [k for k, v in VIBES.items() if v in vibes]
    food_labels = [k for k, v in FOOD_PREFS.items() if v in food]
    group_label = next((k for k, v in GROUP_TYPES.items() if v == group), group)

    summary = (
        f"Trip Duration: {days} day(s), starting at {start_time}\n"
        f"Group: {group_label}\n"
        f"Pace: {pace_labels.get(pace, pace)}\n"
        f"Vibes: {', '.join(vibe_labels) if vibe_labels else 'Open to anything'}\n"
        f"Food Preferences: {', '.join(food_labels) if food_labels else 'Open to anything'}"
    )
    if must_have:
        summary += f"\nMust-include: {must_have}"
    return summary


def get_chat_id(query_or_update):
    """Robustly extract chat_id from either a CallbackQuery or Update."""
    if hasattr(query_or_update, 'message') and query_or_update.message:
        return query_or_update.message.chat_id
    if hasattr(query_or_update, 'from_user') and query_or_update.from_user:
        return query_or_update.from_user.id
    if hasattr(query_or_update, 'effective_chat') and query_or_update.effective_chat:
        return query_or_update.effective_chat.id
    raise ValueError("Cannot determine chat_id")


def split_itinerary(text: str) -> list:
    """Split itinerary into Telegram-safe chunks (max 3800 chars each)."""
    MAX_LEN = 3800
    if len(text) <= MAX_LEN:
        return [text]

    chunks = []
    parts = re.split(r'(?=🗓️ DAY \d)', text)
    for part in parts:
        if not part.strip():
            continue
        if len(part) <= MAX_LEN:
            chunks.append(part)
        else:
            lines = part.split('\n')
            current = ""
            for line in lines:
                if len(current) + len(line) + 1 > MAX_LEN:
                    if current:
                        chunks.append(current)
                    current = line + '\n'
                else:
                    current += line + '\n'
            if current.strip():
                chunks.append(current)
    return chunks if chunks else [text[:MAX_LEN], text[MAX_LEN:]]


def format_saved_itinerary(itinerary: str, prefs_summary: str) -> str:
    """Clean up itinerary for saving / sharing (strips Markdown symbols)."""
    header = (
        "🇲🇾 MY JB TRIP ITINERARY\n"
        "========================\n"
        f"{prefs_summary}\n"
        "========================\n\n"
    )
    footer = (
        "\n========================\n"
        "📱 Planned with JB Trip Planner Bot\n"
        "Type /start to plan your own trip!"
    )
    clean = re.sub(r'\*([^*]+)\*', r'\1', itinerary)
    clean = re.sub(r'_([^_]+)_', r'\1', clean)
    return header + clean + footer


async def generate_and_send_itinerary(
    query_or_update, context: ContextTypes.DEFAULT_TYPE, rejected_activity=None
):
    ud = context.user_data
    days = ud.get("days", 1)
    start_time = ud.get("start_time", "10:00")
    pace = ud.get("pace", "balanced")
    prefs = build_preferences_summary(context)
    must_have = ud.get("must_have")

    pace_instructions = {
        "slow":     "2–3 activities per day max. Generous time at each spot. No rushing. Relaxed, meandering exploration.",
        "balanced": "3–4 activities per day. Good mix of exploration and downtime. Realistic travel buffers.",
        "packed":   "5–6 activities per day. Back-to-back, efficient routing. Every hour is used. Early starts, late evenings.",
    }
    pace_note = pace_instructions.get(pace, pace_instructions["balanced"])

    must_have_note = (
        f"\nMUST-INCLUDE: The user specifically requested '{must_have}'. "
        "Make sure this appears at an appropriate day and time. Build surrounding stops around it logically."
    ) if must_have else ""

    rejection_note = ""
    if rejected_activity:
        rejection_note = (
            f"\nIMPORTANT: The user rejected '{rejected_activity}'. "
            "Replace ONLY that specific entry with a genuinely different alternative. "
            "Keep all other activities and meals exactly the same."
        )

    existing_itinerary = ""
    if ud.get("itinerary_text") and rejected_activity:
        existing_itinerary = f"\nExisting itinerary to modify:\n{ud['itinerary_text']}"

    food_labels = [k for k, v in FOOD_PREFS.items() if v in ud.get("selected_food", set())]
    food_instruction = (
        f"The user enjoys: {', '.join(food_labels)}. "
        "Vary the 3 meals each day so breakfast, lunch and dinner each feature "
        "a DIFFERENT cuisine from their preferences. Never repeat the same cuisine twice in one day. "
        "If they picked only one cuisine, use it for one meal and complement the rest with fitting local options."
    ) if food_labels else (
        "Spread a variety of local JB cuisines across meals each day — "
        "mix hawker, Malay, Chinese, and any interesting local options. Keep it varied and exciting."
    )

    prompt = f"""You are a deeply knowledgeable local JB (Johor Bahru) expert and travel curator.
Your job: craft the BEST possible personalised itinerary for this traveller using your FULL knowledge of JB.
Think beyond generic tourist stops — mix iconic must-dos with hidden gems, local favourites, and underrated spots.
You have COMPLETE FREEDOM to choose any real, currently operating venue in Johor Bahru, Malaysia.

User Preferences:
{prefs}
{must_have_note}
{rejection_note}
{existing_itinerary}

PACE RULE: {pace_note}
MEAL RULE: {food_instruction}

CURATION PRINCIPLES:
- Consider the group type deeply: family with kids needs different spots than a couple or a solo traveller
- Cluster geographically — don't plan stops that require zig-zagging across the city
- Balance well-known spots with at least 1–2 local gems per day
- For shopaholic vibes: include night markets, specialty shops, not just malls
- For foodie vibes: include a supper spot or late-night hawker if timing allows
- For culture vibes: include context, history, and meaningful details
- For nature vibes: consider Gunung Pulai, Desaru, Tanjung Piai, Kota Tinggi waterfalls etc.

Generate a complete {days}-day itinerary. Use EXACTLY this format:

---
🗓️ DAY 1 — [Creative, punchy day title that captures the theme]

⏰ [TIME] | 🥐 BREAKFAST — [Place Name]
📌 [Full street address, e.g. "No. 12, Jalan Dhoby, Johor Bahru City Centre"]
[What to order]
💰 Est. Cost: RM [X]–[Y] per pax (~SGD [A]–[B])

⏰ [TIME] | 📍 [ACTIVITY — Place Name]
📌 [Full address or district]
[2–3 sentences: what to do/see, one insider tip]
💰 Est. Cost: RM [X]–[Y] per pax (~SGD [A]–[B])   ← write "Free entry" if applicable

⏰ [TIME] | 🍽️ LUNCH — [Place Name]
📌 [Address]
[Must-order dishes, atmosphere]
💰 Est. Cost: RM [X]–[Y] per pax (~SGD [A]–[B])

⏰ [TIME] | 📍 [ACTIVITY — Place Name]
📌 [Address]
[Description, why it's great for this group/vibe]
💰 Est. Cost: RM [X]–[Y] per pax (~SGD [A]–[B])

⏰ [TIME] | 🌙 DINNER — [Place Name]
📌 [Address]
[Must-order dishes, atmosphere]
💰 Est. Cost: RM [X]–[Y] per pax (~SGD [A]–[B])

💸 DAY 1 TOTAL (est. per pax): RM [X]–[Y] (~SGD [A]–[B])

---
[Repeat for each day, each with a different theme and different set of places]

After all days:

💰 *FULL TRIP BUDGET (per person):*
• Activities & Attractions: RM [X]–[Y] (~SGD [A]–[B])
• All Meals ({days} days × 3): RM [X]–[Y] (~SGD [A]–[B])
• Transport (Grab within JB): RM [X]–[Y] (~SGD [A]–[B])
• 🏆 GRAND TOTAL: RM [X]–[Y] (~SGD [A]–[B])

🌟 *JB PRO TIPS:*
1. [Checkpoint timing — best hours to cross, which checkpoint]
2. [Getting around — Grab, parking tips, walking areas]

NON-NEGOTIABLE RULES:
- All places must be REAL, currently operating venues in Johor Bahru, Malaysia
- Start each day at {start_time}, end by 9:30–10pm
- Build in 20–40 min travel time between stops (JB traffic is real, lah)
- SGD/MYR rate = 3.45 for all conversions
- Free entry venues: say so clearly, don't invent fees
- Never repeat the same cuisine twice in one day
- Each day must feel distinct from the others in theme and locations
- Write like a warm, funny local friend — sprinkle in "lah", "shiok", "sedap", "weh" sparingly"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt, generation_config={
            "max_output_tokens": 5000,
        })
        itinerary = response.text
        context.user_data["itinerary_text"] = itinerary

        chat_id = get_chat_id(query_or_update)
        bot = context.application.bot

        await bot.send_message(
            chat_id=chat_id,
            text=(
                "🎉 *Your Personalised JB Itinerary is Ready!*\n\n"
                "📍 Every stop has a location & Google Maps hint\n"
                "💰 Costs shown in both MYR & SGD\n"
                "🍽️ 3 varied meals planned per day\n\n"
                "Not feeling something? Swap it below! 👇"
            ),
            parse_mode="Markdown"
        )

        chunks = split_itinerary(itinerary)
        for chunk in chunks:
            if chunk.strip():
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=chunk.strip(),
                        parse_mode="Markdown"
                    )
                except Exception:
                    try:
                        await bot.send_message(chat_id=chat_id, text=chunk.strip())
                    except Exception as e:
                        logger.error(f"Failed to send chunk: {e}")

        action_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("😕 Swap an Activity / Meal", callback_data="reject_activity")],
            [InlineKeyboardButton("🔄 Regenerate Full Itinerary", callback_data="regenerate_full")],
            [InlineKeyboardButton("✅ Finalise & Save My Trip", callback_data="save_itinerary")],
            [InlineKeyboardButton("📤 Share with Travel Kakis", callback_data="share_itinerary")],
            [InlineKeyboardButton("🏠 Start Over", callback_data="start_over")],
        ])

        await bot.send_message(
            chat_id=chat_id,
            text="*What would you like to do?* 👆",
            parse_mode="Markdown",
            reply_markup=action_keyboard
        )

    except Exception as e:
        logger.error(f"Error generating itinerary: {e}")
        try:
            chat_id = get_chat_id(query_or_update)
            await context.application.bot.send_message(
                chat_id=chat_id,
                text="Oops! Something went wrong generating your itinerary. Please try /start again!"
            )
        except Exception as inner_e:
            logger.error(f"Failed to send error message: {inner_e}")


async def handle_itinerary_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "reject_activity":
        await query.edit_message_text(
            "😤 *What do you want to swap out?*\n\n"
            "Just type the name of the *activity or meal* you'd like to replace.\n\n"
            "Examples:\n"
            "• `Legoland`\n"
            "• `Breakfast at Restoran XYZ`\n"
            "• `Lunch spot`\n"
            "• `Danga Bay`",
            parse_mode="Markdown"
        )
        return HANDLE_REJECTION

    elif query.data == "regenerate_full":
        await query.edit_message_text(
            "🔄 *Generating a completely fresh itinerary...*\n\n"
            "Same preferences, brand new adventure! ✨",
            parse_mode="Markdown"
        )
        context.user_data["itinerary_text"] = None
        await generate_and_send_itinerary(query, context)
        return SHOW_ITINERARY

    elif query.data == "save_itinerary":
        prefs_summary = build_preferences_summary(context)
        itinerary = context.user_data.get("itinerary_text", "")
        saved_text = format_saved_itinerary(itinerary, prefs_summary)

        await query.edit_message_text(
            "✅ *Finalising your trip plan...*\n\nSending a clean copy! 📋",
            parse_mode="Markdown"
        )

        bot = context.application.bot
        chat_id = query.from_user.id

        chunks = split_itinerary(saved_text)
        for chunk in chunks:
            if chunk.strip():
                try:
                    await bot.send_message(chat_id=chat_id, text=chunk.strip())
                except Exception as e:
                    logger.error(f"Save send error: {e}")

        await bot.send_message(
            chat_id=chat_id,
            text=(
                "📌 *Trip saved! Here's your pre-departure checklist:*\n\n"
                "✅ Screenshot or forward these messages to your travel group\n"
                "✅ Save Google Maps links for each location offline\n"
                "✅ Download *Grab* 🚗 — cheapest way to get around JB\n"
                "✅ Exchange SGD → MYR at Johor money changers (beats banks!)\n"
                "✅ Cross early — aim for *before 8am* or *after 10am* to avoid queues\n"
                "✅ Bring some cash for hawker stalls\n\n"
                "🎉 *Selamat berjalan! Have an amazing trip!* 🇲🇾\n\n"
                "_Type /start anytime to plan another JB adventure!_"
            ),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    elif query.data == "share_itinerary":
        await query.edit_message_text(
            "📤 *Share your itinerary!*\n\n"
            "Here's how:\n\n"
            "1️⃣ *Forward* the itinerary messages above to your travel group chat\n"
            "2️⃣ *Long-press* any message → tap *Forward*\n"
            "3️⃣ Or use *Finalise & Save* to get a clean copyable version\n\n"
            "Your kakis are gonna love this trip lah! 🎉",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Finalise & Save My Trip", callback_data="save_itinerary")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_options")],
            ])
        )
        return SHOW_ITINERARY

    elif query.data == "back_to_options":
        await query.edit_message_text(
            "*What would you like to do?* 👆",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("😕 Swap an Activity / Meal", callback_data="reject_activity")],
                [InlineKeyboardButton("🔄 Regenerate Full Itinerary", callback_data="regenerate_full")],
                [InlineKeyboardButton("✅ Finalise & Save My Trip", callback_data="save_itinerary")],
                [InlineKeyboardButton("📤 Share with Travel Kakis", callback_data="share_itinerary")],
                [InlineKeyboardButton("🏠 Start Over", callback_data="start_over")],
            ])
        )
        return SHOW_ITINERARY

    elif query.data == "start_over":
        context.user_data.clear()
        await query.edit_message_text(
            "🔄 *Starting fresh!*\n\nType /start to plan a new JB trip! 🇲🇾",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    return SHOW_ITINERARY


async def handle_rejection_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rejected = update.message.text.strip()
    await update.message.reply_text(
        f"Swapping out *{rejected}* for something you'll love more...\n\n"
        "Updating itinerary with location & cost info...",
        parse_mode="Markdown"
    )
    await generate_and_send_itinerary(update, context, rejected_activity=rejected)
    return SHOW_ITINERARY


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Trip planning cancelled! Type /start anytime to plan your JB adventure 🇲🇾"
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *JB Trip Planner Bot Help*\n\n"
        "*Commands:*\n"
        "/start — Plan a new JB trip\n"
        "/cancel — Cancel current planning\n"
        "/help — Show this message\n\n"
        "*What I'll ask you:*\n"
        "• Trip duration (1–5 days)\n"
        "• Start time (8am–12pm)\n"
        "• Travel vibe (Adventure, Foodie, Culture, etc.)\n"
        "• Who you're travelling with\n"
        "• Your travel pace (slow / balanced / packed)\n"
        "• Any must-visit places (optional — or let AI surprise you!)\n"
        "• Cuisine preferences\n\n"
        "*Each itinerary includes:*\n"
        "📍 Location + Google Maps hint for every stop\n"
        "🥐 Breakfast + 🍽️ Lunch + 🌙 Dinner — different cuisines per day\n"
        "💰 Cost estimates in MYR & SGD\n"
        "💸 Full trip budget summary\n"
        "🌟 Local JB pro tips\n\n"
        "*After generation, you can:*\n"
        "• 😕 Swap any activity or meal\n"
        "• 🔄 Regenerate the whole itinerary\n"
        "• ✅ Finalise & save a clean copy\n"
        "• 📤 Share with your travel group",
        parse_mode="Markdown"
    )


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_days)],
            ASK_START_TIME: [CallbackQueryHandler(ask_start_time, pattern="^time_")],
            ASK_VIBE: [CallbackQueryHandler(handle_vibe_toggle)],
            ASK_GROUP: [CallbackQueryHandler(ask_group, pattern="^group_")],
            ASK_PACE: [CallbackQueryHandler(ask_pace, pattern="^pace_")],
            ASK_MUSTHAVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_musthave),
                CallbackQueryHandler(handle_musthave_skip, pattern="^musthave_skip$"),
            ],
            ASK_FOOD_PREF: [CallbackQueryHandler(handle_food_toggle)],
            SHOW_ITINERARY: [CallbackQueryHandler(handle_itinerary_actions)],
            HANDLE_REJECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rejection_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    # Suggest commands when user types '/'
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^/$"), command_suggestions))

    logger.info("JB Trip Planner Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
