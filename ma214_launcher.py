import os
import json
import shutil
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk

IMAGE = "buintrostats/learnr-lessons:latest" # This should match the image name in the Dockerfile
CONTAINER_NAME = "learnr-lessons" # This should match the container name used in the Docker run command
PORT = "3838"
APP_NAME = "MA214 Tutorial Launcher"
ADMIN_PASSWORD = os.environ.get("MA214_ADMIN_PASSWORD", "1234")
RELEASE_TIME_FORMAT = "%Y-%m-%d %H:%M"

LESSONS = {
    "Lesson 1-1": "01-lesson/01-01-lesson.Rmd", # Update these paths to match the structure in your Docker image
    "Lesson 1-2": "02-lesson/01-02-lesson.Rmd",
    "Lesson 1-3": "03-lesson/01-03-lesson.Rmd",
    "Lesson 1-4": "04-lesson/01-04-lesson.Rmd",
}


def get_app_data_dir():
    if os.name == "nt":
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
        return Path(base_dir) / APP_NAME

    if sys_platform_is_macos():
        return Path.home() / "Library" / "Application Support" / APP_NAME

    return Path.home() / f".{APP_NAME.lower().replace(' ', '-')}"


def sys_platform_is_macos():
    return os.sys.platform == "darwin"


SCHEDULE_PATH = get_app_data_dir() / "lesson_schedule.json"
lesson_schedule = {}


def default_schedule():
    return {
        lesson_name: {
            "rmd_file": rmd_file,
            "available_at": None
        }
        for lesson_name, rmd_file in LESSONS.items()
    }


def load_schedule():
    schedule = default_schedule()

    if not SCHEDULE_PATH.exists():
        return schedule

    try:
        with SCHEDULE_PATH.open("r", encoding="utf-8") as schedule_file:
            saved_schedule = json.load(schedule_file)
    except (OSError, json.JSONDecodeError):
        return schedule

    for lesson_name, settings in saved_schedule.items():
        if lesson_name in schedule and isinstance(settings, dict):
            schedule[lesson_name]["available_at"] = settings.get("available_at") or None

    return schedule


def save_schedule(schedule):
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with SCHEDULE_PATH.open("w", encoding="utf-8") as schedule_file:
        json.dump(schedule, schedule_file, indent=2)


def parse_release_time(value):
    value = value.strip()

    if not value:
        return None

    try:
        return datetime.strptime(value, RELEASE_TIME_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"Use release times like 2026-06-16 09:30."
        ) from exc


def format_release_time(value):
    if not value:
        return ""

    try:
        return datetime.strptime(value, RELEASE_TIME_FORMAT).strftime(RELEASE_TIME_FORMAT)
    except ValueError:
        return value


def get_release_time(lesson_name):
    value = lesson_schedule.get(lesson_name, {}).get("available_at")

    if not value:
        return None

    try:
        return datetime.strptime(value, RELEASE_TIME_FORMAT)
    except ValueError:
        return None


def lesson_is_available(lesson_name):
    release_time = get_release_time(lesson_name)

    if release_time is None:
        return True

    return datetime.now() >= release_time


def available_lesson_names():
    return [
        lesson_name
        for lesson_name in LESSONS
        if lesson_is_available(lesson_name)
    ]


def availability_text(lesson_name):
    release_time = get_release_time(lesson_name)

    if release_time is None:
        return "Available now"

    if datetime.now() >= release_time:
        return f"Available since {release_time.strftime(RELEASE_TIME_FORMAT)}"

    return f"Available after {release_time.strftime(RELEASE_TIME_FORMAT)}"


def find_docker():
    possible_paths = [
        shutil.which("docker"),
        shutil.which("docker.exe"),
        "/usr/local/bin/docker",
        "/opt/homebrew/bin/docker",
        os.path.expanduser("~/.docker/bin/docker"),
        "/Applications/Docker.app/Contents/Resources/bin/docker",
        os.path.expandvars(r"%ProgramFiles%\Docker\Docker\resources\bin\docker.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\Docker\Docker\resources\bin\docker.exe"),
    ]

    for path in possible_paths:
        if path and os.path.exists(path) and os.access(path, os.X_OK):
            return path

    return None


DOCKER = find_docker()


def run_command(command):
    env = os.environ.copy()

    common_docker_paths = [
        "/usr/local/bin",
        "/opt/homebrew/bin",
        os.path.expanduser("~/.docker/bin"),
        "/Applications/Docker.app/Contents/Resources/bin",
        os.path.expandvars(r"%ProgramFiles%\Docker\Docker\resources\bin"),
        os.path.expandvars(r"%LocalAppData%\Programs\Docker\Docker\resources\bin"),
    ]

    env["PATH"] = os.pathsep.join(common_docker_paths + [env.get("PATH", "")])

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )

    return result.returncode, result.stdout, result.stderr


def append_log(text):
    if "log_box" not in globals():
        return

    log_box.insert(tk.END, text + "\n")
    log_box.see(tk.END)
    root.update_idletasks()


def check_docker():
    if DOCKER is None:
        append_log("ERROR: Docker command was not found.")
        append_log("Please make sure Docker Desktop is installed.")
        return False

    append_log(f"Using Docker at: {DOCKER}")

    code, out, err = run_command([DOCKER, "info"])
    return code == 0


def stop_existing_container():
    append_log("Stopping existing tutorial container if needed...")

    subprocess.run(
        [DOCKER, "stop", CONTAINER_NAME],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    subprocess.run(
        [DOCKER, "rm", CONTAINER_NAME],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def pull_image():
    append_log(f"Pulling latest image: {IMAGE}")

    code, out, err = run_command([DOCKER, "pull", IMAGE])

    if out.strip():
        append_log(out.strip())

    if code != 0:
        append_log(err.strip())
        raise RuntimeError("Docker pull failed.")


def start_container(rmd_file):
    append_log(f"Starting tutorial: {rmd_file}")

    command = [
        DOCKER, "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", f"{PORT}:3838",
        "-e", f"RMD_FILE={rmd_file}",
        IMAGE
    ]

    code, out, err = run_command(command)

    # If port is still allocated, automatically stop the container using it and retry once
    if code != 0 and "port is already allocated" in err.lower():
        append_log("Port is already allocated.")
        append_log(f"Attempting to free port {PORT} automatically...")

        stop_containers_using_port(PORT)

        append_log("Retrying docker run...")

        code, out, err = run_command(command)

    if code != 0:
        append_log(err.strip())
        raise RuntimeError("Docker run failed.")

    container_id = out.strip()
    append_log(f"Container started: {container_id}")


def open_browser():
    url = f"http://localhost:{PORT}"
    append_log(f"Opening browser: {url}")
    webbrowser.open(url)


def stop_containers_using_port(port):
    """
    Stop and remove any Docker containers currently using the given local port.
    Example: port = "3838"
    """

    append_log(f"Checking for containers using port {port}...")

    # First try Docker's publish filter
    code, out, err = run_command([
        DOCKER, "ps", "-q",
        "--filter", f"publish={port}"
    ])

    container_ids = []

    if code == 0 and out.strip():
        container_ids = out.strip().splitlines()

    # Fallback: parse docker ps output if publish filter does not find anything
    if not container_ids:
        code, out, err = run_command([
            DOCKER, "ps",
            "--format", "{{.ID}}\t{{.Names}}\t{{.Ports}}"
        ])

        if code == 0 and out.strip():
            for line in out.strip().splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    container_id = parts[0]
                    ports_text = parts[2]

                    # Match examples:
                    # 0.0.0.0:3838->3838/tcp
                    # :::3838->3838/tcp
                    # *:3838->3838/tcp
                    if f":{port}->" in ports_text or f"0.0.0.0:{port}->" in ports_text:
                        container_ids.append(container_id)

    if not container_ids:
        append_log(f"No running containers found using port {port}.")
        return

    append_log(f"Found container(s) using port {port}: {', '.join(container_ids)}")

    for container_id in container_ids:
        append_log(f"Stopping container {container_id}...")

        subprocess.run(
            [DOCKER, "stop", container_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        subprocess.run(
            [DOCKER, "rm", container_id],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    append_log(f"Port {port} is now free.")


def launch_lesson(lesson_name):
    if not lesson_is_available(lesson_name):
        release_time = get_release_time(lesson_name)
        release_text = release_time.strftime(RELEASE_TIME_FORMAT)

        messagebox.showinfo(
            "Lesson not available yet",
            f"{lesson_name} will be available after {release_text}."
        )
        append_log(f"{lesson_name} is locked until {release_text}.")
        refresh_lesson_controls()
        return

    rmd_file = LESSONS[lesson_name]

    def task():
        try:
            append_log("")
            append_log("=" * 60)
            append_log(f"Launching {lesson_name}")
            append_log("=" * 60)

            if not check_docker():
                messagebox.showerror(
                    "Docker is not running",
                    "Docker Desktop does not appear to be running.\n\n"
                    "Please open Docker Desktop first, wait until it starts, "
                    "then try again."
                )
                append_log("ERROR: Docker Desktop is not running.")
                return

            stop_existing_container()
            stop_containers_using_port(PORT)
            pull_image()
            start_container(rmd_file)

            append_log("Waiting for tutorial to start...")
            time.sleep(6)

            open_browser()

            append_log("")
            append_log("Tutorial is running.")
            append_log(f"If the browser did not open, go to http://localhost:{PORT}")
            append_log("")
            append_log("To stop the tutorial, click 'Stop Tutorial'.")

        except Exception as e:
            append_log(f"ERROR: {e}")
            messagebox.showerror("Error", str(e))

    threading.Thread(target=task, daemon=True).start()


def start_selected_tutorial():
    selected_lesson = lesson_combo.get()
    available_lessons = available_lesson_names()

    if selected_lesson not in available_lessons:
        messagebox.showwarning(
            "No lesson selected",
            "No lesson is available yet. Please check again later."
        )
        return

    launch_lesson(selected_lesson)


def stop_tutorial():
    def task():
        append_log("")
        append_log("Stopping tutorial...")

        if DOCKER is None:
            append_log("ERROR: Docker command was not found.")
            return

        subprocess.run(
            [DOCKER, "stop", CONTAINER_NAME],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        subprocess.run(
            [DOCKER, "rm", CONTAINER_NAME],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        append_log("Tutorial stopped.")

    threading.Thread(target=task, daemon=True).start()


def on_app_close():
    """
    Automatically stop the tutorial container when the launcher app is closed.
    """
    try:
        append_log("")
        append_log("Closing app...")
        append_log("Stopping tutorial container if it is running...")

        if DOCKER is not None:
            subprocess.run(
                [DOCKER, "stop", CONTAINER_NAME],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            subprocess.run(
                [DOCKER, "rm", CONTAINER_NAME],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            append_log("Tutorial container stopped.")
        else:
            append_log("Docker command not found; nothing to stop.")

    except Exception as e:
        append_log(f"Error while closing: {e}")

    finally:
        root.destroy()


def refresh_lesson_controls():
    selected_lesson = lesson_combo.get()
    available_lessons = available_lesson_names()

    lesson_combo["values"] = available_lessons

    if selected_lesson in available_lessons:
        lesson_combo.set(selected_lesson)
    elif available_lessons:
        lesson_combo.current(0)
    else:
        lesson_combo.set("")
        lesson_status_var.set("No lessons are available yet.")
        start_button.config(state=tk.DISABLED)
        return

    current_lesson = lesson_combo.get()
    lesson_status_var.set("Available now")
    start_button.config(state=tk.NORMAL)


def on_lesson_selected(event=None):
    refresh_lesson_controls()


def schedule_lesson_refresh():
    refresh_lesson_controls()
    root.after(30000, schedule_lesson_refresh)


def open_admin_settings():
    password = simpledialog.askstring(
        "Admin settings",
        "Enter admin password:",
        show="*",
        parent=root
    )

    if password is None:
        return

    if password != ADMIN_PASSWORD:
        messagebox.showerror("Access denied", "The admin password is incorrect.")
        return

    admin_window = tk.Toplevel(root)
    admin_window.title("Admin Lesson Availability")
    admin_window.geometry("560x320")
    admin_window.transient(root)
    admin_window.grab_set()

    tk.Label(
        admin_window,
        text="Set when each lesson becomes available.",
        font=("Arial", 13, "bold")
    ).pack(pady=(14, 4))

    tk.Label(
        admin_window,
        text=f"Format: {RELEASE_TIME_FORMAT}. Leave blank to make a lesson available now. (For example: 2026-06-16 09:30)",
        font=("Arial", 10)
    ).pack(pady=(0, 10))

    form_frame = tk.Frame(admin_window)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=18)

    entries = {}

    for row_index, lesson_name in enumerate(LESSONS):
        tk.Label(
            form_frame,
            text=lesson_name,
            anchor="w",
            font=("Arial", 11)
        ).grid(row=row_index, column=0, sticky="w", padx=(0, 12), pady=5)

        release_var = tk.StringVar(
            value=format_release_time(
                lesson_schedule.get(lesson_name, {}).get("available_at")
            )
        )

        release_entry = ttk.Entry(
            form_frame,
            textvariable=release_var,
            width=24,
            font=("Arial", 11)
        )
        release_entry.grid(row=row_index, column=1, sticky="ew", pady=5)
        entries[lesson_name] = release_var

    form_frame.columnconfigure(1, weight=1)

    def make_available_now():
        for release_var in entries.values():
            release_var.set("")

    def save_admin_settings():
        new_schedule = default_schedule()

        try:
            for lesson_name, release_var in entries.items():
                release_time = parse_release_time(release_var.get())
                new_schedule[lesson_name]["available_at"] = (
                    release_time.strftime(RELEASE_TIME_FORMAT)
                    if release_time
                    else None
                )
        except ValueError as exc:
            messagebox.showerror("Invalid release time", str(exc), parent=admin_window)
            return

        lesson_schedule.clear()
        lesson_schedule.update(new_schedule)
        save_schedule(lesson_schedule)
        refresh_lesson_controls()

        append_log(f"Lesson schedule saved to {SCHEDULE_PATH}")
        messagebox.showinfo("Saved", "Lesson availability settings were saved.", parent=admin_window)
        admin_window.destroy()

    admin_button_frame = tk.Frame(admin_window)
    admin_button_frame.pack(pady=14)

    tk.Button(
        admin_button_frame,
        text="Make All Available Now",
        width=22,
        command=make_available_now
    ).pack(side=tk.LEFT, padx=6)

    tk.Button(
        admin_button_frame,
        text="Save",
        width=14,
        command=save_admin_settings
    ).pack(side=tk.LEFT, padx=6)

    tk.Button(
        admin_button_frame,
        text="Cancel",
        width=14,
        command=admin_window.destroy
    ).pack(side=tk.LEFT, padx=6)




# =============================================================================
# GUI
# =============================================================================

lesson_schedule = load_schedule()

root = tk.Tk()
root.title("MA214")
root.geometry("700x560")

# Automatically stop Docker container when the app window is closed
root.protocol("WM_DELETE_WINDOW", on_app_close)


title_label = tk.Label(
    root,
    text="Tutorial Launcher",
    font=("Arial", 22, "bold")
)
title_label.pack(pady=15)

instruction_label = tk.Label(
    root,
    text="Choose a lesson to start. Docker Desktop must be running.",
    font=("Arial", 12)
)
instruction_label.pack(pady=5)

# ── Lesson selection dropdown ────────────────────────────────────────────────

selection_frame = tk.Frame(root)
selection_frame.pack(pady=15)

lesson_label = tk.Label(
    selection_frame,
    text="Select lesson:",
    font=("Arial", 12)
)
lesson_label.pack(side=tk.LEFT, padx=8)

lesson_combo = ttk.Combobox(
    selection_frame,
    values=available_lesson_names(),
    state="readonly",
    width=25,
    font=("Arial", 12)
)
lesson_combo.pack(side=tk.LEFT, padx=8)
lesson_combo.bind("<<ComboboxSelected>>", on_lesson_selected)

# Default selected lesson
if available_lesson_names():
    lesson_combo.current(0)

lesson_status_var = tk.StringVar(value="")
lesson_status_label = tk.Label(
    root,
    textvariable=lesson_status_var,
    font=("Arial", 11, "italic")
)
lesson_status_label.pack(pady=2)

# ── Start / Stop buttons ─────────────────────────────────────────────────────

button_frame = tk.Frame(root)
button_frame.pack(pady=10)

start_button = tk.Button(
    button_frame,
    text="Start Tutorial",
    width=20,
    height=2,
    font=("Arial", 12),
    bg="#1F5E3B",
    fg="black",
    command=start_selected_tutorial
)
start_button.pack(side=tk.LEFT, padx=8)

stop_button = tk.Button(
    button_frame,
    text="Stop Tutorial",
    width=20,
    height=2,
    font=("Arial", 12),
    bg="#340F0F",
    fg="black",
    command=stop_tutorial
)
stop_button.pack(side=tk.LEFT, padx=8)

admin_button = tk.Button(
    root,
    text="Admin Settings",
    width=20,
    font=("Arial", 11),
    command=open_admin_settings
)
admin_button.pack(pady=5)

url_label = tk.Label(
    root,
    text=f"Tutorial URL: http://localhost:{PORT}",
    font=("Arial", 11)
)
url_label.pack(pady=5)

log_box = scrolledtext.ScrolledText(root, width=75, height=15)
log_box.pack(padx=15, pady=15)

append_log("Ready.")
append_log("Please make sure Docker Desktop is running.")
append_log("Choose a lesson from the dropdown, then click Start Tutorial.")
append_log(f"Lesson schedule file: {SCHEDULE_PATH}")
refresh_lesson_controls()
schedule_lesson_refresh()

root.mainloop()
