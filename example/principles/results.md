# Ověření katalogu principů

Vygenerováno skriptem `verify.py`; neupravovat ručně.

## Zapouzdření (`encapsulation`)

| Varianta | Druh | Očekáváno | Nástroj | Shoda |
|---|---|---|---|---|
| `ok_basic` | rušivá změna: modelové řešení bez markerů (kontrola, že reference projde i jako odevzdání) | PASS | PASS | ✓ |
| `ok_property` | rušivá změna: vlastnost (`@property`) navíc, kterou klient čte | PASS | PASS | ✓ |
| `ok_extra_method` | rušivá změna: metoda třídy navíc, kterou klient volá | PASS | PASS | ✓ |
| `ok_wrong_math` | rušivá změna: chyba ve výpočtu součtu v reportu | PASS | PASS | ✓ |
| `ok_style_noise` | rušivá změna: špatný styl: jednopísmenná jména, bez typů a dokumentace | PASS | PASS | ✓ |
| `err_sell_bypasses_remove` | chyba: změna stavu obchází metodu třídy | FAIL (forbid_foreign_writes) | FAIL | ✓ |
| `err_restock_writes_log` | chyba: úprava seznamu nebo slovníku, který patří objektu | FAIL (forbid_foreign_writes) | FAIL | ✓ |
| `err_clear_out_replaces_stock` | chyba: přepsání atributu cizího objektu | FAIL (forbid_foreign_writes) | FAIL | ✓ |
| `err_report_reads_private` | chyba: čtení soukromého atributu zvenku | PASS (mezera G2) | PASS | ✓ |

### Vysvětlení pro studenta (složené z katalogu a reportu, bez LLM)

### `err_sell_bypasses_remove`: změna stavu obchází metodu třídy

**Co:** Funkce `sell` (shop.py:8) mění stav objektu zvenku: na řádku 10 souboru `shop.py` zasahuje do atributu `Inventory._stock` (mění obsah).

**Proč:** Třída má pro tuto změnu metodu, která hlídá pravidla (dost zboží, záznam do historie). Přímý zápis do atributu tato pravidla obejde, takže stav může přestat dávat smysl.

**Jak opravit:** Zavolej metodu objektu (zde `inventory.remove(item, quantity)`) místo zápisu do atributu.

### `err_restock_writes_log`: úprava seznamu nebo slovníku, který patří objektu

**Co:** Funkce `restock` (shop.py:12) mění obsah atributu cizího objektu: na řádku 15 souboru `shop.py` zasahuje do atributu `Inventory.log` (mění obsah).

**Proč:** I `append` do seznamu objektu je změna jeho stavu. O tom, co se do historie zapisuje, má rozhodovat objekt sám; jinak vzniknou záznamy, které neodpovídají žádné operaci.

**Jak opravit:** Nech zápis na metodě třídy, případně přidej metodu, která ho udělá.

### `err_clear_out_replaces_stock`: přepsání atributu cizího objektu

**Co:** Funkce `clear_out` (shop.py:17) přepisuje atribut cizího objektu: na řádku 19 souboru `shop.py` zasahuje do atributu `Inventory._stock` (přiřazuje).

**Proč:** Funkce nahradí vnitřní data objektu vlastní verzí. Objekt o změně neví, a jakmile třída změní způsob uložení dat, funkce přestane fungovat.

**Jak opravit:** Použij metody objektu (`quantity`, `remove`) a vnitřní atribut nech na pokoji.

### Mezera G2: čtení soukromých atributů zvenku se nekontroluje

`forbid_foreign_writes` sleduje jen zápisy a změny. Žádný marker nehlásí `obj._x` mimo třídu objektu (`module_interface` hlídá soukromá jména modulů, ne atributů). Návrh: statická kontrola přístupu k `_atributům` přes jiný objekt než `self`/`cls`, mimo tělo vlastní třídy.

## Oddělení logiky od vstupu a výstupu (`io_separation`)

| Varianta | Druh | Očekáváno | Nástroj | Shoda |
|---|---|---|---|---|
| `ok_basic` | rušivá změna: modelové řešení bez markerů (kontrola, že reference projde i jako odevzdání) | PASS | PASS | ✓ |
| `ok_different_ui` | rušivá změna: jiné uživatelské rozhraní (opakované dotazy, jiné texty, víc výpisů) | PASS | PASS | ✓ |
| `ok_extra_helper` | rušivá změna: pomocná funkce navíc, která nic nevypisuje | PASS | PASS | ✓ |
| `ok_wrong_formula` | rušivá změna: chyba ve výpočtu (průměr dělí n + 1) | PASS | PASS | ✓ |
| `ok_style_noise` | rušivá změna: špatný styl: jednopísmenná jména, bez typů a dokumentace, globální konstanta | PASS | PASS | ✓ |
| `err_print_in_logic` | chyba: výsledek se vypisuje místo vrácení | FAIL (forbid_runtime_calls) | FAIL | ✓ |
| `err_input_in_logic` | chyba: logická funkce čte z klávesnice | FAIL (forbid_runtime_calls) | FAIL | ✓ |
| `err_print_via_helper` | chyba: výstup schovaný v pomocné funkci jiného modulu | FAIL (forbid_runtime_calls) | FAIL | ✓ |
| `err_logic_in_main` | chyba: výpočet přímo v main místo v logických funkcích | FAIL (require_runtime_calls) | FAIL | ✓ |

### Vysvětlení pro studenta (složené z katalogu a reportu, bez LLM)

### `err_print_in_logic`: výsledek se vypisuje místo vrácení

**Co:** Funkce `format_summary` (grades.py:19) vypisuje na obrazovku: na řádku 20 souboru `grades.py` volá `print()`.

**Proč:** Funkce má výsledek vrátit (`return`), ne vypsat. Kdo ji zavolá, pak sám rozhodne, co s výsledkem udělá; vypsaný text už program dál použít nemůže.

**Jak opravit:** Nahraď `print(...)` příkazem `return ...` a vypiš výsledek až v `main`.

### `err_input_in_logic`: logická funkce čte z klávesnice

**Co:** Funkce `parse_grades` (grades.py:4) čte z klávesnice: na řádku 6 souboru `grades.py` volá `input()`.

**Proč:** Funkce dostává data parametrem, a přesto se ptá uživatele. Nedá se tak zavolat s jinými daty (ze souboru, v testu) a parametr ztrácí smysl.

**Jak opravit:** Čti vstup v `main` a funkci ho předej parametrem.

### `err_print_via_helper`: výstup schovaný v pomocné funkci jiného modulu

**Co:** Funkce `average` (grades.py:14) způsobí výpis přes pomocnou funkci: na řádku 19 souboru `grades.py` volá `messages:warn` a ta na řádku 5 souboru `messages.py` volá `print()`.

**Proč:** Na tom, kde je `print` napsaný, nezáleží: logická funkce, která při svém běhu způsobí výpis, je pořád svázaná s obrazovkou.

**Jak opravit:** Vrať informaci (např. text varování) jako součást výsledku a vypiš ji v `main`.

### `err_logic_in_main`: výpočet přímo v main místo v logických funkcích

**Co:** Funkce `main` (app.py:4) počítá sama a logické funkce nevolá: přímo nezavolá žádnou funkci modulu `grades`.

**Proč:** Logické funkce existují, ale `main` je nepoužívá a počítá sám. Výpočet pak opět nejde použít jinde ani vyzkoušet bez klávesnice.

**Jak opravit:** V `main` jen načti vstup, zavolej logické funkce a vypiš jejich výsledek.

