# Zadání: Cena nákupu se slevou

Procvičíte princip **Strategie**. Dostanete kostru balíčku se třemi moduly, `discounts.py`, `pricing.py` a `app.py`. Všude, kde je `raise NotImplementedError`, doplníte vlastní implementaci. Názvy, parametry a návratové typy zachovejte přesně tak, jak jsou v kostře.

## Co program dělá

Program počítá cenu nákupu. Cena je součet cen položek, ze kterého se odečte sleva. Druhů slev je několik (žádná sleva, procentní sleva, množstevní sleva) a obchod je chce časem přidávat. Kalkulačka ceny dostane slevu při vytvoření a při každém výpočtu ji použije.

- **Vstupy:** ceny položek jsou čísla (`float`) v seznamu, procenta a hranice slev jsou čísla, slevový kód je řetězec (`str`).
- **Výstupy:** funkce a metody vracejí cenu jako číslo zaokrouhlené na dvě desetinná místa. Nic se nevypisuje na obrazovku a nic se nečte z klávesnice.

### Pravidla slev

1. Žádná sleva vrátí částku beze změny.
2. Procentní sleva `p` sníží částku o `p` procent: `částka · (100 − p) / 100`. Procento je mezi 0 a 100 včetně.
3. Množstevní sleva s hranicí `n` a procentem `p` sníží částku o `p` procent jen tehdy, když je částka alespoň `n`; menší částka zůstane beze změny. Hranice není záporná, procento je mezi 0 a 100 včetně.
4. Cena nákupu je součet cen položek po slevě, zaokrouhlený funkcí `round(..., 2)`. Prázdný nákup stojí 0.
5. Žádná cena položky nesmí být záporná.

### Chybové případy

Každé porušení pravidel se hlásí výjimkou `ValueError` s krátkou českou zprávou, která říká, co je špatně:

- procentní nebo množstevní sleva s procentem mimo 0–100, množstevní sleva se zápornou hranicí (při vytvoření slevy),
- nákup, ve kterém je alespoň jedna cena záporná (při výpočtu ceny).

## Moduly, třídy a funkce

Balíček obsahuje soubory `__init__.py` (prázdný), `discounts.py`, `pricing.py` a `app.py`.

### Modul `discounts.py`

```python
from typing import Protocol

class Discount(Protocol):
    def apply(self, amount: float) -> float: ...

class NoDiscount:
    def apply(self, amount: float) -> float: ...

class PercentDiscount:
    def __init__(self, percent: float) -> None: ...
    def apply(self, amount: float) -> float: ...

class BulkDiscount:
    def __init__(self, threshold: float, percent: float) -> None: ...
    def apply(self, amount: float) -> float: ...
```

- `Discount` jen popisuje, co umí každá sleva: metodu `apply`. Nic v ní nedoplňujete a ostatní slevy z ní nedědí; stačí, že mají stejnou metodu.
- `NoDiscount`, `PercentDiscount(percent)` a `BulkDiscount(threshold, percent)` jsou jednotlivé slevy. Parametry si uloží pod stejnými jmény a odmítnou neplatné hodnoty.
- `apply(amount)` vrátí částku po slevě podle pravidel 1–3 (bez zaokrouhlení).

### Modul `pricing.py`

```python
from .discounts import Discount

class PriceCalculator:
    def __init__(self, discount: Discount) -> None: ...
    def total(self, prices: list[float]) -> float: ...
```

- `PriceCalculator(discount)` si zapamatuje slevu, kterou dostal.
- `total(prices)` vrátí cenu nákupu podle pravidla 4 se slevou, kterou kalkulačka dostala. Záporná cena položky je chyba.

### Modul `app.py`

```python
from .discounts import BulkDiscount, Discount, NoDiscount, PercentDiscount
from .pricing import PriceCalculator

def checkout(prices: list[float], code: str = "") -> float: ...
```

- `checkout(prices, code)` vybere slevu podle slevového kódu, sestaví s ní kalkulačku a vrátí cenu nákupu:
  - `"STUDENT"`: procentní sleva 10 %,
  - `"VELKY_NAKUP"`: množstevní sleva 5 % od částky 1000,
  - jakýkoli jiný kód (i prázdný): žádná sleva.

## Příklad běhu

```python
>>> from ceny.discounts import BulkDiscount, NoDiscount, PercentDiscount
>>> from ceny.pricing import PriceCalculator
>>> from ceny.app import checkout
>>> PriceCalculator(PercentDiscount(10)).total([120.0, 30.5])
135.45
>>> PriceCalculator(NoDiscount()).total([120.0, 30.5])
150.5
>>> bulk = PriceCalculator(BulkDiscount(1000, 5))
>>> bulk.total([999.9])
999.9
>>> bulk.total([999.9, 0.1, 250.0])
1187.5
>>> checkout([200.0], "STUDENT")
180.0
>>> checkout([19.99, 5.01])
25.0
>>> PercentDiscount(120)
Traceback (most recent call last):
  ...
ValueError: ...
>>> PriceCalculator(NoDiscount()).total([10.0, -1.0])
Traceback (most recent call last):
  ...
ValueError: ...
```

(Název balíčku `ceny` je v příkladu jen ilustrační; použijte název složky, ve které kostru máte.)

## Princip: Strategie

Strategie znamená, že zaměnitelné chování (tady způsob výpočtu slevy) je zabalené do samostatných objektů se stejným rozhraním a kód, který ho používá, ho dostane zvenku a jen ho zavolá. V této úloze je strategií sleva s metodou `apply` a kontextem je `PriceCalculator`: slevu dostane v konstruktoru a v `total` ji použije voláním `self.discount.apply(...)`. Kalkulačka nezjišťuje, o jaký druh slevy jde (žádné větvení podle typu slevy ani počítání procent sama), a žádnou slevu si sama nevytváří. Kterou slevu použít, rozhoduje jen kód, který kalkulačku sestavuje (`checkout` v `app.py`). Díky tomu se dá přidat nový druh slevy, aniž by se `pricing.py` musel upravit, a kalkulačku lze vyzkoušet s jakoukoli slevou.
