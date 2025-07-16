import requests
import logging

import dearpygui.dearpygui as dpg
import conparser as cp

logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


OPENROUTER_API_KEY = cp.config['SETTINGS']['openrouterapikey']

class Status():
    running = False


def set_status(sender, app_data, user_data):
    if Status.running == False:
        dpg.configure_item("start_button", label="Stop")
        dpg.set_value(user_data, "Running: True")
        logger.debug("Bot started")

    elif Status.running == True:
        dpg.configure_item("start_button", label="Start")
        dpg.set_value(user_data, "Running: False")
        logger.debug("Bot stopped")

    Status.running = not Status.running


def save_config():
    cp.config['SETTINGS']['blacklisted_usernames'] = dpg.get_value("usernames")
    cp.config['SETTINGS']['gameconlogpath'] = dpg.get_value("conlog")
    cp.config['SETTINGS']['chatkey'] = dpg.get_value("chat_keybind")
    with open(cp.CONFIG_FILE, 'w') as configfile:
        cp.config.write(configfile)
    logger.debug("Configuration saved")


def openrouter_interact(user: str, message: str, content="Ты - игрок в кс2. Ограничивай ответ до 120 символов. Ты общаешься с другими игроками как из своей так и с противоположной команды. Учитывай что не все сообщения адресуются тебе, иногда они нейтральные. Не будь слишком дружелюбным, будь сдержанным и максимально коротким. Не говори о том что ты ИИ и пытайся доказать что ты реальный игрок. Будь саркастичным, или токсичным если игроки также агрессивны, но если нет - будь нейтральным или дружелюбным. Пиши с маленькой буквы. Не будь слишком изобретательным, будь максимально стандартным СНГ игроком в кс или доту. Отвечай максимально коротко на формальные фразы типа GG или glhf, буквально пару слов. Используй маты."):
    logger.debug("Sending to OpenRouter: %s -> %s", user, message)
    message = f"I'm {user}, {message}"

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
    dpg.create_viewport(title='Chat-Strike', width=600, height=300)

    with dpg.window(label="Chat-Strike", width=600, height=300, tag="Chat-Strike"):
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



    dpg.set_primary_window("Chat-Strike", True)
    dpg.setup_dearpygui()
    dpg.show_viewport()

    with dpg.handler_registry():
        dpg.add_key_press_handler(dpg.mvKey_Add, callback=set_status, user_data=status_text)

    if cp.config['SETTINGS']['gameconlogpath'] != None:
        logfile = open(cp.CON_LOG_FILE_PATH, encoding='utf-8')
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
                username, message = cp.parse_log(game, line)

                if username and message:
                    #print(f"[DEBUG] {username}: {message}:")
                    # This way we prevent chat-gpt from talking to itself
                    logger.debug("Username: %s", username)
                    if username not in cp.BLACKLISTED_USERNAMES:
                        reply = openrouter_interact(username, message)
                        if reply:
                            cp.sim_key_presses(reply)
                        else:
                            logger.debug("Empty reply, skipping keystrokes")
                    else:
                        logger.debug("Message ignored from blacklisted user")
                else:
                    continue
    
    if logfile:
        logfile.close()
    dpg.destroy_context()








if __name__ == "__main__":
    main()
