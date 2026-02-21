import requests, os, threading, concurrent.futures, subprocess, platform, pyperclip, sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
from packaging.version import Version
from PIL import Image
from io import BytesIO

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
GRID_ROWS = 3

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

# ------------------------
# FUCNTIONS
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
        return icon_cache[icon_url]

    try:
        r = requests.get(icon_url, timeout=5)
        img = Image.open(BytesIO(r.content)).resize(size)
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
        icon_cache[icon_url] = ctk_img
        return ctk_img
    except:
        return None


def start_spinner():
    global loading_label, loading_animation_running, spinner_index

    loading_animation_running = True
    spinner_index = 0

    for widget in results_frame.winfo_children():
        widget.destroy()

    loading_label = ctk.CTkLabel(
        results_frame,
        text="Searching...",
        font=("Arial", 15)
    )

    loading_label.pack(pady=20)
    animate_spinner()


def animate_spinner():
    global spinner_index
    if not loading_animation_running:
        return
    frame = SPINNER_FRAMES[spinner_index % len(SPINNER_FRAMES)]
    loading_label.configure(
        text=f"{frame} Searching mods..."
    )
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


def add_mod_checkbox(name, mod_id, icon_url=None):
    if name in mod_vars:
        return

    mods_dict[name] = mod_id
    var = ctk.BooleanVar(value=True)
    index = len(mod_vars)

    col = index // GRID_ROWS
    row = index % GRID_ROWS

    container = ctk.CTkFrame(mods_frame, fg_color="transparent")

    container.grid(
        row=row,
        column=col,
        padx=15,
        pady=10,
        sticky="w"
    )

    icon = get_icon(icon_url, size=(28, 28))

    if icon:
        icon_label = ctk.CTkLabel(
            container,
            image=icon,
            text=""
        )
        icon_label.pack(side="left", padx=(0, 6))

    checkbox = ctk.CTkCheckBox(
        container,
        text=name,
        variable=var
    )

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
        root.after(0, lambda: update_search_results(results))
    except:
        pass


def update_search_results(results):
    for widget in results_frame.winfo_children():
        widget.destroy()

    for mod in results:

        name = mod["title"]
        mod_id = mod["project_id"]
        icon = get_icon(mod.get("icon_url"))

        btn = ctk.CTkButton(
            results_frame,
            text=name,
            image=icon,
            compound="left",
            command=lambda n=name, m=mod_id, i=mod.get("icon_url"): add_mod_from_search(n, m, i)
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

            progress_bar.set((i+1)/total)

            progress_label.configure(
                text=f"{i+1}/{total} completed"
            )

# SUMMARY
    summary = f"Download Summary for Minecraft {version}\n\n"

    if downloaded:
        summary += f"Downloaded ({len(downloaded)}):\n"
        summary += "\n".join(downloaded) + "\n\n"

    if missing:
        summary += f"Not Available for this version ({len(missing)}):\n"
        summary += "\n".join(missing) + "\n\n"

    if failed:
        summary += f"Failed ({len(failed)}):\n"
        summary += "\n".join(failed) + "\n\n"

    messagebox.showinfo("Download Complete", summary)
# ------------------------
# GUI
# ------------------------

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("JSMD - Just a Simple Mod Downloader")
root.geometry("600x800")
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

root.iconbitmap(resource_path("icon.ico"))

# Title
ctk.CTkLabel(root, text="JSMD - Just a Simple Mod Downloader",
             font=("Arial", 26)).pack(pady=10)

# Version
version_var = ctk.StringVar(value=get_mc_versions()[0])

ctk.CTkOptionMenu(root,
                  values=get_mc_versions(),
                  variable=version_var).pack(pady=5)

# Folder
folder_var = ctk.StringVar(value=getModsFolder())

folder_frame = ctk.CTkFrame(root, fg_color="transparent")
folder_frame.pack(pady=5)

ctk.CTkButton(folder_frame,
              text="Select Folder",
              command=choose_folder,
              width=140).grid(row=0, column=0, padx=5)

ctk.CTkButton(folder_frame,
              text="Copy Path",
              command=copy_folder_path,
              width=120).grid(row=0, column=1, padx=5)

ctk.CTkButton(folder_frame,
              text="Open Folder",
              command=open_folder_path,
              width=120).grid(row=0, column=2, padx=5)

ctk.CTkLabel(root,
             textvariable=folder_var,
             wraplength=550).pack()
# Search

search_entry = ctk.CTkEntry(root,
                            placeholder_text="Search mods...",
                            )

search_entry.pack(pady=5)
search_entry.bind("<KeyRelease>", on_search_key)

results_frame = ctk.CTkScrollableFrame(root,
                                        width=550,
                                        height=120)
results_frame.pack(pady=5)

# Mods list
mods_frame = ctk.CTkScrollableFrame(root,
                                    width=550,
                                    height=150,
                                    orientation="horizontal")

mods_frame.pack(pady=10)

def get_project_icon(mod_id):
    try:
        r = requests.get(f"{api}/project/{mod_id}", timeout=5)
        return r.json().get("icon_url")
    except:
        return None


for mod, mod_id in mods_dict.items():
    icon_url = get_project_icon(mod_id)
    add_mod_checkbox(mod, mod_id, icon_url)

# Progress
progress_bar = ctk.CTkProgressBar(root, width=400)
progress_bar.pack(pady=10)

progress_label = ctk.CTkLabel(root, text="")
progress_label.pack()

# Download
ctk.CTkButton(root,
              text="Download Mods",
              command=start_download_thread,
              height=40).pack(pady=20)

root.mainloop()