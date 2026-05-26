import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import date, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0"}

CINEMAS = {
    "Ангара", "Берёзка", "Вымпел", "Жуковский", "Искра", "Кинопарк",
    "Космос", "Марс", "Молодёжный", "Нева", "Рассвет", "Салют",
    "Сатурн", "Спутник", "Тула", "Факел", "Эльбрус", "Юность"
}

INFO_RE = re.compile(r"^(\d{4})\s*/\s*(\d+)\s*мин\s*/\s*(.*?)\s*/\s*(\d+\+)$")
TIME_RE = re.compile(r"^[0-2]\d:[0-5]\d$")
PRICE_RE = re.compile(r"^(\d+)\s*[PР₽]$")
ADDRESS_RE = re.compile(
    r"\b(ул\.|улица|б-р|бульвар|проспект|пр-т|шоссе|набережная|переулок|пер\.|площадь|д\.\s*\d+|дом\s+\d+|центр\s+«|районный центр)\b",
    re.I
)

BASE_COLS = [
    "russian_title", "year", "country", "genre", "director", "rating_tmdb",
    "description", "cinema", "address", "date", "session_time",
    "duration_min", "age_rating", "format", "has_subtitles", "price",
    "source_parsing", "source_url"
]


def clean(x):
    if pd.isna(x):
        return None
    x = re.sub(r"\s+", " ", str(x)).strip()
    return x or None


def norm_title(x):
    x = clean(x)
    if not x:
        return None
    x = x.lower().replace("ё", "е")
    x = re.sub(r"[^\w\s]", " ", x)
    return re.sub(r"\s+", " ", x).strip()


def search_title(x):
    x = clean(x)
    if not x:
        return None
    x = re.sub(r"\(.*?\)", "", x)
    x = re.sub(r"\bперевыпуск\b", "", x, flags=re.I)
    x = re.sub(r"\bповторный показ\b", "", x, flags=re.I)
    x = re.sub(r"\s+", " ", x).strip()
    return x or None


def get_lines(url):
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")
    return [clean(x) for x in soup.get_text("\n").split("\n") if clean(x)]


def parse_moskino_day(day):
    url = f"https://mos-kino.ru/schedule/?date={day}"
    lines = get_lines(url)
    rows = []
    cinema = address = title = info = None
    i = 0

    while i < len(lines):
        line = lines[i]

        if line in CINEMAS:
            cinema, address, title, info = line, None, None, None
            i += 1
            continue

        if ADDRESS_RE.search(line):
            address = line
            i += 1
            continue

        if i + 1 < len(lines) and INFO_RE.match(lines[i + 1]):
            m = INFO_RE.match(lines[i + 1])
            title = line
            info = {
                "year": int(m.group(1)),
                "duration_min": int(m.group(2)),
                "country": clean(m.group(3)),
                "age_rating": m.group(4)
            }
            i += 2
            continue

        if TIME_RE.match(line) and title and info:
            fmt, subtitles, price = None, False, None
            j = i + 1

            while j < len(lines):
                x = lines[j]
                stop = x in CINEMAS or INFO_RE.match(x) or TIME_RE.match(x)
                stop = stop or (j + 1 < len(lines) and INFO_RE.match(lines[j + 1]))

                if stop:
                    break

                if x in ["2D", "3D"]:
                    fmt = x
                elif x == "СУБ":
                    subtitles = True
                elif PRICE_RE.match(x):
                    price = int(PRICE_RE.match(x).group(1))
                    break

                j += 1

            rows.append({
                "russian_title": title,
                "year": info["year"],
                "country": info["country"],
                "genre": None,
                "director": None,
                "rating_tmdb": None,
                "description": None,
                "cinema": cinema,
                "address": address,
                "date": str(day),
                "session_time": line,
                "duration_min": info["duration_min"],
                "age_rating": info["age_rating"],
                "format": fmt,
                "has_subtitles": subtitles,
                "price": price,
                "source_parsing": "moskino",
                "source_url": url
            })

            i = j + 1
            continue

        i += 1

    return pd.DataFrame(rows)


def parse_moskino(start_day=None, days=7):
    if start_day is None:
        start_day = date.today()

    frames = []

    for n in range(days):
        part = parse_moskino_day(start_day + timedelta(days=n))
        if not part.empty:
            frames.append(part)

    if not frames:
        return pd.DataFrame(columns=BASE_COLS)

    df = pd.concat(frames, ignore_index=True)
    return df[~df["country"].str.contains("россия", case=False, na=False)].reset_index(drop=True)


def parse_pioner():
    url = "https://pioner-distribution.ru/films"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "lxml")
    rows = []

    for a in soup.find_all("a", href=True):
        title = clean(a.get_text(" ", strip=True))
        if "kinopoisk.ru/film" in a["href"] and title and len(title) > 1:
            rows.append({
                "russian_title": title,
                "source_parsing": "pioner",
                "source_url": url
            })

    if not rows:
        return pd.DataFrame(columns=BASE_COLS)

    return pd.DataFrame(rows).drop_duplicates("russian_title").reset_index(drop=True)


def tmdb_get(path, api_key, **params):
    params["api_key"] = api_key
    r = requests.get(f"https://api.themoviedb.org/3{path}", params=params)
    return r.json()


def empty_tmdb(title):
    return {
        "russian_title": title,
        "tmdb_id": None,
        "tmdb_title": None,
        "original_title": None,
        "year_tmdb": None,
        "country_tmdb": None,
        "genre_tmdb": None,
        "director_tmdb": None,
        "rating_tmdb_new": None,
        "description_tmdb": None
    }


def tmdb_info(title, api_key):
    query = search_title(title)

    search = tmdb_get(
        "/search/movie",
        api_key,
        query=query,
        language="ru-RU",
        include_adult="false"
    )

    results = search.get("results", [])

    if not results:
        return empty_tmdb(title)

    movie = results[0]

    details = tmdb_get(
        f"/movie/{movie['id']}",
        api_key,
        language="ru-RU",
        append_to_response="credits"
    )

    release_date = details.get("release_date") or movie.get("release_date")
    crew = details.get("credits", {}).get("crew", [])

    return {
        "russian_title": title,
        "tmdb_id": movie.get("id"),
        "tmdb_title": details.get("title") or movie.get("title"),
        "original_title": details.get("original_title") or movie.get("original_title"),
        "year_tmdb": release_date[:4] if release_date else None,
        "country_tmdb": ", ".join(c["name"] for c in details.get("production_countries", []) if c.get("name")),
        "genre_tmdb": ", ".join(g["name"] for g in details.get("genres", []) if g.get("name")),
        "director_tmdb": ", ".join(p["name"] for p in crew if p.get("job") == "Director"),
        "rating_tmdb_new": details.get("vote_average") or movie.get("vote_average"),
        "description_tmdb": details.get("overview") or movie.get("overview")
    }


def build_table(api_key, start_day=None, days=7):
    moskino = parse_moskino(start_day=start_day, days=days)
    pioner = parse_pioner()

    for df in [moskino, pioner]:
        for col in BASE_COLS:
            if col not in df.columns:
                df[col] = None

    data = pd.concat(
        [moskino[BASE_COLS], pioner[BASE_COLS]],
        ignore_index=True
    )

    data["title_norm"] = data["russian_title"].apply(norm_title)

    data = (
        data
        .drop_duplicates("title_norm")
        .reset_index(drop=True)
    )

    rows = []

    for title in data["russian_title"].dropna().unique():
        rows.append(tmdb_info(title, api_key))

    final = data.merge(
        pd.DataFrame(rows),
        on="russian_title",
        how="left"
    )

    final["year"] = final["year_tmdb"].where(final["year_tmdb"].notna(), final["year"])
    final["country"] = final["country_tmdb"].where(final["country_tmdb"].notna(), final["country"])
    final["genre"] = final["genre_tmdb"].where(final["genre_tmdb"].notna(), final["genre"])
    final["director"] = final["director_tmdb"].where(final["director_tmdb"].notna(), final["director"])
    final["rating_tmdb"] = final["rating_tmdb_new"].where(final["rating_tmdb_new"].notna(), final["rating_tmdb"])
    final["description"] = final["description_tmdb"].where(final["description_tmdb"].notna(), final["description"])
    final["tmdb_id"] = pd.to_numeric(final["tmdb_id"], errors="coerce").astype("Int64")

    final = final.drop(
        columns=[
            "title_norm",
            "tmdb_title",
            "year_tmdb",
            "country_tmdb",
            "genre_tmdb",
            "director_tmdb",
            "rating_tmdb_new",
            "description_tmdb"
        ],
        errors="ignore"
    )

    cols = [
        "russian_title",
        "original_title",
        "tmdb_id",
        "year",
        "country",
        "genre",
        "director",
        "rating_tmdb",
        "description",
        "cinema",
        "address",
        "date",
        "session_time",
        "duration_min",
        "age_rating",
        "format",
        "has_subtitles",
        "price",
        "source_parsing",
        "source_url"
    ]

    return final[cols].sort_values("russian_title").reset_index(drop=True)


def load_csv(name):
    paths = [name, f"data/{name}"]
    for path in paths:
        try:
            return pd.read_csv(path)
        except FileNotFoundError:
            pass
    raise FileNotFoundError(name)


def normalize_tmdb_id(df):
    df = df.copy()
    df["tmdb_id"] = pd.to_numeric(df["tmdb_id"], errors="coerce").astype("Int64")
    return df.dropna(subset=["tmdb_id"])


def find_release_candidates(
    current_df,
    festival_file="foreign_festival_films_tmdb.csv",
    certificates_file="certificates_clean_tmdb.csv"
):
    festival = normalize_tmdb_id(load_csv(festival_file))
    certificates = normalize_tmdb_id(load_csv(certificates_file))
    current = normalize_tmdb_id(current_df)

    data = festival.merge(
        certificates,
        on="tmdb_id",
        how="inner",
        suffixes=("_festival", "_certificate")
    )

    data = data[~data["tmdb_id"].isin(current["tmdb_id"])].copy()

    sort_cols = [col for col in ["year_festival", "festival", "russian_title"] if col in data.columns]
    if sort_cols:
        data = data.sort_values(sort_cols, ascending=[False] + [True] * (len(sort_cols) - 1))

    return data.drop_duplicates("tmdb_id").reset_index(drop=True)
