"""Core converter from YummySoup! libraries to Paprika Recipe Manager 3 archives."""
from __future__ import annotations

import base64
import datetime as dt
import gzip
import hashlib
from html.parser import HTMLParser
import json
import re
import sqlite3
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

APPLE_EPOCH = dt.datetime(2001, 1, 1)


@dataclass
class ConversionReport:
    recipes: int = 0
    primary_images: int = 0
    secondary_images: int = 0
    missing_primary_images: int = 0
    errors: int = 0


class YummyHTMLToText(HTMLParser):
    """Minimal HTML-to-Markdown-ish text converter for YummySoup rich text fields."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.bold = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"br", "p", "div", "li"}:
            self.parts.append("\n")
        if tag in {"b", "strong"}:
            self.parts.append("**")
            self.bold = True
        if tag == "li":
            self.parts.append("- ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"p", "div", "li"}:
            self.parts.append("\n")
        if tag in {"b", "strong"} and self.bold:
            self.parts.append("**")
            self.bold = False

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        value = "".join(self.parts).replace("\xa0", " ")
        value = re.sub(r"[ \t]+\n", "\n", value)
        value = re.sub(r"\n[ \t]+", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()


def html_to_text(value: str | None) -> str:
    """Convert YummySoup HTML fields to text accepted by Paprika."""
    if not value:
        return ""
    parser = YummyHTMLToText()
    parser.feed(value)
    text = parser.text()

    # Normalize bold numbered steps. YummySoup HTML can produce forms such as
    # **2. **, which Paprika displays with literal asterisks.
    text = re.sub(r"\*\*\s*(\d+)\.\s*\*\*", r"**\1.**", text)

    # Paprika's Markdown parser needs a separator after the closing **.
    # YummySoup sometimes stores <b>1.</b>Text, yielding **1.**Text.
    text = re.sub(r"(\*\*\d+\.\*\*)(?=\S)", r"\1 ", text)

    # YummySoup embeds secondary photos as [2], [3], ...; Paprika uses [photo:2].
    return re.sub(r"\[(\d{1,2})\]", r"[photo:\1]", text)


def decode_openstep_string(token: str) -> str:
    token = token.strip()
    if token.startswith('"') and token.endswith('"'):
        token = token[1:-1]
        token = token.replace(r'\"', '"').replace(r"\\", "\\")
    return re.sub(r"\\U([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), token)


def parse_ingredient_array(raw: str | None) -> list[dict[str, str]]:
    """Parse the OpenStep-style property-list array used by YummySoup."""
    if not raw:
        return []
    objects = re.findall(r"\{(.*?)\}", raw, flags=re.S)
    result: list[dict[str, str]] = []
    for obj in objects:
        item: dict[str, str] = {}
        for match in re.finditer(r"([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*?);", obj, flags=re.S):
            key, value = match.groups()
            item[key] = decode_openstep_string(value)
        if item:
            result.append(item)
    return result


def ingredients_to_text(raw: str | None) -> str:
    lines: list[str] = []
    for item in parse_ingredient_array(raw):
        name = item.get("name", "").strip()
        if not name:
            continue
        if item.get("isGroupTitle") == "1":
            lines.append(name.upper())
            continue
        parts = [item.get("quantity", "").strip(), item.get("measurement", "").strip(), name]
        line = " ".join(part for part in parts if part)
        method = item.get("method", "").strip()
        if method:
            line += f", {method}"
        lines.append(line)
    return "\n".join(lines)


def apple_date(value: Any) -> str:
    if value in (None, ""):
        return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        date = APPLE_EPOCH + dt.timedelta(seconds=float(value))
        return date.strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OverflowError):
        return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_categories(keywords: str | None, cuisine: str | None) -> list[str]:
    values: list[str] = []
    if keywords:
        values.extend(re.split(r"[,;]", keywords))
    if cuisine and cuisine.strip():
        values.append(cuisine.strip())
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = value.strip()
        if value and value.casefold() not in seen:
            out.append(value)
            seen.add(value.casefold())
    return out


def safe_filename(name: str, fallback: str) -> str:
    clean = re.sub(r"[/:\\]", "-", name).strip().strip(".")
    clean = re.sub(r"\s+", " ", clean)
    return (clean[:180] or fallback) + ".paprikarecipe"


def recipe_hash(recipe: dict[str, Any]) -> str:
    payload = dict(recipe)
    payload.pop("hash", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def find_recipe_images(unique_id: str, image_names: set[str]) -> list[tuple[int, str]]:
    pattern = re.compile(rf"^{re.escape(unique_id)}-Image(\d+)\.[^.]+$", re.I)
    found: list[tuple[int, str]] = []
    for name in image_names:
        match = pattern.match(Path(name).name)
        if match:
            found.append((int(match.group(1)), name))
    return sorted(found, key=lambda item: item[0])


def make_recipe(row: sqlite3.Row, images: list[tuple[int, str, bytes]]) -> dict[str, Any]:
    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, "yummysoup:" + (row["ZUNIQUEID"] or str(row["Z_PK"])))).upper()
    source = (row["ZATTRIBUTION"] or "").strip()
    if not source and row["ZIMPORTEDFROMURL"]:
        source = re.sub(r"^https?://(?:www\.)?", "", row["ZIMPORTEDFROMURL"]).split("/")[0]

    notes_parts = [part.strip() for part in (row["ZNOTES"], row["ZPRIVATENOTES"]) if part and part.strip()]
    recipe: dict[str, Any] = {
        "nutritional_info": "",
        "photo_hash": None,
        "uid": uid,
        "categories": clean_categories(row["ZKEYWORDS"], row["ZCUISINE"]),
        "name": (row["ZNAME"] or "Untitled Recipe").strip(),
        "description": html_to_text(row["ZRECIPEDESCRIPTION"]),
        "photo_data": None,
        "prep_time": (row["ZPREPTIME"] or "").strip(),
        "directions": html_to_text(row["ZDIRECTIONS"]),
        "source": source,
        "photos": [],
        "image_url": None,
        "total_time": "",
        "hash": "",
        "photo_large": None,
        "difficulty": str(row["ZDIFFICULTY"] or "") if row["ZDIFFICULTY"] else "",
        "source_url": (row["ZIMPORTEDFROMURL"] or "").strip(),
        "ingredients": ingredients_to_text(row["ZINGREDIENTSARRAY"]),
        "notes": "\n\n".join(notes_parts),
        "created": apple_date(row["ZDATECREATED"]),
        "rating": int(row["ZRATING"] or 0),
        "cook_time": (row["ZCOOKINGTIME"] or "").strip(),
        "servings": (row["ZYIELD"] or "").strip(),
        "photo": None,
    }
    for number, image_name, image_bytes in images:
        ext = Path(image_name).suffix.lower() or ".jpg"
        filename = f"{str(uuid.uuid4()).upper()}{ext}"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        digest = hashlib.sha256(image_bytes).hexdigest().upper()
        recipe["photos"].append({"data": encoded, "hash": digest, "filename": filename, "name": str(number)})
        if number == 1:
            paprika_photo_name = f"{uid}{ext}"
            recipe["photo"] = paprika_photo_name
            recipe["photo_large"] = paprika_photo_name
            recipe["photo_data"] = encoded
            recipe["photo_hash"] = digest
    recipe["hash"] = recipe_hash(recipe)
    return recipe


def locate_in_directory(package: Path) -> tuple[Path, Path]:
    db = package / "Library Database.SQL"
    images = package / "Images"
    if not db.exists():
        matches = list(package.rglob("Library Database.SQL"))
        if not matches:
            raise FileNotFoundError("Library Database.SQL not found")
        db = matches[0]
        images = db.parent / "Images"
    return db, images


def _iter_zip_members(input_path: Path, temp: Path) -> tuple[Path, set[str], Callable[[str], bytes], zipfile.ZipFile]:
    zip_source = zipfile.ZipFile(input_path)
    names = zip_source.namelist()
    db_member = next((name for name in names if name.endswith("/Library Database.SQL") or name == "Library Database.SQL"), None)
    if not db_member:
        zip_source.close()
        raise FileNotFoundError("Library Database.SQL not found in ZIP archive")
    db_path = temp / "Library Database.SQL"
    db_path.write_bytes(zip_source.read(db_member))
    image_members = {name for name in names if "/Images/" in name and not name.endswith("/")}

    def get_image(name: str) -> bytes:
        return zip_source.read(name)

    return db_path, image_members, get_image, zip_source


def convert(input_path: Path, output_path: Path, limit: int | None = None) -> ConversionReport:
    """Convert a YummySoup! library package or ZIP into a Paprika .paprikarecipes archive."""
    report = ConversionReport()
    with tempfile.TemporaryDirectory(prefix="yummy2paprika-") as temp_dir:
        temp = Path(temp_dir)
        zip_source: zipfile.ZipFile | None = None
        if input_path.is_dir():
            db_path, images_dir = locate_in_directory(input_path)
            image_names = {str(path.relative_to(images_dir)) for path in images_dir.rglob("*") if path.is_file()} if images_dir.exists() else set()

            def get_image(name: str) -> bytes:
                return (images_dir / name).read_bytes()

        else:
            db_path, image_names, get_image, zip_source = _iter_zip_members(input_path, temp)

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        sql = "SELECT * FROM ZRECIPES ORDER BY Z_PK"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        rows = con.execute(sql)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        used_names: set[str] = set()
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as out:
            for row in rows:
                try:
                    unique_id = row["ZUNIQUEID"] or ""
                    image_members = find_recipe_images(unique_id, image_names)
                    images = [(number, member, get_image(member)) for number, member in image_members]
                    if any(number == 1 for number, _, _ in images):
                        report.primary_images += 1
                    else:
                        report.missing_primary_images += 1
                    report.secondary_images += sum(1 for number, _, _ in images if number > 1)

                    recipe = make_recipe(row, images)
                    filename = safe_filename(recipe["name"], recipe["uid"])
                    base = filename[: -len(".paprikarecipe")]
                    counter = 2
                    while filename.casefold() in used_names:
                        filename = f"{base} ({counter}).paprikarecipe"
                        counter += 1
                    used_names.add(filename.casefold())

                    raw = json.dumps(recipe, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    out.writestr(filename, gzip.compress(raw, mtime=0))
                    report.recipes += 1
                except Exception as exc:  # noqa: BLE001 - conversion should continue with a report
                    report.errors += 1
                    print(f"ERROR recipe Z_PK={row['Z_PK']}: {exc}")
        con.close()
        if zip_source:
            zip_source.close()
    return report
