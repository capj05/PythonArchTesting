**Kde je chyba:** v souboru `grades.py`, ve funkci `format_summary` (řádek 27), na řádku 28 voláš `print()`.

**Princip:** „Logic apart from input and output" (logika odděleně od vstupu a výstupu). Funkce, které něco počítají, dostanou data jako parametry a výsledek vracejí. S uživatelem (klávesnice, obrazovka, soubory) mluví jen funkce uživatelského rozhraní, typicky `main`.

**Proč je to problém:** `format_summary` výsledek jen vytiskne, takže ho program nemůže dál použít. Nelze ho ani vyzkoušet v testu bez sledování obrazovky ani použít jinde než pro tisk.

**Jak to opravit:** v `format_summary` nahraď `print(...)` za `return ...` a změň návratový typ na `str`. Vytištění udělej až v `main` v `app.py`, tedy `print(format_summary(grades))`.
