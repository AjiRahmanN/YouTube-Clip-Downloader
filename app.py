"""
YouTube Clip Downloader - Streamlit App
=========================================
Preview video, pilih rentang start-end pakai slider, download + potong
otomatis (video & subtitle), lengkap dengan progress bar asli.

Jalanin dengan: streamlit run app.py
"""

import base64
import io
import os
import tempfile
import zipfile

import streamlit as st

from downloader import (
    check_ffmpeg, download_full, format_hms, get_video_info, trim_local,
)
from subtitles import trim_srt_file


def parse_time_str(s):
    """'46', '39:46', atau '1:03:41' -> total detik (int). Lempar ValueError kalau gak valid."""
    s = (s or "").strip()
    if not s:
        raise ValueError("Waktu gak boleh kosong")
    try:
        parts = [float(p) for p in s.split(":")]
    except ValueError:
        raise ValueError(f"Format '{s}' gak valid (pakai SS, MM:SS, atau HH:MM:SS)")
    if len(parts) == 1:
        total = parts[0]
    elif len(parts) == 2:
        total = parts[0] * 60 + parts[1]
    elif len(parts) == 3:
        total = parts[0] * 3600 + parts[1] * 60 + parts[2]
    else:
        raise ValueError(f"Format '{s}' gak valid (pakai SS, MM:SS, atau HH:MM:SS)")
    return int(total)


st.set_page_config(page_title="YouTube Clip Downloader", page_icon="✂️", layout="centered")

st.markdown("""
<style>
    div.stButton > button, div.stDownloadButton > button { font-weight: 600; border-radius: 8px; }
    .clip-range { font-size: 0.95rem; color: #2dd4bf; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("✂️ YouTube Clip Downloader")
st.caption("Preview, potong rentang waktu, dan download video + subtitle otomatis.")

if "video_info" not in st.session_state:
    st.session_state.video_info = None
if "loaded_url" not in st.session_state:
    st.session_state.loaded_url = None

# ---------- 1. Input URL ----------
url = st.text_input("URL video YouTube", placeholder="https://www.youtube.com/watch?v=...")
col_load, col_ffmpeg = st.columns([1, 3])
with col_load:
    load_clicked = st.button("Muat Video", type="primary", use_container_width=True)
with col_ffmpeg:
    if not check_ffmpeg():
        st.warning("ffmpeg gak ketemu di PATH. Video butuh ffmpeg buat gabung/potong.", icon="⚠️")

if load_clicked and url:
    with st.spinner("Ngambil info video..."):
        try:
            new_info = get_video_info(url)
            st.session_state.video_info = new_info
            st.session_state.loaded_url = url
            st.session_state.clips = [{"id": 0, "start": 0, "end": min(60, new_info["duration"] or 60)}]
            st.session_state.next_clip_id = 1
        except Exception as e:
            st.error(f"Gagal ambil info video: {e}")
            st.session_state.video_info = None

info = st.session_state.video_info

# ---------- 2. Preview + slider (cuma muncul kalau info udah ke-load) ----------
if info and st.session_state.loaded_url == url:
    st.subheader(info["title"])
    duration = max(info["duration"], 1)

    if "clips" not in st.session_state:
        st.session_state.clips = [{"id": 0, "start": 0, "end": min(60, duration)}]
    if "next_clip_id" not in st.session_state:
        st.session_state.next_clip_id = 1

    # Preview: YouTube embed mentah lewat HTML (bukan st.iframe)
    embed_url = f"https://www.youtube.com/embed/{info['id']}"
    st.markdown(
        f'<iframe width="100%" height="360" src="{embed_url}" '
        f'frameborder="0" allow="accelerometer; autoplay; clipboard-write; '
        f'encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>',
        unsafe_allow_html=True,
    )
    st.caption("Player di atas ikut YouTube asli - bebas di-scrub buat cari momen yang pas.")

    st.divider()
    st.markdown("#### Klip")

    remove_id = None
    for i, clip in enumerate(st.session_state.clips):
        cid = clip["id"]
        with st.container(border=True):
            cols = st.columns([2, 2, 3, 1])
            with cols[0]:
                start_str = st.text_input("Mulai", value=format_hms(clip["start"]),
                                           key=f"start_{cid}", label_visibility="collapsed" if i else "visible")
            with cols[1]:
                end_str = st.text_input("Selesai", value=format_hms(clip["end"]),
                                         key=f"end_{cid}", label_visibility="collapsed" if i else "visible")
            with cols[2]:
                if i == 0:
                    st.write("")
                try:
                    new_start = parse_time_str(start_str)
                    new_end = parse_time_str(end_str)
                    if new_start > duration or new_end > duration:
                        st.error(f"Video cuma {format_hms(duration)}, waktu melebihi durasi.")
                    elif new_end <= new_start:
                        st.error("Selesai harus lebih besar dari Mulai.")
                    else:
                        clip["start"], clip["end"] = new_start, new_end
                        st.markdown(
                            f'<span class="clip-range">Klip {i + 1}: {format_hms(new_start)} → '
                            f'{format_hms(new_end)} ({format_hms(new_end - new_start)})</span>',
                            unsafe_allow_html=True,
                        )
                except ValueError as e:
                    st.error(str(e))
            with cols[3]:
                if i == 0:
                    st.write("")
                if len(st.session_state.clips) > 1 and st.button("🗑️", key=f"del_{cid}"):
                    remove_id = cid

    if remove_id is not None:
        st.session_state.clips = [c for c in st.session_state.clips if c["id"] != remove_id]
        st.rerun()

    if st.button("+ Tambah klip"):
        last_end = st.session_state.clips[-1]["end"]
        new_start = min(last_end, duration)
        new_id = st.session_state.next_clip_id
        st.session_state.next_clip_id += 1
        st.session_state.clips.append({"id": new_id, "start": new_start, "end": min(new_start + 60, duration)})
        st.rerun()

    # ---------- Opsi download ----------
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        quality_label = st.selectbox("Kualitas video", ["Terbaik", "1080p", "720p", "480p"])
        quality_map = {"Terbaik": "best", "1080p": "1080", "720p": "720", "480p": "480"}
        quality = quality_map[quality_label]
        audio_only = st.checkbox("Audio saja (MP3)")
    with c2:
        precise = st.checkbox("Potongan presisi frame-exact", value=False,
                               help="Re-encode, lebih lambat tapi presisi. Default: cepat, boleh geser 1-2 detik.")
        keep_full = st.checkbox("Sertakan juga video lengkap (belum dipotong) di dalam zip")

    all_langs = sorted(set(info["manual_sub_langs"]) | set(info["auto_sub_langs"]))
    want_subs = st.checkbox("Auto-download subtitle", value=bool(all_langs), disabled=not all_langs)
    sub_langs = []
    if not all_langs:
        st.caption("Video ini gak punya subtitle/caption sama sekali.")
    elif want_subs:
        default_langs = [l for l in ("id", "en") if l in all_langs] or all_langs[:1]
        sub_langs = st.multiselect("Bahasa subtitle", all_langs, default=default_langs)

    valid_clips = [c for c in st.session_state.clips if c["end"] > c["start"]]
    st.divider()
    go = st.button(f"⬇️ Download {len(valid_clips)} Klip (langsung ke-download)", type="primary",
                    use_container_width=True, disabled=not check_ffmpeg() or not valid_clips)

    # ---------- Proses download ----------
    if go:
        progress_bar = st.progress(0.0)
        status = st.empty()

        def format_speed(bps):
            if not bps:
                return "-"
            for unit in ("B", "KiB", "MiB", "GiB"):
                if bps < 1024:
                    return f"{bps:.1f}{unit}/s"
                bps /= 1024
            return f"{bps:.1f}TiB/s"

        def on_progress(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                done = d.get("downloaded_bytes", 0)
                pct = (done / total * 100) if total else 0
                if total:
                    progress_bar.progress(min(done / total, 1.0))
                eta = d.get("eta")
                status.text(f"Download: {pct:.1f}% | speed: {format_speed(d.get('speed'))} | "
                            f"ETA: {format_hms(eta) if eta else '-'}")
            elif d["status"] == "finished":
                progress_bar.progress(1.0)
                status.text("Download selesai, memotong tiap klip...")

        workdir = tempfile.mkdtemp(prefix="ytclip_")
        try:
            video_path, sub_path = download_full(
                url, output_path=workdir, quality=quality, audio_only=audio_only,
                progress_hook=on_progress, want_subtitles=want_subs and bool(sub_langs),
                sub_langs=sub_langs or None,
            )
            base, ext = os.path.splitext(video_path)
            safe_title = "".join(c for c in info["title"] if c.isalnum() or c in " _-")[:40].strip() or "klip"

            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, clip in enumerate(valid_clips, start=1):
                    status.text(f"Memotong klip {i}/{len(valid_clips)}...")
                    cut_video = f"{base}_clip{i}{ext}"
                    ok, err = trim_local(video_path, cut_video, clip["start"], clip["end"], precise=precise)
                    if not ok:
                        st.error(f"Gagal motong klip {i}: {err[-300:]}")
                        continue
                    label = f"{safe_title}_klip{i}_{format_hms(clip['start']).replace(':', '-')}"
                    zf.write(cut_video, arcname=f"{label}{ext}")

                    if sub_path:
                        cut_sub = f"{base}_clip{i}.srt"
                        n = trim_srt_file(sub_path, cut_sub, clip["start"], clip["end"])
                        if n > 0:
                            zf.write(cut_sub, arcname=f"{label}.srt")

                if keep_full:
                    zf.write(video_path, arcname=os.path.basename(video_path))

            zip_buf.seek(0)
            zip_bytes = zip_buf.read()
            progress_bar.progress(1.0)
            status.text("Selesai, memulai download otomatis...")

            zip_name = f"{safe_title}.zip"
            b64 = base64.b64encode(zip_bytes).decode()
            st.html(
                f'<a id="autodl" href="data:application/zip;base64,{b64}" '
                f'download="{zip_name}"></a>'
                f'<script>document.getElementById("autodl").click();</script>',
                unsafe_allow_javascript=True,
            )
            st.success(f"Selesai! {len(valid_clips)} klip di-zip ({zip_name}) - "
                       f"download seharusnya langsung mulai otomatis di browser.")
            with open(os.path.join(workdir, zip_name), "wb") as f:
                f.write(zip_bytes)
            with open(os.path.join(workdir, zip_name), "rb") as f:
                st.download_button("⬇️ Kalau download otomatis gak jalan, klik ini",
                                    f, file_name=zip_name, use_container_width=True)

        except Exception as e:
            st.error(f"Gagal: {e}")
        # sengaja gak hapus workdir - file klip masih dibaca dari situ kalau
        # tombol fallback manual di atas dipakai