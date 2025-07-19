import os
import tempfile
import subprocess
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

UPLOAD_FOLDER = 'static/gifs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

BOT_TOKEN = "7973939667:AAFRZP8Sv_qqgO-JHyNM2Tnmsp1X8_WZ0Yk"

MAX_SIZE_MB = 2.45

def convert_video_to_gif_ffmpeg(input_path, output_path, width=320, height=320, start=0, duration=5, fps=10, colors=256):
    # نستخدم فلتر hflip للمرآة
    # ونضيف فلتر palettegen و paletteuse لتحسين جودة الألوان وتقليل الحجم
    # مع التحكم بعدد الألوان
    palette_path = output_path + "_palette.png"

    # 1. إنشاء باليت للألوان
    palette_cmd = [
        'ffmpeg',
        '-ss', str(start),
        '-t', str(duration),
        '-i', input_path,
        '-vf', f'hflip,scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,fps={fps},palettegen=max_colors={colors}',
        '-y',
        palette_path
    ]
    p1 = subprocess.run(palette_cmd, capture_output=True)
    if p1.returncode != 0:
        raise Exception(f"ffmpeg palettegen error: {p1.stderr.decode()}")

    # 2. إنشاء GIF باستخدام الباليت
    gif_cmd = [
        'ffmpeg',
        '-ss', str(start),
        '-t', str(duration),
        '-i', input_path,
        '-i', palette_path,
        '-lavfi', f'hflip,scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,fps={fps}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5',
        '-gifflags', '+transdiff',
        '-y',
        output_path
    ]
    p2 = subprocess.run(gif_cmd, capture_output=True)
    if p2.returncode != 0:
        raise Exception(f"ffmpeg gif creation error: {p2.stderr.decode()}")

    # حذف ملف الباليت بعد الاستخدام
    if os.path.exists(palette_path):
        os.remove(palette_path)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبًا! \n"
        "ارسل لي فيديو لتحويله إلى GIF بحجم 320x320.\n"
        "تقدر تستخدم الأمر /convert لكتابة وقت البداية والنهاية بالثواني.\n"
        "مثال: /convert 3 7 (يحول الفيديو من الثانية 3 إلى 7)\n"
        "إذا ما حددت أوقات، سيأخذ أول 5 ثواني."
    )


async def convert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("الرجاء ارسال أمر /convert مع رقمين: وقت البداية ووقت النهاية بالثواني.\nمثال: /convert 3 7")
        return
    try:
        start_sec = float(args[0])
        end_sec = float(args[1])
        if start_sec < 0 or end_sec <= start_sec:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("الرجاء التأكد من أن الوقت هو رقم صحيح أو عشري، وأن النهاية أكبر من البداية.")
        return

    context.user_data['start_sec'] = start_sec
    context.user_data['end_sec'] = end_sec
    await update.message.reply_text(f"تم ضبط وقت المقطع من {start_sec} إلى {end_sec} ثانية. أرسل الفيديو الآن.")


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("أرسل فيديو فقط.")
        return

    file_id = video.file_id
    file = await context.bot.get_file(file_id)

    with tempfile.TemporaryDirectory() as tmpdirname:
        input_path = os.path.join(tmpdirname, "input.mp4")
        output_path = os.path.join(tmpdirname, "output.gif")

        await file.download_to_drive(input_path)

        start_sec = context.user_data.get('start_sec', 0)
        end_sec = context.user_data.get('end_sec', start_sec + 5)
        duration_sec = max(end_sec - start_sec, 1)

        # تجربة ضبط جودة GIF وحجم الملف مع تقليل FPS والألوان تلقائيا
        fps_options = [10, 7, 5]
        colors_options = [256, 128, 64]

        success = False
        last_exception = None

        for fps in fps_options:
            for colors in colors_options:
                try:
                    convert_video_to_gif_ffmpeg(input_path, output_path,
                                                width=320, height=320,
                                                start=start_sec, duration=duration_sec,
                                                fps=fps, colors=colors)
                    size_mb = os.path.getsize(output_path) / (1024 * 1024)
                    if size_mb <= MAX_SIZE_MB:
                        success = True
                        break
                except Exception as e:
                    last_exception = e
                    continue
            if success:
                break

        if success:
            with open(output_path, 'rb') as gif_file:
                await update.message.reply_animation(gif_file, caption=f"✅ تم الإنشاء بحجم {size_mb:.2f} ميجابايت. (fps={fps}, colors={colors})")
        else:
            msg = f"حدث خطأ أثناء التحويل أو أن حجم الملف تجاوز {MAX_SIZE_MB} ميجابايت."
            if last_exception:
                msg += f"\n\nتفاصيل الخطأ: {last_exception}"
            await update.message.reply_text(msg)

        context.user_data.pop('start_sec', None)
        context.user_data.pop('end_sec', None)


# AIOHTTP web server for Render
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


# Main app logic
async def main():
    # Telegram bot
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


if __name__ == '__main__':
    asyncio.run(main())
