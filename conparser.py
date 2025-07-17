import time
import configparser
import keyboard
import psutil
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
CONFIG_FILE = 'config.ini'

config.read(CONFIG_FILE, encoding='utf-8')

BLACKLISTED_USERNAMES = [name.strip() for name in config['SETTINGS'].get('blacklisted_usernames', '').split(',') if name.strip()]
CON_LOG_FILE_PATH = config['SETTINGS']['gameconlogpath']
CHAT_KEY = config['SETTINGS']['chatkey']
TEAM_CHAT_KEY = config['SETTINGS'].get('teamchatkey', 'u')
# Use UTF-8 by default as modern Source games output logs in this encoding.
# Set `conlogencoding` in `config.ini` if your game uses another codepage.
CON_LOG_ENCODING = config['SETTINGS'].get('conlogencoding', 'utf-8')


@dataclass
class ParsedLog:
    username: str
    message: str
    chat_type: str | None
    prefix: str
    is_dead: bool = False


def detect_game(custom_proc="customproc"):
    pname = None
    for proc in psutil.process_iter():
        match proc.name():
            case "hl.exe":
                pname = "hl"
                break
            case "hl2.exe":
                pname = "hl2"
                break
            case "cs2.exe":
                pname = "cs2"
                break
            case _:
                if proc.name() == custom_proc:
                    pname = custom_proc.strip(".exe")
                    break
                else:
                    continue
    return pname


# really hacky but it works
def parse_log(game, line: str):
    """
    Parses source console logs, if it detects

    Args:
        game (str): Specifies the game as to use the appropriate format
        line (str): String fetched from the source console log to parse

        Returns:
            list: In-game username (index 0), message (index 1),
                  and chat type 'all' or 'team' (index 2)

    """


    if "Source2Shutdown" in line:
        exit() #TODO: make this optional

    is_dead = False
    parsed_log = ["", ""]
    username = ""
    message = ""
    chat_type = None
    prefix = ""
    match game:
        case "cs2":
            if "[TEAM]" in line or "[Т]" in line or "[СП]" in line:
                chat_type = "team"
                if "[TEAM]" in line:
                    prefix = "[TEAM]"
                    parsed_log = line.partition("[TEAM] ")[2].split(": ")
                elif "[Т]" in line:
                    prefix = "[Т]"
                    parsed_log = line.partition("[Т] ")[2].split(": ")
                else:
                    prefix = "[СП]"
                    parsed_log = line.partition("[СП] ")[2].split(": ")
            elif "[ALL]" in line or "[ВСЕМ]" in line:
                chat_type = "all"
                if "[ALL]" in line:
                    prefix = "[ALL]"
                    parsed_log = line.partition("[ALL] ")[2].split(": ")
                else:
                    prefix = "[ВСЕМ]"
                    parsed_log = line.partition("[ВСЕМ] ")[2].split(": ")



     
        case "hl":
            if ": " in line:
                parsed_log = line.split(": ")
                parsed_log[0] = parsed_log[0][1:] # For some reason usernames start with '☻' in this game, probably some weird unicode thing.

        case "hl2":
            if "*DEAD*" in line:
                parsed_log = line.replace("*DEAD* ", '')
            if " : " in line:
                parsed_log = line.split(" :  ")

        case _:                                                                         
            return None   

    username = parsed_log[0]
    username = username.replace(u'\u200e', '')

    message = parsed_log[1]

    logger.debug(
        "Parsed line '%s' -> %s",
        line.strip(),
        [username, message, chat_type, prefix, is_dead]
    )

    return ParsedLog(username, message, chat_type, prefix, is_dead)





def rt_file_read(file: __file__):
    """Reads console.log in real time and yields new lines."""
    line = file.readline()
    if not line:
        # небольшая пауза, чтобы не крутить цикл на 100%
        time.sleep(0.01)
    return line


def sim_key_presses(text: str, key: str = CHAT_KEY):
    """Send a chat message using several input methods."""
    keyboard.press_and_release(key)
    time.sleep(0.05)
    try:
        keyboard.write(text)
    except Exception as exc:
        logger.debug("keyboard.write failed: %s, falling back to win32", exc)
        _win32_write(text)
    time.sleep(0.05)
    keyboard.press_and_release('enter')


def _win32_write(text: str):
    """Fallback input using Win32 API for games that ignore keyboard.write."""
    import ctypes

    user32 = ctypes.windll.user32
    for char in text:
        vk = user32.VkKeyScanW(ord(char)) & 0xFF
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)


