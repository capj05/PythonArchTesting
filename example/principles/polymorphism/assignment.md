# Zadání: Plochy tvarů

Procvičíte princip **Polymorfismus**. Dostanete kostru balíčku se dvěma moduly, `shapes.py` a `report.py`. Všude, kde je `raise NotImplementedError`, doplníte vlastní implementaci. Názvy, parametry a návratové typy zachovejte přesně tak, jak jsou v kostře.

## Co program dělá

Program pracuje s rovinnými tvary: kruhem, obdélníkem a čtvercem. Každý tvar umí spočítat svou plochu a popsat se jednou větou. Nad seznamem tvarů pracují dvě funkce: součet ploch a textový přehled.

- **Vstupy:** rozměry tvarů jsou čísla (`float`), seznam tvarů je `list`.
- **Výstupy:** funkce vracejí číslo nebo text (viz níže). Nic se nevypisuje na obrazovku a nic se nečte z klávesnice.

### Pravidla tvarů

1. Každý rozměr (poloměr, strany) je kladné číslo (větší než 0).
2. Plocha kruhu je π · r² (použijte `math.pi`), plocha obdélníku šířka · výška, plocha čtverce strana².
3. Popis tvaru je jedna věta s rozměry tak, jak je vypíše f-string:
   - kruh: `kruh o poloměru 1.0`,
   - obdélník: `obdélník 2.0 x 3.0` (šířka, malé písmeno `x`, výška),
   - čtverec: `čtverec o straně 2.0`.

### Chybové případy

- Vytvoření tvaru s rozměrem, který není kladný, se hlásí výjimkou `ValueError` s krátkou českou zprávou, která říká, co je špatně.
- Obecný tvar `Shape` sám vytvořit nejde (`TypeError`): existují jen konkrétní tvary.

## Moduly, třídy a funkce

Balíček obsahuje soubory `__init__.py` (prázdný), `shapes.py` a `report.py`.

### Modul `shapes.py`

```python
import math
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self) -> float: ...
    @abstractmethod
    def describe(self) -> str: ...

class Circle(Shape):
    def __init__(self, radius: float) -> None: ...
    def area(self) -> float: ...
    def describe(self) -> str: ...

class Rectangle(Shape):
    def __init__(self, width: float, height: float) -> None: ...
    def area(self) -> float: ...
    def describe(self) -> str: ...

class Square(Shape):
    def __init__(self, side: float) -> None: ...
    def area(self) -> float: ...
    def describe(self) -> str: ...
```

- `Shape` je společný základ všech tvarů. Předepisuje, co každý tvar umí: `area()` a `describe()`. Sám žádnou plochu nepočítá.
- `Circle(radius)`, `Rectangle(width, height)` a `Square(side)` si rozměry uloží (pod stejnými jmény jako parametry) a odmítnou nekladný rozměr.
- `area()` vrátí plochu tvaru podle pravidla 2.
- `describe()` vrátí popis tvaru podle pravidla 3.

### Modul `report.py`

```python
from .shapes import Shape

def total_area(shapes: list[Shape]) -> float: ...
def describe_all(shapes: list[Shape]) -> str: ...
```

- `total_area(shapes)` vrátí součet ploch všech tvarů v seznamu. Pro prázdný seznam vrátí `0.0`.
- `describe_all(shapes)` vrátí přehled: jeden řádek na tvar ve tvaru `popis: plocha X`, kde `X` je plocha zaokrouhlená na dvě desetinná místa (`:.2f`). Řádky jsou v pořadí seznamu a oddělené znakem `\n` (za posledním řádkem už nový řádek není). Pro prázdný seznam vrátí prázdný text `""`.

## Příklad běhu

```python
>>> from tvary.shapes import Circle, Rectangle, Shape, Square
>>> from tvary.report import describe_all, total_area
>>> shapes = [Circle(1.0), Rectangle(2.0, 3.0), Square(2.0)]
>>> total_area(shapes)
13.141592653589793
>>> print(describe_all(shapes))
kruh o poloměru 1.0: plocha 3.14
obdélník 2.0 x 3.0: plocha 6.00
čtverec o straně 2.0: plocha 4.00
>>> total_area([])
0.0
>>> Circle(0)
Traceback (most recent call last):
  ...
ValueError: ...
>>> Shape()
Traceback (most recent call last):
  ...
TypeError: ...
```

(Název balíčku `tvary` je v příkladu jen ilustrační; použijte název složky, ve které kostru máte.)

## Princip: Polymorfismus

Polymorfismus znamená, že různé druhy objektů mají společné rozhraní a kód, který s nimi pracuje, jen volá jejich metody: každý objekt sám ví, jak danou věc udělat po svém. V této úloze je společným rozhraním abstraktní třída `Shape` s metodami `area` a `describe`; každý konkrétní tvar z ní dědí a metody si implementuje sám. Funkce v `report.py` pracují s libovolným tvarem jen voláním `shape.area()` a `shape.describe()`: nezjišťují, o jaký druh tvaru jde (žádné `isinstance` ani `type`), a nesahají na rozměry jednotlivých tvarů. Díky tomu se dá přidat nový tvar, aniž by se `report.py` musel upravit, a abstraktní základ zaručí, že žádný tvar nezapomene některou z metod implementovat.
