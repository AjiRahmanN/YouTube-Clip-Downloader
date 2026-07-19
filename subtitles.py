"""
subtitles.py
============
Parsing, pemotongan, dan penulisan ulang file subtitle format SRT.

Kenapa perlu modul terpisah: subtitle hasil download yt-dlp itu buat
video PENUH. Kalau videonya dipotong ke rentang tertentu, subtitle-nya
juga harus dipotong & di-retime (dikurangi offset start), atau timing-nya
bakal meleset total dari video hasil potongan.
"""

import re
from dataclasses import dataclass

_TIME_RE = re.compile(r'(\d+):(\d{2}):(\d{2})[,.](\d{3})')
_BLOCK_SPLIT_RE = re.compile(r'\r?\n\r?\n+')


@dataclass
class SubEntry:
    start: float  # detik
    end: float    # detik
    text: str


def srt_time_to_seconds(t_str):
    """'00:01:02,500' -> 62.5"""
    m = _TIME_RE.search(t_str)
    if not m:
        raise ValueError(f"Format waktu SRT tidak valid: {t_str!r}")
    h, mnt, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mnt * 60 + s + ms / 1000


def seconds_to_srt_time(sec):
    """62.5 -> '00:01:02,500'"""
    if sec < 0:
        sec = 0
    total_ms = round(sec * 1000)
    h, rem = divmod(total_ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(path):
    """Baca file .srt, kembalikan list SubEntry. Format non-standar/BOM ditolerir."""
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        content = f.read()

    entries = []
    for block in _BLOCK_SPLIT_RE.split(content.strip()):
        lines = [ln for ln in block.strip().splitlines() if ln.strip() != '']
        if len(lines) < 2:
            continue
        # baris pertama index (angka) -> skip, baris kedua "start --> end"
        time_line_idx = 0
        if lines[0].strip().isdigit():
            time_line_idx = 1
        if time_line_idx >= len(lines) or '-->' not in lines[time_line_idx]:
            continue
        start_str, end_str = lines[time_line_idx].split('-->')
        try:
            start = srt_time_to_seconds(start_str)
            end = srt_time_to_seconds(end_str)
        except ValueError:
            continue
        text = '\n'.join(lines[time_line_idx + 1:]).strip()
        entries.append(SubEntry(start=start, end=end, text=text))
    return entries


def trim_srt(entries, clip_start, clip_end):
    """Ambil entry yang overlap [clip_start, clip_end], potong batasnya,
    lalu retime relatif ke clip_start (biar subtitle mulai dari 0 lagi)."""
    result = []
    for e in entries:
        if e.end <= clip_start or e.start >= clip_end:
            continue  # di luar rentang, buang
        new_start = max(e.start, clip_start) - clip_start
        new_end = min(e.end, clip_end) - clip_start
        if new_end <= new_start:
            continue
        result.append(SubEntry(start=new_start, end=new_end, text=e.text))
    return result


def write_srt(entries, path):
    with open(path, 'w', encoding='utf-8') as f:
        for i, e in enumerate(entries, start=1):
            f.write(f"{i}\n")
            f.write(f"{seconds_to_srt_time(e.start)} --> {seconds_to_srt_time(e.end)}\n")
            f.write(f"{e.text}\n\n")


def trim_srt_file(src_path, dst_path, clip_start, clip_end):
    """Shortcut: baca file src, potong ke rentang, tulis ke dst.
    Return jumlah entry hasil potongan (0 = gak ada subtitle di rentang itu)."""
    entries = parse_srt(src_path)
    trimmed = trim_srt(entries, clip_start, clip_end)
    write_srt(trimmed, dst_path)
    return len(trimmed)
