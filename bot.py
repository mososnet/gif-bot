import os
import tempfile
import subprocess
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    ContextTypes,
    CommandHandler
)

BOT_TOKEN = "7973939667:AAFRZP8Sv_qqgO-JHyNM2Tnmsp1X8_WZ0Yk"

def convert_video_to_gif_with_mirror(input_path, output_path, size=320, start=0, duration=5, fps=15):
    # فلتر ffmpeg لتطبيق مرايا جانبية مع توسيط الفيديو الأصلي داخل 320x320
    vf_filter = (
        f"split=3[main][left][right];"
        f"[left]crop=iw/4:ih:0:0,hflip,scale={size//4}:{size}[left_mirror];"
        f"[right]crop=iw/4:ih:iw*3/4:0,hflip,scale={size//4}:{size}[right_mirror];"
        f"[main]scale={size//2}:{size}[main_scaled];"
        f"[left_mirror][main_scaled][right_mirror]hstack=3,"
        f"fps={fps},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
    )

    command = [
        "ffmpeg",
        "-ss", str(start),
        "-t", str(duration),
        "-i", input_path,
        "-vf", vf_filter,
        "-gifflags", "+transdiff",
        "-y",
        output_path
    ]

    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"ffmpeg error: {result.stderr.decode()}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبًا!\n"
        "أرسل لي فيديو، وسأحوّله لك إلى GIF بحجم 320x320 مع مرايا جانبية.\n"
        "يمكنك استخدام الأمر /convert لتحديد وقت البداية والنهاية (بالثواني).\n"
        "مثال: /convert 3 7\n"
        "إذا لم تحدد، سيأخذ أول 5 ثوانٍ."
    )

async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text(
            "الرجاء إرسال /convert مع وقت البداية ووقت النهاية (ثوانٍ).\nمثال: /convert 3 7"
        )
        return
    try:
        start_sec = float(args[0])
        end_sec = float(args[1])
        if start_sec < 0 or end_sec <= start_sec:
            raise ValueError()
    except ValueError:
        await update.message.reply_text(
            "تأكد من أن الأوقات أرقام صحيحة وأن النهاية أكبر من البداية."
        )
        return

    context.user_data['start_sec'] = start_sec
    context.user_data['end_sec'] = end_sec
    await update.message.reply_text(f"تم ضبط المقطع من {start_sec} إلى {end_sec} ثانية. أرسل الفيديو الآن.")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("أرسل فيديو فقط.")
        return

    file_id = video.file_id
    file = await context.bot.get_file(file_id)

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input.mp4")
        output_path = os.path.join(tmpdir, "output.gif")

        await file.download_to_drive(input_path)

        start_sec = context.user_data.get('start_sec', 0)
        end_sec = context.user_data.get('end_sec', start_sec + 5)
        duration_sec = max(end_sec - start_sec, 1)

        try:
            convert_video_to_gif_with_mirror(
                input_path,
                output_path,
                size=320,
                start=start_sec,
                duration=duration_sec,
                fps=15
            )
            size_mb = os.path.getsize(output_path) / (1024*1024)
            if size_mb > 2.45:
                await update.message.reply_text(
                    f"⚠️ حجم الـ GIF الناتج {size_mb:.2f} ميجابايت، وهذا قد يكون كبيراً للتحميل."
                )
            with open(output_path, "rb") as gif_file:
                await update.message.reply_animation(gif_file, caption=f"✅ تم الإنشاء بحجم {size_mb:.2f} ميجابايت.")
        except Exception as e:
            await update.message.reply_text(f"حدث خطأ أثناء التحويل: {e}")

        context.user_data.pop('start_sec', None)
        context.user_data.pop('end_sec', None)

# Web server لعرض حالة البوت (لـ Render أو Heroku)
async def handle_root(request):
    return web.Response(text="🤖 Telegram bot is running.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, port=8080)
    await site.start()
    print("🌐 Web server running on port 8080.")

async def main():
    bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("convert", convert_command))
    bot_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    await start_web_server()
    await bot_app.initialize()
    await bot_app.start()
    print("🤖 Telegram bot running...")
    try:
        await asyncio.Event().wait()
    finally:
        await bot_app.stop()
        await bot_app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
