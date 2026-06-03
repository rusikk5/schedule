# ---------------------------------------------------------------------------
# Пример WSGI-конфига для PythonAnywhere.
#
# Это НЕ запускается локально. Содержимое нужно скопировать в WSGI-файл
# на PythonAnywhere (вкладка Web → "WSGI configuration file").
#
# Замените YOURUSERNAME на ваше имя пользователя PythonAnywhere.
# ---------------------------------------------------------------------------

import sys

# 1. Путь к папке с проектом (там где лежит app.py)
project_home = "/home/YOURUSERNAME/myschedule"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 2. Постоянные настройки приложения.
#    SECRET_KEY ОБЯЗАТЕЛЬНО задать постоянным — иначе при каждом
#    перезапуске сайта будет слетать вход в админку.
import os
os.environ["SECRET_KEY"] = "ЗАМЕНИ-НА-СВОЙ-ДЛИННЫЙ-СЛУЧАЙНЫЙ-КЛЮЧ"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "ЗАМЕНИ-НА-СВОЙ-ПАРОЛЬ"

# 3. Импортируем Flask-приложение. PythonAnywhere ищет переменную application.
from app import app as application
