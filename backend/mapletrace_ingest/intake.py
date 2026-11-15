"""Safe archive extraction, hashing and format sniffing.

The original zip is never modified. Members are copied into a read-only
working area after checks for path traversal, links, zip bombs and size limits.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath


class IntakeError(Exception):
    pass


@dataclass
class Limits:
    max_total_bytes: int = 8 * 1024**3
    max_files: int = 100_000
    max_ratio: float = 200.0            # compression ratio considered a bomb...
    ratio_min_bytes: int = 50 * 1024**2  # ...but only for members bigger than this
    max_archive_depth: int = 3


@dataclass
class Member:
    original_path: str
    stored_path: Path
    size: int
    sha256: str
    md5: str
    container_mtime: str | None


def hash_file(path: Path) -> tuple[str, str]:
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            sha.update(chunk)
            md5.update(chunk)
    return sha.hexdigest(), md5.hexdigest()


def _safe_relpath(name: str) -> PurePosixPath | None:
    name = name.replace("\\", "/")
    p = PurePosixPath(name)
    if p.is_absolute() or re.match(r"^[A-Za-z]:", name):
        return None
    parts = [part for part in p.parts if part not in ("", ".")]
    if any(part == ".." for part in parts) or not parts:
        return None
    clean = [re.sub(r'[<>:"|?*\x00-\x1f]', "_", part) for part in parts]
    return PurePosixPath(*clean)


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def make_read_only(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        pass


def extract_zip(zip_path: Path, dest: Path, limits: Limits, warn) -> list[Member]:
    """Extract every regular file member into dest. Unsafe members are skipped and reported via warn()."""
    if not zipfile.is_zipfile(zip_path):
        raise IntakeError(f"{zip_path.name} is not a valid zip archive")
    members: list[Member] = []
    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > limits.max_files:
            raise IntakeError(f"archive has {len(infos)} files; limit is {limits.max_files}")
        for info in infos:
            rel = _safe_relpath(info.filename)
            if rel is None:
                warn("unsafe_path_skipped", {"member": info.filename})
                continue
            if _is_symlink(info):
                warn("symlink_skipped", {"member": info.filename})
                continue
            if info.flag_bits & 0x1:
                warn("encrypted_member_skipped", {"member": info.filename})
                continue
            if info.file_size > limits.ratio_min_bytes and info.compress_size and \
                    info.file_size / info.compress_size > limits.max_ratio:
                warn("suspected_zip_bomb_skipped", {"member": info.filename, "size": info.file_size})
                continue
            total += info.file_size
            if total > limits.max_total_bytes:
                raise IntakeError("archive exceeds the total size limit")
            target = dest / Path(*rel.parts)
            # never let two members collide silently
            if target.exists():
                target = target.with_name(f"{target.stem}__dup{len(members)}{target.suffix}")
            target.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with zf.open(info) as src, open(target, "wb") as out:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    written += len(chunk)
                    if written > info.file_size + 1024:  # header lied about size
                        raise IntakeError(f"member {info.filename} is larger than declared")
                    out.write(chunk)
            sha, md5 = hash_file(target)
            make_read_only(target)
            try:
                mtime = datetime(*info.date_time).isoformat()
            except ValueError:
                mtime = None
            members.append(Member(rel.as_posix(), target, written, sha, md5, mtime))
    return members


# --------------------------------------------------------------------------- #
# Format sniffing from content (extensions are hints, not facts)
# --------------------------------------------------------------------------- #

_SIGNATURES: list[tuple[int, bytes, str]] = [
    (0, b"\xff\xd8\xff", "jpeg"),
    (0, b"\x89PNG\r\n\x1a\n", "png"),
    (0, b"GIF87a", "gif"),
    (0, b"GIF89a", "gif"),
    (0, b"II*\x00", "tiff"),
    (0, b"MM\x00*", "tiff"),
    (0, b"BM", "bmp"),
    (0, b"%PDF", "pdf"),
    (0, b"PK\x03\x04", "zip"),
    (0, b"PK\x05\x06", "zip"),
    (0, b"ID3", "mp3"),
    (0, b"fLaC", "flac"),
    (0, b"OggS", "ogg"),
    (0, b"#!AMR", "amr"),
    (0, b"\x1aE\xdf\xa3", "matroska"),
    (0, b"SQLite format 3\x00", "sqlite"),
    (0, b"\x7fELF", "elf"),
    (0, b"MZ", "exe"),
]


def sniff_format(path: Path) -> str:
    with open(path, "rb") as fh:
        head = fh.read(4096)
    if not head:
        return "empty"
    for off, sig, name in _SIGNATURES:
        if head[off:off + len(sig)] == sig:
            if name == "zip":
                return _sniff_zip_container(path)
            return name
    if head[:4] == b"RIFF" and len(head) >= 12:
        kind = head[8:12]
        return {b"WAVE": "wav", b"AVI ": "avi", b"WEBP": "webp"}.get(kind, "riff")
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"heic", b"heix", b"mif1", b"msf1", b"hevc"):
            return "heic"
        if brand in (b"M4A ", b"M4B "):
            return "m4a"
        if brand.startswith(b"qt"):
            return "mov"
        if brand.startswith(b"3g"):
            return "3gp"
        return "mp4"
    if head[:2] == b"\xff\xfb" or head[:2] == b"\xff\xf3":
        return "mp3"
    return _sniff_text(head)


def _sniff_zip_container(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
    except zipfile.BadZipFile:
        return "zip"
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    return "zip"


def _decode_head(head: bytes) -> str | None:
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return head.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if b"\x00" in head[:1024]:
        return None
    controls = sum(1 for b in head if b < 32 and b not in (9, 10, 12, 13))
    if controls / len(head) > 0.02:
        return None
    try:
        return head.decode("utf-8")
    except UnicodeDecodeError as exc:
        if exc.start >= len(head) - 4:  # multi-byte character cut off at the end of the sample
            return head[:exc.start].decode("utf-8", errors="ignore")
    high = sum(1 for b in head if b >= 128)
    if high / len(head) > 0.3:  # legacy-encoded text is mostly ASCII; random binary is not
        return None
    try:
        return head.decode("cp1252")
    except UnicodeDecodeError:
        return None


def _sniff_text(head: bytes) -> str:
    text = _decode_head(head)
    if text is None:
        return "binary"
    t = text.lstrip("﻿ \t\r\n")
    low = t[:2000].lower()
    if t.startswith(">") and re.match(r">\S+.*\n[ACGTNRYKMSWBDHV\-\n]+", t[:2000], re.I):
        return "fasta"
    if t.startswith("##fileformat=VCF"):
        return "vcf"
    if t.startswith("<?xml") or t.startswith("<"):
        if "<gpx" in low:
            return "gpx"
        if "<kml" in low:
            return "kml"
        if "<html" in low:
            return "html"
        return "xml"
    if t.startswith("BEGIN:VCALENDAR"):
        return "ics"
    if re.match(r"\[\d{1,6}\]\s", t):
        return "text"  # line-numbered document ("[0001] ..."), not JSON
    if t.startswith("{") or t.startswith("["):
        first_line = t.splitlines()[0].strip() if t.splitlines() else ""
        if first_line.startswith("{") and first_line.endswith("}") and len(t.splitlines()) > 1:
            return "jsonl"
        return "json"
    if t.startswith("From ") and re.search(r"^(From|Subject|Date):", t, re.M):
        return "mbox"
    header_block = t.split("\n\n", 1)[0] if "\n\n" in t else t[:1500]
    hdrs = {h.lower() for h in re.findall(r"^([A-Za-z\-]+):", header_block, re.M)}
    if {"from", "date"} <= hdrs and ("subject" in hdrs or "to" in hdrs) and ("message-id" in hdrs or "mime-version" in hdrs or "received" in hdrs or "to" in hdrs):
        return "eml"
    return "text"


def decode_text_file(path: Path, max_bytes: int = 50 * 1024**2) -> tuple[str, str]:
    data = path.read_bytes()[:max_bytes]
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace"), "utf-16"
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace"), "latin-1"
