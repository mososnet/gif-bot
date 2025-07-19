import os
import tempfile
import cv2
from moviepy.editor import VideoFileClip, CompositeVideoClip
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler

UPLOAD_FOLDER = 'static/gifs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def add_blur_background(video_path, width, height):
    clip = VideoFileClip(video_path)

    if clip.h <= clip.w:
        return clip.resize(newsize=(width, height))  # فيديو عرضي، نعدله فقط

    temp_img = f"{tempfile.gettempdir()}/frame.jpg"
    clip.save_frame(temp_img, t=0.5)

    img = cv2.imread(temp_img)
    blur = cv2.GaussianBlur(img, (99, 99), 30)
    bg_path = temp_img.replace("frame.jpg", "blur.jpg")
    cv2.imwrite(bg_path, blur)

    bg_clip = (VideoFileClip(bg_path)
               .set_duration(clip.duration)
               .resize((width, height)))

    fg_clip = clip.resize(height=height).set_position("center")

    final = CompositeVideoClip([bg_clip, fg_clip])
    return final

def convert_to_gif(clip, output_path, max_size_mib):
    fps = 10
    min_fps = 2
    while fps >= min_fps:
        clip.write_gif(output_path, fps=fps)
        size = os.path.getsize(output_path) / (1024 * 1024)
        if size <= max_size_mib:
            return fps, size
        fps -= 1
    return fps, os.path.getsize(output_path) / (1024 * 1024)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل لي فيديو، وسأحوّله لك إلى صورة متحركة GIF مع خلفية ضبابية لو لازم.")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("أرسل فيديو فقط.")
        return

    file_id = video.file_id
    file = await context.bot.get_file(file_id)

    # إنشاء أسماء ملفات مؤقتة فقط
    tmp_dir = tempfile.gettempdir()
    unique_prefix = next(tempfile._get_candidate_names())  # اسم فريد

    input_path = os.path.join(tmp_dir, f"{unique_prefix}.mp4")
    output_path = os.path.join(tmp_dir, f"{unique_prefix}.gif")

    await file.download_to_drive(input_path)

    width, height = 320, 240
    start, end = 0, 5  # أول 5 ثواني
    max_size = 5  # ميجابايت

    try:
        base_clip = add_blur_background(input_path, width, height)
        sub_clip = base_clip.subclip(start, end)
        fps, size = convert_to_gif(sub_clip, output_path, max_size)

        with open(output_path, 'rb') as gif_file:
            await update.message.reply_animation(gif_file, caption=f"✅ تم الإنشاء بحجم {size:.2f}MB وFPS={fps}")

    except Exception as e:
        await update.message.reply_text(f"حدث خطأ أثناء المعالجة: {e}")

    finally:
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)

if __name__ == '__main__':
    BOT_TOKEN = "YOUR_BOT_TOKEN"

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    print("البوت شغّال...")
    app.run_polling()
