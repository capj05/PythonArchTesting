**Kde je chyba:** v souboru `grades.py`, ve funkci `parse_grades` (řádek 19), na řádku 21 voláš `input("Zadej známky: ")`.

**Princip:** „Logic apart from input and output" (logika odděleně od vstupu a výstupu). Funkce, které něco počítají nebo zpracovávají, dostávají data jako parametry a vracejí výsledek. S uživatelem (klávesnice, obrazovka, soubory) komunikují jen funkce uživatelského rozhraní, typicky `main`.

**Proč je to problém:** `parse_grades` má parametr `text`, ale hned ho přepíše výsledkem `input()`. Předaná data se tedy nikdy nepoužijí. `app.py` volá `parse_grades("")` a funkci nelze zavolat s jinými daty, například ze souboru nebo v testu, bez klávesnice.

**Oprava:** Přesuň `input(...)` (včetně ošetření `EOFError`) do `main` v `app.py`. Načtený text předej funkci `parse_grades(text)` a v ní řádek s `input()` smaž.
