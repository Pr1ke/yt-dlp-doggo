from urllib.parse import urlparse
import datetime
import telebot
import config
import yt_dlp
import re
import shutil
import time
import os
from telebot import types
from telebot.util import quick_markup

bot = telebot.TeleBot(config.token)
last_edited = {}
buffer = config.directory+"buffer/"
archive = config.directory+"archive/"
favorites = config.directory+"favorites/"
playlist = config.directory+"playlist/" 



def youtube_url_validation(url):
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

    youtube_regex_match = re.match(youtube_regex, url)
    return youtube_regex_match




def download_video(message, url, audio=False, format_id="mp4", target=buffer):
    url_info = urlparse(url)
    if url_info.scheme:
        if url_info.netloc in ['www.youtube.com', 'youtu.be', 'youtube.com', 'youtu.be']:
            if not youtube_url_validation(url):
                bot.reply_to(message, 'Konnte die URL nicht erkennen)')
                return

        def progress(d):

            if d['status'] == 'downloading':
                try:
                    update = False

                    if last_edited.get(f"{message.chat.id}-{msg.message_id}"):
                        if (datetime.datetime.now() - last_edited[f"{message.chat.id}-{msg.message_id}"]).total_seconds() >= 5:
                            update = True
                    else:
                        update = True

                    if update:
                        perc = round(d['downloaded_bytes'] *
                                     100 / d['total_bytes'])
                        bot.edit_message_text(
                            chat_id=message.chat.id, message_id=msg.message_id, text=f"Downloading {d['info_dict']['title']}\n\n{perc}%")
                        last_edited[f"{message.chat.id}-{msg.message_id}"] = datetime.datetime.now()
                except Exception as e:
                    print(e)

        msg = bot.reply_to(message, 'Lade Herunter...')
        with yt_dlp.YoutubeDL({'paths': {'home':target},'format': format_id, 'outtmpl': 'outputs/%(title)s.%(ext)s', 'progress_hooks': [progress], 'postprocessors': [{  # Extract audio using ffmpeg
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }] if audio else [], 'max_filesize': config.max_filesize}) as ydl:
            try:
                info = ydl.extract_info(url, download=True, )

                bot.edit_message_text(
                    chat_id=message.chat.id, message_id=msg.message_id, text='Ich sende die Datei an Telegram...')
                try:
                    if audio:
                        bot.send_audio(message.chat.id, open(
                            info['requested_downloads'][0]['filepath'], 'rb'), reply_to_message_id=message.message_id)

                    else:
                        bot.send_video(message.chat.id, open(
                            info['requested_downloads'][0]['filepath'], 'rb'), reply_to_message_id=message.message_id)
                    bot.delete_message(message.chat.id, msg.message_id)
                except Exception as e:
                    bot.edit_message_text(
                        chat_id=message.chat.id, message_id=msg.message_id, text=f"Ich konnte die Datei nicht an Telegram senden, sie ist wahrscheinlich größer als *{round(config.max_filesize / 1000000)}MB*", parse_mode="MARKDOWN")
                finally:
                    for file in info['requested_downloads']:
                        cleanup(file['filepath'])
            except Exception as e:
                if isinstance(e, yt_dlp.utils.DownloadError):
                    bot.edit_message_text(
                        'Ungültige URL', message.chat.id, msg.message_id)
                else:
                    bot.edit_message_text(
                        'Es gab einen Fehler beim Herunterladen.', message.chat.id, msg.message_id)
    else:
        bot.reply_to(message, 'Ungültige URL')


def cleanup(newFile: str, moveToFavorite=False):
    filelist = get_all_files_in_directory(buffer)
    for f in filelist:
        if not f == newFile and not moveToFavorite:
            os.rename(f, archive + os.path.basename(f))
        elif moveToFavorite:
            os.rename(f, favorites + os.path.basename(f)) 

def copyAllFiles(source: str, destination: str):
    filelist = get_all_files_in_directory(source)
    for f in filelist:
        shutil.copy(f, destination)

def clearPlaylist():
    filelist = get_all_files_in_directory(playlist)
    for f in filelist:
        os.remove(f)
    time.sleep(2)

def get_all_files_in_directory(path):
    all_files = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = os.path.join(root, file)
            all_files.append(file_path)
    return all_files

def log(message, text: str, media: str):
    if config.logs:
        if message.chat.type == 'private':
            chat_info = "Private chat"
        else:
            chat_info = f"Group: *{message.chat.title}* (`{message.chat.id}`)"

        bot.send_message(
            config.logs, f"Download request ({media}) from @{message.from_user.username} ({message.from_user.id})\n\n{chat_info}\n\n{text}")


def get_text(message):
    if len(message.text.split(' ')) < 2:
        if message.reply_to_message and message.reply_to_message.text:
            return message.reply_to_message.text

        else:
            return None
    else:
        return message.text.split(' ')[1]
    


@bot.message_handler(commands=['start', 'help'])
def test(message):
    bot.reply_to(
        message, "*Schicke mir einen Videolink* und ich werde das Video runterladen, funktioniert mit *YouTube*, *Twitter*, *TikTok*, *Reddit* und vielen mehr!", parse_mode="MARKDOWN")
    bot.reply_to(
        message, "/play - um das letzte Video abzuspielen."
    )
    bot.reply_to(
        message, "/playfavorites - um deine favorierten Videos abzuspielen."
    )
    bot.reply_to(
        message, "/playarchive - um deine archivierten Videos abzuspielen."
    )
    bot.reply_to(
        message, "/randomize - um all deine Videos abzuspielen."
    )
    bot.reply_to(
        message, "/archive - um das letzte Video zu archivieren."
    )
    bot.reply_to(
        message, "/favorite - um das letzte Video zu favorisieren."
    )
    bot.reply_to(
        message, "Standardmäßig werden Videos im Archiv gespeichert."
    )

@bot.message_handler(commands=['download'])
def download_command(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, 'Ich konnte die URL nicht erkennen, probiere es mit `/download url`', parse_mode="MARKDOWN")
        return

    log(message, text, 'video')
    download_video(message, text)


@bot.message_handler(commands=['audio'])
def download_audio_command(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, 'Ich konnte die URL nicht erkennen, probiere es mit `/audio url`', parse_mode="MARKDOWN")
        return

    log(message, text, 'audio')
    download_video(message, text, True)

@bot.message_handler(commands=['play'])
def playBuffer(message):
    clearPlaylist()
    copyAllFiles(buffer, playlist)
    bot.reply_to(
        message, 'Ich spiele das letzte Video ab.', parse_mode="MARKDOWN")
    return

@bot.message_handler(commands=['playfavorites'])
def playFavorites(message):
    clearPlaylist()
    copyAllFiles(favorites, playlist)
    bot.reply_to(
        message, 'Ich spiele die favorisierten Videos ab.', parse_mode="MARKDOWN")
    return

@bot.message_handler(commands=['playarchive'])
def playArchive(message):
    clearPlaylist()
    copyAllFiles(archive, playlist)
    bot.reply_to(
        message, 'Ich spiele die archivierten Videos ab.', parse_mode="MARKDOWN")
    return

@bot.message_handler(commands=['favorite'])
def favorite(message):
    cleanup("", True)
    bot.reply_to(
            message, 'Video wurde favorisiert.', parse_mode="MARKDOWN")
    return

@bot.message_handler(commands=['archive'])
def archiveLatest(message):
    cleanup("", False)
    bot.reply_to(
            message, 'Video wurde archiviert.', parse_mode="MARKDOWN")
    return

@bot.message_handler(commands=['randomize'])
def randomizeVideos(message):
    cleanup("")
    clearPlaylist()

    copyAllFiles(archive, playlist)
    copyAllFiles(favorites, playlist)

    bot.reply_to(
            message, 'Playlist wurde zurückgesetzt und alle Videos eingefügt.', parse_mode="MARKDOWN")
    return

@bot.message_handler(commands=['custom'])
def custom(message):
    text = get_text(message)
    if not text:
        bot.reply_to(
            message, 'Ich konnte die URL nicht erkennen, probiere es mit  `/custom url`', parse_mode="MARKDOWN")
        return

    msg = bot.reply_to(message, 'Ermittle Format...')

    with yt_dlp.YoutubeDL() as ydl:
        info = ydl.extract_info(text, download=False)

    data = {f"{x['resolution']}.{x['ext']}": {
        'callback_data': f"{x['format_id']}"} for x in info['formats'] if x['video_ext'] != 'none'}

    markup = quick_markup(data, row_width=2)

    bot.delete_message(msg.chat.id, msg.message_id)
    bot.reply_to(message, "Wähle bitte ein Format", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.from_user.id == call.message.reply_to_message.from_user.id:
        url = get_text(call.message.reply_to_message)
        bot.delete_message(call.message.chat.id, call.message.message_id)
        download_video(call.message.reply_to_message, url,
                       format_id=f"{call.data}+bestaudio")
    else:
        bot.answer_callback_query(call.id, "You didn't send the request")


@bot.message_handler(func=lambda m: True, content_types=["text", "pinned_message", "photo", "audio", "video", "location", "contact", "voice", "document"])
def handle_private_messages(message):
    text = message.text if message.text else message.caption if message.caption else None

    if message.chat.type == 'private':
        log(message, text, 'video')
        download_video(message, text)
        return


bot.infinity_polling()
