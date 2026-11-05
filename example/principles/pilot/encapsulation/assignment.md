# Zadání: Skladová evidence

Procvičíte princip **Zapouzdření**. Dostanete kostru balíčku se dvěma moduly, `inventory.py` a `shop.py`. Všude, kde je `raise NotImplementedError`, doplníte vlastní implementaci. Názvy, parametry a návratové typy zachovejte přesně tak, jak jsou v kostře.

## Co program dělá

Program vede evidenci zboží na skladě. Sklad si pamatuje, kolik kusů které položky (zboží identifikovaného názvem) je k dispozici. Nad skladem pracují čtyři operace: prodej, naskladnění dodávky, vyprázdnění položky a textový přehled.

- **Vstupy:** názvy položek jsou řetězce (`str`), množství jsou celá čísla (`int`).
- **Výstupy:** funkce mění stav skladu, nebo vracejí číslo či text (viz níže). Nic se nevypisuje na obrazovku a nic se nečte z klávesnice.

### Pravidla skladu

1. Množství jakékoli položky na skladě je vždy celé číslo větší než 0. Položka, které by zbylo 0 kusů, ze skladu úplně zmizí (nevede se jako položka s nulou).
2. Položka, která na skladě není, má množství 0.
3. Přidávat i ubírat lze jen kladný počet kusů (větší než 0).
4. Ze skladu nelze ubrat víc kusů, než je k dispozici, ani ubrat z položky, která tam není.

### Chybové případy

Každé porušení pravidel se hlásí výjimkou `ValueError` s krátkou českou zprávou, která říká, co je špatně. Při chybě zůstává sklad beze změny.

- počáteční zásoba obsahuje množství, které není kladné,
- `add` nebo `remove` dostane množství, které není kladné,
- `remove` chce ubrat víc kusů, než je na skladě, nebo ubírá neexistující položku,
- `restock` dostane dodávku, ve které je alespoň jedno množství nekladné. Dodávka se zpracuje buď celá, nebo vůbec: pokud je neplatná byť jediná položka, sklad se nezmění vůbec.
- `sell` přenáší chyby z `remove`.

## Moduly, třídy a funkce

Balíček obsahuje soubory `__init__.py` (prázdný), `inventory.py` a `shop.py`.

### Modul `inventory.py`

```python
class Inventory:
    def __init__(self, stock: dict[str, int] | None = None) -> None: ...
    def add(self, item: str, quantity: int) -> None: ...
    def remove(self, item: str, quantity: int) -> None: ...
    def quantity(self, item: str) -> int: ...
    def items(self) -> dict[str, int]: ...
```

- `__init__(stock=None)` vytvoří sklad. Bez argumentu je sklad prázdný. Pokud je předán slovník `název -> množství`, sklad z něj vyjde, ale později se slovníkem nesouvisí: změna slovníku, který jste předali, sklad nijak neovlivní. Položky s množstvím 0 se při vytváření vynechají; záporné množství je chyba (`ValueError`).
- `add(item, quantity)` přidá `quantity` kusů položky `item`. Neexistující položka se tím na skladě objeví.
- `remove(item, quantity)` odebere `quantity` kusů položky. Pokud by po odebrání zbylo 0, položka ze skladu zmizí.
- `quantity(item)` vrátí množství dané položky, pro neznámou položku 0.
- `items()` vrátí slovník `název -> množství` se všemi položkami na skladě. Je to kopie: úprava vráceného slovníku sklad nijak nezmění.

### Modul `shop.py`

```python
from .inventory import Inventory

def sell(inventory: Inventory, item: str, quantity: int) -> None: ...
def restock(inventory: Inventory, deliveries: dict[str, int]) -> None: ...
def clear_out(inventory: Inventory, item: str) -> int: ...
def report(inventory: Inventory) -> str: ...
```

- `sell(inventory, item, quantity)` prodá `quantity` kusů položky `item` ze zadaného skladu. Chyby viz výše.
- `restock(inventory, deliveries)` naskladní dodávku, slovník `název -> množství`. Všechna množství musí být kladná, jinak `ValueError` a sklad zůstane nezměněn. Prázdná dodávka je v pořádku a nic nemění.
- `clear_out(inventory, item)` odstraní ze skladu všechny kusy položky `item` a vrátí, kolik jich bylo. Pokud položka na skladě nebyla, vrátí 0 a nic se nestane.
- `report(inventory)` vrátí textový přehled skladu: jeden řádek na položku ve tvaru `název: množství`, řádky seřazené abecedně podle názvu a oddělené znakem `\n` (za posledním řádkem už nový řádek není). Pro prázdný sklad vrátí text `(sklad je prázdný)`.

## Příklad běhu

```python
>>> from sklad.inventory import Inventory
>>> from sklad.shop import sell, restock, clear_out, report
>>> inv = Inventory({"jablka": 10, "hrusky": 4})
>>> sell(inv, "jablka", 3)
>>> inv.quantity("jablka")
7
>>> restock(inv, {"slivky": 5, "hrusky": 1})
>>> print(report(inv))
hrusky: 5
jablka: 7
slivky: 5
>>> clear_out(inv, "hrusky")
5
>>> clear_out(inv, "banany")
0
>>> sell(inv, "jablka", 100)
Traceback (most recent call last):
  ...
ValueError: ...
>>> restock(inv, {"slivky": 2, "jablka": 0})
Traceback (most recent call last):
  ...
ValueError: ...
>>> inv.items()
{'jablka': 7, 'slivky': 5}
>>> sell(inv, "jablka", 7)
>>> inv.items()
{'slivky': 5}
```

(Název balíčku `sklad` je v příkladu jen ilustrační; použijte název složky, ve které kostru máte.)

## Princip: Zapouzdření

Zapouzdření znamená, že objekt si svůj stav spravuje sám: ostatní kód ho mění jen voláním metod objektu a čte jen přes jeho veřejné metody, na atributy začínající podtržítkem zvenku nesahá. V této úloze je stavem skladu to, kolik čeho je na skladě, a pravidla skladu (množství jsou kladná, nelze ubrat víc, než je k dispozici, položka s nulou zmizí) mají ležet na jednom místě, uvnitř třídy `Inventory`. Funkce v `shop.py` jsou ostatní kód: skladem smějí pracovat jen přes jeho veřejné metody `add`, `remove`, `quantity` a `items`. Díky tomu se dá vnitřní uložení dat v `Inventory` kdykoli změnit, aniž by se `shop.py` musel upravit, a žádná funkce nemůže pravidla skladu obejít.
