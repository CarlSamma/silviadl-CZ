import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import json
import threading
import os
import re
import shlex


class SharePointDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SharePoint / Stream Video Downloader")
        self.root.geometry("1000x750")

        # Variables
        self.url_var = tk.StringVar()
        self.cookies_var = tk.StringVar(value="cookies.txt")
        self.output_name_var = tk.StringVar(value="video_download")
        self.audio_only_var = tk.BooleanVar(value=False)
        self.separate_merge_var = tk.BooleanVar(value=False)
        self.video_id_var = tk.StringVar(value="")
        self.audio_id_var = tk.StringVar(value="")
        self.formats = []
        self.download_thread = None
        self.downloadable_only = False
        self.download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download")
        os.makedirs(self.download_dir, exist_ok=True)

        self.build_ui()

    def build_ui(self):
        # --- URL & Cookies ---
        url_frame = ttk.LabelFrame(self.root, text="URL & Cookies", padding=10)
        url_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(url_frame, text="Video URL:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(url_frame, textvariable=self.url_var, width=90).grid(row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(url_frame, text="Get Formats", command=self.thread_fetch_formats).grid(row=0, column=2)

        ttk.Label(url_frame, text="Cookies:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(url_frame, textvariable=self.cookies_var, width=60).grid(row=1, column=1, sticky=tk.EW, padx=5)
        ttk.Button(url_frame, text="Browse", command=self.browse_cookies).grid(row=1, column=2)

        url_frame.columnconfigure(1, weight=1)

        # --- Options ---
        opt_frame = ttk.LabelFrame(self.root, text="Download Options", padding=10)
        opt_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Checkbutton(opt_frame, text="Audio only (extract MP3)",
                        variable=self.audio_only_var,
                        command=self.on_audio_only_toggle).grid(row=0, column=0, sticky=tk.W)

        ttk.Checkbutton(opt_frame, text="Download separate streams, then merge with FFmpeg",
                        variable=self.separate_merge_var).grid(row=0, column=1, sticky=tk.W, padx=20)

        ttk.Label(opt_frame, text="Output name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(opt_frame, textvariable=self.output_name_var, width=40).grid(row=1, column=1, sticky=tk.W, padx=5)
        ttk.Label(opt_frame, text="(without extension)").grid(row=1, column=2, sticky=tk.W)

        # --- Formats List ---
        fmt_frame = ttk.LabelFrame(self.root, text="Available Formats (click to select)", padding=10)
        fmt_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        cols = ("ID", "Type", "Ext", "Resolution", "FPS", "Size", "Proto", "VCodec", "ACodec")
        self.tree = ttk.Treeview(fmt_frame, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=90, anchor=tk.CENTER)
        self.tree.column("ID", width=160)
        self.tree.column("Resolution", width=120)

        vsb = ttk.Scrollbar(fmt_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(fmt_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)
        fmt_frame.rowconfigure(0, weight=1)
        fmt_frame.columnconfigure(0, weight=1)

        # --- Selection Controls ---
        sel_frame = ttk.Frame(fmt_frame)
        sel_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=5)

        ttk.Button(sel_frame, text="Set as VIDEO", command=self.set_video).grid(row=0, column=0, padx=5)
        ttk.Button(sel_frame, text="Set as AUDIO", command=self.set_audio).grid(row=0, column=1, padx=5)
        ttk.Button(sel_frame, text="Auto Select Best", command=self.auto_select).grid(row=0, column=2, padx=5)
        ttk.Button(sel_frame, text="Refresh Formats", command=self.thread_fetch_formats).grid(row=0, column=3, padx=5)
        self.filter_btn = ttk.Button(sel_frame, text="Filter Downloadable", command=self.toggle_downloadable_filter)
        self.filter_btn.grid(row=0, column=4, padx=5)

        self.sort_smallest_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(sel_frame, text="Sort by smallest", variable=self.sort_smallest_var,
                        command=self.on_sort_toggle).grid(row=0, column=5, padx=5)

        style = ttk.Style()
        style.configure("Fastest.TButton", font=("Segoe UI", 10, "bold"), background="#00AA00")
        ttk.Button(sel_frame, text="⚡⚡⚡ FASTEST AUDIO ⚡⚡⚡", command=self.fastest_audio_only,
                   style="Fastest.TButton").grid(row=0, column=6, padx=5, ipady=3)

        self.lbl_sel = ttk.Label(sel_frame, text="Video: [auto] | Audio: [auto]", font=("Segoe UI", 9, "bold"))
        self.lbl_sel.grid(row=0, column=7, padx=20)

        # --- Action & Progress ---
        act_frame = ttk.Frame(self.root)
        act_frame.pack(fill=tk.X, padx=10, pady=5)

        self.btn_download = ttk.Button(act_frame, text="START DOWNLOAD", command=self.thread_download)
        self.btn_download.pack(side=tk.LEFT, padx=5)

        ttk.Button(act_frame, text="Open Output Folder", command=self.open_folder).pack(side=tk.LEFT, padx=5)

        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, mode='determinate', maximum=100)
        self.progress.pack(fill=tk.X, padx=10, pady=5)

        # --- Log ---
        log_frame = ttk.LabelFrame(self.root, text="Log / yt-dlp Output", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = tk.Text(log_frame, height=10, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(fill=tk.Y, side=tk.RIGHT)
        self.log_text.config(yscrollcommand=log_scroll.set)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def browse_cookies(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self.cookies_var.set(path)

    def log(self, msg):
        self.root.after(0, lambda: (self.log_text.insert(tk.END, msg + "\n"),
                                    self.log_text.see(tk.END)))

    def update_progress(self, value):
        self.root.after(0, lambda: self.progress.configure(value=value))

    def on_audio_only_toggle(self):
        if self.audio_only_var.get():
            self.lbl_sel.config(text="MODE: Audio only")

    def on_sort_toggle(self):
        self.populate_formats()

    def get_base_cmd(self):
        url = self.url_var.get().strip()
        cookies = self.cookies_var.get()
        if not url:
            messagebox.showerror("Error", "Inserisci l'URL del video.")
            return None
        if not os.path.exists(cookies):
            messagebox.showerror("Error", f"File cookies non trovato:\n{cookies}")
            return None

        cmd = [
            "yt-dlp",
            "--no-warnings",
            "--cookies", os.path.abspath(cookies),
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "--referer", url
        ]
        return cmd, url

    # ------------------------------------------------------------------
    # Fetch Formats
    # ------------------------------------------------------------------
    def thread_fetch_formats(self):
        t = threading.Thread(target=self.fetch_formats, daemon=True)
        t.start()

    def fetch_formats(self):
        res = self.get_base_cmd()
        if not res:
            return
        cmd, url = res
        cmd.extend(["-J", url])

        self.log("Fetching format list... please wait.")
        self.root.after(0, lambda: self.tree.delete(*self.tree.get_children()))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode != 0:
                self.log(f"yt-dlp ERROR:\n{result.stderr}")
                return

            data = json.loads(result.stdout)
            self.formats = data.get("formats", [])

            if not self.formats:
                self.log("No formats found. Check URL / cookies.")
                return

            self.log(f"Loaded {len(self.formats)} formats.")
            self.populate_formats()
            self.auto_select()

        except Exception as e:
            self.log(f"Exception during fetch: {e}")

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def populate_formats(self):
        self.root.after(0, lambda: self.tree.delete(*self.tree.get_children()))
        
        # Collect audio formats for finding smallest
        audio_formats = []
        for f in self.formats:
            if self.downloadable_only and not self.is_downloadable_format(f):
                continue
            acodec = f.get("acodec", "none")
            if acodec not in (None, "none") and f.get("ext") in ("m4a", "mp3", "webm", "ogg"):
                size = f.get("filesize") or f.get("filesize_approx") or float('inf')
                audio_formats.append((size, f.get("format_id")))
        
        # Sort audio by size if enabled
        if self.sort_smallest_var.get() and audio_formats:
            audio_formats.sort(key=lambda x: x[0])
            smallest_id = audio_formats[0][1]
        else:
            smallest_id = None
        
        # Populate tree
        for f in self.formats:
            if self.downloadable_only and not self.is_downloadable_format(f):
                continue

            fid = f.get("format_id", "N/A")
            ext = f.get("ext", "N/A")
            resol = f.get("resolution", "N/A")
            fps = f.get("fps", "N/A") if f.get("fps") else "N/A"
            size = f.get("filesize") or f.get("filesize_approx") or "N/A"
            proto = f.get("protocol", "N/A")
            vcodec = f.get("vcodec", "none")
            acodec = f.get("acodec", "none")

            if vcodec not in (None, "none") and acodec not in (None, "none"):
                typ = "both"
            elif vcodec not in (None, "none"):
                typ = "video"
            elif acodec not in (None, "none"):
                typ = "audio"
            else:
                typ = "unknown"

            def insert_row(_fid=fid, _ext=ext, _typ=typ, _res=resol, _fps=fps, _sz=size, _pr=proto, _vc=vcodec, _ac=acodec):
                item = self.tree.insert("", tk.END, values=(_fid, _typ, _ext, _res, _fps, _sz, _pr, _vc, _ac))
                # Highlight smallest audio in green
                if smallest_id and _fid == smallest_id and _typ == "audio":
                    self.tree.item(item, tags=("fastest",))
                    self.tree.tag_configure("fastest", background="#90EE90")
            self.root.after(0, insert_row)

    def toggle_downloadable_filter(self):
        self.downloadable_only = not self.downloadable_only
        label = "Show All Formats" if self.downloadable_only else "Filter Downloadable"
        self.filter_btn.config(text=label)
        self.log("Filtering downloadable-only formats." if self.downloadable_only else "Showing all formats.")
        self.populate_formats()

    def is_downloadable_format(self, f):
        fid = str(f.get("format_id", "")).lower()
        proto = str(f.get("protocol", "")).lower()
        vcodec = f.get("vcodec")
        acodec = f.get("acodec")

        if fid.startswith("hls-group") or fid.startswith("hls-vnex-group"):
            return False
        if fid.startswith("dash-") and "group" in fid:
            return False

        if vcodec in (None, "none") and acodec in (None, "none"):
            return False

        if "unknown" in str(f.get("format_note", "")).lower():
            return False

        # Keep direct audio/video streams and combined streams.
        return True

    def set_video(self):
        sel = self.tree.selection()
        if not sel:
            return
        fid = self.tree.item(sel[0])["values"][0]
        self.video_id_var.set(fid)
        self.lbl_sel.config(text=f"Video: {fid} | Audio: {self.audio_id_var.get() or '[none]'}")
        self.log(f"Selected VIDEO format: {fid}")

    def set_audio(self):
        sel = self.tree.selection()
        if not sel:
            return
        fid = self.tree.item(sel[0])["values"][0]
        self.audio_id_var.set(fid)
        self.lbl_sel.config(text=f"Video: {self.video_id_var.get() or '[none]'} | Audio: {fid}")
        self.log(f"Selected AUDIO format: {fid}")

    def auto_select(self):
        self.video_id_var.set("bestvideo")
        self.audio_id_var.set("bestaudio")
        self.lbl_sel.config(text="Auto: bestvideo + bestaudio (yt-dlp default)")

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    def thread_download(self):
        if self.download_thread and self.download_thread.is_alive():
            messagebox.showwarning("Attendi", "Un download è già in corso.")
            return
        self.download_thread = threading.Thread(target=self.download, daemon=True)
        self.download_thread.start()

    def download(self):
        res = self.get_base_cmd()
        if not res:
            return
        cmd, url = res
        out_name = self.output_name_var.get().strip() or "download"

        if self.audio_only_var.get():
            aid = self.audio_id_var.get() or "bestaudio"
            cmd.extend([
                "-f", aid,
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "-o", os.path.join(self.download_dir, f"{out_name}.%(ext)s"),
                url
            ])
            self.run_ytdlp(cmd, "Downloading audio only...")
            return

        if self.separate_merge_var.get():
            vid = self.video_id_var.get() or "bestvideo"
            aid = self.audio_id_var.get() or "bestaudio"

            v_cmd = cmd.copy()
            v_cmd.extend(["-f", vid, "-o", os.path.join(self.download_dir, f"{out_name}_video.%(ext)s"), url])
            self.log("=" * 50)
            self.log("STEP 1/3: Downloading VIDEO stream")
            rc = self.run_ytdlp(v_cmd, "Video stream download...")
            if rc != 0:
                self.log("ABORT: video download failed.")
                return

            a_cmd = cmd.copy()
            a_cmd.extend(["-f", aid, "-o", os.path.join(self.download_dir, f"{out_name}_audio.%(ext)s"), url])
            self.log("=" * 50)
            self.log("STEP 2/3: Downloading AUDIO stream")
            rc = self.run_ytdlp(a_cmd, "Audio stream download...")
            if rc != 0:
                self.log("ABORT: audio download failed.")
                return

            self.log("=" * 50)
            self.log("STEP 3/3: Merging with FFmpeg")
            v_file = None
            a_file = None
            for f in os.listdir(self.download_dir):
                if f.startswith(f"{out_name}_video") and not f.endswith(".part"):
                    v_file = os.path.join(self.download_dir, f)
                if f.startswith(f"{out_name}_audio") and not f.endswith(".part"):
                    a_file = os.path.join(self.download_dir, f)

            if not v_file or not a_file:
                self.log("ERROR: cannot locate downloaded streams.")
                return

            out_mp4 = os.path.join(self.download_dir, f"{out_name}.mp4")
            ffm_cmd = [
                "ffmpeg", "-y",
                "-i", v_file,
                "-i", a_file,
                "-c", "copy",
                "-movflags", "+faststart",
                out_mp4
            ]
            try:
                proc = subprocess.run(ffm_cmd, capture_output=True, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
                if proc.returncode == 0:
                    self.log(f"SUCCESS: merged -> {out_mp4}")
                    try:
                        os.remove(v_file)
                        os.remove(a_file)
                        self.log("Cleaned temporary video/audio files.")
                    except Exception as e:
                        self.log(f"Cleanup warning: {e}")
                else:
                    self.log(f"FFmpeg ERROR:\n{proc.stderr}")
            except Exception as e:
                self.log(f"FFmpeg exception: {e}")
            return

        if self.video_id_var.get() and self.audio_id_var.get() and not self.video_id_var.get().startswith("best"):
            fmt_spec = f"{self.video_id_var.get()}+{self.audio_id_var.get()}"
        else:
            fmt_spec = "bv*+ba/b"

        cmd.extend([
            "-f", fmt_spec,
            "--merge-output-format", "mp4",
            "-o", os.path.join(self.download_dir, f"{out_name}.%(ext)s"),
            url
        ])
        self.run_ytdlp(cmd, "Downloading & merging with yt-dlp...")

    def run_ytdlp(self, cmd, status_msg):
        self.log("-" * 50)
        self.log(status_msg)
        self.log("CMD: " + " ".join(shlex.quote(c) for c in cmd))
        self.update_progress(0)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            percent_pattern = re.compile(r'\[download\]\s+(\d+\.?\d*)%')
            for line in process.stdout:
                line = line.rstrip()
                self.log(line)

                m = percent_pattern.search(line)
                if m:
                    self.update_progress(float(m.group(1)))

            process.wait()
            self.update_progress(100)
            self.log(f"Exit code: {process.returncode}")
            return process.returncode

        except Exception as e:
            self.log(f"Process error: {e}")
            return -1

    def fastest_audio_only(self):
        """Find smallest audio format and download it directly as MP3."""
        audio_formats = []
        for f in self.formats:
            acodec = f.get("acodec", "none")
            if acodec not in (None, "none") and f.get("ext") in ("m4a", "mp3", "webm", "ogg"):
                size = f.get("filesize") or f.get("filesize_approx") or float('inf')
                audio_formats.append((size, f.get("format_id"), f.get("ext")))

        if not audio_formats:
            self.log("No audio formats found!")
            return

        audio_formats.sort(key=lambda x: x[0])
        best_size, best_id, best_ext = audio_formats[0]
        self.log(f"⚡ FASTEST: {best_id} ({best_ext}) - {best_size/1024/1024:.1f}MB")

        res = self.get_base_cmd()
        if not res:
            return
        cmd, url = res
        out_name = self.output_name_var.get().strip() or "fastest_audio"

        cmd.extend([
            "-f", best_id,
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", os.path.join(self.download_dir, f"{out_name}.%(ext)s"),
            url
        ])
        self.run_ytdlp(cmd, f"⚡ Downloading fastest audio: {best_id}")

    def open_folder(self):
        os.startfile(self.download_dir)


if __name__ == "__main__":
    root = tk.Tk()
    app = SharePointDownloaderGUI(root)
    root.mainloop()
