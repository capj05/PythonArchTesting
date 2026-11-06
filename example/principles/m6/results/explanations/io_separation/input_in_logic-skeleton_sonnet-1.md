**Kde je chyba:** v souboru `grades.py`, ve funkci `parse_grades` (řádek 8), na řádku 9: `text = input("Zadej známky: ")`.

**Jaký princip to porušuje:** „Logic apart from input and output" (logika odděleně od vstupu a výstupu). Funkce, které něco počítají, mají dostat data jako parametry a vrátit výsledek. S uživatelem (klávesnice, obrazovka, soubory) mluví jen funkce uživatelského rozhraní, typicky `main`.

**Proč je to problém:** `parse_grades` dostane `text` jako parametr, ale hned ho přepíše vstupem z klávesnice. Funkci proto nelze zavolat s jinými daty (ze souboru, v testu) a parametr `text` ztrácí smysl. Všimni si, že `main` v `app.py` posílá prázdný řetězec `""`, který se nikdy nepoužije.

**Jak to opravit:** řádek 9 z `parse_grades` smaž. Vstup načti v `main` pomocí `input("Zadej známky: ")` a předej ho funkci: `parse_grades(text)`.
