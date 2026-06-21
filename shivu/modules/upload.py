import os
import requests
from datetime import datetime
from pymongo import ReturnDocument
from PIL import Image

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from shivu import db, application, collection

# ==========================================================
# constants & collections
# ==========================================================
TEMP_DIR = "temp_upload"
os.makedirs(TEMP_DIR, exist_ok=True)

# 🛑 YAHAN APNA IMGBB API KEY DAALNA HAI 🛑
IMGBB_API_KEY = "95c5713baa2adf32c45f91191939d7ad"

# Sticker Configuration
STICKER_FILE_ID = "CAACAgUAAyEFAASsVPZOAAKlC2m-gprvRR2VReCarRJIbv_naowQAAJCGAACyAVoVjLmxGezxTrmHgQ"
sticker_settings = db["sticker_settings"]

# Log Group where the message will be sent
LOG_GROUP_ID = -1003773882799

# Allowed uploaders IDs
ALLOWED_UPLOADERS = {
    7641508639,
}

MARKET_COL = db["market"]

# ==========================================================
# rarity maps (number based)
# ==========================================================
RARITY_MAP = {
    1: "⛩ Normal", 2: "🏮 Standard", 3: "🍀 Regular", 4: "🔮 Mystic",
    5: "🎐 Eternal", 6: "👑 Royal", 7: "🔥 Infernal", 8: "🎊 Astral",
    9: "🏮 Classic", 10: "🎭 Mythic", 11: "🧧 Continental", 12: "🎈 Chunbiyo"
}

RARITY_PRICE_MAP = {
    1: 1000, 2: 1500, 3: 2500, 4: 4000,
    5: 6000, 6: 8000, 7: 12000, 8: 18000,
    9: 250000, 10: 350000, 11: 200000, 12: 400000
}

# ==========================================================
# helpers (Fallback Upload Logic Added Here)
# ==========================================================
def upload_with_fallback(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError("File not found")

    # 1. Try ImgBB First (Works only for images, videos will fail and fallback)
    if IMGBB_API_KEY and IMGBB_API_KEY != "YOUR_IMGBB_API_KEY_HERE":
        try:
            with open(file_path, "rb") as file:
                r = requests.post(
                    "https://api.imgbb.com/1/upload",
                    data={"key": IMGBB_API_KEY},
                    files={"image": file},
                    timeout=60
                )
            if r.status_code == 200:
                data = r.json()
                if "data" in data and "url" in data["data"]:
                    return data["data"]["url"]
        except Exception:
            pass # Fallback to Catbox

    # 2. Try Catbox if ImgBB fails (or if file is a video)
    try:
        with open(file_path, "rb") as file:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": file},
                timeout=120
            )
        if r.status_code == 200 and r.text.startswith("https"):
            return r.text.strip()
    except Exception:
        pass # Fallback to Graph.org

    # 3. Try Graph.org as last resort
    try:
        with open(file_path, "rb") as file:
            r = requests.post(
                "https://graph.org/upload",
                files={"file": file},
                timeout=60
            )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and "src" in data[0]:
                return "https://graph.org" + data[0]["src"]
    except Exception:
        pass

    raise Exception("Upload failed on all servers (ImgBB, Catbox, Graph.org)")


async def get_next_sequence_number(name: str):
    seq = await db.sequences.find_one_and_update(
        {"_id": name},
        {"$inc": {"sequence_value": 1}},
        return_document=ReturnDocument.AFTER
    )
    if not seq:
        await db.sequences.insert_one({"_id": name, "sequence_value": 1})
        return "1"
    return str(seq["sequence_value"])


async def get_reusable_id():
    slot = await collection.find_one({"deleted": True}, sort=[("id", 1)])
    if slot:
        return str(slot["id"])
    return await get_next_sequence_number("character_id")

# ==========================================================
# Sticker Logic (Required for upload)
# ==========================================================
async def apply_sticker(image_path: str) -> str:
    base_img = Image.open(image_path).convert("RGBA")

    # Fetch sticker from Telegram
    sticker_file = await application.bot.get_file(STICKER_FILE_ID)
    sticker_path = f"{TEMP_DIR}/sticker_{sticker_file.file_unique_id}.webp"
    await sticker_file.download_to_drive(sticker_path)

    sticker_img = Image.open(sticker_path).convert("RGBA")

    # Calculate sizes
    bw, bh = base_img.size
    new_w = int(bw * 0.18)
    ratio = new_w / sticker_img.width
    new_h = int(sticker_img.height * ratio)

    sticker_img = sticker_img.resize((new_w, new_h), Image.LANCZOS)
    x = int(bw * 0.02)
    y = int(bh * 0.02)

    # Paste sticker
    base_img.paste(sticker_img, (x, y), sticker_img)
    final_path = f"{TEMP_DIR}/final_{os.path.basename(image_path)}"
    base_img.save(final_path, "PNG")

    # Clean up downloaded sticker
    try:
        os.remove(sticker_path)
    except:
        pass

    return final_path

# ==========================================================
# /upload command (direct upload logic)
# ==========================================================
async def upload_waifu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    user = update.effective_user

    # Authentication Check
    if user.id not in ALLOWED_UPLOADERS:
        return await msg.reply_text("❌ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀᴜᴛʜᴏʀɪᴢᴇᴅ ᴛᴏ ᴜsᴇ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ.")

    reply = msg.reply_to_message
    
    # --- CHECK: Allow Photo, Video, or Animation (GIF) ---
    if not reply or not (reply.photo or reply.video or reply.animation) or len(context.args) < 3:
        return await msg.reply_text(
            "❌ ᴜsᴀɢᴇ:\nʀᴇᴘʟʏ ᴛᴏ ᴀ <b>ᴘʜᴏᴛᴏ ᴏʀ ᴠɪᴅᴇᴏ</b> ᴡɪᴛʜ\n/upload name anime rarity_number",
            parse_mode="HTML"
        )

    name = context.args[0].replace("-", " ").title()
    anime = context.args[1].replace("-", " ").title()
    
    try:
        rarity_no = int(context.args[2])
    except ValueError:
        return await msg.reply_text("❌ ʀᴀʀɪᴛʏ ᴍᴜsᴛ ʙᴇ ᴀ ɴᴜᴍʙᴇʀ (1-12).")

    if rarity_no not in RARITY_MAP:
        return await msg.reply_text("❌ ɪɴᴠᴀʟɪᴅ ʀᴀʀɪᴛʏ ɴᴜᴍʙᴇʀ.")

    rarity_text = RARITY_MAP[rarity_no]
    market_price = RARITY_PRICE_MAP.get(rarity_no, 1000)

    # Determine media type
    is_video = bool(reply.video or reply.animation)
    media_obj = reply.video or reply.animation if is_video else reply.photo[-1]

    # Process Media
    processing_msg = await msg.reply_text(f"⏳ ᴘʀᴏᴄᴇssɪɴɢ {'ᴠɪᴅᴇᴏ' if is_video else 'ɪᴍᴀɢᴇ'}, ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...")
    
    tg_file = await media_obj.get_file()
    ext = ".mp4" if is_video else ".png"
    base_path = f"{TEMP_DIR}/user_{tg_file.file_unique_id}{ext}"
    await tg_file.download_to_drive(base_path)

    # Check sticker settings (Only apply if it's NOT a video)
    use_sticker = False
    final_upload_path = base_path
    
    if not is_video:
        setting = await sticker_settings.find_one({"user_id": user.id})
        use_sticker = setting.get("enabled", False) if setting else False

        if use_sticker:
            try:
                await processing_msg.edit_text("⏳ ᴀᴘᴘʟʏɪɴɢ sᴛɪᴄᴋᴇʀ...")
                final_upload_path = await apply_sticker(base_path)
            except Exception as e:
                await processing_msg.edit_text(f"⚠️ ᴡᴀʀɴɪɴɢ: ғᴀɪʟᴇᴅ ᴛᴏ ᴀᴘᴘʟʏ sᴛɪᴄᴋᴇʀ. ᴘʀᴏᴄᴇᴇᴅɪɴɢ ᴡɪᴛʜᴏᴜᴛ ɪᴛ.\n`{e}`")
                final_upload_path = base_path

    await processing_msg.edit_text(f"⏳ ᴜᴘʟᴏᴀᴅɪɴɢ {'ᴠɪᴅᴇᴏ' if is_video else 'ɪᴍᴀɢᴇ'} ᴛᴏ sᴇʀᴠᴇʀ...")
    try:
        # Fallback system is called here
        media_url = upload_with_fallback(final_upload_path)
    except Exception as e:
        # Cleanup on fail
        try:
            os.remove(base_path)
            if final_upload_path != base_path:
                os.remove(final_upload_path)
        except:
            pass
        return await processing_msg.edit_text(f"❌ ᴜᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ:\n`{e}`")

    # Try to extract and upload video thumbnail (Useful for inline query previews)
    thum_url = None
    if is_video and hasattr(media_obj, 'thumbnail') and media_obj.thumbnail:
        try:
            thum_file = await media_obj.thumbnail.get_file()
            thum_path = f"{TEMP_DIR}/thumb_{thum_file.file_unique_id}.jpg"
            await thum_file.download_to_drive(thum_path)
            # Use fallback system for thumbnails too
            thum_url = upload_with_fallback(thum_path)
            os.remove(thum_path)
        except Exception:
            pass # Ignore if thumbnail fails to upload

    char_id = await get_reusable_id()

    # Prepare Database Document
    db_doc = {
        "id": char_id,
        "name": name,
        "anime": anime,
        "rarity": rarity_text,
        "rarity_number": rarity_no,
        "deleted": False,
        "added_by": user.first_name,    
        "likes": 0,
        "dislikes": 0,
        "upload_timestamp": datetime.utcnow()
    }

    if is_video:
        db_doc["vid_url"] = media_url
        if thum_url:
            db_doc["thum_url"] = thum_url
            # Fallback for code expecting an img_url even if it's an AMV
            db_doc["img_url"] = thum_url 
    else:
        db_doc["img_url"] = media_url

    # DB Save Operations
    try:
        await collection.update_one(
           {"id": char_id},
           {"$set": db_doc},
           upsert=True
        )
        
        await MARKET_COL.insert_one({
            "seller_id": user.id,
            "seller_name": user.first_name,
            "waifu_id": char_id,
            "name": name,
            "anime": anime,
            "rarity": rarity_no, 
            "image": thum_url if is_video and thum_url else media_url, # Show thumb in market if video
            "price": market_price,
            "quantity": 1,
            "likes": 0,
            "dislikes": 0,
            "listed_at": datetime.utcnow()
        })
    except Exception as db_err:
        return await msg.reply_text(f"❌ Dᴀᴛᴀʙᴀsᴇ sᴀᴠᴇ ғᴀɪʟᴇᴅ:\n`{db_err}`")

    # Group Notification Caption
    caption = (
        f"✨ <b>Character Name:</b> {name}\n"
        f"🎬 <b>Anime Name:</b> {anime}\n"
        f"💎 <b>Rarity:</b> {rarity_text}\n"
        f"🆔 <b>ID:</b> {char_id}\n"
        f"👤 <b>Uploaded By:</b> "
        f"<a href='tg://user?id={user.id}'>{user.first_name}</a>\n"
        f"💰 <b>Market Price:</b> {market_price}"
    )

    # Send Notification to the specific Group
    try:
        if is_video:
            await context.bot.send_video(
                chat_id=LOG_GROUP_ID,
                video=media_url,
                caption=caption,
                parse_mode="HTML"
            )
        else:
            await context.bot.send_photo(
                chat_id=LOG_GROUP_ID,
                photo=media_url,
                caption=caption,
                parse_mode="HTML"
            )
    except Exception as e:
        await msg.reply_text(f"⚠️ ᴡᴀɪғᴜ ᴀᴅᴅᴇᴅ ᴛᴏ ᴅʙ, ʙᴜᴛ ғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ʟᴏɢ ᴛᴏ ɢʀᴏᴜᴘ: {e}")

    await processing_msg.edit_text(
        f"✅ <b>{'Vɪᴅᴇᴏ' if is_video else 'Wᴀɪғᴜ'} sᴜᴄᴄᴇssғᴜʟʟʏ ᴜᴘʟᴏᴀᴅᴇᴅ!</b>\n"
        f"🆔 <b>ɪᴅ:</b> {char_id}\n"
        f"🪄 <b>Sᴛɪᴄᴋᴇʀ:</b> {'ON' if use_sticker else ('N/A (Video)' if is_video else 'OFF')}",
        parse_mode="HTML"
    )

    # Clean up temp files
    try:
        if os.path.exists(base_path):
            os.remove(base_path)
        if use_sticker and final_upload_path != base_path and os.path.exists(final_upload_path):
            os.remove(final_upload_path)
    except:
        pass

# ==========================================================
# handlers
# ==========================================================
application.add_handler(CommandHandler("upload", upload_waifu))
