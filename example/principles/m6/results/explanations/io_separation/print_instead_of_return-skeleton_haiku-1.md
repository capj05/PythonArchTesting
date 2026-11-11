**Kde je chyba:** v souboru `grades.py`, ve funkci `format_summary` (řádek 30), na řádku 31 voláš `print()`.

**Princip:** „Logic apart from input and output" (Logika odděleně od vstupu a výstupu). Funkce, které něco počítají, mají dostat data jako parametry a výsledek vrátit pomocí `return`. S uživatelem (klávesnice, obrazovka, soubory) mluví jen funkce uživatelského rozhraní, typicky `main`.

**Proč je to problém:** `format_summary` výsledek jen vytiskne, takže ho program nemůže dál použít. Funkci nelze znovu využít jinde (v jiném programu, na webu) ani ji pohodlně otestovat bez obrazovky. Slouží jen k tisku.

**Jak opravit:** v `format_summary` nahraď `print(...)` za `return f"Počet známek: ..., průměr: ..."` a změň návratový typ z `None` na `str`. V `app.py` ve funkci `main` pak výsledek vytiskni: `print(format_summary(grades))`.
