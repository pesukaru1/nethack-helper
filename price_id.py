from simple_term_menu import TerminalMenu
from bs4 import BeautifulSoup
import pandas as pd
import re




with open('price_id.html', 'r', encoding='utf-8') as file:
    soup = BeautifulSoup(file, "lxml")

def gettable(category):
    target_category = soup.find('h3', string=category)
    all_next_tables = target_category.find_all_next('table')
    target_table = all_next_tables[1]
    return target_table

def main():

    options = ["Scrolls", "Potions"]
    terminal_menu = TerminalMenu(options)
    menu_item_index = terminal_menu.show()

    charisma = input("Charisma: ")

    target_table = gettable(options[menu_item_index])

    clear_table = pd.read_html(str(target_table))[0]

    print(clear_table.columns)

if __name__ == "__main__":
    main()