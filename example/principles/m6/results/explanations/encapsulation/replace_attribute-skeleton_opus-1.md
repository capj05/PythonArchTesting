**Kde je chyba:** v souboru `shop.py`, ve funkci `clear_out`, na řádku 30: `inventory._stock = rest`.

**Porušený princip: Encapsulation (zapouzdření).** Objekt spravuje svůj stav sám. Ostatní kód ho mění jen voláním metod objektu a nesahá na atributy začínající podtržítkem.

**Proč je to problém:** `clear_out` zvenku přepisuje vnitřní atribut `Inventory._stock`. Třída `Inventory` o změně neví a její pravidla (např. kontroly v `remove()`) se obejdou. Jakmile třída změní způsob ukládání dat, funkce přestane fungovat.

**Jak to opravit:** Atribut `_stock` nepřepisuj. Zjištěné množství odeber veřejnou metodou: `inventory.remove(item, amount)`. Pak můžeš smazat i řádky 28–30, protože kopii slovníku z `items()` už nepotřebuješ.
