import requests
import logging
import os
import sys
from collections import deque
import pyperclip  # работа с буфером обмена
import re

import dearpygui.dearpygui as dpg
import conparser as cp

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


OPENROUTER_API_KEY = cp.config['SETTINGS']['openrouterapikey']

SYSTEM_PROMPT_FILE = "system_prompt.txt"
BIND_PROMPTS_DIR = "bind_prompts"
DEFAULT_SYSTEM_PROMPT = (
    "Ты - игрок в кс2. Ограничивай ответ до 120 символов. "
)

try:
    with open(SYSTEM_PROMPT_FILE, encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
except FileNotFoundError:
    logger.debug("System prompt file not found, using default")
    SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT

# История диалога. Ограничиваем размер, чтобы не съесть лишние токены
MAX_HISTORY_TOKENS = 3000
conversation_history = deque([
    {"role": "system", "content": SYSTEM_PROMPT}
], maxlen=50)


def _count_tokens(messages):
    """Очень грубая оценка числа токенов."""
    return sum(len(m.get("content", "").split()) for m in messages)


def _trim_history():
    while len(conversation_history) > 1 and _count_tokens(conversation_history) > MAX_HISTORY_TOKENS:
        conversation_history.popleft()

class Status():
    running = False


def load_bind_prompts(directory: str) -> dict[int, str]:
    prompts = {}
    if not os.path.isdir(directory):
        return prompts
    for i in range(1, 11):
        path = os.path.join(directory, f"bind{i}.txt")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                prompts[i] = f.read().strip()
    return prompts


_BIND_PROMPTS = load_bind_prompts(BIND_PROMPTS_DIR)

BIND_PATTERN = re.compile(r"\[?bind(\d{1,2})\]?(?:\s+(team|all))?", re.IGNORECASE)


def check_bind_command(line: str):
    match = BIND_PATTERN.search(line)
    if not match:
        return None
    slot = int(match.group(1))
    if slot < 1 or slot > 10:
        return None
    chat_type = (match.group(2) or "all").lower()
    prompt = _BIND_PROMPTS.get(slot)
    if not prompt:
        return None
    return slot, chat_type, prompt


def openrouter_quick_prompt(prompt: str) -> str:
    data = {
        "model": "deepseek/deepseek-chat-v3-0324",
        "messages": [{"role": "system", "content": prompt}],
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
        logger.exception("OpenRouter quick prompt failed: %s", exc)
        return ""


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


def openrouter_interact(user: str, message: str, prefix: str = ""):
    logger.debug("Sending to OpenRouter: %s -> %s", user, message)
    prefix_text = f"{prefix} " if prefix else ""
    debug_log(f"> {prefix_text}{user}: {message}")
    message = f"{prefix_text}{user}: {message}"

    global conversation_history
    conversation_history.append({"role": "user", "content": message})
    _trim_history()

    messages = list(conversation_history)
    data = {
        "model": "deepseek/deepseek-chat-v3-0324",
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
        conversation_history.append({"role": "assistant", "content": reply})
        _trim_history()
        logger.debug("Received from OpenRouter: %s", reply)
        debug_log(f"< {reply}")
        return reply
    except Exception as exc:
        logger.exception("OpenRouter request failed: %s", exc)
        if conversation_history:
            conversation_history.pop()
        return ""


def reset_history():
    conversation_history.clear()
    conversation_history.append({"role": "system", "content": SYSTEM_PROMPT})
    debug_log("[INFO] history reset")


def show_history():
    messages = list(conversation_history)
    if messages and messages[0].get("role") == "system":
        messages = messages[1:]
    messages = list(reversed(messages))
    text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    print(text)
    debug_log(text)


def main():
    logfile = None
    username = ""
    message = ""
    game = cp.detect_game()
    logger.debug("Detected game: %s", game)

    

    dpg.create_context()
    dpg.create_viewport(title='Chat-Strike', width=600, height=600)

    if sys.platform.startswith('win'):
        # Попробуем подобрать стандартный моноширинный шрифт с поддержкой кириллицы
        win_dir = os.environ.get('WINDIR', 'C:\\Windows')
        for fname in ("consola.ttf", "lucon.ttf", "cour.ttf"):
            font_path = os.path.join(win_dir, "Fonts", fname)
            if os.path.exists(font_path):
                with dpg.font_registry():
                    with dpg.font(font_path, 14) as default_font:
                        dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)
                    dpg.bind_font(default_font)
                break
        else:
            font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSansMono.ttf")
            if os.path.exists(font_path):
                with dpg.font_registry():
                    with dpg.font(font_path, 14) as default_font:
                        dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)
                    dpg.bind_font(default_font)
    else:
        font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSansMono.ttf")
        if os.path.exists(font_path):
            with dpg.font_registry():
                with dpg.font(font_path, 14) as default_font:
                    dpg.add_font_range_hint(dpg.mvFontRangeHint_Cyrillic)
                dpg.bind_font(default_font)

    with dpg.window(label="Chat-Strike", width=600, height=250, tag="Chat-Strike"):
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
        dpg.add_button(label="Reset history", callback=lambda: reset_history())
        dpg.add_button(label="Show history", callback=lambda: show_history())

    with dpg.window(label="Debug Console", width=600, height=300, pos=(0,260), tag="Debug Console"):
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
                line = line.strip()
                if not line:
                    continue
                logger.debug(line)
                bind_data = check_bind_command(line)
                if bind_data:
                    _slot, chat_type, prompt = bind_data
                    reply = openrouter_quick_prompt(prompt)
                    if reply:
                        key = cp.TEAM_CHAT_KEY if chat_type == "team" else cp.CHAT_KEY
                        cp.sim_key_presses(reply, key)
                        pyperclip.copy(reply)
                    continue

                parsed = cp.parse_log(game, line)
                if parsed is None:
                    continue
                username = parsed.username
                message = parsed.message
                chat_type = parsed.chat_type
                prefix = parsed.prefix
                display_name = cp.sanitize_username(username)


                if username and message:
                    #print(f"[DEBUG] {username}: {message}:")
                    # This way we prevent chat-gpt from talking to itself
                    logger.debug("Username: %s", username)
                    checked_username = cp.sanitize_username(username).lower()
                    blacklisted = any(
                        checked_username == b.lower() for b in cp.BLACKLISTED_USERNAMES
                    )

                    if (not blacklisted) or ("[test]" in message):
                        reply = openrouter_interact(display_name, message, prefix)
                        if reply:
                            if reply.strip() == "[IGNORE]":
                                logger.debug("[IGNORE] received, skipping keystrokes")
                            else:
                                key = cp.TEAM_CHAT_KEY if chat_type == "team" else cp.CHAT_KEY
                                cp.sim_key_presses(reply, key)
                                pyperclip.copy(reply) # Копируем ответ в буфер обмена
                        else:
                            logger.debug("Empty reply, skipping keystrokes")
                            debug_log("[INFO] Empty reply")
                    else:
                        logger.debug("Message ignored from blacklisted user") 
                else:
                    continue
    
    if logfile:
        logfile.close()
    dpg.destroy_context()

if __name__ == "__main__":
    main()
