# chat-strike

Inspired by Isaac Duarte's https://github.com/Isaac-Duarte/source_cmd_parser this script integrates chat-gpt into Counter-Strike 2 (Or any GldSource, Source/2 game) allowing people in the same server to interact with it.

## Requirements

- 64bit Windows
- Python 3.11+ < 3.12

It is highly recommended that you possess an OpenRouter API key, but it is not necessary unless you're attempting to use `/chat.py`

## Usage

First, you must enable console logging, to achieve this you can do one of the following:

+ For CS:S type the following into the in-game developer console: ``con_logfile <filename>; con_timestamp 1`` (you must do this each time you open the game)

+ For CS2 or HL add `-condebug` to your game's launch options on Steam.

If you used the latter option your path probably looks something like this: ``C:\Program Files\SteamLibrary\steamapps\common\Counter-Strike Global Offensive\game\csgo\console.log``

+ Open `config.ini` и впишите `gameconlogpath`. Логи CS2 теперь сохраняются в UTF-8,
поэтому `conlogencoding` по умолчанию установлен в `utf-8`. Если ваш клиент пишет
лог в другой кодировке (например, `cp1251`), укажите её в этом поле. Здесь же можно
задать список ников в `blacklisted_usernames` и свой OpenRouter API ключ.

Now you can do `python chat.py`. В интерфейсе появилась отладочная консоль, куда дублируются ваши сообщения и ответы бота. Если кириллица отображается как `???`, проверьте `fonts/DejaVuSansMono.ttf` и убедитесь, что файл на месте.

The system prompt for ChatGPT is stored in `system_prompt.txt`. Вы можете
отредактировать этот файл, чтобы изменить поведение бота.


### Example

```python
import conparser as cp

game = cp.detect_game()

with open(cp.CON_LOG_FILE_PATH, encoding=cp.CON_LOG_ENCODING) as logfile:
        logfile.seek(0, 2)  # Point cursor to the end of console.log to retrieve latest line
        while True:
            line = cp.rt_file_read(logfile)
            if not line:
                continue
            print(cp.parse_log(game, line))  # ParsedLog(username, message, chat_type, prefix, is_dead)
```


## How it works

Very similar to Isaac's framework this script reads the console log file. New entries are parsed and sent to chat-gpt to generate a response which is then sent back in game chat through simulated keystrokes.
Now the bot pastes messages from the clipboard to avoid stray characters when movement keys are held.

If messages do not appear in game, try running the script with administrator rights. Some games ignore simulated key presses without the proper permissions.
If the LLM replies with `[IGNORE]`, nothing will be sent to the in-game chat.

## Bind prompts

В папке `bind_prompts` лежат файлы `bind1.txt` – `bind10.txt`.
В каждом напишите системный промпт для быстрого сообщения.

Горячие клавиши настраиваются в `config.ini` в секции `[HOTKEYS]`.
Пример по умолчанию:

```
[HOTKEYS]
f3 = [bind1 all]
f4 = [bind2 all]
...
```

Строка вида `[bind1 team]` задаёт слот файла с промптом и тип чата (`team` или `all`).
При нажатии соответствующей клавиши бот отправит сгенерированный текст в выбранный чат без учёта истории.
