#!/usr/bin/env python3

import html
import json
import re
import shutil
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = ROOT / "data" / "_raw_data.json"
OUTPUT_DIR = ROOT / "static" / "src" / "img" / "products"
DOCS_DIR = ROOT / "docs"
SOURCES_DOC = DOCS_DIR / "PRODUCT_IMAGE_SOURCES.md"
SOURCES_JSON = DOCS_DIR / "product_image_sources.json"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "RefugeAventuriersImageFetcher/1.0"
REQUEST_DELAY = 3.0
FORCE_REFRESH = {
    "prod_biere_ambree_savoie_33cl",
    "prod_cosmopolitan",
    "prod_margarita",
    "prod_mojito",
    "prod_sirop_de_canne_70cl",
    "prod_verre_de_rhum",
    "prod_verre_de_tequila",
}

EXACT_FILE_TITLES = {
    "prod_biere_ambree_savoie_33cl": "File:Bruegel Amber.JPG",
    "prod_cosmopolitan": "File:Cosmopolitan cocktail drink.jpg",
    "prod_margarita": "File:Klassiche Margarita.jpg",
    "prod_mojito": "File:Cocktail Mojito.jpg",
    "prod_sirop_de_canne_70cl": "File:Sugar Syrup.jpg",
    "prod_verre_de_rhum": "File:Glass of rum from Réunion.jpg",
    "prod_verre_de_tequila": "File:Tequila shots.jpg",
}

BLACKLIST = (
    "logo",
    "icon",
    "label",
    "diagram",
    "drawing",
    "flag",
    "map",
    "symbol",
    "coat of arms",
)

SEARCH_TERMS = {
    "prod_vitus_50_cl": ["wheat beer bottle"],
    "prod_blonde_du_mont_blanc_50cl": ["blonde beer bottle"],
    "prod_kellerbier_1516_50cl": ["lager beer bottle"],
    "prod_biere_ambree_savoie_33cl": ["amber beer bottle"],
    "prod_ipa_houblonnee_33cl": ["ipa beer bottle"],
    "prod_biere_sans_alcool_33cl": ["non alcoholic beer bottle"],
    "prod_taurasi_nero_ne_75cl": ["red wine bottle"],
    "prod_pinot_nero_75cl": ["pinot noir wine bottle"],
    "prod_cotes_du_rhone_75cl": ["cotes du rhone wine bottle", "red wine bottle"],
    "prod_malbec_argentine_75cl": ["malbec wine bottle"],
    "prod_muscadet_75cl": ["muscadet wine bottle", "white wine bottle"],
    "prod_chardonnay_75cl": ["chardonnay wine bottle"],
    "prod_sauvignon_blanc_75cl": ["sauvignon blanc wine bottle"],
    "prod_riesling_alsace_75cl": ["riesling wine bottle"],
    "prod_margarita": ["margarita cocktail"],
    "prod_mojito": ["mojito cocktail"],
    "prod_old_fashioned": ["old fashioned cocktail"],
    "prod_cafe_bauju": ["ginger beer cocktail"],
    "prod_aperol_spritz": ["aperol spritz cocktail"],
    "prod_cosmopolitan": ["cosmopolitan cocktail"],
    "prod_negroni": ["negroni cocktail"],
    "prod_verre_de_tequila": ["tequila shot glass"],
    "prod_verre_de_whisky": ["whisky glass"],
    "prod_verre_de_vodka": ["vodka shot glass"],
    "prod_verre_de_rhum": ["rum glass"],
    "prod_verre_de_gin": ["gin and tonic glass"],
    "prod_perrier_1l": ["sparkling water bottle"],
    "prod_coca_cola_33cl": ["cola can", "coca cola can"],
    "prod_jus_d_orange_20cl": ["orange juice glass"],
    "prod_eau_minerale_50cl": ["mineral water bottle"],
    "prod_vodka_75cl": ["vodka bottle"],
    "prod_tequila_75cl": ["tequila bottle"],
    "prod_cointreau_1l": ["cointreau bottle"],
    "prod_citron_vert_la_piece": ["lime fruit"],
    "prod_rhum_blanc_75cl": ["white rum bottle", "rum bottle"],
    "prod_feuilles_de_menthe": ["mint leaves"],
    "prod_ginger_beer_1l": ["ginger beer bottle"],
    "prod_sirop_de_canne_70cl": ["sugar syrup bottle"],
    "prod_whisky_scotch_75cl": ["scotch whisky bottle"],
    "prod_orange_la_piece": ["orange fruit"],
    "prod_angostura_bitters_20cl": ["angostura bitters bottle", "bitters bottle"],
    "prod_prosecco_75cl": ["prosecco bottle"],
    "prod_aperol_1l": ["aperol bottle"],
    "prod_cranberry_1l": ["cranberry juice bottle", "cranberry juice"],
    "prod_gin_75cl": ["gin bottle"],
    "prod_campari_75cl": ["campari bottle"],
    "prod_vermouth_rouge_75cl": ["sweet vermouth bottle", "vermouth bottle"],
}


def read_raw_products():
    data = json.loads(RAW_DATA_PATH.read_text(encoding="utf-8"))
    return data["products"]


def strip_html(value):
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def commons_request(params):
    url = f"{COMMONS_API}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(6):
        try:
            with urlopen(request) as response:
                payload = json.load(response)
            time.sleep(REQUEST_DELAY)
            return payload
        except HTTPError as exc:
            if exc.code != 429 or attempt == 5:
                raise
            time.sleep(2 + attempt * 2)
        except URLError:
            if attempt == 5:
                raise
            time.sleep(2 + attempt * 2)


def search_commons(query):
    data = commons_request(
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": 6,
            "gsrsearch": query,
            "gsrlimit": 8,
            "prop": "imageinfo|info",
            "inprop": "url",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": 800,
        }
    )
    pages = sorted(
        (data.get("query", {}).get("pages") or {}).values(),
        key=lambda page: page.get("index", 999),
    )
    for page in pages:
        image_info = (page.get("imageinfo") or [{}])[0]
        mime = image_info.get("mime")
        title = page.get("title", "")
        lower_title = title.lower()
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        if any(term in lower_title for term in BLACKLIST):
            continue
        if image_info.get("width", 0) < 400 or image_info.get("height", 0) < 400:
            continue
        return {
            "title": title,
            "page_url": page.get("fullurl"),
            "image_url": image_info.get("thumburl") or image_info.get("url"),
            "mime": mime,
            "license": strip_html((image_info.get("extmetadata") or {}).get("LicenseShortName", {}).get("value")),
            "license_url": strip_html((image_info.get("extmetadata") or {}).get("LicenseUrl", {}).get("value")),
            "artist": strip_html((image_info.get("extmetadata") or {}).get("Artist", {}).get("value")),
            "credit": strip_html((image_info.get("extmetadata") or {}).get("Credit", {}).get("value")),
            "query": query,
        }
    return None


def lookup_commons_file(file_title):
    data = commons_request(
        {
            "action": "query",
            "format": "json",
            "titles": file_title,
            "prop": "imageinfo|info",
            "inprop": "url",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": 800,
        }
    )
    pages = list((data.get("query", {}).get("pages") or {}).values())
    if not pages:
        return None
    page = pages[0]
    image_info = (page.get("imageinfo") or [{}])[0]
    mime = image_info.get("mime")
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        return None
    return {
        "title": page.get("title", file_title),
        "page_url": page.get("fullurl"),
        "image_url": image_info.get("thumburl") or image_info.get("url"),
        "mime": mime,
        "license": strip_html((image_info.get("extmetadata") or {}).get("LicenseShortName", {}).get("value")),
        "license_url": strip_html((image_info.get("extmetadata") or {}).get("LicenseUrl", {}).get("value")),
        "artist": strip_html((image_info.get("extmetadata") or {}).get("Artist", {}).get("value")),
        "credit": strip_html((image_info.get("extmetadata") or {}).get("Credit", {}).get("value")),
        "query": file_title,
    }


def download_file(url, destination):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(6):
        try:
            temp_destination = destination.with_suffix(destination.suffix + ".part")
            with urlopen(request) as response, temp_destination.open("wb") as output:
                shutil.copyfileobj(response, output)
            temp_destination.replace(destination)
            time.sleep(REQUEST_DELAY)
            return
        except HTTPError as exc:
            if exc.code != 429 or attempt == 5:
                raise
            time.sleep(2 + attempt * 2)
        except URLError:
            if attempt == 5:
                raise
            time.sleep(2 + attempt * 2)


def extension_for_mime(mime):
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }[mime]


def write_sources_doc(entries):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Sources des images produits",
        "",
        "Images réelles téléchargées depuis Wikimedia Commons pour les produits du module `refuge_aventuriers`.",
        "",
        "| Produit | Fichier local | Recherche | Fichier Commons | Licence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        lines.append(
            "| {name} | `{file}` | `{query}` | [{title}]({page_url}) | {license} |".format(
                name=entry["name"].replace("|", "/"),
                file=entry["file_name"],
                query=entry["query"],
                title=entry["title"].replace("|", "/"),
                page_url=entry["page_url"],
                license=entry["license"] or "n/a",
            )
        )
    SOURCES_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_sources_json():
    if not SOURCES_JSON.exists():
        return {}
    entries = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in entries}


def write_sources_json(entries):
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_JSON.write_text(
        json.dumps(sorted(entries.values(), key=lambda entry: entry["id"]), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = load_sources_json()
    failures = []
    for product in read_raw_products():
        product_id = product["id"]
        existing_entry = entries.get(product_id)
        force_refresh = product_id in FORCE_REFRESH
        if existing_entry and not force_refresh:
            file_path = OUTPUT_DIR / existing_entry["file_name"]
            if file_path.exists() and file_path.stat().st_size >= 4096:
                print(f"SKIP {product_id} -> {existing_entry['title']}", flush=True)
                continue
        if force_refresh:
            entries.pop(product_id, None)
        match = None
        exact_title = EXACT_FILE_TITLES.get(product_id)
        if exact_title:
            match = lookup_commons_file(exact_title)
        if not match:
            queries = SEARCH_TERMS.get(product_id, [product["name"]])
            for query in queries:
                match = search_commons(query)
                if match:
                    break
        if not match:
            failures.append(product_id)
            continue
        extension = extension_for_mime(match["mime"])
        file_name = f"{product_id}{extension}"
        destination = OUTPUT_DIR / file_name
        for stale_file in OUTPUT_DIR.glob(f"{product_id}.*"):
            if stale_file != destination:
                stale_file.unlink()
        if force_refresh or not destination.exists() or destination.stat().st_size < 4096:
            download_file(match["image_url"], destination)
        entries[product_id] = {
            "id": product_id,
            "name": product["name"],
            "file_name": file_name,
            **match,
        }
        write_sources_json(entries)
        print(f"OK {product_id} -> {match['title']}", flush=True)

    write_sources_doc(sorted(entries.values(), key=lambda entry: entry["id"]))
    write_sources_json(entries)

    if failures:
        print("FAILED:", ", ".join(failures))
        raise SystemExit(1)

    print(f"Downloaded {len(entries)} product images.", flush=True)


if __name__ == "__main__":
    main()
