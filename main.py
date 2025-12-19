"""
Spotify Downloader - A modern, smooth GUI application for downloading Spotify songs and playlists
Uses spotdl as the backend for downloading with full metadata support

First run will automatically:
1. Check Python version and warn if unstable
2. Install FFmpeg (Windows only, via winget)
3. Install all requirements from requirements.txt
4. Install the latest spotdl version
"""

import subprocess
import sys
import os
import re
import psutil

# Constants
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
RECOMMENDED_PYTHON = "3.11"

def get_optimal_workers():
    """Calculate optimal worker count based on system specs"""
    try:
        cpu_count = os.cpu_count() or 4
        ram_gb = psutil.virtual_memory().total / (1024**3)
        
        # Base on CPU cores (use half to avoid overload)
        cpu_based = max(2, cpu_count // 2)
        
        # Limit based on RAM (1 worker per 2GB RAM, min 2)
        ram_based = max(2, int(ram_gb / 2))
        
        # Take the minimum of both, cap at 8
        optimal = min(cpu_based, ram_based, 8)
        
        return optimal
    except Exception:
        return 4  # Safe default

def first_run_setup():
    """Run setup checks and installations before importing other modules"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Check Python version
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print()
    print("=" * 60)
    print("  Spotify Downloader - Setup")
    print("=" * 60)
    print(f"  [*] Python Version: {version_str}")
    
    if version >= (3, 14):
        print()
        print("  [!] WARNING: Unstable Python version detected!")
        print(f"      Python {version_str} is a pre-release/unstable version.")
        print("      Some features may not work correctly.")
        print()
        print(f"      RECOMMENDED: Downgrade to Python {RECOMMENDED_PYTHON}")
        print(f"      Download: https://www.python.org/downloads/release/python-3119/")
        print()
        print("      Continuing anyway... (issues may occur)")
    elif version < (3, 9):
        print()
        print(f"  [-] ERROR: Python {version_str} is too old!")
        print("      Minimum required: Python 3.9")
        print("      Download: https://www.python.org/downloads/")
        print("=" * 60)
        input("Press Enter to exit...")
        sys.exit(1)
    else:
        print("  [+] Python version OK")
    
    # 2. Check and install FFmpeg
    print()
    print("  [*] Checking FFmpeg...")
    ffmpeg_ok = False
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        ffmpeg_ok = result.returncode == 0
    except FileNotFoundError:
        pass
    
    if not ffmpeg_ok:
        print("  [*] FFmpeg not found. Installing...")
        if sys.platform == "win32":
            # Try winget first (Windows 10/11)
            try:
                result = subprocess.run(
                    ["winget", "install", "ffmpeg", "--accept-source-agreements", "--accept-package-agreements"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    print("  [+] FFmpeg installed via winget")
                    print("  [!] Please RESTART your terminal/IDE for FFmpeg to be available!")
                    input("      Press Enter after restarting your terminal...")
                else:
                    raise Exception("winget failed")
            except Exception:
                print("  [-] Could not auto-install FFmpeg.")
                print()
                print("      Please install manually:")
                print("      1. Download from: https://www.gyan.dev/ffmpeg/builds/")
                print("         (Get 'ffmpeg-release-essentials.zip')")
                print("      2. Extract to C:\\ffmpeg")
                print("      3. Add C:\\ffmpeg\\bin to your PATH")
                print()
                print("      Or run in cmd: winget install ffmpeg")
                print("=" * 60)
                input("Press Enter to exit...")
                sys.exit(1)
        else:
            print("  [-] FFmpeg not found.")
            print("      Please install FFmpeg:")
            print("      - macOS: brew install ffmpeg")
            print("      - Linux: sudo apt install ffmpeg")
            print("=" * 60)
            input("Press Enter to exit...")
            sys.exit(1)
    else:
        print("  [+] FFmpeg OK")
    
    # 3. Install requirements.txt
    print()
    print("  [*] Installing dependencies...")
    requirements_path = os.path.join(script_dir, "requirements.txt")
    if os.path.exists(requirements_path):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", requirements_path, "-q"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("  [+] Dependencies installed")
        else:
            print("  [!] Some dependencies may have failed to install")
    else:
        print("  [!] requirements.txt not found, installing core packages...")
        subprocess.run([sys.executable, "-m", "pip", "install", "customtkinter", "spotipy", "-q"])
        print("  [+] Core packages installed")
    
    # 4. Install latest spotdl
    print()
    print("  [*] Installing/updating spotdl...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "spotdl", "-q"],
        capture_output=True,
        text=True
    )
    
    # Check what version got installed
    try:
        ver_result = subprocess.run(
            [sys.executable, "-m", "spotdl", "--version"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        version_match = re.search(r'(\d+\.\d+\.\d+)', ver_result.stdout + ver_result.stderr)
        if version_match:
            spotdl_ver = version_match.group(1)
            print(f"  [+] spotdl {spotdl_ver} installed")
            
            # Warn if old version due to Python compatibility
            if spotdl_ver.startswith("3."):
                print()
                print("  [!] Note: spotdl v3.x installed (v4 requires Python <3.14)")
                print("      Some features may be limited. Downgrade Python to use v4.")
    except Exception:
        print("  [+] spotdl installed")
    
    print()
    print("=" * 60)
    print("  [+] Setup complete! Starting application...")
    print("=" * 60)
    print()


# Run setup before importing heavy modules
first_run_setup()

# Now import the rest
import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import queue
import json
import webbrowser
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import spotipy
    from spotipy.oauth2 import SpotifyPKCE
    SPOTIPY_AVAILABLE = True
except ImportError:
    SPOTIPY_AVAILABLE = False

# Modern Spotify-inspired color scheme
COLORS = {
    "bg_dark": "#0a0a0a",
    "bg_card": "#121212",
    "bg_card_hover": "#1a1a1a",
    "bg_input": "#1e1e1e",
    "accent": "#1DB954",
    "accent_hover": "#1ed760",
    "accent_dim": "#169c46",
    "text": "#ffffff",
    "text_dim": "#a7a7a7",
    "text_muted": "#6a6a6a",
    "red": "#e91429",
    "red_hover": "#f53b4c",
    "border": "#282828",
    "border_light": "#3e3e3e",
    "gradient_start": "#1DB954",
    "gradient_end": "#191414"
}

ctk.set_appearance_mode("dark")


class SpotifyDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("Spotify Downloader")
        self.geometry("900x700")
        self.minsize(800, 600)
        self.configure(fg_color=COLORS["bg_dark"])
        
        # Variables
        self.output_folder = ctk.StringVar(value=os.path.join(os.path.expanduser("~"), "Music", "SpotifyDownloads"))
        self.audio_format = ctk.StringVar(value="mp3")
        self.worker_count = ctk.IntVar(value=get_optimal_workers())
        self.is_downloading = False
        self.log_queue = queue.Queue()
        
        # Spotify Auth
        self.spotify_client = None
        self.spotify_auth = None
        self.user_info = None
        self.client_id = None
        self.config_dir = os.path.join(os.path.expanduser("~"), ".spotdl")
        self.config_path = os.path.join(self.config_dir, "app_config.json")
        self.cache_path = os.path.join(self.config_dir, ".spotify_cache")
        
        # Create directories
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.output_folder.get(), exist_ok=True)
        
        # Build UI
        self.create_ui()
        
        # Load saved config and try auto-login
        self.after(100, self.auto_login)
        
        # Start log consumer
        self.after(100, self.process_log_queue)
    
    def create_ui(self):
        # Main scrollable container
        self.main_frame = ctk.CTkScrollableFrame(
            self, 
            fg_color="transparent",
            scrollbar_button_color=COLORS["bg_input"],
            scrollbar_button_hover_color=COLORS["accent"]
        )
        self.main_frame.pack(fill="both", expand=True, padx=30, pady=20)
        
        self.create_header()
        self.create_account_card()
        self.create_download_card()
        self.create_settings_card()
        self.create_progress_card()
    
    def create_header(self):
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 30))
        
        # Logo and title row
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")
        
        # Spotify-style logo circle
        logo_frame = ctk.CTkFrame(
            title_frame,
            width=56,
            height=56,
            corner_radius=28,
            fg_color=COLORS["accent"]
        )
        logo_frame.pack(side="left", padx=(0, 16))
        logo_frame.pack_propagate(False)
        
        ctk.CTkLabel(
            logo_frame,
            text="♫",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#000000"
        ).place(relx=0.5, rely=0.5, anchor="center")
        
        text_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        text_frame.pack(side="left")
        
        ctk.CTkLabel(
            text_frame,
            text="Spotify Downloader",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            text_frame,
            text="Download songs & playlists with full metadata",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text_dim"]
        ).pack(anchor="w", pady=(2, 0))
        
        # Version badge
        version_badge = ctk.CTkFrame(
            header,
            fg_color=COLORS["bg_input"],
            corner_radius=12
        )
        version_badge.pack(side="right")
        
        ctk.CTkLabel(
            version_badge,
            text="v1.2.0",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"]
        ).pack(padx=12, pady=6)
    
    def create_card(self, parent, title=None, icon=None):
        """Create a styled card container with optional icon"""
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["bg_card"],
            corner_radius=16,
            border_width=0
        )
        card.pack(fill="x", pady=(0, 16))
        
        if title:
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=24, pady=(20, 14))
            
            # Title with optional icon
            title_container = ctk.CTkFrame(header, fg_color="transparent")
            title_container.pack(side="left")
            
            if icon:
                ctk.CTkLabel(
                    title_container,
                    text=icon,
                    font=ctk.CTkFont(size=18),
                    text_color=COLORS["accent"]
                ).pack(side="left", padx=(0, 10))
            
            ctk.CTkLabel(
                title_container,
                text=title,
                font=ctk.CTkFont(size=17, weight="bold"),
                text_color=COLORS["text"]
            ).pack(side="left")
            
            return card, header
        
        return card
    
    def create_account_card(self):
        card, header = self.create_card(self.main_frame, "Spotify Account", "🎧")
        
        # Status label in header
        status_text = "spotipy not installed" if not SPOTIPY_AVAILABLE else "Not connected"
        self.account_status = ctk.CTkLabel(
            header,
            text=status_text,
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"]
        )
        self.account_status.pack(side="right")
        
        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 18))
        
        # Disable login button if spotipy is not available
        login_state = "normal" if SPOTIPY_AVAILABLE else "disabled"
        self.login_btn = ctk.CTkButton(
            btn_frame,
            text="🔑  Connect Spotify",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            corner_radius=8,
            fg_color=COLORS["accent"] if SPOTIPY_AVAILABLE else COLORS["bg_input"],
            hover_color=COLORS["accent_hover"],
            command=self.show_login_dialog,
            state=login_state
        )
        self.login_btn.pack(side="left", padx=(0, 10))
        
        self.liked_btn = ctk.CTkButton(
            btn_frame,
            text="❤️  Download Liked Songs",
            font=ctk.CTkFont(size=14),
            height=42,
            corner_radius=8,
            fg_color=COLORS["red"],
            hover_color=COLORS["red_hover"],
            command=self.download_liked_songs,
            state="disabled"
        )
        self.liked_btn.pack(side="left", padx=(0, 10))
        
        self.logout_btn = ctk.CTkButton(
            btn_frame,
            text="Logout",
            font=ctk.CTkFont(size=13),
            height=42,
            width=80,
            corner_radius=8,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            command=self.logout,
            state="disabled"
        )
        self.logout_btn.pack(side="left")
    
    def create_download_card(self):
        card, _ = self.create_card(self.main_frame, "Download from URL", "🔗")
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=(0, 18))
        
        ctk.CTkLabel(
            content,
            text="Paste a Spotify track, album, or playlist URL",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"]
        ).pack(anchor="w", pady=(0, 8))
        
        # URL input row
        input_row = ctk.CTkFrame(content, fg_color="transparent")
        input_row.pack(fill="x")
        
        self.url_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="https://open.spotify.com/track/... or playlist/... or album/...",
            height=45,
            corner_radius=8,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(size=14)
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.download_btn = ctk.CTkButton(
            input_row,
            text="⬇️  Download",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=45,
            width=140,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.start_url_download
        )
        self.download_btn.pack(side="left")
    
    def create_settings_card(self):
        card, _ = self.create_card(self.main_frame, "Settings", "⚙️")
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=(0, 18))
        
        # Output folder row
        folder_row = ctk.CTkFrame(content, fg_color="transparent")
        folder_row.pack(fill="x", pady=(0, 12))
        
        ctk.CTkLabel(
            folder_row,
            text="Output Folder",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"],
            width=100
        ).pack(side="left")
        
        self.folder_entry = ctk.CTkEntry(
            folder_row,
            textvariable=self.output_folder,
            height=38,
            corner_radius=8,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(size=13)
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(
            folder_row,
            text="Browse",
            height=38,
            width=80,
            corner_radius=8,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            command=self.browse_folder
        ).pack(side="left")
        
        # Format row
        format_row = ctk.CTkFrame(content, fg_color="transparent")
        format_row.pack(fill="x")
        
        ctk.CTkLabel(
            format_row,
            text="Audio Format",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"],
            width=100
        ).pack(side="left")
        
        formats_frame = ctk.CTkFrame(format_row, fg_color="transparent")
        formats_frame.pack(side="left")
        
        for fmt in ["mp3", "flac", "ogg", "opus", "m4a"]:
            ctk.CTkRadioButton(
                formats_frame,
                text=fmt.upper(),
                variable=self.audio_format,
                value=fmt,
                font=ctk.CTkFont(size=13),
                fg_color=COLORS["accent"],
                hover_color=COLORS["accent_hover"],
                border_color=COLORS["border"]
            ).pack(side="left", padx=(0, 20))
        
        # Worker count row
        worker_row = ctk.CTkFrame(content, fg_color="transparent")
        worker_row.pack(fill="x", pady=(12, 0))
        
        ctk.CTkLabel(
            worker_row,
            text="Workers",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"],
            width=100
        ).pack(side="left")
        
        worker_frame = ctk.CTkFrame(worker_row, fg_color="transparent")
        worker_frame.pack(side="left", fill="x", expand=True)
        
        self.worker_slider = ctk.CTkSlider(
            worker_frame,
            from_=1,
            to=8,
            number_of_steps=7,
            variable=self.worker_count,
            width=200,
            height=18,
            fg_color=COLORS["bg_input"],
            progress_color=COLORS["accent"],
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
            command=self.update_worker_label
        )
        self.worker_slider.pack(side="left", padx=(0, 10))
        
        self.worker_label = ctk.CTkLabel(
            worker_frame,
            text=f"{self.worker_count.get()} threads",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text"],
            width=80
        )
        self.worker_label.pack(side="left")
        
        # Auto-detect button
        ctk.CTkButton(
            worker_frame,
            text="Auto",
            font=ctk.CTkFont(size=11),
            height=26,
            width=50,
            corner_radius=6,
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["border"],
            command=self.auto_detect_workers
        ).pack(side="left", padx=(10, 0))
        
        # System info label
        try:
            cpu_count = os.cpu_count() or 4
            ram_gb = psutil.virtual_memory().total / (1024**3)
            self.system_info_label = ctk.CTkLabel(
                worker_row,
                text=f"({cpu_count} cores, {ram_gb:.0f}GB RAM)",
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text_dim"]
            )
            self.system_info_label.pack(side="right")
        except Exception:
            pass
    
    def update_worker_label(self, value):
        self.worker_label.configure(text=f"{int(value)} threads")
    
    def auto_detect_workers(self):
        optimal = get_optimal_workers()
        self.worker_count.set(optimal)
        self.worker_label.configure(text=f"{optimal} threads")
    
    def create_progress_card(self):
        card, header = self.create_card(self.main_frame, "Progress", "📊")
        
        # Cancel button in header
        self.cancel_btn = ctk.CTkButton(
            header,
            text="Cancel",
            font=ctk.CTkFont(size=12),
            height=28,
            width=70,
            corner_radius=6,
            fg_color=COLORS["red"],
            hover_color=COLORS["red_hover"],
            command=self.cancel_download,
            state="disabled"
        )
        self.cancel_btn.pack(side="right")
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=20, pady=(0, 18))
        
        # Status
        self.status_label = ctk.CTkLabel(
            content,
            text="Ready",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_dim"]
        )
        self.status_label.pack(anchor="w", pady=(0, 8))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            content,
            height=8,
            corner_radius=4,
            fg_color=COLORS["bg_input"],
            progress_color=COLORS["accent"]
        )
        self.progress_bar.pack(fill="x", pady=(0, 15))
        self.progress_bar.set(0)
        
        # Log area
        ctk.CTkLabel(
            content,
            text="Download Log",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"]
        ).pack(anchor="w", pady=(0, 5))
        
        self.log_text = ctk.CTkTextbox(
            content,
            height=150,
            corner_radius=8,
            fg_color=COLORS["bg_input"],
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=COLORS["text_dim"]
        )
        self.log_text.pack(fill="x")
    
    # ==================== UTILITY METHODS ====================
    
    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_folder.get())
        if folder:
            self.output_folder.set(folder)
    
    def log(self, message, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"info": "•", "success": "✓", "error": "✗", "warning": "!"}.get(level, "•")
        self.log_queue.put(f"[{timestamp}] {prefix} {message}\n")
    
    def process_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.insert("end", message)
                self.log_text.see("end")
        except queue.Empty:
            pass
        self.after(100, self.process_log_queue)
    
    def set_status(self, text, color=None):
        self.status_label.configure(text=text, text_color=color or COLORS["text_dim"])
    
    def validate_url(self, url):
        pattern = r'https?://open\.spotify\.com/(track|album|playlist|artist)/[a-zA-Z0-9]+'
        return bool(re.match(pattern, url.split('?')[0]))
    
    def clean_url(self, url):
        return url.split('?')[0]
    
    # ==================== SPOTIFY AUTH ====================
    
    def auto_login(self):
        """Try to auto-login from saved config"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.client_id = config.get('client_id')
                    
                    if self.client_id and os.path.exists(self.cache_path):
                        # Try to use cached token
                        self.spotify_auth = SpotifyPKCE(
                            client_id=self.client_id,
                            redirect_uri=SPOTIFY_REDIRECT_URI,
                            scope="user-library-read playlist-read-private",
                            cache_path=self.cache_path,
                            open_browser=False
                        )
                        
                        token = self.spotify_auth.get_cached_token()
                        if token:
                            self.spotify_client = spotipy.Spotify(auth_manager=self.spotify_auth)
                            self.user_info = self.spotify_client.current_user()
                            self.update_account_ui()
                            self.log(f"Auto-logged in as {self.user_info.get('display_name', 'User')}", "success")
        except Exception as e:
            print(f"Auto-login failed: {e}")
    
    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump({'client_id': self.client_id}, f)
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    def show_login_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Connect Spotify")
        dialog.geometry("520x380")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Center
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 520) // 2
        y = self.winfo_y() + (self.winfo_height() - 380) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Content
        frame = ctk.CTkFrame(dialog, fg_color=COLORS["bg_card"], corner_radius=12)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            frame,
            text="🔑 Connect Your Spotify",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLORS["text"]
        ).pack(pady=(25, 15))
        
        ctk.CTkLabel(
            frame,
            text="1. Go to Spotify Developer Dashboard\n"
                 "2. Create a new app\n"
                 f"3. Add Redirect URI: {SPOTIFY_REDIRECT_URI}\n"
                 "4. Copy your Client ID below",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_dim"],
            justify="left"
        ).pack(pady=(0, 15))
        
        ctk.CTkButton(
            frame,
            text="Open Spotify Dashboard →",
            font=ctk.CTkFont(size=13),
            height=36,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=lambda: webbrowser.open("https://developer.spotify.com/dashboard")
        ).pack(pady=(0, 20))
        
        ctk.CTkLabel(
            frame,
            text="Client ID",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=25)
        
        id_entry = ctk.CTkEntry(
            frame,
            height=40,
            corner_radius=8,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(size=13),
            placeholder_text="Paste your Client ID here..."
        )
        id_entry.pack(fill="x", padx=25, pady=(5, 20))
        
        def do_connect():
            client_id = id_entry.get().strip()
            if not client_id:
                return
            
            self.client_id = client_id
            dialog.destroy()
            self.init_spotify_auth()
        
        ctk.CTkButton(
            frame,
            text="Connect",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            corner_radius=8,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=do_connect
        ).pack(fill="x", padx=25, pady=(0, 25))
    
    def init_spotify_auth(self):
        try:
            self.spotify_auth = SpotifyPKCE(
                client_id=self.client_id,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope="user-library-read playlist-read-private",
                cache_path=self.cache_path,
                open_browser=False
            )
            
            auth_url = self.spotify_auth.get_authorize_url()
            webbrowser.open(auth_url)
            self.show_callback_dialog()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to initialize auth: {e}")
    
    def show_callback_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Complete Login")
        dialog.geometry("520x280")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Center
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 520) // 2
        y = self.winfo_y() + (self.winfo_height() - 280) // 2
        dialog.geometry(f"+{x}+{y}")
        
        frame = ctk.CTkFrame(dialog, fg_color=COLORS["bg_card"], corner_radius=12)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            frame,
            text="Paste the URL from your browser after login",
            font=ctk.CTkFont(size=14),
            text_color=COLORS["text"]
        ).pack(pady=(25, 5))
        
        ctk.CTkLabel(
            frame,
            text="(starts with http://127.0.0.1:8888/callback?code=...)",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_dim"]
        ).pack(pady=(0, 15))
        
        url_entry = ctk.CTkEntry(
            frame,
            height=40,
            corner_radius=8,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(size=12),
            placeholder_text="Paste callback URL here..."
        )
        url_entry.pack(fill="x", padx=25, pady=(0, 15))
        
        def complete():
            callback_url = url_entry.get().strip()
            if not callback_url:
                return
            
            try:
                code = self.spotify_auth.parse_response_code(callback_url)
                self.spotify_auth.get_access_token(code)
                self.spotify_client = spotipy.Spotify(auth_manager=self.spotify_auth)
                self.user_info = self.spotify_client.current_user()
                self.save_config()
                dialog.destroy()
                self.update_account_ui()
                self.log(f"Logged in as {self.user_info.get('display_name', 'User')}", "success")
            except Exception as e:
                messagebox.showerror("Error", f"Login failed: {e}")
        
        ctk.CTkButton(
            frame,
            text="✓  Complete Login",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            corner_radius=10,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=complete
        ).pack(fill="x", padx=25, pady=(10, 25))
    
    def update_account_ui(self):
        if self.spotify_client and self.user_info:
            name = self.user_info.get('display_name', 'User')
            self.account_status.configure(text=f"✓ {name}", text_color=COLORS["accent"])
            self.login_btn.configure(state="disabled", fg_color=COLORS["bg_input"])
            self.liked_btn.configure(state="normal")
            self.logout_btn.configure(state="normal")
        else:
            self.account_status.configure(text="Not connected", text_color=COLORS["text_dim"])
            self.login_btn.configure(state="normal", fg_color=COLORS["accent"])
            self.liked_btn.configure(state="disabled")
            self.logout_btn.configure(state="disabled")
    
    def logout(self):
        self.spotify_client = None
        self.user_info = None
        self.spotify_auth = None
        
        # Remove cache
        for f in [self.cache_path, self.config_path]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError as e:
                    print(f"Failed to remove {f}: {e}")
        
        self.update_account_ui()
        self.log("Logged out", "info")
    
    # ==================== DOWNLOAD METHODS ====================
    
    def start_url_download(self):
        url = self.url_entry.get().strip()
        
        if not url:
            messagebox.showwarning("Warning", "Please enter a Spotify URL")
            return
        
        if not self.validate_url(url):
            messagebox.showerror("Error", "Invalid Spotify URL")
            return
        
        clean_url = self.clean_url(url)
        
        # For playlists/albums, use batch download (spotdl handles internally)
        if "/playlist/" in clean_url or "/album/" in clean_url:
            self.start_batch_download(clean_url)
        else:
            self.start_download([clean_url])
    
    def download_liked_songs(self):
        if not self.spotify_client:
            messagebox.showwarning("Warning", "Please connect Spotify first")
            return
        
        if self.is_downloading:
            return
        
        # Ask for limit
        dialog = ctk.CTkInputDialog(
            text="How many songs? (or 'all')",
            title="Liked Songs"
        )
        limit_input = dialog.get_input()
        
        if not limit_input:
            return
        
        try:
            limit = 9999 if limit_input.lower() == 'all' else int(limit_input)
        except ValueError:
            messagebox.showerror("Error", "Enter a valid number")
            return
        
        # Fetch liked songs in background
        self.set_downloading_state(True)
        self.set_status("Fetching liked songs...")
        
        threading.Thread(target=self.fetch_and_download_liked, args=(limit,), daemon=True).start()
    
    def fetch_and_download_liked(self, limit):
        try:
            songs = []
            offset = 0
            
            while len(songs) < limit:
                results = self.spotify_client.current_user_saved_tracks(limit=50, offset=offset)
                
                if not results['items']:
                    break
                
                for item in results['items']:
                    track = item['track']
                    songs.append(track['external_urls']['spotify'])
                    
                    if len(songs) >= limit:
                        break
                
                offset += 50
                self.after(0, lambda c=len(songs): self.set_status(f"Fetched {c} songs..."))
            
            if songs:
                self.log(f"Found {len(songs)} liked songs", "success")
                # Use batch download for liked songs (pass URLs as list)
                self.after(0, lambda s=songs: self.start_batch_download_urls(s))
            else:
                self.after(0, lambda: self.download_complete(False, "No liked songs found"))
                
        except Exception as e:
            self.after(0, lambda: self.download_complete(False, str(e)))
    
    def start_download(self, urls):
        self.set_downloading_state(True)
        self.progress_bar.set(0)
        self.log(f"Starting download of {len(urls)} song(s)...", "info")
        
        threading.Thread(target=self.download_worker, args=(urls,), daemon=True).start()
    
    def start_batch_download(self, url):
        """Download a playlist or album URL - let spotdl handle it as a batch"""
        self.set_downloading_state(True)
        self.progress_bar.set(0)
        
        url_type = "playlist" if "/playlist/" in url else "album"
        self.log(f"Downloading {url_type}...", "info")
        
        threading.Thread(target=self.batch_download_worker, args=([url],), daemon=True).start()
    
    def start_batch_download_urls(self, urls):
        """Download multiple URLs in a single spotdl process (for liked songs)"""
        self.set_downloading_state(True)
        self.progress_bar.set(0)
        self.log(f"Downloading {len(urls)} songs...", "info")
        
        threading.Thread(target=self.batch_download_worker, args=(urls,), daemon=True).start()
    
    def batch_download_worker(self, urls):
        """Worker for batch downloads - uses parallel processing with user-selected worker count"""
        try:
            output_folder = self.output_folder.get()
            audio_format = self.audio_format.get()
            total_urls = len(urls)
            max_workers = self.worker_count.get()
            
            # Detect spotdl version once
            try:
                ver_check = subprocess.run(
                    [sys.executable, "-m", "spotdl", "--version"],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                is_v4 = "4." in (ver_check.stdout + ver_check.stderr)
            except Exception:
                is_v4 = False
            
            env = os.environ.copy()
            env["NO_COLOR"] = "1"
            
            downloaded = 0
            skipped = 0
            errors = 0
            completed = 0
            lock = threading.Lock()
            
            def download_single(url):
                """Download a single URL and return result"""
                if not self.is_downloading:
                    return "cancelled", None
                
                if is_v4:
                    cmd = [
                        sys.executable, "-m", "spotdl",
                        "download", url,
                        "--output", os.path.join(output_folder, "{artist} - {title}.{output-ext}"),
                        "--format", audio_format,
                    ]
                else:
                    cmd = [
                        sys.executable, "-m", "spotdl",
                        url,
                        "--output", output_folder,
                        "--output-format", audio_format,
                        "--path-template", "{artist} - {title}.{ext}",
                    ]
                
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        env=env,
                        cwd=output_folder,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
                    
                    output = result.stdout + result.stderr
                    lower = output.lower()
                    
                    if "already downloaded" in lower or "skipping" in lower or ("oserror" in lower and "already downloaded" in lower):
                        return "skipped", None
                    elif "could not match" in lower or "lookuperror" in lower:
                        match = re.search(r'"([^"]+)"', output)
                        return "error", match.group(1) if match else "Unknown"
                    elif result.returncode == 0:
                        return "downloaded", None
                    else:
                        return "error", None
                except Exception:
                    return "error", None
            
            self.after(0, lambda w=max_workers: self.set_status(f"Downloading with {w} workers..."))
            
            # Use ThreadPoolExecutor for parallel downloads
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(download_single, url): url for url in urls}
                
                for future in as_completed(futures):
                    if not self.is_downloading:
                        executor.shutdown(wait=False, cancel_futures=True)
                        self.after(0, lambda: self.download_complete(False, "Cancelled"))
                        return
                    
                    result, info = future.result()
                    
                    with lock:
                        completed += 1
                        if result == "downloaded":
                            downloaded += 1
                        elif result == "skipped":
                            skipped += 1
                        elif result == "error":
                            errors += 1
                            if info:
                                self.log(f"Could not find: {info}", "warning")
                        
                        # Update progress
                        progress = completed / total_urls
                        d, s, e = downloaded, skipped, errors
                        self.after(0, lambda p=progress: self.progress_bar.set(p))
                        self.after(0, lambda c=completed, t=total_urls, d=d, s=s: 
                            self.set_status(f"Progress: {c}/{t} ({d} new, {s} existed)"))
            
            # Final message
            if downloaded > 0 or skipped > 0:
                if downloaded > 0 and skipped > 0:
                    msg = f"Done! {downloaded} downloaded, {skipped} already existed"
                elif downloaded > 0:
                    msg = f"Downloaded {downloaded} songs!"
                elif skipped > 0:
                    msg = f"All {skipped} songs already existed"
                else:
                    msg = "Download complete"
                if errors > 0:
                    msg += f" ({errors} failed)"
                self.after(0, lambda m=msg: self.download_complete(True, m))
            elif errors > 0:
                self.after(0, lambda e=errors: self.download_complete(False, f"{e} songs failed to download"))
            else:
                self.after(0, lambda: self.download_complete(False, "No songs found or downloaded"))
                
        except Exception as e:
            self.after(0, lambda: self.download_complete(False, str(e)))
    
    def download_single_song(self, url, output_template, audio_format, output_folder):
        """Download a single song - used by thread pool"""
        if not self.is_downloading:
            return None, None
        
        # Detect spotdl version and use appropriate syntax
        # v4.x: spotdl download <url> --output <template> --format <fmt>
        # v3.x: spotdl <url> --output <folder> --output-format <fmt> --path-template <template>
        try:
            ver_check = subprocess.run(
                [sys.executable, "-m", "spotdl", "--version"],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            is_v4 = "4." in (ver_check.stdout + ver_check.stderr)
        except Exception:
            is_v4 = False
        
        if is_v4:
            # spotdl v4.x syntax
            cmd = [
                sys.executable, "-m", "spotdl",
                "download", url,
                "--output", os.path.join(output_folder, "{artist} - {title}.{output-ext}"),
                "--format", audio_format,
            ]
        else:
            # spotdl v3.x syntax
            cmd = [
                sys.executable, "-m", "spotdl",
                url,
                "--output", output_folder,
                "--output-format", audio_format,
                "--path-template", "{artist} - {title}.{ext}",
            ]
        
        env = os.environ.copy()
        env["NO_COLOR"] = "1"
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                cwd=output_folder,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            output_lines = []
            for line in iter(process.stdout.readline, ''):
                if not self.is_downloading:
                    process.terminate()
                    return None, None
                output_lines.append(line)
            
            process.wait()
            
            # Parse output for song name
            result_msg = None
            for line in output_lines:
                clean = re.sub(r'\x1b\[[0-9;]*m', '', line)
                clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean).strip()
                if clean and len(clean) < 200:
                    lower = clean.lower()
                    if any(x in lower for x in ["downloaded", "skipping", "already exists", "error", "lookuperror"]):
                        result_msg = clean
                        break
            
            # Check if successful or skipped (both count as "done")
            success = process.returncode == 0
            skipped = result_msg and "skipping" in result_msg.lower()
            
            return success or skipped, result_msg
            
        except Exception as e:
            return False, str(e)
    
    def download_worker(self, urls):
        try:
            output_folder = self.output_folder.get()
            audio_format = self.audio_format.get()
            output_template = os.path.join(output_folder, "{artist} - {title}.{output-ext}")
            
            total = len(urls)
            completed = 0  # Downloaded + skipped
            skipped = 0
            processed = 0
            
            # Use 2 parallel threads to avoid file conflicts in spotdl-temp folder
            # spotdl v3.x has issues with parallel downloads sharing temp files
            max_workers = 2
            
            self.log(f"Downloading {total} songs...", "info")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all download tasks
                future_to_url = {
                    executor.submit(self.download_single_song, url, output_template, audio_format, output_folder): url 
                    for url in urls
                }
                
                # Process completed downloads
                for future in as_completed(future_to_url):
                    if not self.is_downloading:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                    
                    processed += 1
                    success, msg = future.result()
                    
                    if success:
                        completed += 1
                        # Check if it was skipped (already downloaded)
                        if msg and "skipping" in msg.lower():
                            skipped += 1
                    
                    if msg:
                        level = "info" if success else "warning"
                        self.log(msg, level)
                    
                    # Update progress
                    progress = processed / total
                    downloaded = completed - skipped
                    self.after(0, lambda p=progress: self.progress_bar.set(p))
                    self.after(0, lambda d=downloaded, s=skipped, p=processed, t=total: 
                        self.set_status(f"Downloaded {d}, Skipped {s} / {t} total"))
            
            if self.is_downloading:
                downloaded = completed - skipped
                if skipped > 0:
                    msg = f"Done! {downloaded} downloaded, {skipped} already existed"
                else:
                    msg = f"Downloaded {downloaded} songs!"
                self.after(0, lambda m=msg: self.download_complete(True, m))
            else:
                self.after(0, lambda: self.download_complete(False, "Cancelled"))
                
        except Exception as e:
            self.after(0, lambda: self.download_complete(False, str(e)))
    
    def set_downloading_state(self, downloading):
        self.is_downloading = downloading
        state = "disabled" if downloading else "normal"
        
        self.download_btn.configure(state=state)
        self.liked_btn.configure(state="disabled" if downloading or not self.spotify_client else "normal")
        self.cancel_btn.configure(state="normal" if downloading else "disabled")
    
    def download_complete(self, success, message):
        self.set_downloading_state(False)
        self.progress_bar.set(1 if success else 0)
        
        if success:
            self.set_status(f"✓ {message}", COLORS["accent"])
            self.log(message, "success")
            messagebox.showinfo("Success", f"{message}\n\nSaved to: {self.output_folder.get()}")
        else:
            self.set_status(f"✗ {message}", COLORS["red"])
            self.log(message, "error")
            if "cancel" not in message.lower():
                messagebox.showerror("Error", message)
    
    def cancel_download(self):
        if self.is_downloading:
            self.is_downloading = False
            self.log("Cancelling...", "warning")


def main():
    """Main entry point - setup already done at module load"""
    app = SpotifyDownloader()
    app.mainloop()


if __name__ == "__main__":
    main()
