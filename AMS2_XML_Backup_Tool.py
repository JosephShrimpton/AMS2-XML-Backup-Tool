#!/usr/bin/env python3
"""
AMS2 XML Backup Tool
====================
A GUI tool to safely back up and restore Automobilista 2 Custom AI Driver XMLs.

SAFETY PROMISE:
- Backup: Only copies files. Never moves, deletes, or modifies originals.
- Restore: Only overwrites matching files and adds new ones. Never deletes anything.
- Preview: Shows exactly what will happen before any changes are made.
- Metadata: Every backup includes a manifest for verification.

Author: Generated for AMS2 community
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import json
import datetime
import hashlib
import sys
import threading
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple

# ============================================================================
# THEME COLORS
# ============================================================================
BG_DARK = "#212121"
BG_CARD = "#2D2D2D"
BG_INPUT = "#1A1A1A"
TEXT_PRIMARY = "#E8E9EB"
TEXT_SECONDARY = "#A0A4A8"
ACCENT = "#dc0000"
ACCENT_DARK = "#a80000"
ACCENT_HOVER = "#f02020"
WARN_YELLOW = "#F0C040"
WARN_BG = "#3D2D1A"
ERROR_RED = "#FF6B6B"
ERROR_BG = "#3D1A1A"
INFO_BLUE = "#4A90D9"

# ============================================================================
# DATA CLASSES
# ============================================================================
@dataclass
class FileInfo:
    """Represents a single file in a backup or target."""
    relative_path: str
    size: int
    md5_hash: str
    original_path: Optional[str] = None

@dataclass
class BackupManifest:
    """Metadata about a backup operation."""
    source_path: str
    backup_date: str
    file_count: int
    files: List[Dict]
    tool_version: str = "3.0-safe"
    notes: str = ""

@dataclass
class RestoreAction:
    """Represents a single file action during restore preview."""
    action_type: str  # "OVERWRITE", "NEW", "UNCHANGED", "SKIP"
    relative_path: str
    source_size: int
    dest_size: Optional[int]
    reason: str

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def compute_md5(filepath: Path) -> str:
    """Compute MD5 hash of a file for integrity verification."""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return "ERROR"

def scan_xml_files(directory: Path) -> List[Path]:
    """Recursively find all relevant files in a directory, excluding metadata files."""
    if not directory.exists():
        return []
    xml_files = []
    # Supported file patterns
    patterns = ["*.xml", "*.xml.orig", "*.xml.backup", "*.backup", "*.txt"]
    for pattern in patterns:
        for f in directory.rglob(pattern):
            if f.name != "_backup_metadata.json" and f.name != "_backup_manifest.json":
                xml_files.append(f)
    return sorted(xml_files)

def create_backup(source_dir: Path, backup_base: Path, log_callback=None) -> Tuple[Path, BackupManifest]:
    """
    Create a timestamped backup of all XML files in source_dir.
    Returns: (backup_folder_path, manifest)
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_folder = backup_base / f"CustomAIDrivers_backup_{timestamp}"
    backup_folder.mkdir(parents=True, exist_ok=True)

    xml_files = scan_xml_files(source_dir)

    manifest = BackupManifest(
        source_path=str(source_dir),
        backup_date=timestamp,
        file_count=len(xml_files),
        files=[]
    )

    for src_file in xml_files:
        rel_path = src_file.relative_to(source_dir)
        dest_file = backup_folder / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)

        file_info = {
            "relative_path": str(rel_path),
            "size": src_file.stat().st_size,
            "md5_hash": compute_md5(src_file)
        }
        manifest.files.append(file_info)

    # Save manifest
    with open(backup_folder / "_backup_manifest.json", "w", encoding="utf-8") as f:
        json.dump(asdict(manifest), f, indent=2)

    return backup_folder, manifest

def generate_restore_preview(backup_dir: Path, target_dir: Path) -> List[RestoreAction]:
    """
    Generate a preview of what a restore operation would do.
    Returns a list of RestoreAction objects.
    """
    actions = []
    xml_files = scan_xml_files(backup_dir)

    for src_file in xml_files:
        rel_path = src_file.relative_to(backup_dir)
        dest_file = target_dir / rel_path
        src_size = src_file.stat().st_size
        src_hash = compute_md5(src_file)

        if dest_file.exists():
            dest_size = dest_file.stat().st_size
            dest_hash = compute_md5(dest_file)

            if src_hash == dest_hash:
                actions.append(RestoreAction(
                    action_type="UNCHANGED",
                    relative_path=str(rel_path),
                    source_size=src_size,
                    dest_size=dest_size,
                    reason="File is identical to backup (MD5 match)"
                ))
            else:
                actions.append(RestoreAction(
                    action_type="OVERWRITE",
                    relative_path=str(rel_path),
                    source_size=src_size,
                    dest_size=dest_size,
                    reason="File exists but differs from backup"
                ))
        else:
            actions.append(RestoreAction(
                action_type="NEW",
                relative_path=str(rel_path),
                source_size=src_size,
                dest_size=None,
                reason="File does not exist in target"
            ))

    return actions

def execute_restore(backup_dir: Path, target_dir: Path, 
                    progress_callback=None, log_callback=None) -> Dict:
    """
    Execute a restore operation safely.
    Returns a summary dict with counts.
    """
    actions = generate_restore_preview(backup_dir, target_dir)

    overwrite_count = 0
    new_count = 0
    unchanged_count = 0
    error_count = 0
    errors = []

    total = len(actions)
    for i, action in enumerate(actions):
        dest_file = target_dir / action.relative_path
        src_file = backup_dir / action.relative_path

        try:
            dest_file.parent.mkdir(parents=True, exist_ok=True)

            if action.action_type == "OVERWRITE":
                shutil.copy2(src_file, dest_file)
                overwrite_count += 1
            elif action.action_type == "NEW":
                shutil.copy2(src_file, dest_file)
                new_count += 1
            elif action.action_type == "UNCHANGED":
                unchanged_count += 1
                # Skip - no need to copy identical file
        except Exception as e:
            error_count += 1
            errors.append(f"{action.relative_path}: {str(e)}")

        if progress_callback:
            progress_callback((i + 1) / total)

    return {
        "overwrite": overwrite_count,
        "new": new_count,
        "unchanged": unchanged_count,
        "error": error_count,
        "errors": errors,
        "total": total
    }

def verify_backup_integrity(backup_dir: Path) -> Tuple[bool, List[str]]:
    """
    Verify that all files in a backup match their recorded hashes.
    Returns (is_valid, list_of_issues)
    """
    manifest_file = backup_dir / "_backup_manifest.json"
    if not manifest_file.exists():
        return False, ["No manifest file found in backup"]

    try:
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        return False, [f"Failed to read manifest: {str(e)}"]

    issues = []
    for file_info in manifest.get("files", []):
        rel_path = file_info["relative_path"]
        expected_hash = file_info.get("md5_hash", "")
        actual_file = backup_dir / rel_path

        if not actual_file.exists():
            issues.append(f"MISSING: {rel_path}")
            continue

        actual_hash = compute_md5(actual_file)
        if expected_hash and expected_hash != actual_hash:
            issues.append(f"CORRUPTED: {rel_path} (hash mismatch)")

    return len(issues) == 0, issues

# ============================================================================
# GUI APPLICATION
# ============================================================================

class AMS2XMLBackupTool:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AMS2 XML Backup Tool")
        self.root.geometry("1000x800")
        self.root.configure(bg=BG_DARK)
        self.root.minsize(900, 700)

        # Try to set window icon from .ico file
        self._set_window_icon()

        # Config
        self.config_file = Path.home() / ".ams2_xml_backup_config.json"
        self.config = self.load_config()

        # Backups directory
        self.backups_dir = Path(self.config.get("backup_dir", str(Path.home() / "AMS2_XML_Backups")))
        self.backups_dir.mkdir(exist_ok=True)

        self.setup_styles()
        self.build_ui()
        self.scan_backups()

        # First-time setup: ask where to store config (after main window is built)
        if self.config.get("_needs_setup", False):
            self.root.after(100, self._show_first_time_setup)

    def _get_config_dir(self) -> Path:
        """
        Determine where to store the config file.
        Priority:
        1. If config_location is set in existing config, use that directory
        2. Default to user's home directory
        """
        # Check if we already have a config with a preferred location
        home_config = Path.home() / ".ams2_xml_backup_config.json"
        if home_config.exists():
            try:
                with open(home_config, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "config_location" in data:
                    loc = Path(data["config_location"])
                    if loc.exists():
                        return loc
            except:
                pass
        return Path.home()

    def open_settings(self):
        """Open settings dialog to change config location and other preferences."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("500x300")
        dialog.configure(bg=BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        # Center on main window
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (500 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (300 // 2)
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text="⚙️ Settings", 
                bg=BG_DARK, fg=ACCENT, font=("Segoe UI", 14, "bold")).pack(anchor=tk.W, padx=20, pady=(20, 5))

        # Current config location
        current_loc = self.config.get("config_location", str(Path.home()))
        tk.Label(dialog, text=f"Current config location:",
                bg=BG_DARK, fg=TEXT_SECONDARY, font=("Segoe UI", 10)).pack(anchor=tk.W, padx=20)
        tk.Label(dialog, text=f"{current_loc}/.ams2_xml_backup_config.json",
                bg=BG_DARK, fg=TEXT_PRIMARY, font=("Consolas", 9)).pack(anchor=tk.W, padx=20, pady=(0, 15))

        # Change config location button
        def change_config_location():
            new_dir = self._prompt_config_location()
            # Migrate config to new location
            old_config_file = self.config_file
            self.config["config_location"] = str(new_dir)
            self.config_file = new_dir / ".ams2_xml_backup_config.json"
            self.save_config()
            # Remove old config file if it exists and is different
            if old_config_file.exists() and old_config_file != self.config_file:
                try:
                    old_config_file.unlink()
                except:
                    pass
            self.log(f"✓ Config location changed to: {new_dir}")
            messagebox.showinfo("Settings Updated", 
                               f"Config location updated to: {new_dir}",
                               parent=dialog)
            dialog.destroy()

        change_btn = tk.Button(dialog, text="Change Config Location", command=change_config_location,
                              bg=ACCENT, fg=BG_DARK, font=("Segoe UI", 10, "bold"),
                              relief=tk.FLAT, padx=20, pady=8, cursor="hand2")
        change_btn.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Reset to first-time setup
        def reset_config():
            result = messagebox.askyesno("Reset Config Location", 
                                        "This will clear your config location preference and ask again on next launch.\n\n"
                                        "Your backups and settings will be preserved.\n\n"
                                        "Are you sure?",
                                        parent=dialog)
            if result:
                self.config["_needs_setup"] = True
                self.save_config()
                self.log("⚙ Config reset. Restart the app to choose a new location.")
                messagebox.showinfo("Restart Required", 
                                   "Please restart the app to choose a new config location.",
                                   parent=dialog)
                dialog.destroy()

        reset_btn = tk.Button(dialog, text="Reset & Choose Again on Restart", command=reset_config,
                             bg="#5A5A5A", fg=TEXT_PRIMARY, font=("Segoe UI", 10),
                             relief=tk.FLAT, padx=20, pady=8, cursor="hand2")
        reset_btn.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Close button
        tk.Button(dialog, text="Close", command=dialog.destroy,
                 bg="#5A5A5A", fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold"),
                 relief=tk.FLAT, padx=20, pady=8, cursor="hand2").pack(anchor=tk.E, padx=20, pady=(10, 0))

    def _show_first_time_setup(self):
        """Show the config location dialog after main window is ready."""
        config_dir = self._prompt_config_location()
        self.config.pop("_needs_setup", None)
        self.config["config_location"] = str(config_dir)
        self.config_file = config_dir / ".ams2_xml_backup_config.json"
        self.save_config()
        self.log(f"✓ Config location set to: {config_dir}")

    def _prompt_config_location(self) -> Path:
        """Ask user where they want to store config and backups metadata."""
        dialog = tk.Toplevel(self.root)
        dialog.title("First-Time Setup - Config Location")
        dialog.geometry("550x300")
        dialog.configure(bg=BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        # Center the dialog on the main window
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (550 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (300 // 2)
        dialog.geometry(f"+{x}+{y}")

        tk.Label(dialog, text="⚙️ Welcome to AMS2 XML Backup Tool", 
                bg=BG_DARK, fg=ACCENT, font=("Segoe UI", 14, "bold")).pack(anchor=tk.W, padx=20, pady=(20, 5))

        tk.Label(dialog, text="Choose where to store the app's settings file:",
                bg=BG_DARK, fg=TEXT_PRIMARY, font=("Segoe UI", 11)).pack(anchor=tk.W, padx=20, pady=(5, 15))

        selected_location = {"path": str(Path.home())}

        def choose_folder():
            path = filedialog.askdirectory(title="Select folder for config file", parent=dialog)
            if path:
                selected_location["path"] = path
                dialog.destroy()

        def choose_home():
            selected_location["path"] = str(Path.home())
            dialog.destroy()

        # Primary option: Browse for any folder
        opt_browse = tk.Frame(dialog, bg=BG_CARD, padx=15, pady=15)
        opt_browse.pack(fill=tk.X, padx=20, pady=(0, 10))
        opt_browse.configure(highlightbackground=ACCENT, highlightthickness=2)
        tk.Label(opt_browse, text="📁 Browse for a Folder", bg=BG_CARD, fg=ACCENT,
                font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)
        tk.Label(opt_browse, text="Choose any folder on your PC to store the config file",
                bg=BG_CARD, fg=TEXT_SECONDARY, font=("Segoe UI", 10)).pack(anchor=tk.W, pady=(4, 8))
        tk.Button(opt_browse, text="Browse...", command=choose_folder,
                 bg=ACCENT, fg=BG_DARK, font=("Segoe UI", 10, "bold"),
                 relief=tk.FLAT, padx=25, pady=6, cursor="hand2").pack(anchor=tk.W)

        # Quick options row
        quick_frame = tk.Frame(dialog, bg=BG_DARK)
        quick_frame.pack(fill=tk.X, padx=20, pady=(5, 0))

        tk.Label(quick_frame, text="Quick picks:", bg=BG_DARK, fg=TEXT_SECONDARY,
                font=("Segoe UI", 10)).pack(anchor=tk.W)

        quick_btns = tk.Frame(quick_frame, bg=BG_DARK)
        quick_btns.pack(fill=tk.X, pady=(5, 0))

        # Home button
        tk.Button(quick_btns, text="🏠 Home", command=choose_home,
                 bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 9),
                 relief=tk.FLAT, padx=15, pady=5, cursor="hand2").pack(side=tk.LEFT, padx=(0, 8))

        # Documents button
        def choose_documents():
            docs = Path.home() / "Documents" / "AMS2_XML_Backup_Tool"
            docs.mkdir(parents=True, exist_ok=True)
            selected_location["path"] = str(docs)
            dialog.destroy()

        tk.Button(quick_btns, text="📂 Documents", command=choose_documents,
                 bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 9),
                 relief=tk.FLAT, padx=15, pady=5, cursor="hand2").pack(side=tk.LEFT, padx=(0, 8))

        # AppData button
        def choose_appdata():
            appdata = Path.home() / "AppData" / "Local" / "AMS2_XML_Backup_Tool"
            appdata.mkdir(parents=True, exist_ok=True)
            selected_location["path"] = str(appdata)
            dialog.destroy()

        tk.Button(quick_btns, text="⚙ AppData", command=choose_appdata,
                 bg=BG_CARD, fg=TEXT_PRIMARY, font=("Segoe UI", 9),
                 relief=tk.FLAT, padx=15, pady=5, cursor="hand2").pack(side=tk.LEFT)

        # Wait for user to make a selection
        self.root.wait_window(dialog)
        return Path(selected_location["path"])

    def _get_app_dir(self) -> Path:
        """Get the directory where the app files are located.
        Handles both Python script and PyInstaller .exe builds."""
        if hasattr(sys, '_MEIPASS'):
            # Running from PyInstaller .exe (onefile mode)
            # _MEIPASS is the temp extraction folder where --add-data files are placed
            return Path(sys._MEIPASS)
        else:
            # Running as Python script
            return Path(__file__).parent

    def _set_window_icon(self):
        """Set the window icon from icon.ico if available."""
        try:
            app_dir = self._get_app_dir()
            icon_paths = [
                app_dir / "icon.ico",
                app_dir / "app_icon.ico",
                app_dir / "AMS2 XML Backup Icon.ico",
            ]
            for icon_path in icon_paths:
                if icon_path.exists():
                    self.root.iconbitmap(str(icon_path))
                    break
        except Exception:
            pass  # Icon setting is optional, don't fail if it doesn't work

    def load_config(self) -> dict:
        # First, check if we need to ask for config location
        home_config = Path.home() / ".ams2_xml_backup_config.json"

        # If no config exists at all, we need first-time setup
        if not home_config.exists():
            # We'll return empty and let __init__ handle the prompt
            return {"_needs_setup": True, "custom_ai_path": "", "backup_dir": str(Path.home() / "AMS2_XML_Backups")}

        # Config exists, load it
        try:
            with open(home_config, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Check if user has a preferred config location
            if "config_location" in data:
                config_dir = Path(data["config_location"])
                actual_config = config_dir / ".ams2_xml_backup_config.json"
                if actual_config.exists():
                    with open(actual_config, "r", encoding="utf-8") as f:
                        return json.load(f)

            return data
        except:
            pass

        return {"custom_ai_path": "", "backup_dir": str(Path.home() / "AMS2_XML_Backups")}

    def save_config(self):
        # Determine where to save
        if "config_location" in self.config:
            config_dir = Path(self.config["config_location"])
            config_file = config_dir / ".ams2_xml_backup_config.json"
        else:
            config_file = Path.home() / ".ams2_xml_backup_config.json"

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TFrame", background=BG_DARK)
        style.configure("TLabel", background=BG_DARK, foreground=TEXT_PRIMARY, font=("Segoe UI", 10))
        style.configure("Treeview", background=BG_CARD, foreground=TEXT_PRIMARY, 
                       fieldbackground=BG_CARD, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=BG_DARK, foreground=ACCENT, 
                       font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", ACCENT_DARK)])

    def build_ui(self):
        main_frame = tk.Frame(self.root, bg=BG_DARK)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # ===== HEADER =====
        header = tk.Frame(main_frame, bg=BG_DARK)
        header.pack(fill=tk.X, pady=(0, 12))

        # Try to load app icon PNG
        self.header_icon = None
        try:
            from PIL import Image, ImageTk
            # Look for icon in same directory as app (handles both .py and .exe)
            app_dir = self._get_app_dir()
            icon_paths = [
                app_dir / "AMS2 XML Backup Icon.png",
                app_dir / "app_icon.png",
                app_dir / "icon.png",
            ]
            icon_path = None
            for p in icon_paths:
                if p.exists():
                    icon_path = p
                    break

            if icon_path:
                img = Image.open(icon_path)
                # Scale to a reasonable header size (max 48x48)
                img.thumbnail((48, 48), Image.LANCZOS)
                self.header_icon = ImageTk.PhotoImage(img)
        except Exception:
            self.header_icon = None

        # Header content: icon + text side by side
        header_inner = tk.Frame(header, bg=BG_DARK)
        header_inner.pack(anchor=tk.W)

        if self.header_icon:
            icon_label = tk.Label(header_inner, image=self.header_icon, bg=BG_DARK)
            icon_label.pack(side=tk.LEFT, padx=(0, 12))

        title_frame = tk.Frame(header_inner, bg=BG_DARK)
        title_frame.pack(side=tk.LEFT)

        tk.Label(title_frame, text="AMS2 XML Backup Tool", 
                bg=BG_DARK, fg=ACCENT, font=("Segoe UI", 20, "bold")).pack(anchor=tk.W)

        tk.Label(title_frame, text="Python based tool to create safe and secure backups of your AMS2 .xml files.", 
                bg=BG_DARK, fg=TEXT_SECONDARY, font=("Segoe UI", 11)).pack(anchor=tk.W, pady=(2, 0))

        # ===== PATHS SECTION =====
        paths_card = tk.Frame(main_frame, bg=BG_CARD, padx=18, pady=15)
        paths_card.pack(fill=tk.X, pady=(0, 10))
        paths_card.configure(highlightbackground=ACCENT, highlightthickness=2)

        # Custom AI Drivers Path (DIRECT — no auto-append)
        tk.Label(paths_card, text="📁 Custom AI Drivers Folder", bg=BG_CARD, fg=ACCENT,
                font=("Segoe UI", 11, "bold")).pack(anchor=tk.W)

        tk.Label(paths_card, text="Point this directly to your AMS2 CustomAIDrivers folder.",
                bg=BG_CARD, fg=TEXT_SECONDARY, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(2, 0))

        ai_frame = tk.Frame(paths_card, bg=BG_CARD)
        ai_frame.pack(fill=tk.X, pady=(6, 10))

        self.custom_ai_path_var = tk.StringVar(value=self.config.get("custom_ai_path", ""))
        self.ai_entry = tk.Entry(ai_frame, textvariable=self.custom_ai_path_var,
                                 bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                 font=("Segoe UI", 10), relief=tk.FLAT, bd=10)
        self.ai_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        tk.Button(ai_frame, text="Browse...", command=self.browse_custom_ai,
                 bg=ACCENT, fg=BG_DARK, font=("Segoe UI", 9, "bold"),
                 relief=tk.FLAT, padx=15, pady=6, activebackground=ACCENT_DARK,
                 cursor="hand2").pack(side=tk.RIGHT)

        # Example path hint
        tk.Label(paths_card, text="💡 Example: C:\\...\\Automobilista 2\\UserData\\CustomAIDrivers",
                bg=BG_CARD, fg=TEXT_SECONDARY, font=("Segoe UI", 9)).pack(anchor=tk.W)

        # Backup Destination
        tk.Label(paths_card, text="💾 Backup Destination", bg=BG_CARD, fg=ACCENT,
                font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(12, 0))

        tk.Label(paths_card, text="Where your XML backups will be saved.",
                bg=BG_CARD, fg=TEXT_SECONDARY, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(2, 0))

        dest_frame = tk.Frame(paths_card, bg=BG_CARD)
        dest_frame.pack(fill=tk.X, pady=(6, 0))

        self.backup_dir_var = tk.StringVar(value=str(self.backups_dir))
        self.dest_entry = tk.Entry(dest_frame, textvariable=self.backup_dir_var,
                                   bg=BG_INPUT, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
                                   font=("Segoe UI", 10), relief=tk.FLAT, bd=10)
        self.dest_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        tk.Button(dest_frame, text="Browse...", command=self.browse_backup_dir,
                 bg=ACCENT, fg=BG_DARK, font=("Segoe UI", 9, "bold"),
                 relief=tk.FLAT, padx=15, pady=6, activebackground=ACCENT_DARK,
                 cursor="hand2").pack(side=tk.RIGHT)

        # ===== ACTION BUTTONS =====
        btn_frame = tk.Frame(main_frame, bg=BG_DARK)
        btn_frame.pack(fill=tk.X, pady=(0, 8))

        self.backup_btn = tk.Button(btn_frame, text="📦 BACK UP NOW", command=self.run_backup,
                                   bg=ACCENT, fg=BG_DARK, font=("Segoe UI", 12, "bold"),
                                   relief=tk.FLAT, padx=25, pady=12,
                                   activebackground=ACCENT_HOVER, cursor="hand2")
        self.backup_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.verify_btn = tk.Button(btn_frame, text="🔍 VERIFY BACKUP", command=self.run_verify,
                                   bg="#5A5A5A", fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold"),
                                   relief=tk.FLAT, padx=18, pady=12,
                                   activebackground="#6A6A6A", cursor="hand2")
        self.verify_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.preview_btn = tk.Button(btn_frame, text="👁 PREVIEW RESTORE", command=self.preview_restore,
                                    bg="#5A5A5A", fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold"),
                                    relief=tk.FLAT, padx=18, pady=12,
                                    activebackground="#6A6A6A", cursor="hand2")
        self.preview_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.restore_btn = tk.Button(btn_frame, text="🔄 RESTORE", command=self.run_restore,
                                    bg=ACCENT_DARK, fg=BG_DARK, font=("Segoe UI", 12, "bold"),
                                    relief=tk.FLAT, padx=25, pady=12,
                                    activebackground=ACCENT, cursor="hand2")
        self.restore_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.settings_btn = tk.Button(btn_frame, text="⚙ SETTINGS", command=self.open_settings,
                                    bg="#5A5A5A", fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold"),
                                    relief=tk.FLAT, padx=18, pady=12,
                                    activebackground="#6A6A6A", cursor="hand2")
        self.settings_btn.pack(side=tk.LEFT)

        # ===== PROGRESS =====
        self.progress = ttk.Progressbar(main_frame, mode="determinate", style="Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 6))
        self.progress["value"] = 0

        self.status_label = tk.Label(main_frame, text="Ready. Set your Custom AI Drivers folder and click BACK UP NOW.",
                                    bg=BG_DARK, fg=TEXT_SECONDARY, font=("Segoe UI", 10))
        self.status_label.pack(anchor=tk.W, pady=(0, 8))

        # ===== BACKUP LIST =====
        list_card = tk.Frame(main_frame, bg=BG_CARD, padx=12, pady=12)
        list_card.pack(fill=tk.BOTH, expand=True)
        list_card.configure(highlightbackground=ACCENT, highlightthickness=1)

        tk.Label(list_card, text="📋 Available Backups (double-click to preview)", 
                bg=BG_CARD, fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(anchor=tk.W, pady=(0, 6))

        # Delete button row (inside backup list card)
        delete_btn_frame = tk.Frame(list_card, bg=BG_CARD)
        delete_btn_frame.pack(fill=tk.X, pady=(0, 6))

        self.selected_backup_label = tk.Label(delete_btn_frame, text="No backup selected",
                                                bg=BG_CARD, fg=TEXT_SECONDARY,
                                                font=("Segoe UI", 9))
        self.selected_backup_label.pack(side=tk.LEFT)

        self.delete_card_btn = tk.Button(delete_btn_frame, text="🗑 Delete This Backup",
                                          command=self.run_delete_backup, state=tk.DISABLED,
                                          bg="#8B0000", fg=TEXT_PRIMARY, font=("Segoe UI", 9, "bold"),
                                          relief=tk.FLAT, padx=15, pady=5, cursor="hand2")
        self.delete_card_btn.pack(side=tk.RIGHT)


        columns = ("date", "files", "size", "verified", "path")
        self.tree = ttk.Treeview(list_card, columns=columns, show="headings", height=7)
        self.tree.heading("date", text="Backup Date")
        self.tree.heading("files", text="Files")
        self.tree.heading("size", text="Size")
        self.tree.heading("verified", text="Integrity")
        self.tree.heading("path", text="Location")
        self.tree.column("date", width=160, anchor=tk.W)
        self.tree.column("files", width=60, anchor=tk.CENTER)
        self.tree.column("size", width=80, anchor=tk.CENTER)
        self.tree.column("verified", width=80, anchor=tk.CENTER)
        self.tree.column("path", width=450, anchor=tk.W)

        scrollbar = ttk.Scrollbar(list_card, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Context menu for right-click delete
        self.tree_context_menu = tk.Menu(self.tree, tearoff=0, bg=BG_CARD, fg=TEXT_PRIMARY,
                                         font=("Segoe UI", 10), activebackground=ACCENT,
                                         activeforeground=BG_DARK)
        self.tree_context_menu.add_command(label="🗑 Delete Backup", command=self.run_delete_backup)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # ===== LOG =====
        log_frame = tk.LabelFrame(main_frame, text=" Status Log ", bg=BG_DARK, fg=ACCENT,
                                 font=("Segoe UI", 10, "bold"), padx=10, pady=10)
        log_frame.pack(fill=tk.X, pady=(10, 0))

        self.log_text = scrolledtext.ScrolledText(log_frame, bg=BG_INPUT, fg=TEXT_SECONDARY,
                                                   font=("Consolas", 9), height=5, wrap=tk.WORD,
                                                   relief=tk.FLAT, insertbackground=TEXT_PRIMARY)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        # ===== FOOTER =====
        footer = tk.Frame(main_frame, bg=BG_DARK, padx=5, pady=5)
        footer.pack(fill=tk.X, pady=(5, 0))

        tk.Label(footer, text="v1.1", bg=BG_DARK, fg=TEXT_SECONDARY,
                font=("Segoe UI", 9)).pack(side=tk.RIGHT)

        self.log("🏁 AMS2 XML Backup Tool started.")
        self.log("🔒 Safety mode: NO files will ever be deleted.")
        self.log("Point the Custom AI Drivers folder directly to your CustomAIDrivers path.")

    def log(self, message: str):
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def set_status(self, message: str, color: str = TEXT_SECONDARY):
        self.status_label.config(text=message, fg=color)

    def browse_custom_ai(self):
        path = filedialog.askdirectory(title="Select your AMS2 CustomAIDrivers folder")
        if path:
            self.custom_ai_path_var.set(path)
            self.config["custom_ai_path"] = path
            self.save_config()
            self.log(f"✓ Custom AI Drivers folder set to: {path}")

    def browse_backup_dir(self):
        path = filedialog.askdirectory(title="Select Backup Destination Folder")
        if path:
            self.backup_dir_var.set(path)
            self.config["backup_dir"] = path
            self.save_config()
            self.backups_dir = Path(path)
            self.log(f"✓ Backup destination set to: {path}")

    def get_custom_ai_path(self) -> Optional[Path]:
        path_str = self.custom_ai_path_var.get().strip()
        if not path_str:
            return None
        path = Path(path_str)
        return path if path.exists() else None

    def scan_backups(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        backup_dir = Path(self.backup_dir_var.get().strip())
        if not backup_dir.exists():
            return

        for folder in sorted(backup_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if folder.is_dir() and folder.name.startswith("CustomAIDrivers_backup_"):
                try:
                    xml_files = scan_xml_files(folder)
                    total_size = sum(f.stat().st_size for f in xml_files)
                    date_str = folder.name.replace("CustomAIDrivers_backup_", "").replace("_", " ")

                    manifest_file = folder / "_backup_manifest.json"
                    verified = "✓" if manifest_file.exists() else "?"

                    self.tree.insert("", tk.END, values=(
                        date_str, len(xml_files), self.format_size(total_size), verified, str(folder)
                    ))
                except:
                    pass

    def format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024: return f"{size_bytes} B"
        elif size_bytes < 1024**2: return f"{size_bytes/1024:.1f} KB"
        else: return f"{size_bytes/1024**2:.1f} MB"

    def set_buttons_state(self, state: str):
        self.backup_btn.config(state=state)
        self.restore_btn.config(state=state)
        self.preview_btn.config(state=state)
        self.verify_btn.config(state=state)
        self.settings_btn.config(state=state)

    # ===== BACKUP =====
    def run_backup(self):
        custom_ai_path = self.custom_ai_path_var.get().strip()
        backup_dir = self.backup_dir_var.get().strip()

        if not custom_ai_path:
            messagebox.showerror("Missing Path", "Please set your Custom AI Drivers folder path.")
            return

        custom_ai = Path(custom_ai_path)
        if not custom_ai.exists():
            messagebox.showerror("Folder Not Found",
                                f"The folder does not exist:\n{custom_ai_path}\n\n"
                                f"Please browse to your AMS2 CustomAIDrivers folder.")
            return

        if not backup_dir:
            messagebox.showerror("Missing Path", "Please set a backup destination.")
            return

        thread = threading.Thread(target=self._do_backup, args=(custom_ai, Path(backup_dir)))
        thread.daemon = True
        thread.start()

    def _do_backup(self, source_dir: Path, backup_base: Path):
        self.set_buttons_state(tk.DISABLED)
        self.set_status("Scanning for XML files...", ACCENT)
        self.progress["value"] = 5

        try:
            xml_files = scan_xml_files(source_dir)
            self.log(f"Found {len(xml_files)} file(s) in {source_dir}")

            if not xml_files:
                self.set_status("No files found to back up.", WARN_YELLOW)
                self.log("⚠ No files found. Folder may be empty.")
                return

            self.progress["value"] = 15
            self.set_status(f"Creating backup with {len(xml_files)} files...", ACCENT)

            backup_folder, manifest = create_backup(source_dir, backup_base)

            self.progress["value"] = 100
            total_size = sum(f["size"] for f in manifest.files)

            self.set_status(f"✓ Backup complete: {backup_folder.name}", ACCENT)
            self.log(f"✓ BACKUP SUCCESS: {manifest.file_count} files copied")
            self.log(f"  Location: {backup_folder}")
            self.log(f"  Total size: {self.format_size(total_size)}")
            self.log(f"  Integrity: MD5 hashes recorded in manifest")
            self.log(f"  ORIGINAL FILES: Completely untouched (only copied)")

            self.scan_backups()

            messagebox.showinfo("Backup Complete",
                               f"✓ {manifest.file_count} XML file(s) safely backed up.\n\n"
                               f"Location: {backup_folder}\n"
                               f"Size: {self.format_size(total_size)}\n\n"
                               f"Your original files were NOT modified.")

        except Exception as e:
            self.set_status(f"✗ Backup failed: {str(e)}", ERROR_RED)
            self.log(f"✗ ERROR: {str(e)}")
            messagebox.showerror("Backup Failed", str(e))
        finally:
            self.set_buttons_state(tk.NORMAL)
            self.progress["value"] = 0

    # ===== VERIFY =====
    def run_verify(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select a Backup", "Please select a backup from the list to verify.")
            return

        backup_path = Path(self.tree.item(selected[0])["values"][4])

        thread = threading.Thread(target=self._do_verify, args=(backup_path,))
        thread.daemon = True
        thread.start()

    def _do_verify(self, backup_dir: Path):
        self.set_buttons_state(tk.DISABLED)
        self.set_status("Verifying backup integrity...", ACCENT)
        self.progress["value"] = 30

        try:
            is_valid, issues = verify_backup_integrity(backup_dir)

            self.progress["value"] = 100

            if is_valid:
                self.set_status(f"✓ Backup verified: all files intact", ACCENT)
                self.log(f"✓ VERIFICATION PASSED: {backup_dir.name}")
                self.log(f"  All files match their recorded MD5 hashes.")
                messagebox.showinfo("Verification Passed",
                                   f"✓ All files in backup are intact.\n\n"
                                   f"Backup: {backup_dir.name}\n"
                                   f"Every file matches its original hash.")
            else:
                self.set_status(f"✗ Backup has issues", ERROR_RED)
                self.log(f"✗ VERIFICATION FAILED: {backup_dir.name}")
                for issue in issues:
                    self.log(f"  - {issue}")
                messagebox.showerror("Verification Failed",
                                    f"✗ Issues found in backup:\n\n" + "\n".join(issues))

        except Exception as e:
            self.set_status(f"✗ Verification error: {str(e)}", ERROR_RED)
            self.log(f"✗ ERROR: {str(e)}")
        finally:
            self.set_buttons_state(tk.NORMAL)
            self.progress["value"] = 0

    # ===== PREVIEW =====
    def preview_restore(self):
        backup_folder = self._get_selected_backup()
        if not backup_folder:
            return

        target_dir = self._get_target_dir()
        if not target_dir:
            return

        thread = threading.Thread(target=self._do_preview, args=(backup_folder, target_dir))
        thread.daemon = True
        thread.start()

    def _do_preview(self, backup_dir: Path, target_dir: Path):
        self.set_buttons_state(tk.DISABLED)
        self.set_status("Generating restore preview...", ACCENT)
        self.progress["value"] = 30

        try:
            actions = generate_restore_preview(backup_dir, target_dir)

            overwrites = [a for a in actions if a.action_type == "OVERWRITE"]
            new_files = [a for a in actions if a.action_type == "NEW"]
            unchanged = [a for a in actions if a.action_type == "UNCHANGED"]

            self.progress["value"] = 100

            self.set_status(f"👁 Preview ready: {len(overwrites)} overwrite, {len(new_files)} new, {len(unchanged)} unchanged", ACCENT)
            self.log(f"👁 PREVIEW for {backup_dir.name}:")
            self.log(f"  OVERWRITE: {len(overwrites)} files (will be replaced)")
            self.log(f"  NEW:       {len(new_files)} files (will be added)")
            self.log(f"  UNCHANGED: {len(unchanged)} files (already match, skipped)")
            self.log(f"  DELETED:   0 files (nothing will be removed)")

            self._show_preview_dialog(backup_dir, target_dir, actions)

        except Exception as e:
            self.set_status(f"✗ Preview failed: {str(e)}", ERROR_RED)
            self.log(f"✗ ERROR: {str(e)}")
        finally:
            self.set_buttons_state(tk.NORMAL)
            self.progress["value"] = 0

    def _show_preview_dialog(self, backup_dir: Path, target_dir: Path, actions: List[RestoreAction]):
        dialog = tk.Toplevel(self.root)
        dialog.title("Restore Preview")
        dialog.geometry("750x600")
        dialog.configure(bg=BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="👁 Restore Preview", bg=BG_DARK, fg=ACCENT,
                font=("Segoe UI", 16, "bold")).pack(anchor=tk.W, padx=15, pady=(15, 5))

        summary_text = (
            f"Target folder: {target_dir}\n"
            f"Backup: {backup_dir.name}\n\n"
            f"Actions that will be taken:\n"
            f"  • OVERWRITE:  {len([a for a in actions if a.action_type == 'OVERWRITE'])} file(s)\n"
            f"  • NEW:        {len([a for a in actions if a.action_type == 'NEW'])} file(s)\n"
            f"  • UNCHANGED:  {len([a for a in actions if a.action_type == 'UNCHANGED'])} file(s)\n"
            f"  • DELETED:    0 file(s) — NOTHING will be removed\n\n"
            f"Total files in backup: {len(actions)}"
        )

        summary = tk.Label(dialog, text=summary_text, bg=BG_DARK, fg=TEXT_PRIMARY,
                          font=("Consolas", 10), justify=tk.LEFT)
        summary.pack(anchor=tk.W, padx=15, pady=5)

        safety_dialog = tk.Frame(dialog, bg=WARN_BG, padx=10, pady=8)
        safety_dialog.pack(fill=tk.X, padx=15, pady=10)
        tk.Label(safety_dialog, text="🔒 No files will be deleted. Only overwrite + add operations.",
                bg=WARN_BG, fg=WARN_YELLOW, font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)

        tk.Label(dialog, text="File-by-file details:", bg=BG_DARK, fg=TEXT_SECONDARY,
                font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, padx=15, pady=(10, 5))

        details_text = scrolledtext.ScrolledText(dialog, bg=BG_CARD, fg=TEXT_PRIMARY,
                                                font=("Consolas", 9), height=14, wrap=tk.WORD,
                                                relief=tk.FLAT)
        details_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        for action in actions:
            icon = {"OVERWRITE": "🔄", "NEW": "➕", "UNCHANGED": "✓"}.get(action.action_type, "?")
            line = f"{icon} [{action.action_type:10}] {action.relative_path}\n"
            if action.action_type == "OVERWRITE":
                line += f"     (backup: {self.format_size(action.source_size)} → target: {self.format_size(action.dest_size or 0)})\n"
            details_text.insert(tk.END, line)

        details_text.config(state=tk.DISABLED)

        btn_frame = tk.Frame(dialog, bg=BG_DARK)
        btn_frame.pack(fill=tk.X, padx=15, pady=15)

        tk.Button(btn_frame, text="✓ Proceed with Restore",
                 command=lambda: [dialog.destroy(), self.run_restore_confirmed(backup_dir, target_dir)],
                 bg=ACCENT, fg=BG_DARK, font=("Segoe UI", 10, "bold"),
                 relief=tk.FLAT, padx=20, pady=8, cursor="hand2").pack(side=tk.RIGHT, padx=(10, 0))

        tk.Button(btn_frame, text="✗ Cancel",
                 command=dialog.destroy,
                 bg="#5A5A5A", fg=TEXT_PRIMARY, font=("Segoe UI", 10, "bold"),
                 relief=tk.FLAT, padx=20, pady=8, cursor="hand2").pack(side=tk.RIGHT)

    # ===== RESTORE =====
    def run_restore(self):
        backup_folder = self._get_selected_backup()
        if not backup_folder:
            return

        target_dir = self._get_target_dir()
        if not target_dir:
            return

        result = messagebox.askyesno(
            "Confirm Restore",
            f"Restore from: {backup_folder.name}\n\n"
            f"Target: {target_dir}\n\n"
            f"This will OVERWRITE matching files and ADD new ones.\n"
            f"NO files will be deleted.\n\n"
            f"For a detailed preview first, click No and use PREVIEW RESTORE.\n\n"
            f"Proceed with restore?"
        )
        if result:
            self.run_restore_confirmed(backup_folder, target_dir)

    def run_restore_confirmed(self, backup_dir: Path, target_dir: Path):
        thread = threading.Thread(target=self._do_restore, args=(backup_dir, target_dir))
        thread.daemon = True
        thread.start()

    def _do_restore(self, backup_dir: Path, target_dir: Path):
        self.set_buttons_state(tk.DISABLED)
        self.set_status("Restoring files safely (overwrite + add only)...", ACCENT)
        self.progress["value"] = 10

        try:
            def progress_callback(fraction):
                self.progress["value"] = 10 + int(85 * fraction)
                self.root.update_idletasks()

            result = execute_restore(backup_dir, target_dir, progress_callback, self.log)

            self.progress["value"] = 100

            self.set_status(
                f"✓ Restore complete: {result['overwrite']} overwritten, {result['new']} added, {result['unchanged']} unchanged",
                ACCENT
            )

            self.log(f"✓ RESTORE SUCCESS from {backup_dir.name}:")
            self.log(f"  OVERWRITTEN: {result['overwrite']} file(s)")
            self.log(f"  ADDED:       {result['new']} file(s)")
            self.log(f"  UNCHANGED:   {result['unchanged']} file(s)")
            self.log(f"  ERRORS:      {result['error']} file(s)")
            self.log(f"  DELETED:     0 file(s)")
            self.log(f"  Target:      {target_dir}")
            self.log(f"  NO FILES WERE DELETED.")

            if result['errors']:
                self.log("  Error details:")
                for err in result['errors']:
                    self.log(f"    - {err}")

            msg = (
                f"✓ Restore finished successfully!\n\n"
                f"Overwritten: {result['overwrite']}\n"
                f"Added: {result['new']}\n"
                f"Unchanged: {result['unchanged']}\n"
                f"Errors: {result['error']}\n"
                f"Deleted: 0\n\n"
                f"Your custom AI drivers are restored."
            )

            if result['errors']:
                msg += f"\n\n⚠ {result['error']} error(s) occurred:\n" + "\n".join(result['errors'][:5])

            messagebox.showinfo("Restore Complete", msg)

        except Exception as e:
            self.set_status(f"✗ Restore failed: {str(e)}", ERROR_RED)
            self.log(f"✗ ERROR: {str(e)}")
            messagebox.showerror("Restore Failed", str(e))
        finally:
            self.set_buttons_state(tk.NORMAL)
            self.progress["value"] = 0

    def _get_selected_backup(self) -> Optional[Path]:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select a Backup", "Please select a backup from the list first.")
            return None
        return Path(self.tree.item(selected[0])["values"][4])

    def _get_target_dir(self) -> Optional[Path]:
        path_str = self.custom_ai_path_var.get().strip()
        if not path_str:
            messagebox.showerror("Missing Path", "Please set your Custom AI Drivers folder path first.")
            return None
        path = Path(path_str)
        if not path.exists():
            result = messagebox.askyesno(
                "Folder Not Found",
                f"The folder does not exist:\n{path_str}\n\n"
                f"Would you like to create it?"
            )
            if result:
                path.mkdir(parents=True, exist_ok=True)
                self.log(f"Created folder: {path}")
            else:
                return None
        return path

    # ===== DELETE BACKUP =====
    def show_context_menu(self, event):
        """Show right-click context menu on treeview."""
        # Select the item under cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.tree_context_menu.post(event.x_root, event.y_root)

    def on_tree_select(self, event=None):
        """Enable/disable delete card button based on tree selection."""
        selected = self.tree.selection()
        if selected:
            backup_name = self.tree.item(selected[0])["values"][0]
            self.selected_backup_label.config(text=f"Selected: {backup_name}", fg=TEXT_PRIMARY)
            self.delete_card_btn.config(state=tk.NORMAL)
        else:
            self.selected_backup_label.config(text="No backup selected", fg=TEXT_SECONDARY)
            self.delete_card_btn.config(state=tk.DISABLED)

    def _is_valid_backup_folder(self, path: Path) -> bool:
        """Ensure we only delete actual backup folders, not random directories."""
        return (
            path.exists()
            and path.is_dir()
            and path.name.startswith("CustomAIDrivers_backup_")
            and (path / "_backup_manifest.json").exists()
        )

    def run_delete_backup(self):
        """Validate selection and show confirmation before deleting."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select a Backup", "Please select a backup to delete.")
            return

        backup_path = Path(self.tree.item(selected[0])["values"][4])

        # Safety validation
        if not self._is_valid_backup_folder(backup_path):
            messagebox.showerror("Invalid Backup",
                                f"This does not appear to be a valid backup folder:\n\n"
                                f"{backup_path}\n\n"
                                f"Deletion cancelled for safety.")
            self.log(f"✗ DELETE BLOCKED: Invalid backup folder {backup_path.name}")
            return

        # Gather info for confirmation dialog
        try:
            xml_files = scan_xml_files(backup_path)
            file_count = len(xml_files)
            total_size = sum(f.stat().st_size for f in xml_files)
        except Exception:
            file_count = 0
            total_size = 0

        # Show confirmation dialog
        result = messagebox.askyesno(
            "⚠️ Confirm Delete Backup",
            f"You are about to delete this backup:\n\n"
            f"Name: {backup_path.name}\n"
            f"Files: {file_count}\n"
            f"Size: {self.format_size(total_size)}\n"
            f"Location:\n{backup_path}\n\n"
            f"✅ ONLY this folder will be deleted.\n"
            f"✅ Other backups in the same location are SAFE.\n"
            f"✅ Your original CustomAIDrivers files are NOT affected.\n\n"
            f"⚠️ This action cannot be undone.\n\n"
            f"Are you sure you want to delete this backup?"
        )

        if result:
            thread = threading.Thread(target=self._do_delete_backup, args=(backup_path, file_count, total_size))
            thread.daemon = True
            thread.start()

    def _do_delete_backup(self, backup_path: Path, file_count: int, total_size: int):
        """Execute deletion of a single backup folder."""
        self.set_buttons_state(tk.DISABLED)
        self.set_status(f"Deleting backup: {backup_path.name}...", WARN_YELLOW)
        self.progress["value"] = 30

        try:
            # Final safety check before deletion
            if not self._is_valid_backup_folder(backup_path):
                raise ValueError("Backup folder validation failed before deletion.")

            shutil.rmtree(backup_path)

            self.progress["value"] = 100
            self.set_status(f"🗑 Deleted backup: {backup_path.name}", ACCENT)
            self.log(f"🗑 DELETED BACKUP: {backup_path.name}")
            self.log(f"  Files removed: {file_count}")
            self.log(f"  Size freed: {self.format_size(total_size)}")
            self.log(f"  Location: {backup_path}")
            self.log(f"  ✅ Other backups are untouched.")

            messagebox.showinfo("Backup Deleted",
                               f"🗑 Backup deleted successfully.\n\n"
                               f"Name: {backup_path.name}\n"
                               f"Files: {file_count}\n"
                               f"Size: {self.format_size(total_size)}\n\n"
                               f"Other backups remain safe.")

            # Refresh the list and clear selection
            self.scan_backups()
            self.selected_backup_label.config(text="No backup selected", fg=TEXT_SECONDARY)
            self.delete_card_btn.config(state=tk.DISABLED)

        except Exception as e:
            self.set_status(f"✗ Delete failed: {str(e)}", ERROR_RED)
            self.log(f"✗ DELETE ERROR: {str(e)}")
            messagebox.showerror("Delete Failed", str(e))
        finally:
            self.set_buttons_state(tk.NORMAL)
            self.progress["value"] = 0

    def on_tree_double_click(self, event):
        self.preview_restore()


def main():
    root = tk.Tk()
    app = AMS2XMLBackupTool(root)
    root.mainloop()


if __name__ == "__main__":
    main()
