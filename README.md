# YouTube Clip Downloader

Web app buat preview video YouTube, pilih rentang waktu pakai slider,
lalu download + potong otomatis (video & subtitle sekaligus).

## Cara pakai

1. Install dependency:
   ```
   pip install -r requirements.txt
   ```
2. Pastikan **ffmpeg** udah terpasang & kebaca (`ffmpeg -version` harus jalan).
3. Jalankan:
   ```
   streamlit run app.py
   ```
4. Browser bakal kebuka otomatis ke `http://localhost:8501`.

## Alur pakai di app

1. Paste URL video YouTube, klik **Muat Video**.
2. Timeline preview (player YouTube asli) muncul - bebas di-scrub buat
   cari momen yang pas.
3. Centang **"Potong ke rentang waktu tertentu"**, geser slider buat
   pilih start-end. Preview otomatis loncat ke titik start yang dipilih
   tiap slider digeser.
4. Atur kualitas, audio-only, potongan presisi (frame-exact vs cepat),
   dan subtitle sesuai kebutuhan.
5. Klik **Download & Potong** - progress bar asli muncul selama proses
   download, diikuti proses potong lokal (cepat, gak butuh internet lagi).
6. Tombol download video (dan subtitle .srt kalau ada) muncul setelah
   selesai.

## Struktur file

- `app.py` - UI Streamlit
- `downloader.py` - logika inti yt-dlp + ffmpeg (download penuh -> potong lokal)
- `subtitles.py` - parsing & pemotongan file subtitle SRT biar timing-nya
  ikut nyesuain sama klip hasil potongan
- `.streamlit/config.toml` - tema

## Catatan

Video selalu didownload penuh dulu (bukan streaming-cut langsung), baru
dipotong lokal - ini pilihan desain yang disengaja demi keandalan
(auto-retry, progress bar akurat, gak gantung ke stabilitas koneksi
pas proses potong). Konsekuensinya: buat video yang sangat panjang,
tetap perlu bandwidth buat download videonya secara utuh meski cuma
mau ambil klip pendek.
