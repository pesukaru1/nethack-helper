from bs4 import BeautifulSoup
import re  # для регулярных выражений
from lxml import html, etree
import os
import pandas as pd

with open('price_id.html', 'r', encoding='utf-8') as file:
    soup = BeautifulSoup(file, "lxml")

h3titles = soup.find_all("h4")
onetag = soup.find("h3")

# for h3tag in h3titles:
#     print(h3tag.text.strip())

# print(onetag.text)

header = soup.find('h3', string='Potions')

if header:
    # 3. Ищем следующую таблицу после этого заголовка
    all_subsequent_tables = header.find_all_next('table')

target_table_tag = all_subsequent_tables[1]
target_table = pd.read_html(str(target_table_tag))

print(target_table)