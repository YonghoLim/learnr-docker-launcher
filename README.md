# MA214 Tutorial Launcher

This launcher starts MA214 R Shiny/learnr tutorial lessons from a Docker image.
It is built with Python, Tkinter, Docker Desktop, and PyInstaller.

## Important Build Note

Build the app on the same operating system you want to distribute:

- Build the macOS app on macOS.
- Build the Windows app on Windows.

PyInstaller does not reliably cross-compile macOS apps from Windows or Windows apps from macOS.

## Requirements

Install these before building:

- Python 3.10 or newer
- Docker Desktop
- PyInstaller

Install PyInstaller:

```bash
python3 -m pip install pyinstaller
```

On Windows, use:

```powershell
py -m pip install pyinstaller
```

## Project Files

Main files:

- `ma214_launcher.py`: launcher source code
- `MA214 Tutorial Launcher.spec`: PyInstaller build configuration

Build output folders:

- `build/`: temporary PyInstaller build files
- `dist/`: finished app output

## Admin Lesson Schedule

The launcher includes admin-controlled lesson availability.

Default admin password:

```text
1234
```

You can override it with an environment variable before building or running:

macOS:

```bash
export MA214_ADMIN_PASSWORD="your-password"
```

Windows PowerShell:

```powershell
$env:MA214_ADMIN_PASSWORD="your-password"
```

Lesson release times use this format:

```text
YYYY-MM-DD HH:MM
```

Example:

```text
2026-06-16 09:30
```

Lessons scheduled for the future are hidden from normal users until their release time.

## Build for macOS

Run these commands from this folder:

```bash
cd /path/to/app
python3 -m PyInstaller "MA214 Tutorial Launcher.spec"
```

The macOS app will be created at:

```text
dist/MA214 Tutorial Launcher.app
```

To create a zip file for distribution:

```bash
cd dist
zip -r "MA214 Tutorial Launcher_macOS.zip" "MA214 Tutorial Launcher.app"
```

Students should:

1. Install Docker Desktop.
2. Start Docker Desktop and wait until it is running.
3. Open `MA214 Tutorial Launcher.app`.

## Build for Windows

Open PowerShell in this folder and run:

```powershell
py -m PyInstaller "MA214 Tutorial Launcher.spec"
```

The Windows app folder will be created at:

```text
dist\MA214 Tutorial Launcher
```

The executable will be:

```text
dist\MA214 Tutorial Launcher\MA214 Tutorial Launcher.exe
```

To create a zip file for distribution:

```powershell
Compress-Archive -Path "dist\MA214 Tutorial Launcher" -DestinationPath "dist\MA214 Tutorial Launcher_Windows.zip" -Force
```

Students should:

1. Install Docker Desktop.
2. Start Docker Desktop and wait until it is running.
3. Open `MA214 Tutorial Launcher.exe`.

## Build Without the Spec File

If the spec file is missing, you can build directly.

macOS:

```bash
python3 -m PyInstaller --windowed --name "MA214 Tutorial Launcher" ma214_launcher.py
```

Windows:

```powershell
py -m PyInstaller --windowed --name "MA214 Tutorial Launcher" ma214_launcher.py
```

After building once, PyInstaller will generate a new `.spec` file that you can reuse.

## Clean Build

If the app behaves strangely after code changes, remove old build output and rebuild.

macOS:

```bash
rm -rf build dist
python3 -m PyInstaller "MA214 Tutorial Launcher.spec"
```

Windows PowerShell:

```powershell
Remove-Item -Recurse -Force build, dist
py -m PyInstaller "MA214 Tutorial Launcher.spec"
```

## Docker Image

The launcher currently uses this Docker image:

```text
buintrostats/learnr-lessons:latest
```

This value is set in `ma214_launcher.py`:

```python
IMAGE = "buintrostats/learnr-lessons:latest"
```

If you publish a new Docker image or tag, update this value before rebuilding the app.

## Troubleshooting

If the launcher says Docker is not running:

- Open Docker Desktop manually.
- Wait until Docker Desktop fully starts.
- Try the launcher again.

If the app cannot find Docker:

- Confirm Docker Desktop is installed.
- Restart the computer after installing Docker Desktop.
- On Windows, confirm Docker works in PowerShell:

```powershell
docker info
```

- On macOS, confirm Docker works in Terminal:

```bash
docker info
```

If port `3838` is already in use:

- The launcher tries to stop existing Docker containers using that port automatically.
- If it still fails, close other local Shiny apps or containers using port `3838`.

If students cannot see a lesson:

- Open `Admin Settings`.
- Enter the admin password.
- Check the release time for that lesson.
- Leave the release time blank to make the lesson available immediately.
