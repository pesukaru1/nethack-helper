from simple_term_menu import TerminalMenu
from bs4 import BeautifulSoup
import pandas as pd
import re
from collections import defaultdict





with open('price_id.html', 'r', encoding='utf-8') as file:
    soup = BeautifulSoup(file, "lxml")

def gettable(category):
    target_category = soup.find('h3', string=category)
    all_next_tables = target_category.find_all_next('table')
    target_table = all_next_tables[1]
    return target_table

def find_column_by_number(df_columns, number):
    for col in df_columns:
        col_str = str(col)
        ranges = re.findall(r'\d+', col_str)

        if not ranges:
            continue

        if len(ranges) == 1:
            threshold = int(ranges[0])
            if '<' in col_str:
                if number < threshold:
                    return col
            elif '>' in col_str:
                if number > threshold:
                    return col
        elif len(ranges) == 2:
            low, high = int(ranges[0]), int(ranges[1])
            if low <= number <= high:
                return col

    print("Значение харизмы не попадает в допустимый диапазон")
    return None

def getresult(table, column, value):
    df = table
    mask = df[column].astype(str).str.contains(value)
    result = df.loc[mask, df.columns[-1]]
    return result



def main():

    options = ["Scrolls", "Potions"]
    terminal_menu = TerminalMenu(options)
    menu_item_index = terminal_menu.show()

    charisma = input("Charisma: ")

    target_table = gettable(options[menu_item_index])

    clear_table = pd.read_html(str(target_table))[0]

    target_column = find_column_by_number(clear_table.columns, int(charisma))

    price = input("Price: ")

    id_results = getresult(clear_table, target_column, price)

    pd.set_option('display.max_colwidth', None)





    print(id_results)

if __name__ == "__main__":
    main()