**Kde je chyba:** v souboru `shop.py`, ve funkci `clear_out`, na řádku 23: `inventory._stock = left`.

**Princip:** Zapouzdření (Encapsulation). Objekt spravuje svůj stav sám. Ostatní kód ho mění jen voláním metod objektu a atributy začínající podtržítkem zvenčí nepřepisuje.

**Proč je to problém:** Funkce přepíše vnitřní slovník `_stock` třídy `Inventory` svou vlastní verzí. Objekt o změně neví a obchází pravidla, která drží jeho metody (například `remove`). Pokud třída změní způsob ukládání dat, `clear_out` přestane fungovat.

**Jak to opravit:** Odeberte řádky 21 až 23 a zboží odeberte veřejnou metodou. Množství už máte v `qty`, takže stačí zavolat `inventory.remove(item, qty)`.
