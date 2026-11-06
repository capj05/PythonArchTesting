**Kde je chyba:** v souboru `shop.py`, ve funkci `clear_out` (od řádku 25), na řádku 28: `inventory._stock.pop(item)`.

**Který princip porušuje:** Zapouzdření (Encapsulation). Objekt spravuje svůj stav sám a ostatní kód ho mění jen voláním jeho metod. Atributů začínajících podtržítkem se zvenčí nedotýká.

**Proč je to problém:** `_stock` patří třídě `Inventory`. Zápisem přímo do něj funkce obchází metodu třídy, která hlídá pravidla skladu (například že nelze ubrat víc, než je k dispozici). Stav skladu pak může přestat dávat smysl. Každá změna toho, jak si `Inventory` data uchovává, by navíc rozbila i `clear_out`.

**Jak to opravit:** Zavolej metodu, která tuto změnu provádí. V `Inventory` už je `remove(item, quantity)`, takže stačí `inventory.remove(item, amount)`. `amount` už ve funkci máš z `inventory.quantity(item)`.
