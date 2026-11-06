**Kde je chyba:** v souboru `shop.py`, ve funkci `clear_out` (řádek 21), na řádku 26: `inventory._stock = remaining`.

**Princip Encapsulation (zapouzdření):** objekt spravuje svůj stav sám. Ostatní kód ho mění jen voláním metod objektu a nesahá na atributy začínající podtržítkem.

**Proč je to problém:** funkce přepíše vnitřní data třídy `Inventory` svou vlastní verzí. Pravidla, která hlídá třída (například kontrola množství v `add` a `remove`), se tím obejdou. Pokud `Inventory` změní způsob ukládání dat, `clear_out` přestane fungovat.

**Jak to opravit:** nepřiřazuj do `_stock` zvenku. Použij veřejné metody. Například zjisti množství pomocí `inventory.quantity(item)` a odeber ho pomocí `inventory.remove(item, count)`. Tím položka ze skladu zmizí a o změnu se postará sama třída.
