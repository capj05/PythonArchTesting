# Zadání: Souhrn známek

## Co program dělá

Program načte od uživatele jeden řádek se známkami oddělenými mezerami, spočítá z nich průměr a vypíše krátký souhrn.

### Vstup

Jeden řádek textu zadaný z klávesnice. Řádek obsahuje celá čísla od 1 do 5 oddělená jednou nebo více mezerami, například `1 2 2 3 5`.

### Výstup

Jeden řádek ve tvaru:

```
Počet známek: 5, průměr: 2.60
```

Průměr se vypisuje zaokrouhlený na dvě desetinná místa.

### Chybové případy

Program nesmí skončit chybou (výjimkou) vypsanou uživateli. Při chybném vstupu vypíše jednu řádku s chybovým hlášením a skončí:

- Řádek je prázdný nebo obsahuje jen mezery (žádné známky): `Chyba: nebyla zadána žádná známka.`
- Některá položka není celé číslo (např. `abc`, `2.5`): `Chyba: "abc" není celé číslo.` (uvede se právě ta chybná položka).
- Některé číslo leží mimo rozsah 1 až 5: `Chyba: známka 7 je mimo rozsah 1 až 5.` (uvede se právě to chybné číslo; pokud je chybných víc, platí první zleva).

Tyto chyby se v kódu signalizují výjimkou `ValueError` s textem hlášení (bez předpony `Chyba: `, kterou doplňuje uživatelské rozhraní).

### Příklady běhu

```
Zadej známky: 1 2 2 3 5
Počet známek: 5, průměr: 2.60
```

```
Zadej známky: 4   4 1
Počet známek: 3, průměr: 3.00
```

```
Zadej známky: 1 x 3
Chyba: "x" není celé číslo.
```

```
Zadej známky: 2 6
Chyba: známka 6 je mimo rozsah 1 až 5.
```

```
Zadej známky:
Chyba: nebyla zadána žádná známka.
```

## Struktura programu

Kostra obsahuje dva moduly. Signatury ponechte přesně tak, jak jsou uvedeny.

### Modul `grades.py`

```python
def parse_grades(text: str) -> list[int]:
    ...

def average(grades: list[int]) -> float:
    ...

def format_summary(grades: list[int]) -> str:
    ...
```

- `parse_grades(text)` převede řádek textu na seznam známek. Při chybném vstupu vyvolá `ValueError` podle pravidel výše.
- `average(grades)` vrátí aritmetický průměr známek.
- `format_summary(grades)` vrátí text souhrnu, tedy řetězec ve tvaru `Počet známek: 5, průměr: 2.60`.

### Modul `app.py`

```python
from .grades import format_summary, parse_grades


def main() -> None:
    ...
```

- `main()` je funkce uživatelského rozhraní: vyzve uživatele (`Zadej známky: `), načte řádek, použije funkce z `grades.py` a vypíše výsledek, nebo při `ValueError` vypíše chybové hlášení.

## Princip: Oddělení logiky od vstupu a výstupu

V této úloze jde o to, aby funkce, které něco počítají nebo zpracovávají, dostávaly data jako parametry a výsledek vracely, místo aby ho vypisovaly nebo si data samy četly z klávesnice. Zpracování textu, výpočet průměru i sestavení věty souhrnu jsou logika; čtení řádku od uživatele a vypsání výsledku či chyby je vstup a výstup, který patří jen do `main`. Díky tomu lze logiku z `grades.py` použít znovu (v jiném programu, na webu) a vyzkoušet ji bez klávesnice, zatímco funkce, která výsledek jen vypíše, se dá použít jediným způsobem.
