# AMS2 XML Backup Tool

A simple, safe, and lightweight GUI tool for backing up and restoring your Automobilista 2 (AMS2) Custom AI Driver files. Built for sim racers who use career mode apps and want to protect their custom livery/driver XML files from being overwritten.

<img width="1920" height="1032" alt="Screenshot 2026-07-18 191515" src="https://github.com/user-attachments/assets/ce5d10c3-4916-4ec9-bac0-4f8501b18993" />

---

## What It Does

The **AMS2 XML Backup Tool** creates timestamped backups of all your custom AI driver files from `UserData\CustomAIDrivers\`, then restores them exactly where they came from when you need them back. No data is ever deleted — only overwritten or added.

### Why You Need This

1. **Back up** your custom AI files.
2. **Restore** your custom AI files when you need.

---

## Features

- **Zero-Deletion Guarantee** — Restore only overwrites matching files and adds new ones. Nothing is ever removed.
- **Preview Before Restore** — See exactly what will happen (overwrite count, new files, unchanged files) before you commit.
- **MD5 Hash Verification** — Every backup records file hashes. Verify integrity anytime.
- **Timestamped Backups** — Each backup is dated so you know exactly when it was made.
- **User-Chosen Config Location** — Store your config in Home, Documents, or a custom folder.
- **Custom Icon Support** — Bundled `.ico` and `.png` icons work out of the box.
- **Lightweight** — Single `.exe` file, no installation needed.

---

## Supported File Types

The tool automatically detects and backs up:

| Extension | Example |
|-----------|---------|
| `.xml` | `F-Hitech_Gen1.xml` |
| `.xml.orig` | `F-Hitech_Gen1.xml.orig` |
| `.xml.backup` | `F-Hitech_Gen1.xml.backup` |
| `.backup` | `drivers.backup` |
| `.txt` | `readme.txt` |

---

## Download

Grab the latest release from the [Releases](../../releases) page. Just one `.exe` file — download and run.

> **Requirements:** Windows 10/11. No Python or other dependencies needed.

---

## How to Use

### First Launch

1. Run `AMS2 XML Backup Tool.exe`
2. Choose where to store your config file (Home, Documents, or a custom folder)
3. Browse to your AMS2 `UserData\CustomAIDrivers` folder
4. Choose a backup destination folder

### Backing Up

1. Click **Back Up Now**
2. All files in `CustomAIDrivers` are copied to a timestamped folder
3. A manifest is saved with file hashes for verification

### Restoring

1. Select a backup from the list
2. Click **Preview Restore** to see exactly what will happen
3. Review the report (overwrite / new / unchanged / deleted = 0)
4. Click **Proceed with Restore**
5. Your files are back exactly where they came from

### Settings

Click **Settings** anytime to:
- Change your config file location
- Reset and re-choose on next launch

---

## Workflow Example

```
Before Career Mode App:
  1. Launch AMS2 XML Backup Tool
  2. Click "Back Up Now"
  3. Close the tool
  4. Launch Career Mode App and play

After Career Mode App:
  1. Launch AMS2 XML Backup Tool
  2. Select your backup
  3. Click "Preview Restore" → review
  4. Click "Proceed with Restore"
  5. Your custom AI drivers are restored
```

---

## Building from Source

If you want to build the `.exe` yourself:

### Prerequisites

```bash
pip install Pillow
pip install pyinstaller
```

### Build Command

```bash
python -m PyInstaller --onefile --windowed --name "AMS2 XML Backup Tool" --icon=icon.ico --add-data "icon.ico;." --add-data "AMS2 XML Backup Icon.png;." AMS2_XML_Backup_Tool.py
```

The `--add-data` flags bundle the icons into the `.exe` so users don't need separate icon files.

---

## Technical Details

### How It Works

- **Backup:** Copies all matching files from `CustomAIDrivers` to a dated subfolder in your chosen backup location. Preserves relative folder structure.
- **Restore:** Iterates through the backup, overwrites files that exist and differ, copies in files that don't exist, and leaves everything else untouched. Deleted files count is always zero.
- **Config:** A small JSON file stores your paths. You choose where it lives.

### How Icons Work in the Bundled .exe

PyInstaller's `--onefile` mode extracts bundled files to a temporary folder at runtime. The app uses `sys._MEIPASS` to locate the extracted icons automatically:

```python
def _get_app_dir(self) -> Path:
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller onefile: files extracted to temp folder
        return Path(sys._MEIPASS)
    else:
        # Python script: files in .py folder
        return Path(__file__).parent
```

This means icons work seamlessly whether you're running the `.py` script or the bundled `.exe`.

---

## File Structure

```
AMS2 XML Backup Tool.exe          # Main application
icon.ico                           # Window icon (bundled)
AMS2 XML Backup Icon.png           # Header image (bundled)
```

---

## FAQ

**Q: Will this delete any of my files?**

A: No. The restore process never deletes anything. It only overwrites files that match by name and differ in content, and copies in files that don't exist yet.

**Q: Can I restore a backup?**

A: Yes.

**Q: Does this back up my livery textures?**

A: No, and it doesn't need to. This tool only backs up the small XML files in `UserData\CustomAIDrivers`. The livery textures in `Vehicles\Textures\Custom Liveries\` are not touched.

**Q: Can I move the .exe after building it?**

A: Yes. The `.exe` is fully portable. Just keep it somewhere you remember, since your config and backup paths are stored separately.

**Q: What if I choose the wrong config location on first launch?**

A: Click **Settings** in the app and choose again, or delete the config file and restart — the setup dialog will reappear.

---

## License

[MIT License](LICENSE)

---

> **Disclaimer:** This tool is an independent utility and is not affiliated with Reiza Studios or Automobilista 2. Use at your own risk. Always verify your backups before relying on them.
