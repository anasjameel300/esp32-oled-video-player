import os
import sys
import subprocess
import shutil
import re
import tempfile
from PIL import Image, ImageEnhance

# ==============================================================================
# DEFAULT CONFIGURATION
# ==============================================================================
INPUT_VIDEO = "Video.mp4"    # Default source video
OUTPUT_PROJECT = "OLEDVideo"  # Target Arduino project folder (e.g. OLEDVideo, OLEDVideo_Firework, OLEDVideo3)
DURATION = None              # Process only the first X seconds. Set to None to convert the full video.
FPS = 30                     # Target playback frame rate
WIDTH = 128                  # Target width for SSD1306
HEIGHT = 64                  # Target height for SSD1306
THRESHOLD = 128              # 1-bit threshold (0-255). Pixels >= THRESHOLD become white.
CONTRAST = 1.2               # Contrast multiplier (1.0 = original, >1.0 increases contrast)
FIT_MODE = "crop"            # "crop" (fills screen by cropping) or "pad" (fits screen with black borders)
INVERT = False               # Set to True if you want to invert black and white colors

# ==============================================================================
# CLI ARGUMENTS PARSING (Overrides default configuration if provided)
# ==============================================================================
def parse_arguments():
    global INPUT_VIDEO, OUTPUT_PROJECT, FPS, THRESHOLD
    
    # Help message
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h", "/?"]:
        print("\nESP32 OLED Video Conversion Utility")
        print("Usage:")
        print("    python convert.py [input_video] [target_project] [fps] [threshold]")
        print("\nExamples:")
        print("    python convert.py Video.mp4 OLEDVideo 30 128")
        print("    python convert.py video1.mp4 OLEDVideo_Firework 30 128")
        print("    python convert.py Video2.mp4 OLEDVideo3 30 128")
        print()
        sys.exit(0)
        
    if len(sys.argv) == 1:
        # Search the root directory for any video files
        video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        root_videos = []
        for file in os.listdir("."):
            if os.path.isfile(file):
                _, ext = os.path.splitext(file)
                if ext.lower() in video_extensions:
                    root_videos.append(file)
        
        if len(root_videos) == 1:
            INPUT_VIDEO = root_videos[0]
            # Automatically derive target project name
            video_name = os.path.splitext(os.path.basename(INPUT_VIDEO))[0]
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', video_name)
            OUTPUT_PROJECT = f"OLEDVideo_{clean_name}"
            print(f"Auto-detected video file at root: '{INPUT_VIDEO}'")
            print(f"Automatically set target project directory: '{OUTPUT_PROJECT}'")
        elif len(root_videos) > 1:
            # Sort by modification time to find the newest one
            root_videos.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            INPUT_VIDEO = root_videos[0]
            video_name = os.path.splitext(os.path.basename(INPUT_VIDEO))[0]
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', video_name)
            OUTPUT_PROJECT = f"OLEDVideo_{clean_name}"
            print(f"[WARNING] Multiple video files detected in the root directory: {root_videos}")
            print(f"Auto-detected newest video: '{INPUT_VIDEO}'")
            print(f"Automatically set target project directory: '{OUTPUT_PROJECT}'")

    if len(sys.argv) > 1:
        INPUT_VIDEO = sys.argv[1]
    if len(sys.argv) > 2:
        OUTPUT_PROJECT = sys.argv[2]
    elif len(sys.argv) > 1:
        # Automatically derive target project name from input video filename!
        # E.g. my_song.mp4 -> OLEDVideo_my_song
        video_name = os.path.splitext(os.path.basename(INPUT_VIDEO))[0]
        # Clean up video name (replace special characters with underscores)
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', video_name)
        OUTPUT_PROJECT = f"OLEDVideo_{clean_name}"
    if len(sys.argv) > 3:
        try:
            FPS = int(sys.argv[3])
        except ValueError:
            print(f"[WARNING] Invalid FPS value '{sys.argv[3]}'. Using default: {FPS}")
    if len(sys.argv) > 4:
        try:
            THRESHOLD = int(sys.argv[4])
        except ValueError:
            print(f"[WARNING] Invalid THRESHOLD value '{sys.argv[4]}'. Using default: {THRESHOLD}")

# ==============================================================================
# SYSTEM CHECKS
# ==============================================================================
def check_prerequisites():
    print("Checking prerequisites...")
    
    # 1. Check Pillow
    try:
        from PIL import Image
    except ImportError:
        print("\n[ERROR] Python library 'Pillow' is not installed.")
        print("Please install it by running the following command in your terminal:")
        print("    pip install Pillow")
        sys.exit(1)

    # 2. Check FFmpeg
    ffmpeg_found = False
    if shutil.which("ffmpeg"):
        ffmpeg_found = True
    elif os.path.exists("ffmpeg.exe"):
        ffmpeg_found = True
        
    if not ffmpeg_found:
        print("\n[ERROR] FFmpeg was not found on your system.")
        print("To run this script, FFmpeg must be installed and added to your system PATH,")
        print("or the 'ffmpeg.exe' executable must be placed in this project directory.")
        print("\nHow to install FFmpeg on Windows:")
        print("1. Download the build from: https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-essentials.7z")
        print("2. Extract the files and copy 'ffmpeg.exe' (found in the 'bin' folder) into this folder.")
        sys.exit(1)
        

        
    print("Prerequisites verified successfully.\n")

def get_video_info(video_path):
    """
    Runs ffmpeg to query video details and parses the output using regex.
    """
    if not os.path.exists(video_path):
        print(f"[ERROR] Input video '{video_path}' not found in the current directory.")
        sys.exit(1)
        
    cmd = ["ffmpeg", "-i", video_path]
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo)
    stderr = result.stderr
    
    # Parse duration
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
    duration_secs = 0.0
    if duration_match:
        hours = int(duration_match.group(1))
        minutes = int(duration_match.group(2))
        seconds = float(duration_match.group(3))
        duration_secs = hours * 3600 + minutes * 60 + seconds
        
    # Parse resolution and original FPS
    resolution = "Unknown"
    fps = 0.0
    video_stream_match = re.search(r"Video:.*?\s(\d+x\d+)\s", stderr)
    if video_stream_match:
        resolution = video_stream_match.group(1)
        
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr)
    if fps_match:
        fps = float(fps_match.group(1))
        
    return {
        "duration": duration_secs,
        "resolution": resolution,
        "fps": fps
    }

# ==============================================================================
# IMAGE PROCESSING
# ==============================================================================
def process_frame(img_path, fit_mode, width, height, contrast, threshold, invert):
    """
    Resizes, crops/pads, adjusts contrast, and thresholds an image.
    Returns the processed PIL Image (mode '1') and packed bytes.
    """
    img = Image.open(img_path)
    w, h = img.size
    
    src_ratio = w / h
    tgt_ratio = width / height
    
    # 1. Resize and crop/pad to maintain aspect ratio
    if fit_mode == "crop":
        if src_ratio > tgt_ratio:
            new_h = height
            new_w = int(w * (height / h))
            img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - width) // 2
            img_fitted = img_resized.crop((left, 0, left + width, height))
        else:
            new_w = width
            new_h = int(h * (width / w))
            img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            top = (new_h - height) // 2
            img_fitted = img_resized.crop((0, top, width, top + height))
    elif fit_mode == "pad":
        if src_ratio > tgt_ratio:
            new_w = width
            new_h = int(h * (width / w))
            img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            img_fitted = Image.new("RGB", (width, height), (0, 0, 0))
            top = (height - new_h) // 2
            img_fitted.paste(img_resized, (0, top))
        else:
            new_h = height
            new_w = int(w * (height / h))
            img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            img_fitted = Image.new("RGB", (width, height), (0, 0, 0))
            left = (width - new_w) // 2
            img_fitted.paste(img_resized, (left, 0))
    else:
        img_fitted = img.resize((width, height), Image.Resampling.LANCZOS)
        
    # 2. Grayscale conversion
    img_gray = img_fitted.convert("L")
    
    # 3. Apply contrast enhancement
    if contrast != 1.0:
        enhancer = ImageEnhance.Contrast(img_gray)
        img_gray = enhancer.enhance(contrast)
        
    # 4. Thresholding to binarize (1-bit B/W)
    pixels = list(img_gray.tobytes())
    bw_pixels = []
    for p in pixels:
        is_above = p >= threshold
        is_on = is_above if not invert else not is_above
        bw_pixels.append(255 if is_on else 0)
        
    # Recreate image for preview
    img_bw = Image.new("1", (width, height))
    img_bw.putdata([1 if p == 255 else 0 for p in bw_pixels])
    
    # 5. Pack into SSD1306 / Adafruit GFX compatible bitmap bytes
    byte_array = bytearray()
    for i in range(0, len(bw_pixels), 8):
        byte = 0
        for bit in range(8):
            if bw_pixels[i + bit] > 0:
                byte |= (1 << (7 - bit))
        byte_array.append(byte)
        
    return img_bw, byte_array

def generate_ino_file(project_dir):
    project_name = os.path.basename(project_dir)
    ino_path = os.path.join(project_dir, f"{project_name}.ino")
    
    # Do not overwrite if it already exists to protect custom changes
    if os.path.exists(ino_path):
        return
        
    print(f"Generating Arduino sketch file: '{ino_path}'...")
    
    ino_code = f"""/*
 * ESP32 SSD1306 OLED Video Player: {project_name}
 * Plays 1-bit monochrome video frames from flash memory (PROGMEM).
 * 
 * Wiring:
 *   OLED GND -> ESP32 GND
 *   OLED VCC -> ESP32 3.3V
 *   OLED SDA -> ESP32 GPIO 21
 *   OLED SCL -> ESP32 GPIO 22
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "frames.h"

// ==============================================================================
// CONFIGURATION
// ==============================================================================
// Enable TEST_MODE to play only the first 24 frames (1 second of video)
#define TEST_MODE false

// OLED Display Configuration
#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1  // Share reset pin or set to -1 if not used
#define SCREEN_ADDRESS 0x3C

// Target Frame Rate Config
#ifndef TARGET_FPS
#define TARGET_FPS     30
#endif
const uint32_t FRAME_PERIOD_US = 1000000 / TARGET_FPS;

// Pin Definitions for I2C
#define I2C_SDA 21
#define I2C_SCL 22

// Initialize SSD1306 display object
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Diagnostic Variables
uint32_t last_fps_report_time = 0;
uint32_t frames_rendered = 0;
float actual_fps = 0.0;

void setup() {{
  Serial.begin(115200);
  while (!Serial) {{
    delay(10); // Wait for serial port to connect (mainly for native USB boards)
  }}
  
  Serial.println("\\n--- ESP32 OLED Video Player Initialization ---");
  
  #if TEST_MODE
    Serial.println("Mode: TEST MODE ENABLED (playing only first 24 frames)");
  #else
    Serial.print("Mode: NORMAL MODE (playing full ");
    Serial.print(TOTAL_FRAMES);
    Serial.println(" frames)");
  #endif
  
  // Initialize I2C bus with custom pins
  Serial.print("Initializing I2C bus (SDA: ");
  Serial.print(I2C_SDA);
  Serial.print(", SCL: ");
  Serial.print(I2C_SCL);
  Serial.println(")...");
  Wire.begin(I2C_SDA, I2C_SCL);
  
  // Configure fast I2C clock
  Serial.println("Setting I2C clock to Fast Mode (800 kHz)...");
  Wire.setClock(800000); 

  // Initialize display
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {{
    Serial.println(F("[ERROR] SSD1306 allocation failed. Check wiring and address (0x3C)."));
    while (true) {{
      delay(1000);
    }}
  }}
  
  Serial.println("SSD1306 initialized successfully.");
  
  // Set Display Clock Divide Ratio/Oscillator Frequency (Command 0xD5)
  // Maximize internal oscillator frequency to eliminate camera banding and flicker
  display.ssd1306_command(0xD5);
  display.ssd1306_command(0xF0);

  display.clearDisplay();
  display.display();
  
  last_fps_report_time = millis();
}}

void loop() {{
  int frame_limit = TEST_MODE ? TEST_FRAMES : TOTAL_FRAMES;
  
  for (int i = 0; i < frame_limit; i++) {{
    uint32_t frame_start_us = micros();
    
    display.clearDisplay();
    display.drawBitmap(0, 0, video_frames[i], SCREEN_WIDTH, SCREEN_HEIGHT, SSD1306_WHITE);
    display.display();
    
    uint32_t render_end_us = micros();
    uint32_t render_time_us = render_end_us - frame_start_us;
    
    frames_rendered++;
    
    uint32_t current_time_ms = millis();
    if (current_time_ms - last_fps_report_time >= 1000) {{
      actual_fps = (float)frames_rendered * 1000.0 / (current_time_ms - last_fps_report_time);
      frames_rendered = 0;
      last_fps_report_time = current_time_ms;
      
      Serial.print("Playback Stats -> Frame: ");
      Serial.print(i + 1);
      Serial.print("/");
      Serial.print(frame_limit);
      Serial.print(" | Render Time: ");
      Serial.print((float)render_time_us / 1000.0, 2);
      Serial.print(" ms | Actual FPS: ");
      Serial.print(actual_fps, 1);
      Serial.println(" Hz");
    }}
    
    uint32_t elapsed_us = micros() - frame_start_us;
    if (elapsed_us < FRAME_PERIOD_US) {{
      uint32_t delay_us = FRAME_PERIOD_US - elapsed_us;
      delayMicroseconds(delay_us);
    }} else {{
      yield();
    }}
  }}
}}
"""
    with open(ino_path, "w") as f:
        f.write(ino_code)

# ==============================================================================
# MAIN PIPELINE
# ==============================================================================
def main():
    parse_arguments()
    check_prerequisites()
    
    # 1. Ensure target project directory exists
    if not os.path.exists(OUTPUT_PROJECT):
        print(f"Target project folder '{OUTPUT_PROJECT}' does not exist. Creating it...")
        os.makedirs(OUTPUT_PROJECT, exist_ok=True)
        
    # 2. Automatically generate the matching .ino sketch file
    generate_ino_file(OUTPUT_PROJECT)
    
    # 3. Locate the video file
    video_file = INPUT_VIDEO
    if not os.path.exists(video_file):
        # Case insensitive fallback
        lower_files = {f.lower(): f for f in os.listdir(".")}
        if video_file.lower() in lower_files:
            video_file = lower_files[video_file.lower()]
        else:
            # Check inside targeted project folder (legacy behavior support)
            legacy_path = os.path.join(OUTPUT_PROJECT, INPUT_VIDEO)
            if os.path.exists(legacy_path):
                video_file = legacy_path
            else:
                print(f"[ERROR] Input video file '{INPUT_VIDEO}' not found at root or project folder.")
                sys.exit(1)
                
    # 4. Move video file inside project directory to make it self-contained
    dest_video_path = os.path.join(OUTPUT_PROJECT, os.path.basename(video_file))
    if os.path.abspath(video_file) != os.path.abspath(dest_video_path):
        print(f"Moving video file '{video_file}' to '{dest_video_path}'...")
        shutil.move(video_file, dest_video_path)
        video_file = dest_video_path
            
    info = get_video_info(video_file)
    print("--- Video Information ---")
    print(f"File:      {video_file}")
    print(f"Duration:  {info['duration']:.2f} seconds")
    print(f"Resolution:{info['resolution']}")
    print(f"Orig FPS:  {info['fps']:.2f} FPS\n")
    
    # Configure output directories relative to the target project folder
    preview_dir = os.path.join(OUTPUT_PROJECT, "preview")
    if os.path.exists(preview_dir):
        shutil.rmtree(preview_dir)
    os.makedirs(preview_dir, exist_ok=True)
    
    frames_h_path = os.path.join(OUTPUT_PROJECT, "frames.h")
    
    # Temporary directory for extracted frames
    temp_dir = tempfile.mkdtemp()
    
    # Run FFmpeg command to extract frames
    if DURATION is not None:
        print(f"Extracting first {DURATION} seconds at {FPS} FPS...")
        cmd = [
            "ffmpeg",
            "-ss", "00:00:00",
            "-t", str(DURATION),
            "-i", video_file,
            "-vf", f"fps={FPS}",
            os.path.join(temp_dir, "frame_%04d.png"),
            "-y"
        ]
    else:
        print(f"Extracting full video ({info['duration']:.2f} seconds) at {FPS} FPS...")
        cmd = [
            "ffmpeg",
            "-i", video_file,
            "-vf", f"fps={FPS}",
            os.path.join(temp_dir, "frame_%04d.png"),
            "-y"
        ]
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
    try:
        subprocess.run(cmd, check=True, startupinfo=startupinfo)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg extraction failed: {e}")
        shutil.rmtree(temp_dir)
        sys.exit(1)
        
    # Get list of extracted frames
    frame_files = sorted([f for f in os.listdir(temp_dir) if f.endswith(".png")])
    total_frames = len(frame_files)
    
    if total_frames == 0:
        print("[ERROR] No frames were extracted by FFmpeg. Please verify the video file format and duration.")
        shutil.rmtree(temp_dir)
        sys.exit(1)
        
    print(f"Extracted {total_frames} frames successfully. Processing and packing...")
    
    all_packed_frames = []
    
    for idx, frame_name in enumerate(frame_files):
        frame_path = os.path.join(temp_dir, frame_name)
        
        # Process image
        img_bw, packed_bytes = process_frame(
            frame_path, 
            FIT_MODE, 
            WIDTH, 
            HEIGHT, 
            CONTRAST, 
            THRESHOLD, 
            INVERT
        )
        
        all_packed_frames.append(packed_bytes)
        
        # Save preview frame inside project's preview folder
        preview_path = os.path.join(preview_dir, f"frame_{idx + 1:03d}.png")
        img_bw.save(preview_path)
        
    # Clean up temporary directory
    shutil.rmtree(temp_dir)
    
    # Write frames.h inside target project folder
    print(f"Writing packed bitmap arrays to '{frames_h_path}'...")
    
    bytes_per_frame = (WIDTH * HEIGHT) // 8
    total_bytes = total_frames * bytes_per_frame
    
    with open(frames_h_path, "w") as f:
        f.write("/*\n")
        f.write(" * OLED Video Frame Data\n")
        f.write(f" * Generated from: {video_file}\n")
        f.write(f" * Dimensions:     {WIDTH}x{HEIGHT}\n")
        f.write(f" * Total Frames:   {total_frames}\n")
        f.write(f" * Target FPS:     {FPS}\n")
        f.write(f" * Size per Frame: {bytes_per_frame} bytes\n")
        f.write(f" * Total Size:     {total_bytes} bytes ({total_bytes / 1024.0:.2f} KB)\n")
        f.write(" */\n\n")
        
        f.write("#ifndef FRAMES_H\n")
        f.write("#define FRAMES_H\n\n")
        f.write("#include <pgmspace.h>\n\n")
        
        f.write(f"#define TOTAL_FRAMES {total_frames}\n")
        f.write(f"#define TARGET_FPS {FPS}\n")
        f.write("#define TEST_FRAMES 24\n\n")
        
        # Write individual frame arrays
        for idx, frame_bytes in enumerate(all_packed_frames):
            f.write(f"const unsigned char frame_{idx:03d}[] PROGMEM = {{\n    ")
            hex_bytes = [f"0x{b:02X}" for b in frame_bytes]
            lines = []
            for i in range(0, len(hex_bytes), 16):
                lines.append(", ".join(hex_bytes[i:i+16]))
            f.write(",\n    ".join(lines))
            f.write("\n};\n\n")
            
        # Write the pointer array
        f.write("const unsigned char* const video_frames[] PROGMEM = {\n")
        pointer_lines = []
        for i in range(0, total_frames, 8):
            chunk = [f"frame_{idx:03d}" for idx in range(i, min(i+8, total_frames))]
            pointer_lines.append("    " + ", ".join(chunk))
        f.write(",\n".join(pointer_lines))
        f.write("\n};\n\n")
        
        f.write("#endif // FRAMES_H\n")
        
    print("\n=======================================================")
    print("CONVERSION COMPLETED SUCCESSFULLY!")
    print("=======================================================")
    print(f"Output File:      {frames_h_path}")
    print(f"Resolution:       {WIDTH}x{HEIGHT} (Monochrome)")
    print(f"Frames Generated: {total_frames}")
    print(f"Duration:         {total_frames / FPS:.2f} seconds (@ {FPS} FPS)")
    print(f"Fit Mode:         {FIT_MODE} (contrast={CONTRAST}, threshold={THRESHOLD})")
    print(f"Bitmap Size:      {total_bytes} bytes ({total_bytes / 1024.0:.2f} KB)")
    print(f"Preview Frames:   Saved in '{preview_dir}/' directory")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
