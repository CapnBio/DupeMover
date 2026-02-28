# DupeMover

**DupeMover** is a powerful, web-based tool designed for media collectors who want to maintain a clean and organized library. While it integrates seamlessly with Plex, it focuses on giving users manual control over their file system to resolve duplicates and misorganized media.

## 🚀 Overview

Have you ever found TV episodes mistakenly filed in your Movies folder? Or discovered you have multiple versions of the same movie (4K, 1080p, and a "Sample" file) taking up precious disk space? 

**DupeMover** finds these duplicates across your entire library and provides a simple, manual interface to either **Delete** the extra copies or **Move** them to the correct directory—all from your web browser.

## ✨ Key Features

- **🔍 Smart Duplicate Scanning:** Automatically identifies Movies and TV Episodes with multiple files in your library.
- **📂 Manual File Mover:** Move files between directories (e.g., from a "Movies" landing zone to a "TV Shows" folder) with a single click.
- **✨ Destination Preview:** See exactly where a file will land before you confirm the move.
- **🗑️ Safe Deletion:** Permanently remove duplicate files or samples with clear confirmation prompts.
- **📦 Bulk Actions:** Select multiple files at once to move or delete them in batches.
- **🔗 Plex Integration:** Connects securely to your Plex server using official OAuth PIN authentication.
- **📍 Library Awareness:** Automatically detects and suggests your existing Plex library folders as destinations for moving files.
- **📱 Responsive Design:** A clean, mobile-friendly interface with "sticky" action buttons for easy access while scrolling long lists.

## 🛠️ Installation

### Prerequisites
- Python 3.7+
- A Plex Media Server

### Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/dupemover.git
   cd dupemover
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python3 app.py
   ```

4. **Access the web UI:**
   Open your browser and navigate to `http://localhost:5055`

## 📖 Usage Guide

1. **Login:** Use the default password `admin` (can be changed in Settings).
2. **Connect Plex:** Follow the "Setup Plex Connection" prompts to link your server.
3. **Configure Targets (Optional):** In **Settings**, you can manually add absolute paths for move destinations, though DupeMover will also automatically list your Plex library folders.
4. **Scan:** Click **Scan for Duplicates** on the dashboard.
5. **Manage:**
   - **Click a row** to select a file.
   - Use the **Move** button to relocate a file to a new folder.
   - Use the **Delete** button to remove unwanted duplicates.
   - Use the **Sticky Header** buttons to perform these actions on all selected files at once.

## 🛡️ Security
- **Authentication:** All actions are protected by a web password.
- **Privacy:** Your Plex token and configuration are stored locally in `config.json`.
- **Manual Control:** No files are ever moved or deleted automatically. Every action requires user confirmation.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
