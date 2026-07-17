import re
import pandas as pd
from collections import defaultdict

# 1. Загружаем все таблицы из файла
tables = pd.read_html('table.html')

# 2. Создаем пустой глобальный индекс
# Ключами здесь будут уже чистые строки-числа (например, '75', '100', '133')
global_index = defaultdict(list)

# Укажите точное название вашего столбца
COLUMN_NAME = 'Показатели' 

# 3. Перебираем таблицы, строки и ячейки
for t_idx, df in enumerate(tables):
    if COLUMN_NAME in df.columns:
        
        # Перебираем строки таблицы. 
        # r_idx — индекс строки, row — все данные этой строки
        for r_idx, row in df.iterrows():
            cell_value = str(row[COLUMN_NAME])  # Приводим к строке на случай наны/чисел
            
            # Извлекаем все числа из строки типа "75 (100/133)"
            # \d+ находит любые группы цифр. Для "75 (100/133)" вернет ['75', '100', '133']
            numbers = re.findall(r'\d+', cell_value)
            
            # Привязываем координаты строки к каждому найденному числу
            for num in numbers:
                coordinate = (t_idx + 1, r_idx + 1) # Сразу делаем отсчет с 1 для человека
                
                # Защита от дублей: если это же число уже встречалось в ЭТОЙ ЖЕ строке,
                # не добавляем его повторно
                if coordinate not in global_index[num]:
                    global_index[num].append(coordinate)

# --- ПРОЦЕСС ПОИСКА ---

# Введите любое из трех чисел, которое вы хотите найти
search_number = '100'

if search_number in global_index:
    print(f"Число '{search_number}' обнаружено в следующих местах:")
    for t_num, r_num in global_index[search_number]:
        print(f" Таблица №{t_num}, Строка №{r_num}")
else:
    print(f"Число '{search_number}' не найдено ни в одной таблице.")
