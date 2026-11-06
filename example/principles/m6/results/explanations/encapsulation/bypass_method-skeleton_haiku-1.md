**Kde je chyba:** v souboru `shop.py`, ve funkci `clear_out` (řádek 21), na řádku 24 příkazem `del inventory._stock[item]`.

**Princip:** Zapouzdření. Objekt spravuje svůj stav sám a ostatní kód ho mění jen voláním jeho metod. Atributů začínajících podtržítkem se zvenku nedotýká.

**Proč je to problém:** Funkce `clear_out` mění vnitřní slovník `Inventory._stock` přímo, mimo třídu. Obchází tak metody `Inventory`, které hlídají pravidla (například kladné množství). Změna toho, jak `Inventory` data ukládá, by navíc `clear_out` rozbila.

**Oprava:** Nesahej na `_stock`. Zavolej metodu vlastníka, která tuto změnu provede. Třída už má `remove(item, quantity)`, takže můžeš zavolat `inventory.remove(item, count)`, když je `count > 0`.
