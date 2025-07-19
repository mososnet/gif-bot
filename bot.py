import os
import tempfile
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

UPLOAD_FOLDER = 'static/gifs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def convert_video_to_gif_ffmpeg(input_path, output_path, width=320, height=240, start=0, duration=5, fps=10):
    # أمر ffmpeg لتحويل جزء من الفيديو إلى gif مع تغيير الحجم
    command = [
        'ffmpeg',
        '-ss', str(start),          # بداية التحويل من الثانية start
        '-t', str(duration),        # مدة الفيديو بالثواني
        '-i', input_path,
        '-vf', f'scale={width}:{height}:flags=lanczos,fps={fps}',
        '-gifflags', '+transdiff',
        '-y',                       # الكتابة فوق الملف لو موجود
        output_path
    ]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0:
        raise Exception(f"ffmpeg error: {result.stderr.decode()}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل لي فيديو، وسأحوّله لك إلى صورة متحركة GIF.")

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

        try:
            convert_video_to_gif_ffmpeg(input_path, output_path)
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            with open(output_path, 'rb') as gif_file:
                await update.message.reply_animation(gif_file, caption=f"✅ تم الإنشاء بحجم {size_mb:.2f} ميجابايت.")
        except Exception as e:
            await update.message.reply_text(f"حدث خطأ أثناء التحويل: {e}")

if __name__ == '__main__':
    BOT_TOKEN = "7973939667:AAFRZP8Sv_qqgO-JHyNM2Tnmsp1X8_WZ0Yk"

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    print("البوت شغّال...")
    app.run_polling()
