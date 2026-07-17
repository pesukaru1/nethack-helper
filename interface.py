from simple_term_menu import TerminalMenu

options = ["Scrolls", "Potions", "Wands"]
terminal_menu = TerminalMenu(options)
menu_entry_index = terminal_menu.show()
print(f"Вы выбрали: {options[menu_entry_index]}")
