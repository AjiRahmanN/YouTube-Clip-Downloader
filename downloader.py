"""
downloader.py
=============
Logika inti download & potong video YouTube (yt-dlp + ffmpeg).
Diadaptasi dari script CLI: selalu download penuh dulu (progress asli,
auto-retry bawaan yt-dlp), baru dipotong lokal - jauh lebih stabil
ketimbang potong langsung dari stream jaringan buat video panjang.
"""

import glob
import os
import shutil
import subprocess

import yt_dlp


def check_ffmpeg(ffmpeg_path=None):
    """Cek apakah ffmpeg bisa ditemukan, lewat PATH atau path custom."""
    if ffmpeg_path:
        if os.path.isfile(ffmpeg_path):
            return True
        exe_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
        return os.path.isfile(os.path.join(ffmpeg_path, exe_name))
    return shutil.which('ffmpeg') is not None


def _resolve_ffmpeg_exe(ffmpeg_path=None):
    if ffmpeg_path:
        if os.path.isfile(ffmpeg_path):
            return ffmpeg_path
        exe_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
        candidate = os.path.join(ffmpeg_path, exe_name)
        if os.path.isfile(candidate):
            return candidate
    return 'ffmpeg'


def get_video_info(url):
    """Ambil metadata video TANPA download (cepat, buat preview & bikin slider)."""
    opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'noplaylist': True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Kumpulin daftar bahasa subtitle yang tersedia (manual + auto-generated)
    manual_langs = sorted((info.get('subtitles') or {}).keys())
    auto_langs = sorted((info.get('automatic_captions') or {}).keys())

    return {
        'id': info.get('id'),
        'title': info.get('title') or 'video',
        'duration': int(info.get('duration') or 0),
        'thumbnail': info.get('thumbnail'),
        'manual_sub_langs': manual_langs,
        'auto_sub_langs': auto_langs,
    }


def build_ydl_opts(output_path, quality, audio_only, ffmpeg_path=None,
                    progress_hook=None, want_subtitles=False, sub_langs=None):
    postprocessors = []
    opts = {
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': False,
    }
    if progress_hook:
        opts['progress_hooks'] = [progress_hook]
    if ffmpeg_path:
        opts['ffmpeg_location'] = ffmpeg_path

    if audio_only:
        opts['format'] = 'bestaudio/best'
        postprocessors.append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        })
    elif quality and quality != 'best':
        opts['format'] = (
            f'bestvideo[vcodec^=avc1][height<={quality}]+bestaudio[acodec^=mp4a]'
            f'/best[vcodec^=avc1][height<={quality}]/best[height<={quality}]'
        )
        opts['merge_output_format'] = 'mp4'
    else:
        opts['format'] = (
            'bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]'
            '/best[vcodec^=avc1]/best'
        )
        opts['merge_output_format'] = 'mp4'

    if want_subtitles:
        opts['writesubtitles'] = True
        opts['writeautomaticsub'] = True
        opts['subtitleslangs'] = sub_langs or ['id', 'en']
        opts['subtitlesformat'] = 'srt/best'
        postprocessors.append({'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'})

    if postprocessors:
        opts['postprocessors'] = postprocessors

    return opts


def find_subtitle_file(video_path):
    """Cari file .srt yang dihasilkan bareng video (nama: <title>.<lang>.srt)."""
    base = os.path.splitext(video_path)[0]
    matches = sorted(glob.glob(f"{base}.*.srt"))
    return matches[0] if matches else None


def download_full(url, output_path='downloads', quality='best', audio_only=False,
                   ffmpeg_path=None, progress_hook=None, want_subtitles=False,
                   sub_langs=None):
    """Download video/audio PENUH (bukan rentang). Return (video_path, subtitle_path_or_None)."""
    os.makedirs(output_path, exist_ok=True)
    ydl_opts = build_ydl_opts(output_path, quality, audio_only, ffmpeg_path,
                               progress_hook, want_subtitles, sub_langs)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = info.get('filepath') or ydl.prepare_filename(info)

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"File hasil download gak ketemu: {video_path}")

    sub_path = find_subtitle_file(video_path) if want_subtitles else None
    return video_path, sub_path


def trim_local(src_path, dst_path, start_time, end_time, precise=False, ffmpeg_path=None):
    """Potong file video LOKAL pakai ffmpeg. Gak nyentuh jaringan sama sekali."""
    ffmpeg_exe = _resolve_ffmpeg_exe(ffmpeg_path)
    cmd = [ffmpeg_exe, '-y']
    if start_time is not None:
        cmd += ['-ss', str(start_time)]
    cmd += ['-i', src_path]
    if end_time is not None:
        duration = end_time - (start_time or 0)
        cmd += ['-t', str(duration)]

    if precise:
        cmd += ['-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-c:a', 'aac', '-b:a', '192k']
    else:
        cmd += ['-c', 'copy']
    cmd.append(dst_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, result.stderr


def format_hms(total_seconds):
    """1234 -> '20:34' atau '1:20:34' kalau lebih dari sejam."""
    total_seconds = int(total_seconds or 0)
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
