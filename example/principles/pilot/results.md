# Pilot evaluace principů: nástroj a LLM soudci

Vygenerováno skriptem `score.py`; neupravovat ručně. Označeno = nástroj `FAIL` (`UNMATCHED` se nepočítá), soudce `violates: true`.

## `encapsulation`

| Míra | nástroj | soudce haiku-1 | soudce sonnet-1 |
|---|---|---|---|
| vložené chyby označené | 9/12 | 12/12 | 12/12 |
| rušivé vady označené (FP) | 0/12 | 3/12 | 4/12 |
| čistá řešení označená | 0/12 | 2/12 | 1/12 |
| nespárovaná | 0/36 | 0/36 | 0/36 |
| nespuštěno | 0/36 | 0/36 | 0/36 |
| vložené chyby označené, nosič čistý | 9/12 | 8/8 | 8/8 |
| rušivé vady označené (FP), nosič čistý | 0/12 | 2/8 | 3/8 |

Nástroj: odevzdání, na kterých některé pravidlo kód nespustilo (`not_run`, řádek „nespuštěno“), nejsou v čitatelích ani jmenovatelích nástroje. Řádky „nosič čistý“ počítají jen vložené varianty, jejichž nosič daný rozhodující považuje za čistý (nástroj `PASS`, soudce `violates: false`); jmenovatel je za lomítkem.

| Nosič | Odevzdání | nástroj | soudce haiku-1 | soudce sonnet-1 |
|---|---|---|---|---|
| skeleton/haiku-1 | w009 | PASS | neporušuje | neporušuje |
| skeleton/opus-1 | w024 | PASS | neporušuje | neporušuje |
| skeleton/sonnet-1 | w030 | PASS | porušuje | porušuje |

## `io_separation`

| Míra | nástroj | soudce haiku-1 | soudce sonnet-1 |
|---|---|---|---|
| vložené chyby označené | 6/9 | 8/9 | 8/9 |
| rušivé vady označené (FP) | 0/12 | 1/12 | 0/12 |
| čistá řešení označená | 0/12 | 0/12 | 0/12 |
| nespárovaná | 0/33 | 0/33 | 0/33 |
| nespuštěno | 0/33 | 0/33 | 0/33 |
| vložené chyby označené, nosič čistý | 6/9 | 8/9 | 8/9 |
| rušivé vady označené (FP), nosič čistý | 0/12 | 1/12 | 0/12 |

Nástroj: odevzdání, na kterých některé pravidlo kód nespustilo (`not_run`, řádek „nespuštěno“), nejsou v čitatelích ani jmenovatelích nástroje. Řádky „nosič čistý“ počítají jen vložené varianty, jejichž nosič daný rozhodující považuje za čistý (nástroj `PASS`, soudce `violates: false`); jmenovatel je za lomítkem.

| Nosič | Odevzdání | nástroj | soudce haiku-1 | soudce sonnet-1 |
|---|---|---|---|---|
| skeleton/haiku-1 | w017 | PASS | neporušuje | neporušuje |
| skeleton/opus-1 | w006 | PASS | neporušuje | neporušuje |
| skeleton/sonnet-1 | w028 | PASS | neporušuje | neporušuje |

## Řešení, která někdo označil (kandidáti přirozených porušení k ruční kontrole)

| Princip | Řešení | Označili | Nástroj | Důvody soudců |
|---|---|---|---|---|
| `encapsulation` | skeleton/sonnet-1 (w030) | soudce haiku-1, soudce sonnet-1 | PASS: - | haiku-1: Pravidlo kladného množství je kromě Inventory zapsáno také v shop.py (restock), takže nežije na jednom místě uvnitř třídy.; sonnet-1: restock v shop.py sám kontroluje, zda jsou množství kladná, a tím duplikuje pravidlo skladu mimo Inventory. |
| `encapsulation` | text/haiku-2 (w033) | soudce haiku-1 | PASS: - | haiku-1: Pravidlo kladného celého množství je v shop.restock zkopírováno mimo třídu Inventory, což zadání výslovně požaduje jinak. |
