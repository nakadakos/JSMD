import requests, os, threading, concurrent.futures, subprocess, platform, pyperclip, sys, hashlib, shutil, webbrowser
import customtkinter as ctk
from tkinter import filedialog, messagebox
from packaging.version import Version
from PIL import Image
from io import BytesIO
from collections import Counter

# ------------------------
# CONFIG
# ------------------------

api = "https://api.modrinth.com/v2"
MAX_THREADS = 6
search_after_id = None
icon_cache = {}
loading_label = None
loading_animation_running = False
spinner_index = 0
SPINNER_FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
GRID_COLS = 3

DEFAULT_MODS = {
    "Fabric API": "P7dR8mSH",
    "Sodium": "AANobbMI",
    "Lithium": "gvQqBUqZ",
    "Mod Menu": "mOgUt4GM",
    "Cloth Config": "9s6osm5g",
    "Iris": "YL57xq9U"
}

mods_dict = DEFAULT_MODS.copy()
mod_vars = {}

installed_mods = {}
installed_mod_vars = {}
inferred_version = None

# ------------------------
# FUNCTIONS
# ------------------------

# GENERAL

def getModsFolder():
    appdata = os.getenv("APPDATA")
    if appdata:
        path = os.path.join(appdata, ".minecraft", "mods")
        os.makedirs(path, exist_ok=True)
        return path
    return ""


def get_mc_versions():
    try:
        res = requests.get(f"{api}/tag/game_version")
        data = res.json()
        versions = []
        for v in data:
            if v["version_type"] == "release":
                ver = v["version"]
                try:
                    if Version(ver) >= Version("1.16.1"):
                        versions.append(ver)
                except:
                    pass
        return sorted(versions, key=Version, reverse=True)
    except:
        return ["1.21", "1.20.1", "1.19.4", "1.18.2"]


def get_icon(icon_url, size=(24, 24)):
    if not icon_url:
        return None
    if icon_url in icon_cache:
        if isinstance(icon_cache[icon_url], ctk.CTkImage):
            return icon_cache[icon_url]
    try:
        r = requests.get(icon_url, timeout=5)
        img = Image.open(BytesIO(r.content))
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        icon_cache[icon_url] = ctk_img
        return ctk_img
    except:
        return None


def get_project_icon(mod_id):
    try:
        r = requests.get(f"{api}/project/{mod_id}", timeout=5)
        return r.json().get("icon_url")
    except:
        return None


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    path = os.path.join(base_path, relative_path)
    if not os.path.exists(path):
        for _ in range(3):
            base_path = os.path.dirname(base_path)
            path = os.path.join(base_path, relative_path)
            if os.path.exists(path):
                break
    return path


# SPINNER

def start_spinner():
    global loading_label, loading_animation_running, spinner_index
    loading_animation_running = True
    spinner_index = 0
    for widget in results_frame.winfo_children():
        widget.destroy()
    loading_label = ctk.CTkLabel(results_frame, text="Searching...", font=("Arial", 15))
    loading_label.pack(pady=20)
    animate_spinner()


def animate_spinner():
    global spinner_index
    if not loading_animation_running:
        return
    frame = SPINNER_FRAMES[spinner_index % len(SPINNER_FRAMES)]
    loading_label.configure(text=f"{frame} Searching mods...")
    spinner_index += 1
    root.after(80, animate_spinner)


def perform_search_with_spinner(query):
    root.after(0, start_spinner)
    perform_search(query)
    root.after(0, stop_spinner)


def stop_spinner():
    global loading_animation_running
    loading_animation_running = False
    if loading_label:
        loading_label.destroy()


# FOLDER ACTIONS

def choose_folder():
    folder = filedialog.askdirectory()
    if folder:
        folder_var.set(folder)


def copy_folder_path():
    path = folder_var.get()
    if path:
        try:
            pyperclip.copy(path)
        except:
            messagebox.showerror("Error", "Failed to copy path.")


def open_folder_path():
    path = folder_var.get()
    if not path or not os.path.exists(path):
        messagebox.showerror("Error", "Folder does not exist.")
        return
    try:
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except:
        messagebox.showerror("Error", "Failed to open folder.")


# MOD CHECKBOXES (Download list)

def add_mod_checkbox(name, mod_id, icon_url=None):
    if name in mod_vars:
        return
    mods_dict[name] = mod_id
    var = ctk.BooleanVar(value=True)
    index = len(mod_vars)
    row = index // GRID_COLS
    col = index % GRID_COLS
    container = ctk.CTkFrame(mods_frame, fg_color="transparent")
    container.grid(row=row, column=col, padx=10, pady=10, sticky="w")
    icon = get_icon(icon_url, size=(28, 28))
    if icon:
        icon_label = ctk.CTkLabel(container, image=icon, text="")
        icon_label.pack(side="left", padx=(0, 6))
    checkbox = ctk.CTkCheckBox(container, text=name, variable=var)
    checkbox.pack(side="left")
    mod_vars[name] = var


# SEARCH

def add_mod_from_search(name, mod_id, icon_url=None):
    add_mod_checkbox(name, mod_id, icon_url)
    progress_label.configure(text=f"Added: {name}")


def perform_search(query):
    if not query.strip():
        return
    try:
        res = requests.get(
            f"{api}/search",
            params={
                "query": query,
                "facets": '[["categories:fabric"]]',
                "limit": 10
            }
        )
        results = res.json()["hits"]
        for mod in results:
            url = mod.get("icon_url")
            if url and url not in icon_cache:
                try:
                    r = requests.get(url, timeout=3)
                    mod["_pil_img"] = Image.open(BytesIO(r.content))
                except:
                    mod["_pil_img"] = None
        root.after(0, lambda: update_search_results(results))
    except:
        pass


def update_search_results(results):
    for widget in results_frame.winfo_children():
        widget.destroy()
    for mod in results:
        name = mod["title"]
        mod_id = mod["project_id"]
        icon_url = mod.get("icon_url")
        pil_img = mod.get("_pil_img")
        
        if pil_img and icon_url not in icon_cache:
            icon_cache[icon_url] = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(24, 24))
            
        icon = icon_cache.get(icon_url)
        if not icon and icon_url:
            icon = get_icon(icon_url, size=(24, 24))

        btn = ctk.CTkButton(
            results_frame,
            text=name,
            image=icon,
            compound="left",
            command=lambda n=name, m=mod_id, i=icon_url: add_mod_from_search(n, m, i)
        )
        btn.pack(fill="x", padx=5, pady=2)


def on_search_key(event):
    global search_after_id
    query = search_entry.get().strip()
    if search_after_id:
        root.after_cancel(search_after_id)
    if query == "":
        for widget in results_frame.winfo_children():
            widget.destroy()
        return
    search_after_id = root.after(
        400,
        lambda: threading.Thread(
            target=perform_search_with_spinner,
            args=(query,),
            daemon=True
        ).start()
    )


# DOWNLOAD

def get_download_url(mod_id, mc_version):
    res = requests.get(f"{api}/project/{mod_id}/version")
    for v in res.json():
        if mc_version in v["game_versions"] and "fabric" in v["loaders"]:
            return v["files"][0]["url"]
    return None


def download_file(mod, mod_id, mc_version, folder):
    url = get_download_url(mod_id, mc_version)
    if not url:
        return ("missing", mod)
    try:
        filename = url.split("/")[-1]
        path = os.path.join(folder, filename)
        r = requests.get(url)
        with open(path, "wb") as f:
            f.write(r.content)
        return ("downloaded", mod)
    except:
        return ("failed", mod)


def start_download_thread():
    threading.Thread(target=start_download, daemon=True).start()


def start_download():
    folder = folder_var.get()
    version = version_var.get()
    selected = [
        (mod, mods_dict[mod])
        for mod, var in mod_vars.items()
        if var.get()
    ]
    total = len(selected)
    if total == 0:
        messagebox.showwarning("No Mods Selected", "Please select at least one mod.")
        return
    progress_bar.set(0)
    downloaded = []
    missing = []
    failed = []
    with concurrent.futures.ThreadPoolExecutor(MAX_THREADS) as executor:
        futures = {
            executor.submit(download_file, mod, mod_id, version, folder): mod
            for mod, mod_id in selected
        }
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result, mod = future.result()
            if result == "downloaded":
                downloaded.append(mod)
            elif result == "missing":
                missing.append(mod)
            else:
                failed.append(mod)
            progress_bar.set((i + 1) / total)
            progress_label.configure(text=f"{i + 1}/{total} completed")

    summary = f"Download Summary for Minecraft {version}\n\n"
    if downloaded:
        summary += f"Downloaded ({len(downloaded)}):\n" + "\n".join(downloaded) + "\n\n"
    if missing:
        summary += f"Not Available for this version ({len(missing)}):\n" + "\n".join(missing) + "\n\n"
    if failed:
        summary += f"Failed ({len(failed)}):\n" + "\n".join(failed) + "\n\n"
    messagebox.showinfo("Download Complete", summary)


# -----------------------------------------------
# INSTALLED MODS SCANNING & VERSION INFERENCE
# -----------------------------------------------

def sha512_of_file(filepath):
    h = hashlib.sha512()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def lookup_mod_by_hash(sha512):
    try:
        res = requests.post(
            f"{api}/version_files",
            json={"hashes": [sha512], "algorithm": "sha512"},
            timeout=10
        )
        data = res.json()
        if sha512 in data:
            version_data = data[sha512]
            project_id = version_data.get("project_id")
            game_versions = version_data.get("game_versions", [])
            loaders = version_data.get("loaders", [])
            return project_id, game_versions, loaders
    except:
        pass
    return None, [], []


def get_project_name(project_id):
    try:
        res = requests.get(f"{api}/project/{project_id}", timeout=5)
        data = res.json()
        return data.get("title", project_id), data.get("icon_url")
    except:
        return project_id, None


def scan_installed_mods_worker():
    """Scans the mods folder, identifies each .jar via Modrinth hash, infers MC version."""
    global installed_mods, inferred_version

    folder = folder_var.get()
    if not folder or not os.path.exists(folder):
        return

    jars = [f for f in os.listdir(folder) if f.endswith(".jar")]

    if not jars:
        root.after(0, lambda: scan_status_label.configure(text="No mods found in folder."))
        root.after(0, refresh_installed_mods_ui)
        return

    root.after(0, lambda: scan_status_label.configure(text=f"⠸ Scanning {len(jars)} mod(s)..."))

    found = {}
    all_mc_versions = []

    def process_jar(filename):
        filepath = os.path.join(folder, filename)
        sha = sha512_of_file(filepath)
        project_id, game_versions, loaders = lookup_mod_by_hash(sha)

        if project_id and "fabric" in loaders:
            name, icon_url = get_project_name(project_id)
            pil_img = None
            if icon_url and icon_url not in icon_cache:
                try:
                    r = requests.get(icon_url, timeout=3)
                    pil_img = Image.open(BytesIO(r.content))
                except:
                    pass
            return filename, {
                "name": name,
                "mod_id": project_id,
                "game_versions": game_versions,
                "icon_url": icon_url,
                "filename": filename,
                "_pil_img": pil_img
            }
        else:
            # Unknown mod — store with filename as name
            return filename, {
                "name": filename.replace(".jar", ""),
                "mod_id": None,
                "game_versions": [],
                "icon_url": None,
                "filename": filename,
                "_pil_img": None
            }

    with concurrent.futures.ThreadPoolExecutor(MAX_THREADS) as executor:
        futures = {executor.submit(process_jar, jar): jar for jar in jars}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            filename, info = future.result()
            found[filename] = info
            all_mc_versions.extend(info["game_versions"])
            root.after(0, lambda i=i: scan_status_label.configure(
                text=f"⠸ Scanned {i+1}/{len(jars)} mod(s)..."
            ))

    installed_mods = found

    # pick the most common MC version across all mods
    release_versions = []
    for v in all_mc_versions:
        try:
            if Version(v) >= Version("1.16.1"):
                release_versions.append(v)
        except:
            pass

    if release_versions:
        version_counts = Counter(release_versions)
        inferred_version = version_counts.most_common(1)[0][0]
    else:
        inferred_version = None

    root.after(0, refresh_installed_mods_ui)
    root.after(0, lambda: scan_status_label.configure(
        text=f"✔ Found {len(found)} mod(s)" +
             (f" — Inferred version: {inferred_version}" if inferred_version else " — Version unknown")
    ))
    old_label = inferred_version if inferred_version else "Unknown"
    root.after(0, lambda: backup_folder_var.set(f"mods_{old_label}"))


def refresh_installed_mods_ui():
    global installed_mod_vars
    installed_mod_vars = {}

    for widget in installed_mods_frame.winfo_children():
        widget.destroy()

    if not installed_mods:
        ctk.CTkLabel(installed_mods_frame, text="No mods detected.", text_color="gray").pack(pady=10)
        return

    for filename, info in installed_mods.items():
        name = info["name"]
        icon_url = info["icon_url"]
        pil_img = info.get("_pil_img")

        var = ctk.BooleanVar(value=True)
        installed_mod_vars[filename] = var

        row_frame = ctk.CTkFrame(installed_mods_frame, fg_color="transparent")
        row_frame.pack(fill="x", padx=5, pady=2)

        if pil_img and icon_url not in icon_cache:
            icon_cache[icon_url] = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(22, 22))
            
        icon = icon_cache.get(icon_url)
        if not icon and icon_url:
            icon = get_icon(icon_url, size=(22, 22))
            
        if icon:
            ctk.CTkLabel(row_frame, image=icon, text="").pack(side="left", padx=(0, 5))

        ctk.CTkCheckBox(row_frame, text=name, variable=var).pack(side="left")

        vers = info.get("game_versions", [])
        if vers:
            # Show highest version supported
            try:
                best = sorted([v for v in vers], key=Version, reverse=True)[0]
                ctk.CTkLabel(row_frame, text=f"[{best}]", text_color="gray",
                             font=("Arial", 11)).pack(side="right", padx=5)
            except:
                pass


def scan_installed_mods():
    threading.Thread(target=scan_installed_mods_worker, daemon=True).start()


# -----------------------------------------------
# VERSION SWITCH
# -----------------------------------------------

def switch_version_thread():
    threading.Thread(target=switch_version_worker, daemon=True).start()


def switch_version_worker():
    folder = folder_var.get()
    new_version = version_var.get()
    old_version = inferred_version

    if not folder or not os.path.exists(folder):
        messagebox.showerror("Error", "Mods folder does not exist.")
        return

    # get selected installed mods to include in the switch
    selected_installed = {
        filename: installed_mods[filename]
        for filename, var in installed_mod_vars.items()
        if var.get() and filename in installed_mods
    }

    if not selected_installed and not installed_mods:
        messagebox.showwarning("No Mods", "No installed mods detected. Please scan your mods folder first.")
        return

    # build confirm message
    old_label = old_version if old_version else "Unknown"
    backup_folder_name = backup_folder_var.get().strip()
    if not backup_folder_name:
        backup_folder_name = "mods_backup"
    backup_path = os.path.join(os.path.dirname(folder), backup_folder_name)

    mod_names = [info["name"] for info in selected_installed.values()]
    mod_list_preview = "\n  • ".join(mod_names[:10])
    if len(mod_names) > 10:
        mod_list_preview += f"\n  ... and {len(mod_names) - 10} more"

    confirm_msg = (
        f"Version Switch: {old_label}  →  {new_version}\n\n"
        f"The following will happen:\n"
        f"  1. Current mods will be moved to:\n     {backup_path}\n\n"
        f"  2. Compatible versions of {len(selected_installed)} mod(s) will be\n"
        f"     downloaded for Minecraft {new_version}:\n"
        f"  • {mod_list_preview}\n\n"
        f"Mods with no known project ID will only be backed up.\n\n"
        f"Do you want to proceed?"
    )

    confirmed = messagebox.askyesno("Confirm Version Switch", confirm_msg)
    if not confirmed:
        return

    root.after(0, lambda: progress_label.configure(text="Backing up old mods..."))
    root.after(0, lambda: progress_bar.set(0))

    # mmove old mods to backup folder
    os.makedirs(backup_path, exist_ok=True)
    jars_in_folder = [f for f in os.listdir(folder) if f.endswith(".jar")]

    for jar in jars_in_folder:
        src = os.path.join(folder, jar)
        dst = os.path.join(backup_path, jar)
        try:
            shutil.move(src, dst)
        except Exception as e:
            pass

    root.after(0, lambda: progress_label.configure(
        text=f"Backed up {len(jars_in_folder)} file(s) to {backup_folder_name}"
    ))

    # download new versions of identified mods
    to_download = [
        (info["name"], info["mod_id"])
        for info in selected_installed.values()
        if info.get("mod_id")
    ]

    total = len(to_download)
    if total == 0:
        messagebox.showinfo("Done", f"Mods backed up to '{backup_folder_name}'.\nNo mods with known IDs to download.")
        root.after(0, scan_installed_mods)
        return

    downloaded = []
    missing = []
    failed = []

    with concurrent.futures.ThreadPoolExecutor(MAX_THREADS) as executor:
        futures = {
            executor.submit(download_file, name, mod_id, new_version, folder): name
            for name, mod_id in to_download
        }
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result, mod = future.result()
            if result == "downloaded":
                downloaded.append(mod)
            elif result == "missing":
                missing.append(mod)
            else:
                failed.append(mod)
            root.after(0, lambda i=i: progress_bar.set((i + 1) / total))
            root.after(0, lambda i=i, mod=mod: progress_label.configure(
                text=f"Downloading: {i+1}/{total}"
            ))

    summary = f"Version Switch Complete: {old_label} → {new_version}\n\n"
    summary += f"Old mods backed up to: {backup_folder_name}\n\n"
    if downloaded:
        summary += f"Downloaded ({len(downloaded)}):\n" + "\n".join(downloaded) + "\n\n"
    if missing:
        summary += f"Not Available for {new_version} ({len(missing)}):\n" + "\n".join(missing) + "\n\n"
    if failed:
        summary += f"Failed ({len(failed)}):\n" + "\n".join(failed) + "\n\n"

    messagebox.showinfo("Switch Complete", summary)

    # Rescan after switch
    root.after(0, scan_installed_mods)


# ------------------------
# GUI & STARTUP
# ------------------------

def populate_default_mods_bg():
    mods_info = []
    with concurrent.futures.ThreadPoolExecutor(MAX_THREADS) as executor:
        futures = {executor.submit(get_project_icon, mod_id): (mod, mod_id) for mod, mod_id in mods_dict.items()}
        for future in concurrent.futures.as_completed(futures):
            mod, mod_id = futures[future]
            icon_url = future.result()
            img = None
            if icon_url and icon_url not in icon_cache:
                try:
                    r = requests.get(icon_url, timeout=5)
                    img = Image.open(BytesIO(r.content))
                except:
                    pass
            mods_info.append((mod, mod_id, icon_url, img))
            
    root.after(0, lambda: apply_default_mods(mods_info))

def apply_default_mods(mods_info):
    for mod, mod_id, icon_url, img in mods_info:
        if img and icon_url not in icon_cache:
            icon_cache[icon_url] = ctk.CTkImage(light_image=img, dark_image=img, size=(28, 28))
        add_mod_checkbox(mod, mod_id, icon_url)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("JSMD - Just a Simple Mod Downloader")
root.geometry("1000x800")
root.minsize(900, 700)

icon_path = resource_path("icon.ico")
if os.path.exists(icon_path):
    try:
        root.iconbitmap(icon_path)
    except Exception:
        pass

# Root layout
root.grid_columnconfigure(0, weight=1)
root.grid_rowconfigure(2, weight=1)

# ── Title & Header ──────────────────────────────────────────
header_frame = ctk.CTkFrame(root, fg_color="transparent")
header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
header_frame.grid_columnconfigure(1, weight=1)

title_label = ctk.CTkLabel(header_frame, text="JSMD", font=ctk.CTkFont(family="Arial", size=32, weight="bold"))
title_label.grid(row=0, column=0, sticky="w")

subtitle_label = ctk.CTkLabel(header_frame, text="Just a Simple Mod Downloader", font=ctk.CTkFont(family="Arial", size=14), text_color="gray")
subtitle_label.grid(row=1, column=0, sticky="w")

# ── Global Settings (Folder & Version) ─────────────────────────
settings_frame = ctk.CTkFrame(root, corner_radius=10)
settings_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
settings_frame.grid_columnconfigure(3, weight=1)

mc_versions = get_mc_versions()
version_var = ctk.StringVar(value=mc_versions[0])
folder_var = ctk.StringVar(value=getModsFolder())
backup_folder_var = ctk.StringVar(value="mods_backup")

# Version
ctk.CTkLabel(settings_frame, text="Minecraft Version:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=(20, 10), pady=15, sticky="w")
version_menu = ctk.CTkOptionMenu(settings_frame, values=mc_versions, variable=version_var, width=140)
version_menu.grid(row=0, column=1, padx=10, pady=15, sticky="w")

# Folder
ctk.CTkLabel(settings_frame, text="Mods Folder:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=(30, 10), pady=15, sticky="w")
folder_label = ctk.CTkLabel(settings_frame, textvariable=folder_var, text_color="gray", anchor="w")
folder_label.grid(row=0, column=3, padx=10, pady=15, sticky="ew")

folder_btn_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
folder_btn_frame.grid(row=0, column=4, padx=20, pady=15, sticky="e")
ctk.CTkButton(folder_btn_frame, text="Change", command=choose_folder, width=80).pack(side="left", padx=5)
ctk.CTkButton(folder_btn_frame, text="Open", command=open_folder_path, width=80).pack(side="left", padx=5)

# ── Tabview ──────────────────────────────────────────
tabview = ctk.CTkTabview(root, corner_radius=10)
tabview.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))

tab_download = tabview.add("Download Mods")
tab_manage = tabview.add("Manage Installed Mods")

tab_download.grid_columnconfigure(0, weight=1)
tab_download.grid_rowconfigure(3, weight=1)

tab_manage.grid_columnconfigure(0, weight=1)
tab_manage.grid_rowconfigure(1, weight=1)

# ==========================================
# --- DOWNLOAD TAB ---
# ==========================================
# Search
search_frame = ctk.CTkFrame(tab_download, fg_color="transparent")
search_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
search_frame.grid_columnconfigure(0, weight=1)

search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search Modrinth for Fabric mods...", height=35)
search_entry.grid(row=0, column=0, sticky="ew")
search_entry.bind("<KeyRelease>", on_search_key)

# Search Results
results_frame = ctk.CTkScrollableFrame(tab_download, height=130, corner_radius=8)
results_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 10))

# Mods to Download
mods_header = ctk.CTkLabel(tab_download, text="Selected Mods to Download", font=ctk.CTkFont(size=16, weight="bold"))
mods_header.grid(row=2, column=0, sticky="w", padx=15, pady=(10, 5))

mods_frame = ctk.CTkScrollableFrame(tab_download, corner_radius=8)
mods_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))

# Download Action
action_frame = ctk.CTkFrame(tab_download, fg_color="transparent")
action_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(5, 15))
action_frame.grid_columnconfigure(0, weight=1)

progress_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
progress_frame.grid(row=0, column=0, sticky="ew", padx=(0, 15))
progress_frame.grid_columnconfigure(0, weight=1)

progress_bar = ctk.CTkProgressBar(progress_frame, height=10)
progress_bar.set(0)
progress_bar.grid(row=0, column=0, sticky="ew", pady=(0, 5))

progress_label = ctk.CTkLabel(progress_frame, text="Ready", text_color="gray", font=ctk.CTkFont(size=12))
progress_label.grid(row=1, column=0, sticky="w")

download_btn = ctk.CTkButton(action_frame, text="⬇ Download Selected", command=start_download_thread, height=45, font=ctk.CTkFont(size=15, weight="bold"))
download_btn.grid(row=0, column=1)

# ==========================================
# --- MANAGE TAB ---
# ==========================================
manage_top_frame = ctk.CTkFrame(tab_manage, fg_color="transparent")
manage_top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
manage_top_frame.grid_columnconfigure(1, weight=1)

scan_btn = ctk.CTkButton(manage_top_frame, text="🔍 Scan Mods Folder", command=scan_installed_mods, fg_color="#2d6a4f", hover_color="#1b4332", height=35, font=ctk.CTkFont(weight="bold"))
scan_btn.grid(row=0, column=0, padx=(0, 15))

scan_status_label = ctk.CTkLabel(manage_top_frame, text="Click 'Scan Mods Folder' to detect installed mods.", text_color="gray", font=ctk.CTkFont(size=13))
scan_status_label.grid(row=0, column=1, sticky="w")

add_mod_btn = ctk.CTkButton(manage_top_frame, text="➕ Add Mod", command=lambda: tabview.set("Download Mods"), height=35, font=ctk.CTkFont(weight="bold"), width=120)
add_mod_btn.grid(row=0, column=2, padx=(15, 0))

installed_mods_frame = ctk.CTkScrollableFrame(tab_manage, corner_radius=8)
installed_mods_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

manage_bottom_frame = ctk.CTkFrame(tab_manage, fg_color="transparent")
manage_bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 15))
manage_bottom_frame.grid_columnconfigure(0, weight=1)

switch_info = ctk.CTkLabel(manage_bottom_frame, text="Switch Version: backs up current mods and downloads them for the selected target version.", text_color="gray", justify="left")
switch_info.grid(row=0, column=0, sticky="w")

backup_frame = ctk.CTkFrame(manage_bottom_frame, fg_color="transparent")
backup_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
backup_frame.grid_columnconfigure(1, weight=1)

ctk.CTkLabel(backup_frame, text="Backup Folder Name:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 10))
backup_entry = ctk.CTkEntry(backup_frame, textvariable=backup_folder_var, width=150)
backup_entry.grid(row=0, column=1, sticky="w")

switch_btn = ctk.CTkButton(backup_frame, text="⚡ Switch Version", command=switch_version_thread, fg_color="#5c4a1e", hover_color="#3d2b0e", height=40, font=ctk.CTkFont(weight="bold"))
switch_btn.grid(row=0, column=2, padx=(10, 0))

# ── Footer ──────────────────────────────────────────
footer_frame = ctk.CTkFrame(root, fg_color="transparent")
footer_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))
footer_frame.grid_columnconfigure(0, weight=1)

designer_label = ctk.CTkLabel(footer_frame, text="Designed by Nakadakos", text_color="gray", font=ctk.CTkFont(size=12))
designer_label.grid(row=0, column=0, sticky="w")

def open_feedback():
    webbrowser.open("https://github.com/nakadakos/JSMD/issues")

feedback_btn = ctk.CTkButton(footer_frame, text="Report Error / Feedback", command=open_feedback, fg_color="transparent", text_color="#aaaaaa", hover_color="#333333", font=ctk.CTkFont(size=12, underline=True), width=150, height=20, cursor="hand2")
feedback_btn.grid(row=0, column=1, sticky="e")

# Start background fetch of default mods
threading.Thread(target=populate_default_mods_bg, daemon=True).start()

root.mainloop()
