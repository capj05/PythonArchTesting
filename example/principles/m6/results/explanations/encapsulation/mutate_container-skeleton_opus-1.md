**Kde je chyba:** v souboru `shop.py`, ve funkci `clear_out` (od řádku 25), na řádku 29: `del inventory._stock[item]`.

**Princip:** Zapouzdření (Encapsulation). Objekt spravuje svůj stav sám. Ostatní kód ho mění jen voláním metod objektu a nesahá na atributy začínající podtržítkem.

**Proč je to problém:** Funkce `clear_out` mění vnitřní atribut `Inventory._stock` zvenčí a obchází metody třídy `Inventory`, které hlídají její pravidla (například že položka s množstvím 0 není vedená a že nelze ubrat víc, než je skladem). Kdyby třída změnila způsob ukládání dat, tento kód by přestal fungovat.

**Oprava:** Místo přímého zápisu zavolej metodu skladu, která tuto změnu provede. V kódu je to `inventory.remove(item, amount)`, kde `amount` je množství získané z `inventory.quantity(item)`.
