#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
price_id.py — ценовая идентификация предметов NetHack (свитки и зелья).

Что делает:
  * по цене продажи/покупки (таблицы NetHack 3.6.0+, файл price_id.html)
    находит возможные предметы и предлагает псевдоним для ввода в игре;
  * ведёт сессии (устройство/герой/роль/харизма и др. характеристики);
  * запоминает соответствия «метка в игре ↔ псевдоним» и распознанные
    предметы; распознанные исключаются из будущих списков;
  * обновляет CSV-файлы сессии: appearance;alias;function.

Зависимостей нет — только стандартная библиотека Python 3 (подходит Termux).

Запуск:
  python3 price_id.py                 # интерактивный режим
  python3 price_id.py s 30 scroll GHOTI
  python3 price_id.py b 300 potion
  python3 price_id.py --help
"""

import argparse
import csv
import difflib
import json
import os
import re
import shutil
import sys
import time
from html.parser import HTMLParser

VERSION = "0.4"
FORMAT_VERSION = 1

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# Сокращения предметов (можно править в price_id_abbr.json после первого запуска)
# --------------------------------------------------------------------------

DEFAULT_ABBR = {
    "scrolls": {
        # имя: [стиль 1 (короткий), стиль 2 (средний), стиль 3 (сжатый)]
        "identify": ["id", "ident", "iden"],
        "light": ["li", "light", "lite"],
        "blank paper": ["bp", "blank", "bpap"],
        "enchant weapon": ["ew", "enchw", "enweap"],
        "enchant armor": ["ea", "enchar", "earm"],
        "remove curse": ["rc", "remcur", "rcur"],
        "confuse monster": ["comon", "confmon", "cfmon"],
        "destroy armor": ["darm", "destarm", "dstarm"],
        "fire": ["fire", "fr", "fir"],
        "food detection": ["fd", "food", "fdet"],
        "gold detection": ["gd", "gold", "gdet"],
        "magic mapping": ["mm", "magmap", "mmap"],
        "scare monster": ["scare", "scar", "scmon"],
        "teleportation": ["tp", "tele", "tport"],
        "amnesia": ["amn", "amnes", "amnesia"],
        "create monster": ["crmon", "cremon", "crtmon"],
        "earth": ["eart", "earth", "erth"],
        "taming": ["tam", "taming", "tame"],
        "charging": ["chrg", "charg", "chg"],
        "genocide": ["geno", "genoc", "gen"],
        "punishment": ["pun", "punish", "pnsh"],
        "stinking cloud": ["stink", "stinkc", "scloud"],
    },
    "potions": {
        "water": ["wt", "water", "wat"],
        "holy water": ["hw", "holy", "hly"],
        "unholy water": ["uw", "unholy", "unly"],
        "booze": ["booze", "booz", "bz"],
        "fruit juice": ["fj", "fruitj", "fju"],
        "see invisible": ["sinv", "seeinv", "si"],
        "sickness": ["sick", "sickn", "sk"],
        "confusion": ["conf", "confus", "cnf"],
        "extra healing": ["eheal", "exh", "xheal"],
        "hallucination": ["hallu", "halluc", "halu"],
        "healing": ["heal", "healing", "hl"],
        "restore ability": ["rest", "restor", "rst"],
        "sleeping": ["sleep", "sleepin", "slp"],
        "blindness": ["blind", "blindn", "bld"],
        "gain energy": ["ge", "gainen", "gegy"],
        "invisibility": ["inv", "invis", "invs"],
        "monster detection": ["md", "mondet", "mdet"],
        "object detection": ["od", "objdet", "odet"],
        "enlightenment": ["enl", "enlight", "elt"],
        "full healing": ["fheal", "fullh", "fhl"],
        "levitation": ["lev", "levit", "lvt"],
        "polymorph": ["poly", "polym", "ply"],
        "speed": ["spd", "speed", "sped"],
        "acid": ["acid", "acd", "aci"],
        "oil": ["oil", "ol", "oi"],
        "gain ability": ["ga", "gainab", "gab"],
        "gain level": ["gl", "gainl", "glv"],
        "paralysis": ["para", "paral", "prl"],
    },
}

# Полный пул меток свитков NetHack 3.6.x (21 «боевых» + 20 запасных, часть
# из которых в конкретной партии не появляется). Используется только для
# подсказок при опечатках — ввод не блокируется.
BUILTIN_LABELS = {
    "scrolls": [
        "ZELGO MER", "JUYED AWK YACC", "NR 9", "XIXAXA XOXAXA XUXAXA",
        "PRATYAVAYAH", "DAIYEN FOOELS", "LEP GEX VEN ZEA", "PRIRUTSENIE",
        "ELBIB YLOH", "VERR YED HORRE", "VENZAR BORGAVVE", "THARR", "YUM YUM",
        "KERNOD WEL", "ELAM EBOW", "DUAM XNAHT", "ANDOVA BEGARIN", "KIRJE",
        "VE FORBRYDERNE", "HACKEM MUCHE", "VELOX NEB", "FOOBIE BLETCH",
        "TEMOV", "GARVEN DEH", "READ ME", "ETAOIN SHRDLU", "LOREM IPSUM",
        "FNORD", "KO BATE", "ABRA KA DABRA", "ASHPD SODALG", "ZLORFIK",
        "GNIK SISI VLE", "HAPAX LEGOMENON", "EIRIS SAZUN IDISI",
        "PHOL ENDE WODAN", "GHOTI", "MAPIRO MAHAMA DIROMAT",
        "VAS CORP BET MANI", "XOR OTA", "STRC PRST SKRZ KRK",
    ],
    "potions": [
        "ruby", "pink", "orange", "yellow", "emerald", "dark green", "cyan",
        "sky blue", "brilliant blue", "magenta", "purple-red", "puce",
        "milky", "swirly", "bubbly", "smoky", "cloudy", "effervescent",
        "black", "golden", "brown", "fizzy", "dark", "white", "murky",
    ],
}

KIND_ALIASES = {
    "scrolls": {"sc", "scr", "scroll", "scrolls", "свиток", "свитки"},
    "potions": {"po", "pot", "potion", "potions", "зелье", "зелья"},
}

KIND_UNIT = {"scrolls": "scroll", "potions": "potion"}
KIND_UNIT_RU = {"scrolls": {"scroll": "свиток", "many": "свитков"},
                "potions": {"potion": "зелье", "many": "зелий"}}


def cha_bracket(cha):
    """Ключ столбца таблицы для значения харизмы."""
    if cha <= 5:
        return "le5"
    if cha <= 7:
        return "6-7"
    if cha <= 10:
        return "8-10"
    if cha <= 15:
        return "11-15"
    if cha <= 17:
        return "16-17"
    if cha == 18:
        return "18"
    return "ge19"


# --------------------------------------------------------------------------
# Разбор price_id.html (стандартный html.parser — работает в Termux)
# --------------------------------------------------------------------------

class _TableParser(HTMLParser):
    """Собирает заголовки и таблицы из сохранённой вики-страницы."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.headings = {"h2": "", "h3": "", "h4": "", "h5": ""}
        self._capture = None
        self._buf = []
        self._table = None
        self._row = None
        self._cell = None
        self._in_caption = False

    def handle_starttag(self, tag, attrs):
        if tag in ("h2", "h3", "h4", "h5"):
            self._capture, self._buf = tag, []
        elif tag == "table":
            self._table = {"caption": "", "rows": []}
        elif tag == "caption" and self._table is not None:
            self._in_caption, self._buf = True, []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = ""
        elif tag == "br" and self._cell is not None:
            self._cell += " "

    def handle_endtag(self, tag):
        if tag in ("h2", "h3", "h4", "h5") and self._capture == tag:
            self.headings[tag] = " ".join("".join(self._buf).split())
            for lower in {"h2": ("h3", "h4", "h5"), "h3": ("h4", "h5"),
                          "h4": ("h5",)}.get(tag, ()):
                self.headings[lower] = ""
            self._capture = None
        elif tag == "table" and self._table is not None:
            path = " > ".join(v for v in (self.headings["h2"], self.headings["h3"],
                                          self.headings["h4"], self.headings["h5"]) if v)
            self._table["path"] = path
            self.tables.append(self._table)
            self._table = None
        elif tag == "caption" and self._table is not None:
            self._in_caption = False
            self._table["caption"] = " ".join("".join(self._buf).split())
        elif tag == "tr" and self._row is not None:
            if self._table is not None:
                self._table["rows"].append(self._row)
            self._row = None
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join(self._cell.split()))
            self._cell = None

    def handle_data(self, data):
        if self._capture is not None:
            self._buf.append(data)
        if self._in_caption:
            self._buf.append(data)
        if self._cell is not None:
            self._cell += data


def _cell_numbers(text):
    """'120 (160/213)' -> [120, 160, 213]; '30 (23)' -> [30, 23]; '5' -> [5]."""
    return [int(x) for x in re.findall(r"\d+", text)]


def _parse_items_cell(text):
    """'blank paper ("unlabeled scroll"), enchant weapon' -> список предметов."""
    items = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'^(.*?)\s*\((.*)\)$', part)
        if m:
            name = m.group(1).strip()
            note = m.group(2).strip().strip('"')
        else:
            name, note = part, ""
        items.append({"name": name, "note": note})
    return items


def build_data(html_path):
    """Строит структуру данных из price_id.html (таблицы Scrolls/Potions 3.6.0+)."""
    with open(html_path, encoding="utf-8", errors="replace") as f:
        html = f.read()
    parser = _TableParser()
    parser.feed(html)

    classes = {}
    for kind, title in (("scrolls", "Scrolls"), ("potions", "Potions")):
        table = None
        for t in parser.tables:
            if t.get("path", "").endswith(title) and "3.6.0" in t["caption"]:
                table = t
                break
        if table is None:
            raise SystemExit(
                "Не найдена таблица «%s» (NetHack 3.6.0 и позднее) в %s.\n"
                "Проверь, что это сохранённая страница Price identification."
                % (title, html_path))

        header = table["rows"][0]
        # столбцы харизмы: из ячеек вида 'Cha 6–7' / 'Cha ≤ 5' / 'Cha ≥ 19'
        cha_keys = []
        for cell in header[1:8]:
            nums = re.findall(r"\d+", cell)
            if "≤" in cell:
                cha_keys.append("le" + nums[0])
            elif "≥" in cell:
                cha_keys.append("ge" + nums[0])
            elif len(nums) == 2:
                cha_keys.append(nums[0] + "-" + nums[1])
            elif len(nums) == 1:
                cha_keys.append(nums[0])
        rows = []
        for r in table["rows"][1:]:
            if len(r) < 10:
                continue
            row = {"base": int(r[0]), "buy": {}, "sell": _cell_numbers(r[8]),
                   "items": _parse_items_cell(r[9])}
            for i, key in enumerate(cha_keys):
                row["buy"][key] = _cell_numbers(r[1 + i])
            rows.append(row)
        classes[kind] = {"rows": rows}

    # самопроверка структуры: 7 ценовых строк в каждой таблице
    for kind, n_expect in (("scrolls", 7), ("potions", 7)):
        if len(classes[kind]["rows"]) != n_expect:
            raise SystemExit(
                "Таблица «%s»: получено %d строк вместо %d — похоже, вёрстка "
                "страницы изменилась." % (kind, len(classes[kind]["rows"]), n_expect))

    data = {
        "format": "nethack-price-id",
        "format_version": FORMAT_VERSION,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": os.path.basename(html_path),
        "source_note": "Цены NetHack 3.6.0 и позднее (продажа/покупка).",
        "classes": classes,
        "labels": dict(BUILTIN_LABELS),
        "abbr_defaults": dict(DEFAULT_ABBR),
    }
    return data


def save_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ask(prompt):
    """input() с защитой от EOF (пайп, неинтерактивный запуск).

    Возвращает None, если ввод закончился (EOF), иначе — строку (может быть '')."""
    try:
        return input(prompt).strip()
    except EOFError:
        print()
        return None


def find_first_existing(paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def load_or_build_data(args):
    """Ищет data.json или price_id.html, при необходимости перестраивает."""
    candidates_data = [args.data,
                       os.path.join(SCRIPT_DIR, "price_id_data.json"),
                       os.path.join(os.getcwd(), "price_id_data.json")]
    candidates_html = [args.html,
                       os.path.join(SCRIPT_DIR, "price_id.html"),
                       os.path.join(os.path.dirname(SCRIPT_DIR), "price_id.html"),
                       os.path.join(os.getcwd(), "price_id.html"),
                       os.path.join(os.getcwd(), "..", "price_id.html")]

    html_path = find_first_existing(candidates_html)
    data_path = find_first_existing(candidates_data)

    if args.rebuild:
        if not html_path:
            raise SystemExit("--rebuild: не найден price_id.html (укажи --html).")
        data = build_data(html_path)
        target = args.data or os.path.join(SCRIPT_DIR, "price_id_data.json")
        save_json(target, data)
        print("Данные перестроены из %s → %s" % (html_path, target))
        return data

    if data_path:
        data = load_json(data_path)
        if data.get("format") != "nethack-price-id":
            raise SystemExit("Файл %s не является базой price_id." % data_path)
        return data
    if html_path:
        data = build_data(html_path)
        target = args.data or os.path.join(SCRIPT_DIR, "price_id_data.json")
        try:
            save_json(target, data)
        except OSError:
            pass
        return data
    raise SystemExit(
        "Не найдены ни price_id_data.json, ни price_id.html.\n"
        "Положи рядом со скриптом любой из этих файлов или укажи --html/--data.")


def get_abbr(data, args):
    """Сокращения: price_id_abbr.json (правится вручную) поверх встроенных.

    Значение у предмета — строка или список строк (варианты стилей для
    случаев, когда несколько предметов имеют одинаковую цену)."""
    abbr_path = args.abbr or os.path.join(SCRIPT_DIR, "price_id_abbr.json")
    abbr = {k: {n: list(v) if isinstance(v, (list, tuple)) else [v]
                for n, v in items.items()}
            for k, items in DEFAULT_ABBR.items()}
    if os.path.exists(abbr_path):
        try:
            user_abbr = load_json(abbr_path)
            for kind, mapping in user_abbr.items():
                if kind in abbr and isinstance(mapping, dict):
                    for name, val in mapping.items():
                        if isinstance(val, (list, tuple)) and val:
                            abbr[kind][name] = [str(x) for x in val]
                        elif isinstance(val, str) and val:
                            abbr[kind][name] = [val]
        except (OSError, ValueError):
            print("Предупреждение: не удалось прочитать %s, беру встроенные."
                  % abbr_path)
    else:
        try:
            save_json(abbr_path, DEFAULT_ABBR)
            print("Создан файл сокращений: %s (можно править вручную)." % abbr_path)
        except OSError:
            pass
    return abbr


# --------------------------------------------------------------------------
# Сессии и хранилище
# --------------------------------------------------------------------------

def _sanitize_dir(name):
    s = re.sub(r"[^\w\-.]+", "_", name, flags=re.UNICODE).strip("_")
    return s or "session"


class Store:
    """sessions.json + sessions/<имя>/scrolls.csv, potions.csv."""

    def __init__(self, base_dir):
        self.base = base_dir
        self.path = os.path.join(base_dir, "sessions.json")
        self.sessions_dir = os.path.join(base_dir, "sessions")
        os.makedirs(self.sessions_dir, exist_ok=True)
        self.data = {"format": "nethack-price-id-sessions",
                     "format_version": FORMAT_VERSION,
                     "last": None, "sessions": {}}
        if os.path.exists(self.path):
            try:
                self.data = load_json(self.path)
            except (OSError, ValueError):
                bak = self.path + ".bak"
                try:
                    os.replace(self.path, bak)
                except OSError:
                    pass
                print("Внимание: sessions.json повреждён, переименован в %s; "
                      "начинаю с чистого." % bak)

    # --- сохранение ---
    def save(self):
        os.makedirs(self.base, exist_ok=True)
        save_json(self.path, self.data)

    # --- сессии ---
    def names(self):
        return list(self.data["sessions"].keys())

    def add(self, name, hero="", role="", cha=None):
        sdir = _sanitize_dir(name)
        taken = {s.get("dir") for s in self.data["sessions"].values()}
        base, i = sdir, 2
        while sdir in taken:
            sdir = "%s_%d" % (base, i)
            i += 1
        self.data["sessions"][name] = {
            "dir": sdir, "hero": hero, "role": role, "cha": cha,
            "extra": {}, "items": [],
            "created": time.strftime("%Y-%m-%d %H:%M"),
        }
        self.data["last"] = name
        self.save()

    def delete(self, name):
        s = self.data["sessions"].pop(name, None)
        if self.data.get("last") == name:
            self.data["last"] = self.names()[0] if self.names() else None
        self.save()
        if s and s.get("dir"):
            d = os.path.join(self.sessions_dir, s["dir"])
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)

    def session(self, name=None):
        name = name or self.data.get("last")
        if name not in self.data["sessions"]:
            return None, None
        return name, self.data["sessions"][name]

    def csv_dir(self, name):
        s = self.data["sessions"].get(name)
        if not s:
            return None
        return os.path.join(self.sessions_dir, s["dir"])

    # --- предметы ---
    @staticmethod
    def find_item(sess, kind, label):
        up = label.strip().upper()
        for it in sess["items"]:
            if it["kind"] == kind and it["label"].upper() == up:
                return it
        return None

    @staticmethod
    def find_item_any_kind(sess, label):
        up = label.strip().upper()
        for it in sess["items"]:
            if it["label"].upper() == up:
                return it
        return None

    def identified_types(self, sess, kind):
        return {it["identified_as"] for it in sess["items"]
                if it["kind"] == kind and it.get("identified_as")}

    def write_csvs(self, name):
        sess = self.data["sessions"].get(name)
        if not sess or not sess["items"]:
            return []
        d = self.csv_dir(name)
        if not d:
            return []
        os.makedirs(d, exist_ok=True)
        written = []
        for kind in ("scrolls", "potions"):
            rows = [it for it in sess["items"] if it["kind"] == kind]
            path = os.path.join(d, kind + ".csv")
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f, delimiter=";", lineterminator="\n")
                w.writerow(["appearance", "alias", "function"])
                for it in rows:
                    fn = ""
                    if it.get("identified_as"):
                        fn = "%s of %s" % (KIND_UNIT[kind], it["identified_as"])
                    w.writerow([it["label"], it.get("alias", ""), fn])
            written.append(path)
        return written


# --------------------------------------------------------------------------
# Поиск по ценам
# --------------------------------------------------------------------------

class Match(object):
    def __init__(self, row, item, tag):
        self.row = row          # строка таблицы (набор предметов с одной базовой ценой)
        self.item = item        # конкретный предмет
        self.tag = tag          # пометка: '', 'скидка', '+1/3', '+1/3×2'


def lookup(data, kind, mode, price, cha):
    """Возвращает список Match — предметы, которым может соответствовать цена.

    mode='sell': цена, которую магазин предлагает за предмет (столбец Selling price,
                 оба числа: обычная и со скидкой магазина).
    mode='buy':  цена, которую магазин просит (столбец харизмы, три числа:
                 обычная, с надбавкой +1/3 от неопознанности ИЛИ «сучка», с обеими).
    """
    matches = []
    rows = data["classes"][kind]["rows"]
    if mode == "sell":
        for row in rows:
            for i, val in enumerate(row["sell"]):
                if val == price:
                    tag = "" if i == 0 else "скидка"
                    for item in row["items"]:
                        matches.append(Match(row, item, tag))
                    break
    else:
        key = cha_bracket(cha)
        for row in rows:
            vals = row["buy"].get(key, [])
            for i, val in enumerate(vals):
                if val == price:
                    tag = ["", "+1/3", "+1/3×2"][min(i, 2)]
                    for item in row["items"]:
                        matches.append(Match(row, item, tag))
                    break
    return matches


def sucker_sell_rows(data, kind, price):
    """Строки, у которых цена продажи «сучку» (base/3, округл.) равна price.
    Только для подсказки, когда обычный поиск ничего не нашёл."""
    out = []
    for row in data["classes"][kind]["rows"]:
        base = row["base"]
        t = 5 if base == 0 else base
        t = (t * 10) // 3
        t = (t + 5) // 10
        if t == price and base != 0:
            out.append(row)
    return out


def make_alias(data, abbr, kind, matches, mode, price, sell_values,
               sess=None, exclude_label=None):
    """Псевдоним по правилам задачи.

    ≤ 5 предметов  -> сокращения через '/'  (bp/ew/ea/rc). Если такой псевдоним
                      уже занят другим предметом сессии, берётся следующий
                      стиль сокращений (blank/enchw/enchar/remcur и т.д.),
                      чтобы одинаковые по цене предметы различались.
    ≥ 6 предметов  -> s<цена>_<n> (номер считает вызывающий код).
    """
    if not matches:
        return None, None
    if len(matches) > 5:
        return None, "long"
    variants = abbr.get(kind, {})
    style_count = 1
    for m in matches:
        style_count = max(style_count,
                          len(variants.get(m.item["name"]) or [""]))
    used = set()
    if sess is not None:
        for it in sess.get("items", []):
            if exclude_label and it["label"].upper() == exclude_label.upper():
                continue
            if it.get("alias"):
                used.add(it["alias"])

    def combine(style_idx):
        parts = []
        for m in matches:
            lst = variants.get(m.item["name"])
            if not lst:
                lst = [m.item["name"].replace(" ", "")[:4]]
            parts.append(lst[style_idx] if style_idx < len(lst) else lst[-1])
        return "/".join(parts)

    for i in range(style_count):
        cand = combine(i)
        if cand not in used:
            return cand, "short"
    base = combine(style_count - 1)
    k = 2
    while True:
        cand = "%s-%d" % (base, k)
        if cand not in used:
            return cand, "short"
        k += 1


def next_s_index(sess, prefix):
    """Следующий номер для псевдонимов вида s75_1, s75_2 ..."""
    n = 0
    for it in sess["items"]:
        m = re.match(r"^s(\d+)_(\d+)$", it.get("alias", ""))
        if m and ("s" + m.group(1) + "_") == prefix:
            n = max(n, int(m.group(2)))
    return n + 1


def canon_item_name(data, text, kind=None):
    """Канонизирует название предмета: 'ew', 'enchant weapon', 'scroll of enchant
    weapon' -> ('scrolls', 'enchant weapon'). Возвращает список вариантов."""
    t = text.strip().lower()
    t = re.sub(r"^(?:scroll|potion)s?\s+of\s+", "", t)
    t = re.sub(r"^(?:scroll|potion)s?\s+", "", t)
    out = []
    for k, cdata in data["classes"].items():
        if kind and k != kind:
            continue
        for row in cdata["rows"]:
            for it in row["items"]:
                name = it["name"].lower()
                ab = data.get("_abbr", {}).get(k, {}).get(it["name"])
                if isinstance(ab, (list, tuple)):
                    abbrs = [str(x).lower() for x in ab]
                elif ab:
                    abbrs = [str(ab).lower()]
                else:
                    abbrs = []
                if t == name:
                    out.append((k, it["name"], 0))
                elif t in abbrs:
                    out.append((k, it["name"], 1))
    out.sort(key=lambda x: x[2])
    return out


def suggest_label(label, kind):
    """Подсказка при опечатке в метке/цвете (по пулу соответствующего вида)."""
    pool = BUILTIN_LABELS.get(kind, [])
    if label.strip().upper() in (l.upper() for l in pool):
        return None
    near = difflib.get_close_matches(label.strip().upper(), pool, n=1,
                                     cutoff=0.75)
    return near[0] if near else None


# --------------------------------------------------------------------------
# Вывод
# --------------------------------------------------------------------------

def fmt_price(p):
    return "%d zm" % p


# --------------------------------------------------------------------------
# Команды
# --------------------------------------------------------------------------

class App:
    def __init__(self, data, store, abbr, session_name=None):
        self.data = data
        self.store = store
        self.abbr = abbr
        self.data["_abbr"] = abbr
        self.session_name = session_name

    # ---------- служебное ----------
    def require_session(self, interactive=True):
        name, sess = self.store.session(self.session_name)
        if name is None:
            fl = sorted(self.store.names())
            if not fl:
                if not interactive:
                    raise SystemExit("Нет ни одной сессии. Создай: "
                                     "python3 price_id.py sess new <имя>")
                self.new_session_interactive()
                name, sess = self.store.session(self.session_name)
            else:
                if not interactive:
                    if self.session_name:
                        raise SystemExit("Сессия «%s» не найдена. Есть: %s"
                                         % (self.session_name, ", ".join(fl)))
                    raise SystemExit("Не выбрана сессия. Укажи --session <имя> "
                                     "или выбери: " + ", ".join(fl))
                print("Доступные сессии: " + ", ".join(fl))
                self.session_name = fl[0]
                print("Использую «%s»." % fl[0])
                name, sess = self.store.session(self.session_name)
        self.session_name = name
        return name, sess

    def new_session_interactive(self):
        name = _ask("Имя сессии (напр. Android/Mac/PC/Steam): ")
        if name is None:
            raise SystemExit("Ввод недоступен. Создай сессию командой: "
                             "sess new <имя>")
        if not name:
            name = "default"
        if name in self.store.names():
            print("Сессия «%s» уже существует — переключаюсь." % name)
            self.session_name = name
            return
        hero = _ask("Имя героя (можно пропустить): ") or ""
        role = _ask("Роль (можно пропустить): ") or ""
        cha_raw = _ask("Харизма (число, можно позже): ") or ""
        cha = int(cha_raw) if cha_raw.isdigit() else None
        self.store.add(name, hero=hero, role=role, cha=cha)
        self.session_name = name
        print("Сессия «%s» создана." % name)

    def ensure_cha(self, sess, interactive=True):
        if sess.get("cha") is None:
            if not interactive:
                raise SystemExit(
                    "У сессии «%s» не задана харизма. Задай её командой: "
                    "python3 price_id.py sess set cha <число>" % self.session_name)
            raw = _ask("У сессии не задана харизма. Введи число: ") or ""
            if raw.isdigit():
                sess["cha"] = int(raw)
                self.store.save()
        return sess.get("cha")

    # ---------- команды ----------
    def cmd_sell_buy(self, mode, tokens, interactive=True):
        name, sess = self.require_session(interactive)
        if not tokens:
            print("Формат: %s <цена> [scroll|potion] [метка предмета]"
                  % ("s" if mode == "sell" else "b"))
            return
        price_raw = tokens[0]
        if not price_raw.isdigit():
            print("Первым укажи цену числом, например: %s 30 scroll GHOTI"
                  % ("s" if mode == "sell" else "b"))
            return
        price = int(price_raw)
        rest = tokens[1:]
        kind = None
        while rest:
            low = rest[0].strip().lower()
            hit = next((k for k, al in KIND_ALIASES.items() if low in al), None)
            if hit:
                kind = hit
                rest = rest[1:]
            else:
                break
        label = " ".join(rest).strip()
        if kind is None:
            if not interactive:
                raise SystemExit("Укажи вид: scroll или potion.")
            raw = (_ask("Это свиток или зелье? [sc/po]: ") or "").lower()
            kind = next((k for k, al in KIND_ALIASES.items() if raw in al), None)
            if kind is None:
                print("Не понял. Запусти заново и укажи scroll|potion.")
                return
        cha = None
        if mode == "buy":
            cha = self.ensure_cha(sess, interactive)
            if cha is None:
                print("Без харизмы покупку не проверить.")
                return
        matches = lookup(self.data, kind, mode, price, cha)
        # исключаем уже распознанные типы
        ident = self.store.identified_types(sess, kind)
        matches = [m for m in matches if m.item["name"] not in ident]
        sell_values = sorted({m.row["sell"][0] for m in matches})
        alias, alias_kind = make_alias(self.data, self.abbr, kind, matches,
                                       mode, price, sell_values, sess,
                                       exclude_label=label or None)

        # вывод
        unit = KIND_UNIT_RU[kind]["many"]
        w = "Покупка" if mode == "buy" else "Продажа"
        head = "%s %d" % (w, price)
        if mode == "buy":
            head += " (Cha %d)" % cha
        head += " — %s (совпадений: %d):" % (unit, len(matches))
        print(head)
        for i, m in enumerate(matches, 1):
            tag = ("  [%s]" % m.tag) if m.tag else ""
            note = (" (%s)" % m.item["note"]) if m.item.get("note") else ""
            print("  %d. %s%s — %s%s" % (i, m.item["name"], note,
                                         fmt_price(m.row["base"]), tag))
        if not matches:
            print("Ничего не найдено. Проверь цену и вид предмета.")
            if mode == "sell":
                hint = sucker_sell_rows(self.data, kind, price)
                if hint:
                    names = ", ".join(it["name"] for row in hint
                                      for it in row["items"])
                    print("Если у персонажа «сучок» (dunce cap, видимая рубашка, "
                          "Tourist < 15 lvl) — подойдут: %s" % names)
            return
        if alias_kind == "short":
            print("Псевдоним: %s" % alias)
        elif alias_kind == "long":
            if mode == "buy":
                base_price = min(sell_values)
            else:
                base_price = price
            n = next_s_index(sess, "s%d_" % base_price)
            alias = "s%d_%d" % (base_price, n)
            extra = ""
            if mode == "buy" and len(sell_values) > 1:
                extra = "  (sell в категории: %s, взят min)" % \
                        "/".join(str(v) for v in sell_values)
            print("Псевдоним: %s%s" % (alias, extra))

        # регистрируем метку
        if label:
            self.register_item(kind, label, alias, sess, mode, price, matches)

    def register_item(self, kind, label, alias, sess, mode, price, matches):
        sug = suggest_label(label, kind)
        if sug and sug.upper() != label.upper():
            print("Подсказка: метка «%s» не встречается в списке — может, «%s»?"
                  % (label, sug))
        item = Store.find_item(sess, kind, label)
        cand_names = [m.item["name"] for m in matches]
        if item is None:
            item = {"kind": kind, "label": label, "alias": alias,
                    "identified_as": None,
                    "price": {"mode": mode, "value": price},
                    "candidates": cand_names, "updated": time.strftime("%Y-%m-%d %H:%M")}
            sess["items"].append(item)
            verb = "записан"
        else:
            item["updated"] = time.strftime("%Y-%m-%d %H:%M")
            item["price"] = {"mode": mode, "value": price}
            item["candidates"] = cand_names
            if item.get("identified_as"):
                verb = "уже распознан ранее — псевдоним не меняю"
            else:
                item["alias"] = alias
                verb = "обновлён"
        self.store.save()
        files = self.store.write_csvs(self.session_name)
        mine = [p for p in files if p.endswith(kind + ".csv")]
        rel = ", ".join(os.path.relpath(p, self.store.base) for p in mine) or "-"
        print("Запись: %s → %s (%s) [%s]" %
              (label, item.get("alias", ""), verb, rel))

    def cmd_name(self, tokens):
        name, sess = self.require_session()
        if not tokens:
            print("Формат: n <метка> [псевдоним]  (пусто — показать)")
            return
        if len(tokens) == 1:
            it = Store.find_item_any_kind(sess, tokens[0])
            if not it:
                print("Метка «%s» не найдена." % tokens[0])
                return
            self.print_item(it)
            return
        label, alias = " ".join(tokens[:-1]), tokens[-1]
        if alias == "-":
            alias = ""
        item = Store.find_item_any_kind(sess, label)
        if item is None:
            print("Метка «%s» не найдена. Сначала ищи по цене (s/b) или "
                  "распознай (i)." % label)
            return
        item["alias"] = alias
        item["updated"] = time.strftime("%Y-%m-%d %H:%M")
        self.store.save()
        files = self.store.write_csvs(self.session_name)
        mine = [p for p in files if p.endswith(item["kind"] + ".csv")]
        rel = ", ".join(os.path.relpath(p, self.store.base) for p in mine) or "-"
        print("%s → псевдоним «%s» [%s]" % (item["label"], alias, rel))

    def split_label_item(self, sess, tokens):
        """Разбивает 'GHOTI ew' или 'ABRA KA DABRA amnesia' -> (метка, предмет)."""
        text = " ".join(tokens)
        pool = [it["label"] for it in sess["items"]]
        pool += [l for l in BUILTIN_LABELS["scrolls"] + BUILTIN_LABELS["potions"]]
        pool = list(dict.fromkeys(pool))
        up = text.upper()
        pool.sort(key=lambda x: len(x), reverse=True)
        for lab in pool:
            if up == lab.upper():
                return lab, None
            if up.startswith(lab.upper() + " "):
                return lab, text[len(lab):].strip()
        return None, None

    def cmd_identify(self, tokens):
        name, sess = self.require_session()
        if not tokens:
            print("Формат: i <метка> <предмет>   напр.: i GHOTI ew")
            return
        label, item_text = self.split_label_item(sess, tokens)
        if label is None:
            print("Не понял метку. Проверь список меток или сначала запиши "
                  "предмет командой s/b.")
            return
        item = Store.find_item_any_kind(sess, label)
        if item_text is None:
            if item:
                self.print_item(item)
            else:
                print("Метка «%s» пока не записана." % label)
            return
        kind_hint = item["kind"] if item else None
        best = {}
        for k, n, rank in canon_item_name(self.data, item_text, kind_hint):
            key = (k, n)
            if key not in best or rank < best[key]:
                best[key] = rank
        variants = sorted(((k, n, r) for (k, n), r in best.items()),
                          key=lambda x: x[2])
        if not variants:
            print("Не знаю предмет «%s». Примеры: ew, enchant weapon, "
                  "potion of levitation." % item_text)
            return
        exact = [v for v in variants if v[2] == 0] or variants
        if len(exact) > 1:
            opts = ", ".join(
                "%s (%s)" % (n, KIND_UNIT_RU[k]["scroll" if k == "scrolls"
                                                else "potion"])
                for k, n, _ in exact[:6])
            print("Уточни, что именно: " + opts)
            return
        kind, canonical, _ = exact[0]
        if item is None:
            item = {"kind": kind, "label": label, "alias": "",
                    "identified_as": None, "price": None, "candidates": [],
                    "updated": time.strftime("%Y-%m-%d %H:%M")}
            sess["items"].append(item)
            print("(метка %s добавлена в сессию)" % label)
        item["identified_as"] = canonical
        item["updated"] = time.strftime("%Y-%m-%d %H:%M")
        self.store.save()
        files = self.store.write_csvs(self.session_name)
        mine = [p for p in files if p.endswith(kind + ".csv")]
        rel = ", ".join(os.path.relpath(p, self.store.base) for p in mine) or "-"

        print("Распознано: %s = %s of %s" % (label, KIND_UNIT[kind], canonical))
        # где ещё фигурировал этот тип без записи про псевдонимы
        others = [it["label"] for it in sess["items"]
                  if it["kind"] == kind and it is not item
                  and canonical in it.get("candidates", [])
                  and not it.get("identified_as")]
        if others:
            print("Этот предмет входил в списки кандидатов: %s."
                  % ", ".join(others))
        print("Он больше не будет предлагаться в новых списках. [%s]" % rel)

    def cmd_delete(self, tokens):
        name, sess = self.require_session()
        if not tokens:
            print("Формат: d <метка>")
            return
        label = " ".join(tokens)
        item = Store.find_item_any_kind(sess, label)
        if not item:
            print("Метка «%s» не найдена." % label)
            return
        ans = (_ask("Удалить %s (%s)? [y/N] " % (
            item["label"], item.get("alias", ""))) or "").lower()
        if ans != "y":
            print("Отменено.")
            return
        sess["items"].remove(item)
        self.store.save()
        files = self.store.write_csvs(self.session_name)
        mine = [p for p in files if p.endswith(item["kind"] + ".csv")]
        rel = ", ".join(os.path.relpath(p, self.store.base) for p in mine) or "-"
        print("Удалено. [%s]" % rel)

    def print_item(self, it):
        print("%s  (%s)" % (it["label"], KIND_UNIT[it["kind"]]))
        print("  псевдоним: %s" % (it.get("alias") or "—"))
        if it.get("price"):
            print("  цена: %s %d" % ("продажа" if it["price"]["mode"] == "sell"
                                     else "покупка", it["price"]["value"]))
        if it.get("candidates"):
            print("  кандидаты: %s" % ", ".join(it["candidates"]))
        if it.get("identified_as"):
            print("  распознан: %s of %s" % (KIND_UNIT[it["kind"]],
                                             it["identified_as"]))
        else:
            print("  распознан: нет")

    def cmd_list(self, tokens):
        name, sess = self.require_session()
        filt = tokens[0].lower() if tokens else "все"
        items = sess["items"]
        ident = [i for i in items if i.get("identified_as")]
        unk = [i for i in items if not i.get("identified_as")]
        print("Сессия «%s»%s" % (name, (" — герой: %s" % sess.get("hero")) if sess.get("hero") else ""))
        if filt in ("все", "all", ""):
            show_ids, show_un = True, True
        elif filt.startswith("расп") or filt == "id":
            show_ids, show_un = True, False
        else:
            show_ids, show_un = False, True
        if show_un:
            print("Неопознанные (%d):" % len(unk))
            for it in unk:
                print("  %-22s %-11s %s" % (it["label"], KIND_UNIT[it["kind"]],
                                            it.get("alias") or "—"))
        if show_ids:
            print("Распознанные (%d):" % len(ident))
            for it in ident:
                print("  %-22s %-11s = %s of %s" % (it["label"],
                        KIND_UNIT[it["kind"]], KIND_UNIT[it["kind"]],
                        it["identified_as"]))

    def cmd_sess(self, tokens):
        if not tokens:
            cur = self.store.data.get("last")
            for n in self.store.names():
                s = self.store.data["sessions"][n]
                mark = "*" if n == cur else " "
                extra = []
                if s.get("hero"):
                    extra.append("герой: %s" % s["hero"])
                if s.get("role"):
                    extra.append("роль: %s" % s["role"])
                if s.get("cha") is not None:
                    extra.append("Cha: %s" % s["cha"])
                for k, v in (s.get("extra") or {}).items():
                    extra.append("%s: %s" % (k, v))
                print("%s %s%s" % (mark, n, (" — " + ", ".join(extra)) if extra else ""))
            print("(* — текущая; sess use <имя>, sess new <имя>, sess rm <имя>, "
                  "sess set <поле> <значение>)")
            return
        sub = tokens[0].lower()
        if sub == "use" and len(tokens) > 1:
            name = " ".join(tokens[1:])
            if name in self.store.names():
                self.store.data["last"] = name
                self.session_name = name
                self.store.save()
                print("Сессия: «%s»." % name)
            else:
                print("Нет сессии «%s». Есть: %s" % (name, ", ".join(self.store.names())))
        elif sub == "new" and len(tokens) > 1:
            name = " ".join(tokens[1:])
            if name in self.store.names():
                print("Сессия «%s» уже существует." % name)
                return
            hero = _ask("Имя героя (можно пропустить): ") or ""
            role = _ask("Роль (можно пропустить): ") or ""
            raw = _ask("Харизма (число, можно позже): ") or ""
            cha = int(raw) if raw.isdigit() else None
            self.store.add(name, hero=hero, role=role, cha=cha)
            self.session_name = name
            print("Сессия «%s» создана." % name)
        elif sub == "rm" and len(tokens) > 1:
            name = " ".join(tokens[1:])
            if name not in self.store.names():
                print("Нет сессии «%s»." % name)
                return
            ans = (_ask("Удалить сессию «%s» (вместе с её CSV)? [y/N] "
                        % name) or "").lower()
            if ans != "y":
                print("Отменено.")
                return
            self.store.delete(name)
            if self.session_name == name:
                self.session_name = self.store.data.get("last")
            print("Сессия «%s» удалена." % name)
        elif sub == "set" and len(tokens) > 2:
            name, sess = self.require_session()
            field, value = tokens[1].lower(), " ".join(tokens[2:])
            if field in ("cha", "харизма", "charisma"):
                if not value.isdigit():
                    print("Харизма — число.")
                    return
                sess["cha"] = int(value)
                print("Cha = %s" % value)
            elif field in ("hero", "герой"):
                sess["hero"] = value
                print("Герой: %s" % value)
            elif field in ("role", "роль"):
                sess["role"] = value
                print("Роль: %s" % value)
            else:
                sess.setdefault("extra", {})[tokens[1]] = value
                print("Записано: %s = %s" % (tokens[1], value))
            self.store.save()
        else:
            print("sess: показ | use <имя> | new <имя> | rm <имя> | "
                  "set <поле> <значение>")

    def cmd_help(self):
        print("""Команды:
  s <цена> [sc|po] [метка]   продажа: магазин предлагает <цена> за предмет
  b <цена> [sc|po] [метка]   покупка: магазин просит <цена>
  n <метка> [псевдоним]      переименовать/показать запись предмета
  i <метка> [предмет]        отметить распознанным (i GHOTI ew)
  d <метка>                  удалить запись предмета
  l [неоп|расп|все]          список предметов сессии
  sess                       сессии: use/new/rm/set <поле> <значение>
  help                       эта справка
  q                          выход

Пример: s 30 sc GHOTI  →  псевдоним bp/ew/ea/rc""")

    # ---------- интерактивный цикл ----------
    def repl(self):
        name, sess = self.require_session()
        print("NetHack: ценовая идентификация v%s (таблицы 3.6.0+). "
              "help — команды, q — выход." % VERSION)
        while True:
            try:
                line = input("[%s] > " % name).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not line:
                continue
            tokens = line.split()
            cmd = tokens[0].lower()
            args = tokens[1:]
            if cmd in ("q", "quit", "exit", "выход"):
                break
            elif cmd == "help":
                self.cmd_help()
            elif cmd == "s":
                self.cmd_sell_buy("sell", args)
            elif cmd == "b":
                self.cmd_sell_buy("buy", args)
            elif cmd == "n":
                self.cmd_name(args)
            elif cmd == "i":
                self.cmd_identify(args)
            elif cmd == "d":
                self.cmd_delete(args)
            elif cmd == "l":
                self.cmd_list(args)
            elif cmd in ("sess", "session", "сессии"):
                self.cmd_sess(args)
            else:
                print("Неизвестная команда: %s (help — список)" % cmd)
            name, sess = self.store.session(self.session_name)


# --------------------------------------------------------------------------
# Самопроверка
# --------------------------------------------------------------------------

def run_selftest(data, abbr):
    """Проверка ключевых сценариев на боевых данных. Без записи в рабочие файлы."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="price_id_selftest_")
    store = Store(tmp)
    store.add("T", hero="Sel", role="Tester", cha=7)
    app = App(data, store, abbr, "T")
    fails = []

    def names(matches):
        return [m.item["name"] for m in matches]

    # 1. продажа 30 (свитки) -> 4 шт, псевдоним bp/ew/ea/rc
    m = lookup(data, "scrolls", "sell", 30, None)
    got = names(m)
    exp = ["blank paper", "enchant weapon", "enchant armor", "remove curse"]
    if got != exp:
        fails.append("sell 30 scrolls: %s != %s" % (got, exp))
    else:
        alias, kind = make_alias(data, abbr, "scrolls", m, "sell", 30,
                                 sorted({x.row["sell"][0] for x in m}))
        if alias != "bp/ew/ea/rc":
            fails.append("alias sell30: %r" % alias)

    # 2. продажа 100 (свитки) -> amnesia/create monster/earth/taming
    m = lookup(data, "scrolls", "sell", 100, None)
    got = names(m)
    exp = ["amnesia", "create monster", "earth", "taming"]
    if got != exp:
        fails.append("sell 100 scrolls: %s != %s" % (got, exp))
    else:
        alias, kind = make_alias(data, abbr, "scrolls", m, "sell", 100,
                                 sorted({x.row["sell"][0] for x in m}))
        if alias != "amn/crmon/eart/tam":
            fails.append("alias sell100: %r" % alias)

    # 3. продажа 50 (зелья) -> 8 шт, длинный псевдоним s50_n
    m = lookup(data, "potions", "sell", 50, None)
    if len(m) != 8:
        fails.append("sell 50 potions: %d совпадений != 8" % len(m))
    else:
        s = store.data["sessions"]["T"]
        n = next_s_index(s, "s50_")
        if "s50_%d" % n != "s50_1":
            fails.append("s50 counter: %r" % ("s50_%d" % n))

    # 4. покупка 300 при харизме 7 (зелья) -> 10 шт, sell 75 => s75_1
    m = lookup(data, "potions", "buy", 300, 7)
    if len(m) != 10:
        fails.append("buy 300 cha7 potions: %d совпадений != 10" % len(m))
    else:
        sv = sorted({x.row["sell"][0] for x in m})
        if sv[0] != 75:
            fails.append("buy 300: min sell %r != 75" % sv)

    # 5. цепочка регистрации + исключение распознанного
    s = store.data["sessions"]["T"]
    it = {"kind": "scrolls", "label": "GHOTI", "alias": "bp/ew/ea/rc",
          "identified_as": None, "price": {"mode": "sell", "value": 30},
          "candidates": [x.item["name"] for x in lookup(data, "scrolls", "sell", 30, None)]}
    s["items"].append(it)
    files = store.write_csvs("T")
    it2 = Store.find_item(s, "scrolls", "GHOTI")
    if not it2 or it2["alias"] != "bp/ew/ea/rc":
        fails.append("register/lookup GHOTI")
    csv_path = os.path.join(store.csv_dir("T"), "scrolls.csv")
    if not any(p == csv_path for p in files) or not os.path.exists(csv_path):
        fails.append("csv не записан")
    else:
        txt = open(csv_path, encoding="utf-8").read()
        if "GHOTI;bp/ew/ea/rc;" not in txt:
            fails.append("csv содержимое: %r" % txt)
    # распознаём enchant weapon -> исключается из новых списков
    it["identified_as"] = "enchant weapon"
    ident = store.identified_types(s, "scrolls")
    m = [x for x in lookup(data, "scrolls", "sell", 30, None)
         if x.item["name"] not in ident]
    if names(m) != ["blank paper", "enchant armor", "remove curse"]:
        fails.append("exclusion после распознавания: %s" % names(m))
    else:
        alias, kind = make_alias(data, abbr, "scrolls", m, "sell", 30,
                                 sorted({x.row["sell"][0] for x in m}))
        if alias != "bp/ea/rc":
            fails.append("alias после исключения: %r" % alias)
    store.write_csvs("T")
    txt = open(csv_path, encoding="utf-8").read()
    if "GHOTI;bp/ew/ea/rc;scroll of enchant weapon" not in txt:
        fails.append("csv после распознавания: %r" % txt)

    # 6. покупка: сучок/наценка учитывается автоматически (цена из тройки)
    m = lookup(data, "potions", "buy", 400, 7)   # 400 = (400/533) и (300/400)
    if len(m) != 10:
        fails.append("buy 400 cha7: %d != 10" % len(m))

    # 7. одинаковые цены -> разные стили псевдонимов (как в ТЗ)
    s2 = {"items": []}
    m30 = lookup(data, "scrolls", "sell", 30, None)
    sv30 = sorted({x.row["sell"][0] for x in m30})
    a1, _ = make_alias(data, abbr, "scrolls", m30, "sell", 30, sv30, s2)
    s2["items"].append({"kind": "scrolls", "label": "L1", "alias": a1})
    a2, _ = make_alias(data, abbr, "scrolls", m30, "sell", 30, sv30, s2)
    s2["items"].append({"kind": "scrolls", "label": "L2", "alias": a2})
    a3, _ = make_alias(data, abbr, "scrolls", m30, "sell", 30, sv30, s2)
    s2["items"].append({"kind": "scrolls", "label": "L3", "alias": a3})
    a4, _ = make_alias(data, abbr, "scrolls", m30, "sell", 30, sv30, s2)
    if a1 != "bp/ew/ea/rc":
        fails.append("variants a1: %r" % a1)
    if a2 != "blank/enchw/enchar/remcur":
        fails.append("variants a2: %r" % a2)
    if a3 != "bpap/enweap/earm/rcur":
        fails.append("variants a3: %r" % a3)
    if a4 != "bpap/enweap/earm/rcur-2":
        fails.append("variants a4: %r" % a4)
    # повторная запись той же метки не должна повышать стиль
    a_same, _ = make_alias(data, abbr, "scrolls", m30, "sell", 30, sv30, s2,
                           exclude_label="L1")
    if a_same != "bp/ew/ea/rc":
        fails.append("variants self-exclude: %r" % a_same)

    # 8. уникальность сокращений внутри каждого стиля
    for k in ("scrolls", "potions"):
        for style in range(3):
            seen = {}
            for name, lst in abbr[k].items():
                v = lst[style] if style < len(lst) else None
                if v in seen:
                    fails.append("стиль %d: дубликат %r (%s / %s)"
                                 % (style + 1, v, seen[v], name))
                seen[v] = name

    # 9. распознавание названий в команде i: имя, сокращения, все стили
    data["_abbr"] = abbr
    for text, exp_kind, exp_name in (("ew", "scrolls", "enchant weapon"),
                                     ("enweap", "scrolls", "enchant weapon"),
                                     ("scroll of enchant weapon", "scrolls",
                                      "enchant weapon"),
                                     ("potion of levitation", "potions",
                                      "levitation"),
                                     ("lvt", "potions", "levitation"),
                                     ("wt", "potions", "water")):
        v = canon_item_name(data, text)
        if len(v) != 1 or v[0][0] != exp_kind or v[0][1] != exp_name:
            fails.append("canon %r -> %r" % (text, v))

    if fails:
        print("САМОПРОВЕРКА: %d ошибок" % len(fails))
        for f in fails:
            print("  ✗", f)
        return 1
    print("САМОПРОВЕРКА: все проверки пройдены ✓")
    return 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="price_id.py",
        description="Ценовая идентификация предметов NetHack (свитки/зелья, 3.6.0+).")
    ap.add_argument("--html", help="путь к price_id.html")
    ap.add_argument("--data", help="путь к price_id_data.json")
    ap.add_argument("--abbr", help="путь к price_id_abbr.json")
    ap.add_argument("--store", help="каталог для sessions.json и CSV "
                                    "(по умолчанию — рядом со скриптом)")
    ap.add_argument("--session", help="имя сессии")
    ap.add_argument("--rebuild", action="store_true",
                    help="перестроить price_id_data.json из price_id.html")
    ap.add_argument("--selftest", action="store_true", help="самопроверка")
    ap.add_argument("cmd", nargs="*", help="команда (без неё — интерактивный режим)")
    args = ap.parse_args(argv)

    store_dir = args.store or SCRIPT_DIR
    data = load_or_build_data(args)
    abbr = get_abbr(data, args)
    data["_abbr"] = abbr
    store = Store(store_dir)

    if args.selftest:
        sys.exit(run_selftest(data, abbr))

    if not args.cmd:
        App(data, store, abbr, args.session).repl()
        sys.exit(0)

    cmd = args.cmd[0].lower()
    rest = args.cmd[1:]
    app = App(data, store, abbr, args.session)
    if cmd == "s":
        app.cmd_sell_buy("sell", rest, interactive=False)
    elif cmd == "b":
        app.cmd_sell_buy("buy", rest, interactive=False)
    elif cmd == "n":
        app.cmd_name(rest)
    elif cmd == "i":
        app.cmd_identify(rest)
    elif cmd in ("sess", "session", "сессии"):
        app.cmd_sess(rest)
    elif cmd == "l":
        app.cmd_list(rest)
    elif cmd == "help":
        app.cmd_help()
    else:
        print("Неизвестная команда: %s" % cmd)
        sys.exit(2)


if __name__ == "__main__":
    main()
