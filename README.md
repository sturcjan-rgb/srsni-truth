# srsni-data

Datový systém pro basketbalový klub **Sršni Photomate Písek**. Umí:

- najít všechny zápasy klubu v dané sezóně (`discovery.py`),
- dohledat k nim FIBA LiveStats feed (`resolve.py`),
- stáhnout a uložit statistiky do jedné lokální SQLite databáze
  (`db.py`, `sync.py`),
- sledovat právě probíhající zápas naživo (`live.py`),
- a poskytnout to všechno jako nástroje pro Claude Code přes vlastní MCP
  server (`mcp_server.py`).

Je to čistě Python projekt spravovaný přes [uv](https://docs.astral.sh/uv/).

## Jak to funguje pod kapotou

1. `discovery.py` stáhne rozpis celé ligy z `https://nbl.basketball/zapasy`
   s filtrem podle týmu (`c=421` je Sršni Photomate Písek) a sezóny
   (`y=<počáteční rok>`), staticky vykreslenou tabulku, a najde v ní
   všechny zápasy Sršňů - včetně budoucích (ty jsou v tabulce taky, jen
   bez skóre). Datum, čas a jména týmů se berou přímo ze struktury
   tabulky (atribut `data-sort` na buňce s datem, dvě buňky se jmény
   týmů), ne z volného textu.
2. Pokud tabulka u zápasu ještě neobsahuje přímý odkaz na FIBA
   LiveStats (typicky u zápasů dál v budoucnu), `resolve.py` to zkusí
   dohledat na stránce detailu zápasu `https://nbl.basketball/zapas/<nbl_id>`.
   Pokud tam odkaz ještě není, v klidu to přeskočí - zkusí se to příště.
3. Ze `fiba_id` se dá přímo stáhnout JSON se statistikami:
   `https://fibalivestats.dcd.shared.geniussports.com/data/<fiba_id>/data.json`
4. Všechno se ukládá do `srsni.db` (SQLite, negituje se) - tabulka
   `matches` (jeden řádek na zápas) a `snapshots` (historie stažených
   JSONů v čase - nikdy se nepřepisují, jen přidávají).
5. `stats.py` umí z toho JSONu spočítat True Shooting %, Effective FG %
   a poměr asistence/ztráty - čistě, bez sítě, otestováno v `test_stats.py`.

## Instalace

Potřebuješ [uv](https://docs.astral.sh/uv/) a Python 3.10+ (uv si ho v
případě potřeby sám dotáhne).

```bash
uv sync
```

## Vyzkoušet na jednom konkrétním zápase

Nejrychlejší way, jak si systém osahat, je ověřit celý řetězec na
jednom známém zápase (`nbl_id=492428`, `fiba_id=2637874` - viz zadání
projektu):

```bash
# 1) dohledání fiba_id ze stránky zápasu
uv run python3 resolve.py 492428

# 2) spuštění testů nad stats.py (bez sítě, na vymyšlených datech)
uv run python3 test_stats.py

# 3) plná synchronizace aktuální sezóny (najde zápasy, dohledá fiba_id,
#    stáhne statistiky tam, kde už existují)
uv run python3 sync.py

# volitelně konkrétní historická sezóna:
uv run python3 sync.py "2024/25"

# 4) sledování dnešního zápasu naživo (nebo konkrétního nbl_id)
uv run python3 live.py
uv run python3 live.py 492428
```

Po `sync.py` se v adresáři objeví `srsni.db` - dá se prohlížet třeba
přes `sqlite3 srsni.db` nebo jakýkoliv SQLite prohlížeč.

### Poznámka k vývoji

Vývojová sandbox, ve které tenhle projekt vznikl, měla organizační
síťovou politikou zablokovaný přístup na `nbl.basketball` i
`fibalivestats.com`/`geniussports.com`. Přesná struktura rozpisu
(URL `/zapasy` s parametry `y`/`c`/`p1`/`k`, ID týmu 421, sloupce
tabulky) se proto zjišťovala empiricky přes diagnostické běhy v GitHub
Actions (tam síť funguje normálně) - první verze `discovery.py` mířila
na špatnou URL (widget se dvěma zápasy místo celého rozpisu) a
parsování data/týmů z volného textu úplně selhávalo. Aktuální verze je
už postavená na skutečné struktuře stránky a ověřená na reálném běhu
(sezóny 2025/26 i 2026/27, včetně budoucích zápasů).

## Připojení do Claude Code

Server běží přes stdio transport, takže se dá zaregistrovat příkazem
`claude mcp add` (spusť z tohohle adresáře, nebo uprav cestu):

```bash
claude mcp add srsni-data -- uv run --directory /cesta/k/repozitari/srsni-truth python3 mcp_server.py
```

Po připojení má Claude k dispozici čtyři nástroje:

- `list_matches(season)` - seznam zápasů Sršňů a jejich stav
  (`upcoming` / `live` / `finished`)
- `get_boxscore(match_ref)` - poslední známý stav zápasu po hráčích;
  `match_ref` může být `nbl_id`, `fiba_id`, nebo `"latest"` (poslední
  živý/odehraný zápas)
- `get_advanced_stats(match_ref, metric)` - pokročilá metrika po
  hráčích (`true_shooting_pct`, `effective_fg_pct`,
  `assist_to_turnover_ratio`)
- `sync_schedule(season)` - spustí synchronizaci pro danou sezónu na
  počkání a vrátí shrnutí

Než se dá cokoliv smysluplného vyčíst, je potřeba databázi aspoň jednou
naplnit - buď ručně přes `uv run python3 sync.py`, nebo přímo z Claude
Code zavoláním nástroje `sync_schedule`.

## Webový portál

`build_site.py` vygeneruje ze `srsni.db` statický webový portál
(přehled, detail sezóny, detail zápasu, profil hráče - včetně
"hlubokých" statistik jako nejlepší dvojice/trojice/pětky na hřišti
a nejčastější asistenční spojení, viz `lineups.py`/`aggregate.py`).

```bash
uv run python3 build_site.py
# výstup je v dist/ - dá se otevřít lokálně, nebo nasadit kamkoliv
uv run python3 -m http.server --directory dist 8000
```

### Nasazení na GitHub Pages

Workflow `.github/workflows/pages.yml` portál automaticky přegeneruje
a nasadí po každém úspěšném `sync.yml` (nová data) i po změně kódu
portálu. **Vyžaduje to ale jedno jednorázové ruční nastavení**, které
nejde udělat přes API/nástroje:

1. V repozitáři jdi do **Settings → Pages**.
2. U "Source" vyber **GitHub Actions** (místo výchozí volby "Deploy from a branch").
3. Ulož. Od dalšího běhu `pages.yml` se portál nasadí na
   `https://<uživatel>.github.io/srsni-truth/`.

Design (barvy, font Barlow Condensed) vychází z [tv.srsni.com](https://tv.srsni.com/).

## Poznámka k balíčku `mcp`

Balíček `mcp` na PyPI má aktuálně živou verzi 2.x, která přejmenovala
`FastMCP` na `MCPServer` a mění další API. Tenhle projekt proto v
`pyproject.toml` pinuje `mcp[cli]<2`, aby fungovalo staré, stabilní
`FastMCP` API (`from mcp.server.fastmcp import FastMCP`, `@mcp.tool()`,
`mcp.run(transport="stdio")`), které je použité v `mcp_server.py`.

## Struktura projektu

```
discovery.py     - najde zápasy Sršňů v rozpisu (nbl.basketball)
resolve.py       - dohledá fiba_id ze stránky konkrétního zápasu
db.py            - SQLite databáze (matches, snapshots)
stats.py         - čisté funkce nad JSONem z FIBA LiveStats (jeden zápas)
lineups.py       - kombinace hráčů na hřišti + asistenční dvojice (play-by-play)
aggregate.py     - sezónní/kariérní statistiky napříč zápasy
test_*.py        - testy (bez sítě)
sync.py          - orchestrátor: discovery -> resolve -> stažení dat
live.py          - živé sledování probíhajícího zápasu
mcp_server.py    - MCP server nad databází pro Claude Code
build_site.py    - generátor statického webového portálu
templates/       - HTML šablony portálu (Jinja2)
static/          - styl portálu (style.css)
```
