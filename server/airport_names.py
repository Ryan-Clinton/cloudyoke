#!/usr/bin/env python3
"""Airport names the Aviation Weather Center cuts short, written out in full.

    python server/airport_names.py --suggest --work names-check     candidates to check by hand

The AWC's station list clips long names, sometimes mid-word: Le Bourget is "Paris/Le Bourge Arpt" there and
Stevensville is "Stevensvil". FIXES holds every one found and checked by hand, in the AWC's own style (its
abbreviations kept, since Meanwhile expands them), and metar.py writes these into data/reference/index.json in
place of the clipped ones.

--suggest compares the AWC's names with OurAirports' (public domain, https://ourairports.com/data/) for the
countries collected, and prints each name where a word looks like the clipped start of a word in OurAirports'
name. It is a list to read, never applied as it stands: the same rule turns "San Jose" into "Santa Jose" and
"Greene Cnty" into "Greeneville". Checked 25 November 2026 for GB, IM, IE, FR, US, CA and AU.
"""
import argparse
import csv
import gzip
import json
import re
import unicodedata
import urllib.request
from pathlib import Path

FIXES = {
    "EGSD": "Great Yarmouth/N Denes",
    "K2R2": "Indianapolis/Hendricks Cnty",
    "K32S": "Stevensville",
    "K66R": "Columbus/Wells Arpt",
    "K7S6": "White Sulphur Springs",
    "K8S0": "Browning/Starr Arstrp",
    "KAMN": "Alma/Gratiot Community",
    "KBRY": "Bardstown/Samuels Fld",
    "KCDI": "Cambridge Muni",
    "KCHQ": "Charleston/Mississippi",
    "KCNM": "Carlsbad/Cavern City Air Terminal",
    "KCNY": "Moab/Canyonlands Fld",
    "KCOS": "Colorado Springs Arpt",
    "KD55": "Langdon/Robertson Fld",
    "KEDE": "Edenton/Northeastern Rgnl",
    "KF35": "Graford/Possum Kingdom",
    "KFGU": "Collegedale",
    "KH71": "Pryor/Mid-America Industrial",
    "KHGT": "Hunter-Liggett/Tusi",
    "KINW": "Winslow/Lindbergh Rgnl",
    "KM25": "Mayfield/Graves Cnty",
    "KO16": "Garberville",
    "KOEA": "Vincennes-O'Neal",
    "KOGA": "Ogallala/Searle Fld",
    "KSPZ": "Silver Springs",
    "KTCS": "Truth or Consequences Muni",
    "KWAY": "Waynesburg/Greene Cnty",
    "KWEA": "Weatherford-Parker",
    "LFBF": "Toulouse/Francazal Arpt",
    "LFJR": "Angers/Loire Arpt",
    "LFOS": "Vittefleur/St Valery",
    "LFPB": "Paris/Le Bourget Arpt",
    "LFQV": "Charleville/Mezieres",
    "LFSM": "Montbéliard/Courcelles",
    "PAJO": "Hinchinbrook/Johnstone",
    "YWLP": "Wilsons Promontory",
}


def name(icao, given):
    """An airport's name for the index: the checked full name if there is one, else the AWC's, up to its first
    comma (the JSON API adds the state and country) and without the spaces its clipping can leave."""
    return FIXES.get(icao) or (given or icao).split(",")[0].strip() or icao


STATIONS = "https://aviationweather.gov/data/cache/stations.cache.json.gz"
OURAIRPORTS = "https://davidmegginson.github.io/ourairports-data/airports.csv"
COUNTRIES = {"GB", "IM", "IE", "FR", "US", "CA", "AU"}
# The AWC's own abbreviations, which are short on purpose
ABBREVIATIONS = {"muni", "exec", "metro", "mem", "intl", "rgnl", "cnty", "arpt", "fld", "ind", "int", "natl", "mun",
                 "cty", "reg", "regl", "hosp", "mtn", "arpk", "heli", "hlpt", "arfld", "arstrp", "afb", "aaf", "nas",
                 "univ", "isl", "pt", "ft", "blk", "apt", "fed", "aux", "ste", "air", "army", "port", "lake", "city"}


def fold(word):
    return unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode().lower()


def suggest(work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    for url, file in ((STATIONS, "stations.json.gz"), (OURAIRPORTS, "airports.csv")):
        req = urllib.request.Request(url, headers={"User-Agent": "cloudyoke (github.com/Ryan-Clinton/cloudyoke)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            (work / file).write_bytes(r.read())
    full_names = {}
    with open(work / "airports.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            for key in (row["icao_code"], row["gps_code"], row["ident"]):
                if key:
                    full_names.setdefault(key, row["name"])
    for s in json.loads(gzip.decompress((work / "stations.json.gz").read_bytes())):
        icao, site = s.get("icaoId"), s.get("site") or ""
        if s.get("country") not in COUNTRIES or icao not in full_names or icao in FIXES:
            continue
        words = re.findall(r"[^\W\d_]+", full_names[icao])
        folded = {fold(w) for w in words}

        def finish(m):
            w, f = m.group(0), fold(m.group(0))
            if len(f) < 3 or f in folded or f in ABBREVIATIONS:
                return w
            longer = [x for x in words if fold(x).startswith(f) and len(x) > len(w)]
            return w + longer[0][len(w):] if len({fold(x) for x in longer}) == 1 else w

        guess = re.sub(r"[^\W\d_]+", finish, site).strip()
        if guess != site.strip():
            print(f"{icao}\t{site!r}\t{guess!r}\tOurAirports: {full_names[icao]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--suggest", action="store_true", help="print candidate fixes to check by hand")
    ap.add_argument("--work", default="names-check", help="where --suggest keeps the two downloaded lists")
    a = ap.parse_args()
    if a.suggest:
        suggest(a.work)
    else:
        print(json.dumps(FIXES, indent=1, ensure_ascii=False))
