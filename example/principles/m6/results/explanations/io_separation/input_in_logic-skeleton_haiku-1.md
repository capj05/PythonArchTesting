**Kde je chyba:** v souboru `grades.py`, ve funkci `parse_grades` (řádek 8), na řádku 9 voláš `input("Zadej známky: ")`.

**Princip:** „Logic apart from input and output" (logika odděleně od vstupu a výstupu). Funkce, které něco počítají, dostávají data jako parametry a vracejí výsledek. S uživatelem (klávesnice, obrazovka, soubory) mluví jen funkce uživatelského rozhraní, typicky `main`.

**Proč je to problém:** `parse_grades` dostane `text` jako parametr, ale hned ho přepíše tím, co uživatel napíše. Funkci proto nelze zavolat s jinými daty (ze souboru, v testu) a parametr `text` nemá žádný smysl. V `app.py` navíc posíláš prázdný řetězec `""`, který se stejně zahodí.

**Oprava:** řádek 9 v `parse_grades` smaž. V `main` (`app.py`) načti vstup pomocí `input("Zadej známky: ")` a předej ho funkci: `parse_grades(text)`.
