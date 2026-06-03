# Деплой сайта на PythonAnywhere

Пошаговая инструкция, как выложить сайт расписания в интернет бесплатно.
Сайт будет доступен по адресу `https://ВАШЛОГИН.pythonanywhere.com`.

---

## Шаг 1. Регистрация

1. Зайди на https://www.pythonanywhere.com
2. Нажми **Pricing & signup** → выбери **Create a Beginner account** (бесплатный)
3. Подтверди email, войди в аккаунт

---

## Шаг 2. Загрузка файлов проекта

Нужно загрузить эти файлы:
- `app.py`
- `Rozklad.html`
- `admin.html`
- `requirements.txt`
- `schedule.db` (твоя база с уже введённым расписанием!)

**Способ А — через интерфейс (проще):**
1. На PythonAnywhere открой вкладку **Files**
2. В разделе Directories создай папку: введи `myschedule` и нажми **New directory**
3. Зайди в папку `myschedule`
4. Кнопкой **Upload a file** загрузи по очереди все файлы выше

**Способ Б — через консоль (если файлов много):**
1. Вкладка **Consoles** → **Bash**
2. Если проект на GitHub: `git clone https://github.com/ТВОЙ_РЕПО.git myschedule`

> Папка `schedules/` с Excel-файлами и скрипты импорта на сервер НЕ нужны — только файлы из списка выше.

---

## Шаг 3. Установка зависимостей

1. Вкладка **Consoles** → открой **Bash**
2. Выполни:
   ```
   pip3 install --user flask
   ```
   (gunicorn на PythonAnywhere не нужен — у него свой сервер)

---

## Шаг 4. Создание веб-приложения

1. Вкладка **Web** → **Add a new web app** → **Next**
2. Выбери **Manual configuration** (НЕ "Flask"!) → выбери **Python 3.10** → **Next**
3. Дождись создания

---

## Шаг 5. Настройка WSGI

1. На вкладке **Web** найди раздел **Code** → ссылка **WSGI configuration file**
   (что-то вроде `/var/www/ВАШЛОГИН_pythonanywhere_com_wsgi.py`)
2. Нажми на неё — откроется редактор
3. **Удали всё** содержимое и вставь это (из файла `wsgi_pythonanywhere.py`):

   ```python
   import sys
   project_home = "/home/ВАШЛОГИН/myschedule"
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   import os
   os.environ["SECRET_KEY"] = "тут-длинный-случайный-набор-символов"
   os.environ["ADMIN_USERNAME"] = "admin"
   os.environ["ADMIN_PASSWORD"] = "придумай-надёжный-пароль"

   from app import app as application
   ```

4. **Замени** `ВАШЛОГИН` на свой логин PythonAnywhere (в двух местах не нужно — только в пути)
5. **Замени** SECRET_KEY и пароль на свои
6. Нажми **Save** (зелёная кнопка вверху)

---

## Шаг 6. Запуск

1. Вернись на вкладку **Web**
2. Нажми большую зелёную кнопку **Reload**
3. Открой `https://ВАШЛОГИН.pythonanywhere.com` — сайт работает!
4. Админка: `https://ВАШЛОГИН.pythonanywhere.com/admin`

---

## Важные моменты

- **База данных сохраняется.** Файл `schedule.db` лежит на постоянном диске —
  данные не пропадут при перезапуске. Это главное преимущество PythonAnywhere.
- **Бесплатный аккаунт** работает постоянно, но раз в 3 месяца просит нажать
  кнопку "продлить" (приходит письмо на почту).
- **Сменить пароль админки** — поменяй `ADMIN_PASSWORD` в WSGI-файле и нажми Reload.
- **Обновить код** — загрузи новый `app.py`/HTML через Files и нажми Reload.

---

## Если что-то не работает

1. Вкладка **Web** → раздел **Log files** → открой **Error log** — там видна причина.
2. Частая ошибка — неправильный путь в WSGI (`project_home`). Проверь что
   папка называется именно `myschedule` и логин указан верно.
