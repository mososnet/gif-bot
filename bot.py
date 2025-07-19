import os
import tempfile
import cv2
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

UPLOAD_FOLDER = 'static/gifs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def add_blur_background(input_path, width, height, output_path):
    cap = cv2.VideoCapture(input_path)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise ValueError("لم أستطع قراءة أول إطار من الفيديو")

    # حفظ الخلفية الضبابية
    blur = cv2.GaussianBlur(frame, (99, 99), 30)
    blur_path = f"{tempfile.gettempdir()}/blur.jpg"
    cv2.imwrite(blur_path, blur)

    # إنشاء فيديو ضبابي باستخدام ffmpeg
    blurred_video = f"{tempfile.gettempdir()}/blurred.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", blur_path,
        "-t", "5",
        "-vf", f"scale={width}:{height}",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        blurred_video
    ], check=True)

    # تركيب الفيديو فوق الخلفية
    subprocess.run([
        "ffmpeg", "-y",
        "-i", blurred_video,
        "-i", input_path,
        "-filter_complex",
        f"[1:v]scale=-1:{height}[fg];[0:v][fg]overlay=(W-w)/2:(H-h)/2",
        "-t", "5",  # أول 5 ثواني
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        output_path
    ], check=True)

def convert_to_gif(input_path, output_gif, max_size_mib):
    fps = 10
    min_fps = 2

    while fps >= min_fps:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", f"fps={fps},scale=320:-1:flags=lanczos",
            output_gif
        ], check=True)

        size = os.path.getsize(output_gif) / (1024 * 1024)
        if size <= max_size_mib:
            return fps, size

        fps -= 1

    return fps, os.path.getsize(output_gif) / (1024 * 1024)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل لي فيديو، وسأحوّله لك إلى صورة متحركة GIF مع خلفية ضبابية لو لازم.")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("أرسل فيديو فقط.")
        return

    file_id = video.file_id
    file = await context.bot.get_file(file_id)
    unique_name = tempfile.NamedTemporaryFile(delete=True).name
    input_path = f"{unique_name}.mp4"
    blurred_path = f"{unique_name}_blurred.mp4"
    output_gif = f"{unique_name}.gif"
    await file.download_to_drive(input_path)

    width, height = 320, 240
    max_size = 5  # ميجابايت

    try:
        add_blur_background(input_path, width, height, blurred_path)
        fps, size = convert_to_gif(blurred_path, output_gif, max_size)

        with open(output_gif, 'rb') as gif_file:
            await update.message.reply_animation(gif_file, caption=f"✅ تم الإنشاء بحجم {size:.2f}MB وFPS={fps}")

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء المعالجة: {e}")

    finally:
        for path in [input_path, blurred_path, output_gif]:
            if os.path.exists(path):
                os.remove(path)

if __name__ == '__main__':
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    print("البوت شغّال...")
    app.run_polling()
