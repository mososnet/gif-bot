import os
import tempfile
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

UPLOAD_FOLDER = 'static/gifs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def convert_video_to_gif_ffmpeg(input_path, output_path, width=320, height=320, start=0, duration=5, fps=10):
    command = [
        'ffmpeg',
        '-ss', str(start),
        '-t', str(duration),
        '-i', input_path,
        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,fps={fps}',
        '-gifflags', '+transdiff',
        '-y',
        output_path
    ]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"ffmpeg error: {result.stderr.decode()}")

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

        # القيم من أمر /convert لو موجودة، أو القيم الافتراضية
        start_sec = context.user_data.get('start_sec', 0)
        end_sec = context.user_data.get('end_sec', start_sec + 5)
        duration_sec = end_sec - start_sec
        if duration_sec <= 0:
            duration_sec = 5  # fallback لو حصل خطأ

        gif_fps = 10
        gif_width = 320
        gif_height = 320

        try:
            convert_video_to_gif_ffmpeg(input_path, output_path, width=gif_width, height=gif_height,
                                       start=start_sec, duration=duration_sec, fps=gif_fps)
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            with open(output_path, 'rb') as gif_file:
                await update.message.reply_animation(gif_file, caption=f"✅ تم الإنشاء بحجم {size_mb:.2f} ميجابايت.")
        except Exception as e:
            await update.message.reply_text(f"حدث خطأ أثناء التحويل: {e}")

        # نمسح الأوقات بعد استخدام المقطع عشان ما تتكرر على فيديو ثاني
        context.user_data.pop('start_sec', None)
        context.user_data.pop('end_sec', None)

if __name__ == '__main__':
    BOT_TOKEN = "7973939667:AAFRZP8Sv_qqgO-JHyNM2Tnmsp1X8_WZ0Yk"

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("convert", convert_command))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    print("البوت شغّال...")
    app.run_polling()
