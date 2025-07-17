import requests
import logging
import os
import sys

import dearpygui.dearpygui as dpg
import conparser as cp

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


OPENROUTER_API_KEY = cp.config['SETTINGS']['openrouterapikey']

SYSTEM_PROMPT_FILE = "system_prompt.txt"
DEFAULT_SYSTEM_PROMPT = (
    "Ты - игрок в кс2. Ограничивай ответ до 120 символов. "
)

try:
    with open(SYSTEM_PROMPT_FILE, encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
except FileNotFoundError:
    logger.debug("System prompt file not found, using default")
    SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT

class Status():
    running = False


def debug_log(text: str):
    if dpg.does_item_exist("debug_console"):
        current = dpg.get_value("debug_console")
        dpg.set_value("debug_console", f"{text}\n{current}")
        dpg.set_y_scroll("Debug Console", 0)


def set_status(sender, app_data, user_data):
    if Status.running == False:
        dpg.configure_item("start_button", label="Stop")
        dpg.set_value(user_data, "Running: True")
        logger.debug("Bot started")
        debug_log("[INFO] Bot started")

    elif Status.running == True:
        dpg.configure_item("start_button", label="Start")
        dpg.set_value(user_data, "Running: False")
        logger.debug("Bot stopped")
        debug_log("[INFO] Bot stopped")

    Status.running = not Status.running


def save_config():
    cp.config['SETTINGS']['blacklisted_usernames'] = dpg.get_value("usernames")
    cp.config['SETTINGS']['gameconlogpath'] = dpg.get_value("conlog")
    cp.config['SETTINGS']['chatkey'] = dpg.get_value("chat_keybind")
    with open(cp.CONFIG_FILE, 'w') as configfile:
        cp.config.write(configfile)
    logger.debug("Configuration saved")


def openrouter_interact(user: str, message: str, prefix: str = "", content=SYSTEM_PROMPT):
    logger.debug("Sending to OpenRouter: %s -> %s", user, message)
    prefix_text = f"{prefix} " if prefix else ""
    debug_log(f"> {prefix_text}{user}: {message}")
    message = f"I'm {prefix_text}{user}, {message}"

    messages = [{"role": "system", "content": content}, {"role": "user", "content": message}]
    data = {
        "model": "openai/gpt-4.1-nano",
        "messages": messages,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/ANDRYBAS/cs2chatgpt",
        "X-Title": "Chat-Strike",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30,
        )
        logger.debug("OpenRouter status: %s", response.status_code)
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"]
        logger.debug("Received from OpenRouter: %s", reply)
        debug_log(f"< {reply}")
        return reply
    except Exception as exc:
        logger.exception("OpenRouter request failed: %s", exc)
        return ""


def main():
    logfile = None
    username = ""
    message = ""
    game = cp.detect_game()
    logger.debug("Detected game: %s", game)

    

    dpg.create_context()
    dpg.create_viewport(title='Chat-Strike', width=600, height=500)

    if sys.platform.startswith('win'):
        # Попробуем подобрать стандартный моноширинный шрифт с поддержкой кириллицы
        win_dir = os.environ.get('WINDIR', 'C:\\Windows')
        for fname in ("consola.ttf", "lucon.ttf", "cour.ttf"):
            font_path = os.path.join(win_dir, "Fonts", fname)
            if os.path.exists(font_path):
                with dpg.font_registry():
                    default_font = dpg.add_font(font_path, 14)
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)
                    dpg.bind_font(default_font)
                break
        else:
            font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSansMono.ttf")
            if os.path.exists(font_path):
                with dpg.font_registry():
                    default_font = dpg.add_font(font_path, 14)
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)
                    dpg.bind_font(default_font)
    else:
        font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSansMono.ttf")
        if os.path.exists(font_path):
            with dpg.font_registry():
                default_font = dpg.add_font(font_path, 14)
                dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)
                dpg.bind_font(default_font)

    with dpg.window(label="Chat-Strike", width=600, height=180, tag="Chat-Strike"):
        dpg.add_text(f"Detected game: {game}")
        
        dpg.add_input_text(hint="Blacklisted usernames (comma separated)",
                           default_value=','.join(cp.BLACKLISTED_USERNAMES),
                           tag="usernames")
        dpg.add_input_text(hint=".log file path", default_value=cp.CON_LOG_FILE_PATH, tag="conlog")
        dpg.add_input_text(hint="OpenRouter key", default_value=OPENROUTER_API_KEY, password=True, tag="openapi_key")
        dpg.add_input_text(hint="Chat keybind", default_value=cp.CHAT_KEY, tag="chat_keybind")

        dpg.add_button(label="Save", callback=save_config)
        status_text = dpg.add_text("Running: False")

        dpg.add_button(label="Start", callback=set_status, user_data=status_text, tag="start_button")

    with dpg.window(label="Debug Console", width=600, height=300, pos=(0,200), tag="Debug Console"):
        dpg.add_input_text(tag="debug_console", multiline=True, readonly=True, width=-1, height=280)



    dpg.set_primary_window("Chat-Strike", True)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    with dpg.handler_registry():
        dpg.add_key_press_handler(dpg.mvKey_Add, callback=set_status, user_data=status_text)

    if cp.config['SETTINGS']['gameconlogpath'] != None:
        logfile = open(cp.CON_LOG_FILE_PATH, encoding=cp.CON_LOG_ENCODING, errors='ignore')
        logfile.seek(0, 2)
        logger.debug("Log file opened: %s", cp.CON_LOG_FILE_PATH)

        


    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()

        if Status.running == True:
            if logfile:
                
                line = cp.rt_file_read(logfile)
                
                if not line:
                    continue
                logger.debug(line.strip())
                username, message, chat_type, prefix = cp.parse_log(game, line)

                if username and message:
                    #print(f"[DEBUG] {username}: {message}:")
                    # This way we prevent chat-gpt from talking to itself
                    logger.debug("Username: %s", username)
                    if username not in cp.BLACKLISTED_USERNAMES:
                        reply = openrouter_interact(username, message, prefix)
                        if reply:
                            if reply.strip() == "[IGNORE]":
                                logger.debug("[IGNORE] received, skipping keystrokes")
                                debug_log("[INFO] Reply ignored")
                            else:
                                key = cp.TEAM_CHAT_KEY if chat_type == "team" else cp.CHAT_KEY
                                cp.sim_key_presses(reply, key)
                        else:
                            logger.debug("Empty reply, skipping keystrokes")
                            debug_log("[INFO] Empty reply")
                    else:
                        logger.debug("Message ignored from blacklisted user")
                        debug_log("[INFO] Message ignored from blacklisted user")
                else:
                    continue
    
    if logfile:
        logfile.close()
    dpg.destroy_context()








if __name__ == "__main__":
    main()
