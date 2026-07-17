import re
import pandas as pd
from collections import defaultdict

# --- ФУНКЦИЯ ДЛЯ ОПРЕДЕЛЕНИЯ СТОЛБЦА ---
def find_column_by_number(df_columns, number):
    """Ищет среди колонок ту, в диапазон которой попадает number."""
    for col in df_columns:
        # Находим все числа в названии колонки (например, из "Cha 11–15" получим ['11', '15'])
        ranges = re.findall(r'\d+', str(col))
        if len(ranges) == 2:
            low, high = int(ranges[0]), int(ranges[1])
            if low <= number <= high:
                return col
    return None

# --- 1. СБОР ДАННЫХ И ПОСТРОЕНИЕ ИНДЕКСА ---

tables = pd.read_html('table.html')
global_index = defaultdict(list)

for t_idx, df in enumerate(tables):
    # Перебираем только те колонки, которые похожи на диапазоны (содержат "Cha")
    target_columns = [c for c in df.columns if 'Cha' in str(c)]
    
    for col_name in target_columns:
        for r_idx, row in df.iterrows():
            cell_value = str(row[col_name])
            
            # Извлекаем числа из ячейки (например, из "75 (100/133)")
            cell_numbers = re.findall(r'\d+', cell_value)
            
            for num in cell_numbers:
                # Наш составной ключ для хеш-таблицы: (название столбца, число из ячейки)
                key = (col_name, num)
                coordinate = (t_idx + 1, r_idx + 1)
                
                if coordinate not in global_index[key]:
                    global_index[key].append(coordinate)

# --- 2. ОБРАБОТКА ЗАПРОСА ПОЛЬЗОВАТЕЛЯ ---

# Эмуляция ввода пользователя
user_first_num = 12   # Какое имя столбца искать (попадет в Cha 11–15)
user_second_num = '133' # Какое значение искать в ячейках

# Шаг А: Выясняем, какой столбец соответствует числу 12.
# Берем для проверки колонки из первой таблицы (предполагаем, что структура одинакова)
target_column = find_column_by_number(tables[0].columns, user_first_num)

if target_column:
    print(f"Первое число {user_first_num} соответствует столбцу: '{target_column}'")
    
    # Шаг Б: Мгновенно ищем по инвертированному индексу
    search_key = (target_column, str(user_second_num))
    
    if search_key in global_index:
        print(f"Число '{user_second_num}' найдено в столбце '{target_column}':")
        for t_num, r_num in global_index[search_key]:
            print(f"  Таблица №{t_num}, Строка №{r_num}")
    else:
        print(f"В столбце '{target_column}' значение '{user_second_num}' не обнаружено.")
else:
    print(f"Ни один столбец не подходит под число {user_first_num}")
