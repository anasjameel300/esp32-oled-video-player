# ESP32 SSD1306 OLED Video Player Pipeline & Library

This repository contains a complete local Windows-based toolchain that extracts frames from MP4 videos, binarizes them to 1-bit monochrome (128x64), generates ESP32/Arduino-compatible C array bitmap data (`PROGMEM`), and plays them on a 0.96-inch SSD1306 I2C OLED display.

This project is structured to be **highly forkable and easy to use**. You can immediately flash the pre-generated sample projects, or drop in your own video files, run the root-level converter script, and instantly generate custom animations.

---

## 1. Project Directory Structure

```text
esp32/ (Repository Root)
├── .gitignore                    # Prevents heavy media files from being committed to Git
├── README.md                     # Consolidated master documentation (this file)
├── convert.py                    # Root consolidated conversion script
├── convert.bat                   # Root Windows interactive launcher
│
├── OLEDVideo/                    # Project 1 (First Video)
│   ├── OLEDVideo.ino             # Arduino Sketch
│   ├── frames.h                  # Pre-generated frame data (Video 1)
│   └── preview/                  # Preview B/W PNG frames
│
├── OLEDVideo_Firework/           # Project 2 (Fireworks Video)
│   ├── OLEDVideo_Firework.ino    # Arduino Sketch
│   ├── frames.h                  # Pre-generated frame data (Video 2)
│   └── preview/                  # Preview B/W PNG frames
│
└── OLEDVideo3/                   # Project 3 (Video 3)
    ├── OLEDVideo3.ino            # Arduino Sketch
    ├── frames.h                  # Pre-generated frame data (Video 3)
    └── preview/                  # Preview B/W PNG frames
```

---

## 2. Consolidating the Code: Why This Structure?

Originally, each project directory had duplicate copies of `convert.py`, `convert.bat`, and `README.md`. We consolidated these files into the **repository root**:
*   **No Code Duplication**: There is now only *one* conversion engine (`convert.py`) to maintain.
*   **Clean Subdirectories**: The Arduino project folders contain only the code needed for flashing (the `.ino` sketch and the pre-generated `frames.h` headers).
*   **Arduino Compatibility**: Each sketch is placed inside a folder matching its name (e.g., `OLEDVideo3.ino` in `OLEDVideo3/`), which is required by the Arduino IDE.

### Video Organization: Where do video files live?
To keep the workspace clean and highly organized, each source video file is stored **inside its respective project folder** next to the `.ino` sketch:
*   `OLEDVideo/video.mp4`
*   `OLEDVideo_Firework/video1.mp4`
*   `OLEDVideo3/Video2.mp4`

By putting the source video directly *inside* the project folder:
1.  **Self-Contained Projects**: Everything for that animation (the source MP4, the `.ino` sketch, the generated C++ header, and the local preview frames) remains neatly grouped in a single folder.
2.  **Git Exclusions**: The root `.gitignore` recursively ignores all video files (`*.mp4`, `*.MOV`, etc.) and the local `preview/` folders (`**/preview/`) containing intermediate PNG images. This prevents large binary files from bloating your GitHub repository, keeping the repo lightweight and fast to clone, while still tracking the pre-generated `frames.h` files so the code is ready to compile out-of-the-box.

### Creating a New Custom Project
If you want to convert a new video and create a matching Arduino project from scratch:
1.  **Place your video file** (e.g. `dance.mp4`) in the repository root.
2.  **Run the conversion script** from the command line:
    ```cmd
    python convert.py dance.mp4
    ```
3.  **Automatic Scaffolding**: The script will automatically:
    *   Derive the project name (`OLEDVideo_dance`) and create that folder.
    *   Copy the video file inside it to keep it self-contained (`OLEDVideo_dance/dance.mp4`).
    *   Generate the Arduino sketch matching the folder name (`OLEDVideo_dance/OLEDVideo_dance.ino`).
    *   Generate `OLEDVideo_dance/frames.h` (the packed bitmap arrays) and the local previews.
4.  **Ready to Upload**: The new folder is now completely self-contained. Simply open the sketch in the Arduino IDE and flash it!

---

## 3. What do the scripts do?

This repository contains two core utility scripts at the root level to automate the pipeline:

### A. `convert.py` (The Python Engine)
This is the core conversion script. It coordinates the frame extraction and image processing:
1.  **Extracts Frames**: Calls FFmpeg to extract video frames at your target playback frame rate (e.g. 30 FPS) into a temporary directory.
2.  **Processes Images**: Loads each frame using Pillow (PIL), crops/letterboxes it to exactly 128x64 pixels, adjusts the contrast, and binarizes it to 1-bit black/white based on a threshold setting.
3.  **Compiles C++ Data (`frames.h`)**: Packages the 1-bit B/W pixels into horizontal bit-packed byte arrays (1,024 bytes per frame) and compiles them into a C++ header.
4.  **Generates Project Folders**: Creates new project directories and generates matching `.ino` sketches automatically when new videos are provided.

### B. `convert.bat` (The Windows Batch Menu)
This is a user-friendly wrapper for Windows that provides a simple command-line interface:
1.  **Interactive Menu**: Lets you select pre-configured conversions (Video 1, Video 2/Fireworks, Video 3) or enter custom parameters.
2.  **Automates Execution**: Runs `convert.py` with the correct command-line arguments for your selection, handling all video and folder paths automatically.

---


---

## 4. Required Software Setup (Windows)

To run the conversion pipeline locally, you need **Python 3** and **FFmpeg**.

### A. Python & Dependencies
1. If you don't have Python 3 installed, download and install it from [python.org](https://www.python.org/downloads/). (Ensure you check the box **"Add Python to PATH"** during installation).
2. Open Command Prompt (`cmd`) in the repository folder and install the required libraries using `requirements.txt`:
   ```cmd
   pip install -r requirements.txt
   ```

### B. FFmpeg Installation (Choose Option 1 or 2)

#### Option 1: Automatic Installation (Recommended)
You can install FFmpeg natively on Windows 10/11 using the built-in Windows Package Manager (`winget`). Open Command Prompt as Administrator and run:
```cmd
winget install Gyan.FFmpeg.Essentials
```
*Note: Restart your Command Prompt after the installation finishes so the system recognizes the new `ffmpeg` command.*

#### Option 2: Manual Fallback Installation
If you prefer not to use `winget`:
1. Download the zip build of FFmpeg from:  
   [gyan.dev FFmpeg Essentials](https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.7z)
2. Extract the archive.
3. Locate `ffmpeg.exe` inside the extracted `bin/` folder.
4. Copy and paste `ffmpeg.exe` directly into this repository root directory.

---

## 5. How to Convert Videos

### Option A: The Interactive Launcher (Recommended)
Simply double-click **`convert.bat`** at the root of the repository. An interactive menu will prompt you to select:
*   **[1] Video 1** (`Video.mp4` $\rightarrow$ outputs to `OLEDVideo/`)
*   **[2] Video 2** (`OLEDVideo_Firework/video1.mp4` $\rightarrow$ outputs to `OLEDVideo_Firework/`)
*   **[3] Video 3** (`Video2.mp4` $\rightarrow$ outputs to `OLEDVideo3/`)
*   **[4] Custom conversion** (Lets you input a custom video path, target project directory, target FPS, and binarization threshold).

### Option B: Command Line (CLI)
Open Command Prompt in the repository root and call `convert.py` with arguments:
```cmd
python convert.py [input_video] [target_project_folder] [fps] [threshold]
```
#### Examples:
*   Convert Video 1:
    ```cmd
    python convert.py Video.mp4 OLEDVideo 30 128
    ```
*   Convert Video 3 at 24 FPS with a higher threshold (lighter image):
    ```cmd
    python convert.py Video2.mp4 OLEDVideo3 24 140
    ```

---

## 6. Hardware Wiring

Connect your SSD1306 128x64 I2C OLED display to your ESP32 board:

| OLED Pin | ESP32 GPIO Pin | Description |
|:---:|:---:|---|
| **GND** | **GND** | Ground |
| **VCC** | **3.3V** | Power (Ensure your OLED supports 3.3V) |
| **SDA** | **GPIO 21** | I2C Serial Data |
| **SCL** | **GPIO 22** | I2C Serial Clock |

---

## 7. How to Flash and Play on ESP32

1.  Open the Arduino IDE.
2.  Go to **Sketch** -> **Include Library** -> **Manage Libraries...**
3.  Search for and install:
    *   **Adafruit SSD1306**
    *   **Adafruit GFX Library**
    *   *(If prompted, install all required dependencies).*
4.  Open the sketch of your choice (e.g. [`OLEDVideo3/OLEDVideo3.ino`](OLEDVideo3/OLEDVideo3.ino)) inside the Arduino IDE.
5.  Select your ESP32 board and COM port.
6.  Click **Upload** to flash the pre-generated animation!
7.  Open the Serial Monitor at **115200 baud** to see real-time playback diagnostics.

---

## 8. Configuration & Tuning

Every time you change the conversion parameters in the root scripts or batch file, you must **re-run the converter** to rebuild `frames.h`, and then **re-upload** the sketch from the Arduino IDE.

### A. Binarization Settings (at the top of `convert.py`)
*   `THRESHOLD` (0-255, default 128): Higher thresholds make binarized frames brighter (more white pixels); lower thresholds make them darker.
*   `CONTRAST` (default 1.2): Increases the sharpness of boundaries and makes text more legible.
*   `FIT_MODE` ("crop" or "pad"): Choose `"crop"` to center-zoom wide/tall videos to fill the display; choose `"pad"` to add black bars (letterboxing/pillarboxing) and preserve the entire video frame.

### B. Frame Rate (FPS)
*   The script writes the configured FPS to `frames.h` (e.g., `#define TARGET_FPS 30`), and the Arduino sketch dynamically adapts its playback speed to match this rate.
*   Playing at **30 FPS** gives a fluid animation, but consumes more flash memory.
*   Playing at **24 FPS** (or lower) reduces the memory footprint.

### C. Performance & I2C Clock
Achieving a fluid 30 FPS requires updating the screen buffer quickly. 
*   The Arduino sketches configure the ESP32's I2C speed to **800 kHz** (`Wire.setClock(800000)`). A screen transfer takes only **~13 ms**, easily fitting inside the **33.3 ms** frame window of 30 FPS.
*   If your screen shows glitches or does not turn on, reduce this to **400 kHz** (`Wire.setClock(400000)`) in your sketch.

---

## 9. Troubleshooting

*   **Blank Screen**: Ensure SDA is on pin 21 and SCL is on pin 22. Verify that your OLED's I2C address is indeed `0x3C`. If it uses `0x3D`, update `#define SCREEN_ADDRESS 0x3D` in the sketch.
*   **Compilation / Out of Memory**: Storing 18 seconds of video at 30 FPS consumes ~550 KB of flash. Make sure your Arduino IDE partition scheme (**Tools** -> **Partition Scheme**) is set to **Huge APP (3MB No OTA)** to allocate enough program storage space.
