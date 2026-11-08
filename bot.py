import os
import io
import logging
import asyncio

from PIL import Image, ImageOps, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DOTS = [
    (0, 0, 1), (0, 1, 2), (0, 2, 4),
    (1, 0, 8), (1, 1, 16), (1, 2, 32),
    (0, 3, 64), (1, 3, 128)
]

def make_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Envoyer une photo", callback_data="photo")],
        [
            InlineKeyboardButton("50", callback_data="q50"),
            InlineKeyboardButton("70", callback_data="q70"),
            InlineKeyboardButton("90", callback_data="q90")
        ]
    ])

def convert_image(source, width):
    image = Image.open(source)
    image = ImageOps.exif_transpose(image).convert("L")

    height = max(1, round(image.height * width * 2 / (image.width * 4)))
    image = image.resize((width * 2, height * 4))
    pixels = image.load()

    lines = []
    cell_w, cell_h = 24, 44
    margin = 12

    output = Image.new(
        "RGB",
        (width * cell_w + margin * 2,
         height * cell_h + margin * 2),
        "white"
    )
    draw = ImageDraw.Draw(output)

    for y in range(height):
        line = ""
        for x in range(width):
            value = 0
            for dx, dy, bit in DOTS:
                if pixels[x * 2 + dx, y * 4 + dy] < 128:
                    value |= bit

            line += chr(0x2800 + value)

            for dx, dy, bit in DOTS:
                cx = margin + x * cell_w + 6 + dx * 10
                cy = margin + y * cell_h + 5 + dy * 10

                color = "black" if value & bit else "#dddddd"
                draw.ellipse((cx, cy, cx + 6, cy + 6), fill=color)

        lines.append(line)

    text = "\n".join(lines)

    png = io.BytesIO()
    output.save(png, format="PNG")
    png.seek(0)

    txt = io.BytesIO(text.encode("utf-8"))
    txt.seek(0)

    return png, txt

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["width"] = 70
    await update.message.reply_text(
        "⣿ BRAILLE CONVERTER ⣿\n\n"
        "Envoie une photo pour la transformer en Braille.\n"
        "Choisis la qualité :",
        reply_markup=make_menu()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("q"):
        context.user_data["width"] = int(query.data[1:])
        await query.edit_message_text(
            f"✅ Qualité choisie : {context.user_data['width']}\n"
            "Envoie maintenant une photo.",
            reply_markup=make_menu()
        )
    elif query.data == "photo":
        await query.edit_message_text("📸 Envoie ta photo maintenant.")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    status = await message.reply_text("⏳ Conversion en cours...")

    try:
        if message.photo:
            file = await message.photo[-1].get_file()
        else:
            file = await message.document.get_file()

        source = io.BytesIO()
        await file.download_to_memory(source)
        source.seek(0)

        width = context.user_data.get("width", 70)
        png, txt = await asyncio.to_thread(convert_image, source, width)

        await message.reply_photo(
            photo=png,
            caption="🖼️ Ton image Braille est prête !"
        )

        await message.reply_document(
            document=txt,
            filename="braille.txt",
            caption="📝 Ton texte Braille."
        )

        await status.delete()

    except Exception:
        log.exception("Erreur de conversion")
        await status.edit_text(
            "❌ Conversion impossible. Essaie avec une autre photo."
        )

async def main():
    token = os.environ.get("BOT_TOKEN")

    if not token:
        raise RuntimeError("La variable BOT_TOKEN est manquante.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.Document.IMAGE,
        photo_handler
    ))

    print("🤖 BRAILLE CONVERTER ACTIF")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
