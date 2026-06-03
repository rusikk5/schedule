import hmac
import os
import re
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for, send_from_directory

BASE_DIR = Path(__file__).parent
DB_PATH = Path(os.environ.get("DB_PATH", str(BASE_DIR / "schedule.db")))

TIMES_COUNT = 7
DAYS_COUNT = 6

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "kfu2025")

# ---------------------------------------------------------------------------
# Начальные данные (сидирование БД при первом запуске)
# ---------------------------------------------------------------------------

def detect_study_form(name: str) -> str:
    return "заочная" if re.search(r"[-/]з[-/]|[-/]зо[-/]", name) else "очная"


def detect_degree(name: str) -> str:
    if re.search(r"[-/]м[-/]", name): return "магистратура"
    if re.search(r"[-/]с[-/]", name): return "специалитет"
    return "бакалавриат"


def detect_course(name: str) -> int:
    m = re.search(r"-(\d{2})\d", name)
    if not m:
        return 0
    enroll = 2000 + int(m.group(1))
    now = datetime.now()
    acad_start = now.year if now.month >= 9 else now.year - 1
    course = acad_start - enroll + 1
    return course if 1 <= course <= 6 else 0


SEED_GROUP_NAMES = [
    "ИВТ-б-о-251(1)", "ИВТ-б-о-251(2)", "ИВТ-б-о-252(1)", "ИВТ-б-о-252(2)",
    "ИВТ-б-о-241(1)", "ИВТ-б-о-241(2)", "ИВТ-б-о-242(1)", "ИВТ-б-о-242(2)",
    "ИВТ-б-о-232(1)", "ИВТ-б-о-232(2)", "ИВТ-б-о-231(1)", "ИВТ-б-о-231(2)",
    "ПИ-б-о-251(1)", "ПИ-б-о-251(2)", "ПИ-б-о-252(1)", "ПИ-б-о-252(2)",
    "ПИ-б-о-241(1)", "ПИ-б-о-241(2)", "ПИ-б-о-242(1)", "ПИ-б-о-242(2)",
    "ПИ-б-о-231(1)", "ПИ-б-о-231(2)", "ПИ-б-о-232(1)", "ПИ-б-о-232(2)",
    "ПИ-б-о-233(1)", "ПИ-б-о-233(2)",
    "ПИинф-б-о-251(1)", "ПИинф-б-о-251(2)",
    "АТП-б-о-251(1)", "АТП-б-о-251(2)", "АТП-б-о-231(1)", "АТП-б-о-231(2)",
    "САУ-б-о-251(1)", "САУ-б-о-251(2)",
    "СА-б-о-241(1)", "СА-б-о-241(2)", "СА-б-о-231(1)", "СА-б-о-231(2)",
    "МАТ-б-о-251(1)", "МАТ-б-о-251(2)",
    "ПМИ-б-о-251(1)", "ПМИ-б-о-251(2)", "ПМИ-б-о-252(1)", "ПМИ-б-о-252(2)",
    "МАТ-б-о-241(1)", "МАТ-б-о-241(2)",
    "ПМИ-б-о-241(1)", "ПМИ-б-о-241(2)", "ПМИ-б-о-242(1)", "ПМИ-б-о-242(2)",
    "МАТ-б-о-231(1)", "МАТ-б-о-231(2)",
    "ПМИ-б-о-231(1)", "ПМИ-б-о-231(2)",
    "ПМ-б-о-221(1)", "ПМ-б-о-221(2)",
    "Рф-б-о-251(1)", "Рф-б-о-251(2)", "Ф-б-о-251(1)", "Ф-б-о-251(2)",
    "ТФ-б-о-251(1)", "ТФ-б-о-251(2)",
    "Рф-б-о-241(1)", "Рф-б-о-241(2)", "Ф-б-о-241(1)", "Ф-б-о-241(2)",
    "ТФ-б-о-241(1)", "ТФ-б-о-241(2)",
    "Рф-б-о-231(1)", "Рф-б-о-231(2)", "Ф-б-о-231(1)", "Ф-б-о-231(2)",
    "ТФ-б-о-231(1)", "ТФ-б-о-231(2)",
    "Рф-б-о-221", "Ф-б-о-221(1)", "Ф-б-о-221(2)",
    "ТФ-б-о-221(1)", "ТФ-б-о-221(2)",
    "ПМИ-б-о-221(1)", "ПМИ-б-о-221(2)", "ПМИ-б-о-222(1)", "ПМИ-б-о-222(2)",
    "МАТ-б-о-221(1)", "МАТ-б-о-221(2)",
    "ЭЭ-б-о-251(1)", "ЭЭ-б-о-251(2)", "ЭЭ-б-о-241(1)", "ЭЭ-б-о-241(2)",
    "ЭЭ-б-о-231(1)", "ЭЭ-б-о-231(2)", "ЭЭ-б-о-221(1)", "ЭЭ-б-о-221(2)",
    "ИТС-б-о-251(1)", "ИТС-б-о-251(2)", "ИТС-б-о-241(1)", "ИТС-б-о-241(2)",
    "КБ-с-о-251(1)", "КБ-с-о-251(2)", "КБ-с-о-241(1)", "КБ-с-о-241(2)",
]

SEED_SUBJECTS = [
    "Алгоритмы и методы вычислений", "Анализ и тестирование программного обеспечения",
    "Базы данных", "Верификация, аттестация и качество программного обеспечения",
    "Высшая математика", "Дискретная математика", "Иностранный язык",
    "Иностранный язык (немецкий)", "Иностранный язык (французский)",
    "Искусственный интеллект: технологии и человек", "История России",
    "История религий России", "Компьютерные системы", "Компьютерные сети",
    "Математическое и компьютерное моделирование", "Междисциплинарная курсовая работа",
    "Микропроцессорные системы", "Надежность компьютерных систем", "Обработка сигналов",
    "Основы военной подготовки", "Основы российской государственности",
    "Основы социального проектирования", "Параллельные и распределенные вычисления",
    "Прикладная теория цифровых автоматов", "Системное администрирование",
    "Системное программное обеспечение", "Системный анализ и исследование операций",
    "Системы управления базами данных", "Современные базы данных",
    "Современные технологии программирования", "Теория автоматов и формальных языков",
    "Технологии и процесс разработки программного обеспечения",
    "Управление разработкой командных программных проектов", "Физика",
    "Физическая культура", "Физическая культура и спорт",
    "Цифровые технологии в профессиональной сфере", "Человек и право",
    "Экономика личных решений", "Электроника",
    "Учебная практика, проектно-технологическая", "Проектирование бизнес-процессов",
    "Корпоративные ИС", "Языки SQL", "Математическая логика и теория алгоритмов",
    "Теория и технологии программирования на языках высокого уровня",
    "Экономическая культура и финансовая грамотность",
    "Метрология, стандартизация и сертификация", "Материаловедение",
    "Интеллектуальный анализ данных", "Оборудование автоматизированного производства",
    "Проектирование киберфизических систем управления",
    "Управление качеством в промышленности",
    "Технологическая оснастка автоматизированного производства",
    "Системы автоматизированного проектирования технологических комплексов и систем",
    "Имитационное моделирование процессов и систем",
    "Концепции современного естествознания", "Проектирование web-приложений",
    "Web-программирование", "Риторика", "Эффективность информационных систем",
    "Дискретный анализ", "Безопасность природной среды и жизнедеятельности человека",
    "Проектирование информационных систем",
    "Основы организации теоретических и экспериментальных исследований",
    "Вычислительные методы в решении инженерных задач",
    "Проектирование автоматических устройств", "Теория автоматического управления",
    "Управление в организационных системах",
    "Математические методы и модели системного анализа",
    "Теория аналитических функций и операционное исчисление",
    "Технологии проектирования и администрирования систем автоматизированной обработки данных и управления",
    "Производственная практика, технологическая",
    "Вычислительная алгебра в анализе данных",
    "Введение в математическое программирование",
    "Компьютерные методы элементарной математики",
    "Линейная алгебра", "Математический анализ", "Системное программирование",
    "Вычислительная геометрия", "Дифференциальные уравнения", "Функциональный анализ",
    "Алгебра и теория чисел", "Математические основы машинного обучения",
    "Информационная безопасность", "Языки программирования для анализа данных",
    "Статистические методы в машинном обучении",
    "Веб-ресурсы и серверные технологии", "Логическое и функциональное программирование",
    "Комплексный анализ", "Методы оптимизации в машинном обучении",
    "Анализ временных рядов", "Численные методы",
    "Молекулярная физика и термодинамика", "Теоретические основы электротехники",
    "Электричество и магнетизм", "Теория вероятностей и математическая статистика",
    "Электродинамика", "Метрология и физико-технические измерения",
    "Радиоэлектроника", "Метрология", "Радиотехнические цепи и сигналы",
    "Цифровая схемотехника", "Физика полупроводников", "Теория колебаний",
    "Термодинамика и статистическая физика", "Промышленная электроника",
    "Микропроцессорная и микрокомпьютерная техника", "Полупроводниковая электроника",
    "Антенны и распространение радиоволн",
    "Основы метрологии и информационно-измерительная техника",
    "Электрооборудование и автоматика", "Электрические машины",
    "Энергосбережение и эффективность", "Теория автоматического регулирования",
    "Надежность энергосистем", "Электроэнергетические системы и сети",
    "Электрические станции и подстанции", "Электротехника", "Инженерная графика",
    "Техническая электродинамика и распространение радиоволн", "Схемотехника",
    "Компьютерное моделирование", "Общая теория связи",
    "Кроссплатформенное программирование", "Методы и алгоритмы теории графов",
    "Производственная практика, преддипломная",
    "Производственная практика, научно-исследовательская работа",
    "Научный семинар", "Научно-исследовательский семинар",
]

SEED_TEACHERS = [
    "Абибуллаев М.С. (доц.)", "Аджиблаева Э.С. (ст.пр.)", "Алексеев К.Н. (проф.)",
    "Арбузова Н.В. (ст.пр.)", "Арсеничев С.П. (доц.)", "Биленко Г.Р. (ст.пр.)",
    "Слепченко С.П.", "Блонская Л.Л.", "Валуев Д.Г. (ст.пр.)", "Галушко В.И.",
    "Горская И.Ю. (ст.пр.)", "Епишкин И.В.", "Зойкин Е.С.", "Зуев С.А. (доц.)",
    "Ислямов Р.И. (доц.)", "Кислицына Н.Н. (доц.)", "Клинцова М.Н. (доц.)",
    "Ковальчук Е.С.", "Козлова М.Г. (доц.)", "Комар А.А. (ст.пр.)",
    "Кондратенко А.А. (доц.)", "Космачёв О.А. (проф.)", "Крюков С.А.",
    "Кудряшов Ю.Л. (доц.)", "Лосев М.Ю. (доц.)", "Ляшко С.Д. (ст.пр.)",
    "Манаев А.Ю. (доц.)", "Маргасов В.С. (ас.)", "Машьянова Е.Е. (ст.пр.)",
    "Мельниченко Т.В. (доц.)", "Милюков В.В. (доц.)", "Михерский М.Р. (ас.)",
    "Михерский Р.М. (доц.)", "Парменов О.И. (доц.)", "Руденко М.А. (доц.)",
    "Смирнова С.И. (доц.)", "Солдатов М.А. (доц.)", "Сосновский Ю.В. (доц.)",
    "Сычевская А.С. (ст.пр.)", "Таран Е.П. (доц.)", "Тимофеева С.В. (доц.)",
    "Тимофеева С.Н.", "Ткаченко Н.М.", "Тышкевич Д.Л. (доц.)",
    "Филиппов Д.М. (доц.)", "Халилов С.И. (ас.)", "Холодняк О.С. (ст.пр.)",
    "Чабанов В.В. (ст.пр.)", "Чачиев Д.Р. (ас.)", "Черныш Д.П. (ст.пр.)",
    "Черныш И.В. (ст.пр.)", "Шевченко В.И. (доц.)", "Шестакова Е.С. (доц.)",
    "Юферев В.С.", "Иванов С.В. (доц.)", "Иванова Е.В. (ас.)",
    "Круликовский А.П. (доц.)", "Ремесник Е.С. (доц.)", "Вронский Б.М. (доц.)",
    "Викулин Д.В. (доц.)", "Дементьев М.Ю. (ст.пр.)", "Друзин Р.В. (доц.)",
    "Енина А.А. (ас.)", "Ермоленко О.В. (доц.)", "Литвинова Г.В. (доц.)",
    "Нудьга А.А. (доц.)", "Польской И.П. (доц.)", "Степанова Е.И. (ст.пр.)",
    "Степанов А.В. (проф.)", "Скиданчук А.Г. (ст.пр.)", "Цапик Д.К. (ас.)",
    "Адельсеитова А.Б. (доц.)", "Валюх И.Ф. (ас.)", "Герасимова С.В. (проф.)",
    "Грибенко Е.Н. (доц.)", "Калиновский П.С. (ст.пр.)", "Кудрявцев А.Ю.",
    "Лапин Б.П. (доц.)", "Миньчик С.С.", "Соченко Ю.А. (ст.пр.)",
    "Фабрина А.В. (пр.)", "Анафиев А.С. (доц.)", "Анашкин О.В. (проф.)",
    "Баран И.В. (доц.)", "Белозуб В.А. (ст.пр.)", "Блыщик В.Ф. (доц.)",
    "Богосян М.В. (ст.пр.)", "Бридко Т.В. (доц.)", "Водолажская Л.Н. (ст.пр.)",
    "Габриелян Т.О. (доц.)", "Германчук М.С. (доц.)", "Гончарова О.Н. (проф.)",
    "Дядичев В.В. (проф.)", "Дюличева Ю.Ю. (доц.)", "Егоров Ю.А. (доц.)",
    "Иващенко А.А. (ас.)", "Ильченко А.В. (ст.пр.)", "Илясова Ю.В. (доц.)",
    "Козлов А.И. (доц.)", "Коротченко Ю.М. (проф.)", "Косова Е.А. (доц.)",
    "Кузьменко Е.М. (доц.)", "Лукьянова Е.А. (доц.)", "Ляшко А.Д. (ст.пр.)",
    "Макаров О.О. (ст.пр.)", "Махина Г.А. (ст.пр.)", "Менюк С.Г. (доц.)",
    "Миненко Н.А. (доц.)", "Муратов М.А. (проф.)", "Пашкова Ю.С. (доц.)",
    "Польская С.И. (доц.)", "Пономарёва А.В. (доц.)", "Руденко Л.И.",
    "Рудницкий О.И. (доц.)", "Савчук О.С.", "Старков П.А. (доц.)",
    "Стонякин Ф.С. (проф.)", "Стус Е.А. (ст.пр.)", "Терновский В.А. (доц.)",
    "Третьяков Д.В. (доц.)", "Хазова Ю.А. (доц.)", "Цветков Д.О. (доц.)",
    "Чехов В.В. (доц.)", "Шармоянц А.Н. (доц.)", "Юсупова О.В. (ст.пр.)",
    "Якубова А.Р. (доц.)", "Бутрим В.И. (доц.)", "Варагушин П.А. (ст.пр.)",
    "Генералова Е.Н. (ас.)", "Горбованов А.И. (доц.)", "Дзедолик И.В. (проф.)",
    "Ефимова В.М.", "Зарапин О.В. (доц.)", "Кувшинов В.М. (доц.)",
    "Лагунов И.М. (ст.пр.)", "Леляков А.П. (проф.)", "Луговской Н.В. (ст.пр.)",
    "Мазинов А.С. (доц.)", "Михайлова Т.В. (доц.)", "Могиленец Ю.А. (доц.)",
    "Наухацкий И.А. (ас.)", "Никифоров И.Р.", "Новикова Е.А. (доц.)",
    "Полетаев Д.А. (доц.)", "Рыбась А.Ф. (доц.)", "Рябушкин Д.С. (доц.)",
    "Томилин С.В. (доц.)", "Томилина О.А. (ас.)", "Фридман Ю.А. (проф.)",
    "Шевченко Е.В. (ст.пр.)", "Яворский М.А. (проф.)", "Ярыгина Е.А. (ас.)",
    "Яценко А.В. (доц.)", "Абдурахманов Р.Н. (ас.)", "Асанов М.М. (доц.)",
    "Бекиров Э.А. (проф.)", "Бородачева Т.И. (ст.пр.)", "Воскресенская С.Н. (доц.)",
    "Муртазаев Э.Р. (доц.)", "Попов С.С. (ст.пр.)", "Тынчерова Э.Л. (доц.)",
    "Фурсенко Н.А. (ст.пр.)", "Арсеничева М.С. (ст.пр.)", "Бондаренко Д.В. (ст.пр.)",
    "Мелешко А.Г. (ст.пр.)", "Старосек А.В. (ст.пр.)", "Фитаев И.Ш. (доц.)",
    "Кузьмин Н.Н. (доц.)",
]

SEED_ROOMS = [
    "8А пр.Вернадского 4", "9А пр.Вернадского 4", "11А пр.Вернадского 4",
    "16А пр.Вернадского 4", "18А пр.Вернадского 4", "20А пр.Вернадского 4",
    "34А пр.Вернадского 4", "107А пр.Вернадского 4", "113А пр.Вернадского 4",
    "115А пр.Вернадского 4", "117А пр.Вернадского 4", "119А пр.Вернадского 4",
    "120А пр.Вернадского 4", "121А пр.Вернадского 4", "123А пр.Вернадского 4",
    "124А пр.Вернадского 4", "201В пр.Вернадского 4", "209А пр.Вернадского 4",
    "211А пр.Вернадского 4", "215А пр.Вернадского 4", "215Б пр.Вернадского 4",
    "219А пр.Вернадского 4", "224А пр.Вернадского 4", "301А пр.Вернадского 4",
    "301В пр.Вернадского 4", "302А пр.Вернадского 4", "302В пр.Вернадского 4",
    "303А пр.Вернадского 4", "304А пр.Вернадского 4", "305В пр.Вернадского 4",
    "306В пр.Вернадского 4", "308А пр.Вернадского 4", "309А пр.Вернадского 4",
    "309В пр.Вернадского 4", "311В пр.Вернадского 4", "312В пр.Вернадского 4",
    "314В пр.Вернадского 4", "315А пр.Вернадского 4", "315Б пр.Вернадского 4",
    "319А пр.Вернадского 4", "321Б пр.Вернадского 4", "323А пр.Вернадского 4",
    "335А пр.Вернадского 4", "401В пр.Вернадского 4", "405В пр.Вернадского 4",
    "406В пр.Вернадского 4", "409В пр.Вернадского 4", "411Б пр.Вернадского 4",
    "411В пр.Вернадского 4", "412В пр.Вернадского 4", "413В пр.Вернадского 4",
    "414В пр.Вернадского 4", "426Б пр.Вернадского 4", "500Б пр.Вернадского 4",
    "525Б пр.Вернадского 4", "531Б пр.Вернадского 4",
    "6А пр.Вернадского 4", "22А пр.Вернадского 4", "27А пр.Вернадского 4",
    "214А пр.Вернадского 4", "306А пр.Вернадского 4", "316А пр.Вернадского 4",
    "Ул. Ленина, 11 ауд. 3", "Ул. Ленина, 11 ауд. 7",
    "107 ул.Павленко 3", "407 ул.Павленко 3",
    "212/3 ул.Киевская 181", "213/3 ул.Киевская 181", "219/3 ул.Киевская 181",
    "220/3 ул.Киевская 181", "302а/3 ул.Киевская 181", "308/3 ул.Киевская 181",
    "спорт зал ТА",
]

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())
app.permanent_session_lifetime = timedelta(hours=8)

LOGIN_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Вход — Расписание КФУ</title>
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{min-height:100vh;display:grid;place-items:center;
      background:linear-gradient(180deg,#f9fbff 0%,#eef2ff 100%);
      font-family:'Nunito',system-ui,sans-serif;color:#0f1d40}
    .card{background:#fff;border-radius:28px;padding:48px 40px;
      box-shadow:0 24px 60px rgba(15,29,64,.10);width:100%;max-width:400px;margin:24px}
    .logo{width:56px;height:56px;border-radius:14px;
      background:linear-gradient(135deg,#2563c7,#2f7ae3);color:#fff;
      font-weight:900;font-size:1.1rem;display:grid;place-items:center;margin:0 auto 20px}
    h1{text-align:center;font-size:1.4rem;font-weight:800;margin-bottom:6px}
    .sub{text-align:center;color:#6b7794;font-size:.95rem;margin-bottom:32px}
    label{display:block;font-weight:700;font-size:.88rem;color:#6b7794;margin-bottom:6px}
    input[type=text],input[type=password]{
      width:100%;padding:14px 16px;border:1px solid rgba(15,29,64,.12);
      border-radius:14px;font-size:1rem;font-family:inherit;color:#0f1d40;
      background:#f4f7ff;margin-bottom:18px;outline:none;transition:border-color .2s}
    input:focus{border-color:#2f7ae3;background:#fff}
    .error{background:#fff0f0;border-left:4px solid #e03;color:#c00;
      padding:10px 14px;border-radius:8px;font-size:.9rem;font-weight:600;margin-bottom:18px}
    button{width:100%;padding:16px;background:#2f7ae3;color:#fff;border:none;
      border-radius:14px;font-size:1rem;font-weight:800;font-family:inherit;
      cursor:pointer;transition:background .2s}
    button:hover{background:#2563c7}
    .back{text-align:center;margin-top:18px;font-size:.9rem}
    .back a{color:#2f7ae3;text-decoration:none;font-weight:700}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">КФУ</div>
    <h1>Вход в админ-панель</h1>
    <p class="sub">Расписание занятий КФУ</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST" autocomplete="on">
      <label for="u">Логин</label>
      <input type="text" id="u" name="username" autocomplete="username" required>
      <label for="p">Пароль</label>
      <input type="password" id="p" name="password" autocomplete="current-password" required>
      <button type="submit">Войти</button>
    </form>
    <div class="back"><a href="/">← На главную</a></div>
  </div>
</body>
</html>"""

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def safe_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS faculties (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            short_name TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL UNIQUE,
            faculty_id INTEGER REFERENCES faculties(id),
            study_form TEXT,
            course     INTEGER,
            degree     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id   INTEGER NOT NULL,
            week       TEXT    NOT NULL CHECK (week IN ('week1', 'week2')),
            row_index  INTEGER NOT NULL CHECK (row_index >= 0 AND row_index < 7),
            col_index  INTEGER NOT NULL CHECK (col_index >= 0 AND col_index < 6),
            value      TEXT    NOT NULL DEFAULT '',
            UNIQUE (group_id, week, row_index, col_index),
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()


def ensure_group(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO groups(name) VALUES(?)", (name,))
    conn.commit()
    return conn.execute("SELECT id FROM groups WHERE name = ?", (name,)).fetchone()["id"]


def get_groups(conn: sqlite3.Connection) -> list[str]:
    return [r["name"] for r in conn.execute("SELECT name FROM groups ORDER BY name").fetchall()]


def get_schedule_matrix(conn: sqlite3.Connection, group_name: str, week: str) -> list[list[str]]:
    matrix = [["" for _ in range(DAYS_COUNT)] for _ in range(TIMES_COUNT)]
    row = conn.execute("SELECT id FROM groups WHERE name = ?", (group_name,)).fetchone()
    if not row:
        return matrix
    for lesson in conn.execute(
        "SELECT row_index, col_index, value FROM lessons WHERE group_id = ? AND week = ?",
        (row["id"], week),
    ).fetchall():
        matrix[lesson["row_index"]][lesson["col_index"]] = lesson["value"]
    return matrix


def get_all_schedule(conn: sqlite3.Connection) -> dict:
    result: dict = {"study": {"week1": {}, "week2": {}}}
    for name in get_groups(conn):
        result["study"]["week1"][name] = get_schedule_matrix(conn, name, "week1")
        result["study"]["week2"][name] = get_schedule_matrix(conn, name, "week2")
    return result


def init_db() -> None:
    with get_connection() as conn:
        # Добавляем новые столбцы к groups если их ещё нет (миграция)
        for col, definition in [
            ("faculty_id", "INTEGER"),
            ("study_form", "TEXT"),
            ("course",     "INTEGER"),
            ("degree",     "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE groups ADD COLUMN {col} {definition}")
            except sqlite3.OperationalError:
                pass

        create_tables(conn)

        # Сидирование факультетов
        conn.execute(
            "INSERT OR IGNORE INTO faculties(name, short_name) VALUES(?,?)",
            ("Физико-технический институт", "ФТИ"),
        )
        conn.commit()

        # Сидирование групп
        for name in SEED_GROUP_NAMES:
            ensure_group(conn, name)

        # Авто-заполнение study_form / course / degree для всех групп
        for row in conn.execute("SELECT id, name FROM groups WHERE study_form IS NULL").fetchall():
            conn.execute(
                "UPDATE groups SET study_form=?, course=?, degree=? WHERE id=?",
                (detect_study_form(row["name"]), detect_course(row["name"]),
                 detect_degree(row["name"]), row["id"]),
            )

        for name in SEED_SUBJECTS:
            conn.execute("INSERT OR IGNORE INTO subjects(name) VALUES(?)", (name,))
        for name in SEED_TEACHERS:
            conn.execute("INSERT OR IGNORE INTO teachers(name) VALUES(?)", (name,))
        for name in SEED_ROOMS:
            conn.execute("INSERT OR IGNORE INTO rooms(name) VALUES(?)", (name,))
        conn.commit()

# ---------------------------------------------------------------------------
# Generic helper for reference tables (subjects / teachers / rooms)
# ---------------------------------------------------------------------------

ALLOWED_REFS = {"subjects", "teachers", "rooms"}


def _ref_list(conn: sqlite3.Connection, table: str) -> list[dict]:
    return [{"id": r["id"], "name": r["name"]}
            for r in conn.execute(f"SELECT id, name FROM {table} ORDER BY name").fetchall()]

# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("admin"))
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if safe_eq(username, ADMIN_USERNAME) and safe_eq(password, ADMIN_PASSWORD):
            session.permanent = True
            session["logged_in"] = True
            return redirect(url_for("admin"))
        error = "Неверный логин или пароль"
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ---------------------------------------------------------------------------
# Static pages
# ---------------------------------------------------------------------------

@app.after_request
def add_no_cache_headers(response):
    # HTML не кешируем, чтобы правки всегда подхватывались сразу
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
def index():
    return send_from_directory(str(BASE_DIR), "Rozklad.html")


@app.route("/admin")
@login_required
def admin():
    return send_from_directory(str(BASE_DIR), "admin.html")


@app.route("/avatar.jpg")
def avatar():
    return send_from_directory(str(BASE_DIR), "avatar.jpg")

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok"})


@app.route("/api/faculties")
def api_faculties():
    with get_connection() as conn:
        rows = conn.execute("SELECT id, name, short_name FROM faculties ORDER BY name").fetchall()
        return jsonify({"faculties": [dict(r) for r in rows]})


@app.route("/api/groups", methods=["GET"])
def api_groups_get():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT g.name, g.faculty_id, g.study_form, g.course, g.degree,
                   f.short_name AS faculty_short
            FROM groups g
            LEFT JOIN faculties f ON g.faculty_id = f.id
            ORDER BY g.name
        """).fetchall()
        return jsonify({"groups": [dict(r) for r in rows]})


@app.route("/api/schedule")
def api_schedule():
    group = request.args.get("group", "")
    week = request.args.get("week", "week1")
    if week not in ("week1", "week2"):
        return jsonify({"error": "week must be week1 or week2"}), 400
    with get_connection() as conn:
        return jsonify({"group": group, "week": week,
                        "rows": get_schedule_matrix(conn, group, week)})


@app.route("/api/schedule/all")
def api_schedule_all():
    with get_connection() as conn:
        return jsonify(get_all_schedule(conn))


@app.route("/api/subjects", methods=["GET"])
def api_subjects_get():
    with get_connection() as conn:
        return jsonify({"subjects": _ref_list(conn, "subjects")})


@app.route("/api/teachers", methods=["GET"])
def api_teachers_get():
    with get_connection() as conn:
        return jsonify({"teachers": _ref_list(conn, "teachers")})


@app.route("/api/rooms", methods=["GET"])
def api_rooms_get():
    with get_connection() as conn:
        return jsonify({"rooms": _ref_list(conn, "rooms")})

# ---------------------------------------------------------------------------
# Admin API (только авторизованным)
# ---------------------------------------------------------------------------

@app.route("/api/faculties", methods=["POST"])
@login_required
def api_faculties_post():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    short_name = (data.get("short_name") or "").strip() or None
    if not name:
        return jsonify({"error": "name is required"}), 400
    with get_connection() as conn:
        try:
            conn.execute("INSERT INTO faculties(name, short_name) VALUES(?,?)", (name, short_name))
            conn.commit()
            new_id = conn.execute("SELECT id FROM faculties WHERE name=?", (name,)).fetchone()["id"]
        except sqlite3.IntegrityError:
            return jsonify({"error": "already exists"}), 409
    return jsonify({"ok": True, "id": new_id}), 201


@app.route("/api/groups/<string:group_name>/faculty", methods=["PUT"])
@login_required
def api_group_set_faculty(group_name):
    data = request.get_json(silent=True) or {}
    faculty_id = data.get("faculty_id")  # None = убрать факультет
    with get_connection() as conn:
        conn.execute("UPDATE groups SET faculty_id=? WHERE name=?", (faculty_id, group_name))
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/groups", methods=["POST"])
@login_required
def api_groups_post():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    with get_connection() as conn:
        gid = ensure_group(conn, name)
        for week in ("week1", "week2"):
            for r in range(TIMES_COUNT):
                for c in range(DAYS_COUNT):
                    conn.execute(
                        "INSERT OR IGNORE INTO lessons(group_id, week, row_index, col_index, value) VALUES(?,?,?,?,?)",
                        (gid, week, r, c, ""),
                    )
        conn.commit()
    return jsonify({"ok": True, "name": name}), 201


@app.route("/api/schedule/cell", methods=["PUT"])
@login_required
def api_schedule_cell():
    data = request.get_json(silent=True) or {}
    group = (data.get("group") or "").strip()
    week = data.get("week")
    row = data.get("row")
    col = data.get("col")
    value = (data.get("value") or "").strip()

    if not group:
        return jsonify({"error": "group is required"}), 400
    if week not in ("week1", "week2"):
        return jsonify({"error": "week must be week1 or week2"}), 400
    if not isinstance(row, int) or not 0 <= row < TIMES_COUNT:
        return jsonify({"error": f"row must be 0..{TIMES_COUNT - 1}"}), 400
    if not isinstance(col, int) or not 0 <= col < DAYS_COUNT:
        return jsonify({"error": f"col must be 0..{DAYS_COUNT - 1}"}), 400

    with get_connection() as conn:
        gid = ensure_group(conn, group)
        conn.execute(
            "INSERT INTO lessons(group_id, week, row_index, col_index, value) VALUES(?,?,?,?,?) "
            "ON CONFLICT(group_id, week, row_index, col_index) DO UPDATE SET value = excluded.value",
            (gid, week, row, col, value),
        )
        conn.commit()
    return jsonify({"ok": True})


@app.route("/api/check-conflict")
@login_required
def api_check_conflict():
    teacher = (request.args.get("teacher") or "").strip()
    week = request.args.get("week", "week1")
    current_group = (request.args.get("group") or "").strip()

    try:
        row_index = int(request.args.get("row", "0"))
    except ValueError:
        return jsonify({"conflicts": []})

    if not teacher or teacher in ("—", "-") or week not in ("week1", "week2"):
        return jsonify({"conflicts": []})

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT g.name AS group_name, l.value
            FROM lessons l
            JOIN groups g ON l.group_id = g.id
            WHERE l.week = ? AND l.row_index = ? AND l.value != ''
        """, (week, row_index)).fetchall()

        conflicts = []
        for row in rows:
            gname = row["group_name"]
            val = row["value"]
            if gname == current_group:
                continue
            m = re.search(r"\|\|\s*Препод:\s*(.+?)\s*\|\|", val, re.IGNORECASE)
            if m and m.group(1).strip() == teacher:
                conflicts.append({"group": gname})

        return jsonify({"conflicts": conflicts})


LOCATION_KEYWORDS = [
    ("вернадского", "пр.Вернадского"),
    ("павленко",    "ул.Павленко"),
    ("ленина",      "ул.Ленина"),
    ("киевская",    "ул.Киевская"),
    ("васильева",   "ул.Васильева"),
    ("спорт",       "Спортзал"),
]


def get_location(room_str: str) -> str:
    r = (room_str or "").lower()
    for keyword, label in LOCATION_KEYWORDS:
        if keyword in r:
            return label
    return room_str.strip()


@app.route("/api/check-location-conflict")
@login_required
def api_check_location_conflict():
    group = (request.args.get("group") or "").strip()
    week = request.args.get("week", "week1")
    room = (request.args.get("room") or "").strip()

    try:
        row_index = int(request.args.get("row", "0"))
    except ValueError:
        return jsonify({"conflicts": []})

    if not group or not room or room in ("—", "-") or week not in ("week1", "week2"):
        return jsonify({"conflicts": []})

    new_location = get_location(room)

    with get_connection() as conn:
        group_row = conn.execute("SELECT id FROM groups WHERE name = ?", (group,)).fetchone()
        if not group_row:
            return jsonify({"conflicts": []})

        lessons: dict[int, str] = {}
        for lesson in conn.execute(
            "SELECT row_index, value FROM lessons WHERE group_id = ? AND week = ? AND value != ''",
            (group_row["id"], week),
        ).fetchall():
            lessons[lesson["row_index"]] = lesson["value"]

        slot_times = ["08:30", "10:25", "12:20", "14:15", "16:10", "18:20", "20:00"]
        conflicts = []

        for adj_row in (row_index - 1, row_index + 1):
            if adj_row < 0 or adj_row >= TIMES_COUNT:
                continue
            adj_val = lessons.get(adj_row, "")
            if not adj_val:
                continue  # пустой слот = перерыв — предупреждение не нужно

            m = re.search(r"\|\|\s*Ауд\.?\s*:\s*(.+?)\s*$", adj_val, re.IGNORECASE)
            if not m:
                continue
            adj_room = m.group(1).strip()
            if not adj_room or adj_room in ("—", "-"):
                continue

            adj_location = get_location(adj_room)
            # Спортзал не считаем конфликтом: физкультура всегда в спортзале,
            # это запланировано в расписании и студенты успевают
            if "Спортзал" in (adj_location, new_location):
                continue
            if adj_location != new_location:
                direction = "предыдущая пара" if adj_row < row_index else "следующая пара"
                conflicts.append({
                    "row": adj_row,
                    "time": slot_times[adj_row] if adj_row < len(slot_times) else f"пара {adj_row + 1}",
                    "room": adj_room,
                    "direction": direction,
                })

        return jsonify({"conflicts": conflicts})


@app.route("/api/<string:ref_type>", methods=["POST"])
@login_required
def api_ref_post(ref_type):
    if ref_type not in ALLOWED_REFS:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    with get_connection() as conn:
        try:
            conn.execute(f"INSERT INTO {ref_type}(name) VALUES(?)", (name,))
            conn.commit()
            new_id = conn.execute(f"SELECT id FROM {ref_type} WHERE name = ?", (name,)).fetchone()["id"]
        except sqlite3.IntegrityError:
            return jsonify({"error": "already exists"}), 409
    return jsonify({"ok": True, "id": new_id, "name": name}), 201


@app.route("/api/<string:ref_type>/<int:item_id>", methods=["DELETE"])
@login_required
def api_ref_delete(ref_type, item_id):
    if ref_type not in ALLOWED_REFS:
        return jsonify({"error": "not found"}), 404
    with get_connection() as conn:
        conn.execute(f"DELETE FROM {ref_type} WHERE id = ?", (item_id,))
        conn.commit()
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Инициализируем БД при импорте модуля — нужно для WSGI-хостинга
# (PythonAnywhere, gunicorn), где блок __main__ не выполняется.
init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
