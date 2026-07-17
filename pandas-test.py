import pandas as pd

# 1. Читаем все таблицы из HTML-файла
# Функция возвращает список ВСЕХ таблиц, найденных на странице
tables = pd.read_html('price_id.html', displayed_only=True)

# Берем первую таблицу (индекс 0)
df = tables[1]

# print(pd.DataFrame(df))
print(df)