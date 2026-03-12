import os
import datetime
import random
import re

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# =========================
# TOKEN ИЗ ENV
# =========================
TOKEN = "1474765365:AAFzMnm3lukjhVRye4RgPF0rjdHwd433iuM"

if not TOKEN:
    raise RuntimeError("TOKEN не найден в переменных окружения")

# =========================
# ТРАНСЛИТ ДЛЯ MRZ РФ
# =========================
translit = {
    "А":"A","Б":"B","В":"V","Г":"G","Д":"D","Е":"E","Ё":"E",
    "Ж":"ZH","З":"Z","И":"I","Й":"I","К":"K","Л":"L","М":"M",
    "Н":"N","О":"O","П":"P","Р":"R","С":"S","Т":"T","У":"U",
    "Ф":"F","Х":"KH","Ц":"TS","Ч":"CH","Ш":"SH","Щ":"SHCH",
    "Ы":"Y","Э":"E","Ю":"YU","Я":"YA","Ь":"9","Ъ":"X","-":"<"
}

def transliterate(text):
    return "".join(
        translit.get(c, "<" if c == " " else c)
        for c in text.upper()
    )

# =========================
# MRZ КОНТРОЛЬНАЯ ЦИФРА
# =========================
weights = [7, 3, 1]

def char_value(c):
    if c.isdigit():
        return int(c)
    if c == "<":
        return 0
    return ord(c) - 55

def check_digit(data):
    return str(sum(
        char_value(c) * weights[i % 3]
        for i, c in enumerate(data)
    ) % 10)

# =========================
# MRZ РФ
# =========================
def generate_mrz_rf(last, first, middle, series, number, birth, sex, issue, code):
    last, first, middle = map(transliterate, (last, first, middle))

    name = f"{last}<<{first}<{middle}"
    line1 = ("PNRUS" + name).ljust(44, "<")

    series = re.sub(r"\D", "", series)
    number = re.sub(r"\D", "", number)

    passport = series[:3] + number
    cd1 = check_digit(passport)

    birth_dt = datetime.datetime.strptime(birth, "%d.%m.%Y")
    birth_str = birth_dt.strftime("%y%m%d")
    cd2 = check_digit(birth_str)

    sex = "M" if sex == "Мужской" else "F"

    issue_dt = datetime.datetime.strptime(issue, "%d.%m.%Y")
    issue_str = issue_dt.strftime("%y%m%d")

    last_series = series[-1]
    code = code.replace("-", "")

    additional = (last_series + issue_str + code)[:13] + "<"
    cd3 = check_digit(additional)

    filler = "<<<<<<"

    line2_base = (
        passport + cd1 +
        "RUS" +
        birth_str + cd2 +
        sex +
        filler + "<" +
        additional + cd3
    )

    final_cd = check_digit(
        passport + cd1 +
        birth_str + cd2 +
        filler + "<" +
        additional + cd3
    )

    return line1, line2_base + final_cd

# =========================
# РНОКПП УКРАИНА
# =========================
def days_from_1899(date):
    return (date - datetime.date(1899, 12, 31)).days

def control_rnokpp(code):
    weights = [-1, 5, 7, 9, 4, 6, 10, 5, 7]
    return (sum(int(code[i]) * weights[i] for i in range(9)) % 11) % 10

def generate_rnokpp(birth, sex):
    birth = datetime.datetime.strptime(birth, "%d.%m.%Y").date()
    days = str(days_from_1899(birth)).zfill(5)

    serial = random.randrange(1, 10000, 2) if sex == "Мужской" else random.randrange(0, 10000, 2)
    serial = str(serial).zfill(4)

    first9 = days + serial
    return first9 + str(control_rnokpp(first9))

# =========================
# МЕНЮ
# =========================
main_menu = [["🇷🇺 MRZ паспорт РФ"], ["🇺🇦 РНОКПП Украина"]]

# =========================
# HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Генератор документов\n\nВыберите тип:",
        reply_markup=ReplyKeyboardMarkup(main_menu, resize_keyboard=True)
    )

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    mode = context.user_data.get("mode")

    if text == "🇺🇦 РНОКПП Украина":
        context.user_data.clear()
        context.user_data["mode"] = "rnokpp"
        await update.message.reply_text("Введите дату рождения\nDD.MM.YYYY")
        return

    if text == "🇷🇺 MRZ паспорт РФ":
        context.user_data.clear()
        context.user_data["mode"] = "mrz"
        await update.message.reply_text(
            "Введите данные (8 строк):\n\n"
            "Фамилия\nИмя\nОтчество\n"
            "Серия\nНомер\n"
            "Дата рождения DD.MM.YYYY\n"
            "Дата выдачи DD.MM.YYYY\n"
            "Код подразделения"
        )
        return

    # RNOKPP
    if mode == "rnokpp":
        if "birth" not in context.user_data:
            context.user_data["birth"] = text
            await update.message.reply_text(
                "Выберите пол:",
                reply_markup=ReplyKeyboardMarkup(
                    [["Мужской", "Женский"]],
                    resize_keyboard=True
                )
            )
            return

        rnokpp = generate_rnokpp(context.user_data["birth"], text)
        await update.message.reply_text(f"✅ РНОКПП:\n\n{rnokpp}")
        context.user_data.clear()
        return

    # MRZ
    if mode == "mrz":
        data = text.split("\n")
        if len(data) < 8:
            await update.message.reply_text("❌ Нужно ровно 8 строк данных")
            return

        line1, line2 = generate_mrz_rf(
            data[0], data[1], data[2],
            data[3], data[4],
            data[5], "Мужской",
            data[6], data[7]
        )

        await update.message.reply_text(f"MRZ:\n\n{line1}\n{line2}")
        context.user_data.clear()

# =========================
# RUN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler))
    app.run_polling()

if __name__ == "__main__":
    main()
