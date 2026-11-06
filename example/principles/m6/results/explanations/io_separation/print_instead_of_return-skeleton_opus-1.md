**Kde je chyba:** v souboru `grades.py`, ve funkci `format_summary`, na řádku 33 voláš `print()`.

**Princip:** porušuješ princip „Logic apart from input and output" (logika odděleně od vstupu a výstupu). Funkce, které něco počítají nebo sestavují, mají výsledek vracet pomocí `return`. S uživatelem (klávesnice, obrazovka) komunikují jen funkce uživatelského rozhraní, typicky `main`.

**Proč je to problém:** `format_summary` text jen vytiskne a nevrátí ho. Program s ním pak nemůže nic dalšího udělat: nepoužít ho jinde, ani ho otestovat bez obrazovky. Funkci jde použít jediným způsobem, a to vytisknout text.

**Jak opravit:** v `format_summary` nahraď `print(...)` za `return f"Počet známek: ..."` (změň i návratový typ na `str`). V `main` v `app.py` (řádek 16) pak výsledek vytiskni: `print(format_summary(grades))`.
