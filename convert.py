import os
import sys
import subprocess
import shutil
import re
import tempfile
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# ==============================================================================
# DEFAULT CONFIGURATION
# ==============================================================================
INPUT_VIDEO = "Video.mp4"    # Default source video
OUTPUT_PROJECT = "OLEDVideo"  # Target Arduino project folder
DURATION = None              # Process only first X seconds (None = full video)
FPS = 30                     # Target playback frame rate
WIDTH = 128                  # Target width for SSD1306
HEIGHT = 64                  # Target height for SSD1306
THRESHOLD = 128              # 1-bit threshold fallback (0-255). Used if dither is "none"
CONTRAST = 1.1               # Contrast multiplier (1.0 = original, >1.0 increases contrast)
FIT_MODE = "crop"            # "crop" (fills screen edge-to-edge), "pad", or "stretch"
DITHER = "atkinson"          # "atkinson" (recommended for fine detail), "floyd", "bayer", or "none"
SHARPEN = 1.2                # Pre-dither edge enhancement factor
BLACK_POINT = 5              # Keeps dark backgrounds jet black without wiping out shadow details (0-255)
WHITE_POINT = 245            # Keeps bright highlights 100% white (0-255)
INVERT = False               # Set to True if you want to invert black and white colors
CROP_TOP = 0                 # Pixels to cut from top (removes top black bar/letterbox/captions)
CROP_BOTTOM = 0              # Pixels to cut from bottom (removes bottom black bar/letterbox)
CROP_LEFT = 0                # Pixels to cut from left
CROP_RIGHT = 0               # Pixels to cut from right
AUTOCROP = False             # Automatically detect and remove letterbox black bars
GAMMA = 0.65                 # Gamma correction (<1.0 lifts shadow detail in dark scenes without blowing highlights)
BRIGHTNESS = 1.0             # Brightness enhancement multiplier
AUTOCONTRAST = False         # Automatically stretch contrast histogram

# ==============================================================================
# CLI ARGUMENTS PARSING (Overrides default configuration if provided)
# ==============================================================================
def parse_arguments():
    global INPUT_VIDEO, OUTPUT_PROJECT, FPS, THRESHOLD, FIT_MODE, DITHER, CONTRAST, SHARPEN
    global INVERT, CROP_TOP, CROP_BOTTOM, CROP_LEFT, CROP_RIGHT, AUTOCROP, GAMMA, BRIGHTNESS
    global AUTOCONTRAST, BLACK_POINT, WHITE_POINT, DURATION
    
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h", "/?"]:
        print("\nESP32 OLED Video Conversion Utility")
        print("Usage:")
        print("    python convert.py [input_video] [target_project] [fps] [threshold]")
        print("    python convert.py [options]")
        print("\nCropping & Fitting Options:")
        print("    --crop-top [pixels]                  Crop pixels from top (e.g. remove letterbox or captions)")
        print("    --crop-bottom [pixels]               Crop pixels from bottom (e.g. remove letterbox)")
        print("    --crop-left [pixels]                 Crop pixels from left")
        print("    --crop-right [pixels]                Crop pixels from right")
        print("    --crop [top,bottom]                  Shorthand for top,bottom crop (e.g. --crop 436,436)")
        print("    --autocrop                           Automatically detect and remove black letterbox bars")
        print("    --fit [crop|pad|stretch]             Screen fitting mode (default: crop)")
        print("\nVisual Enhancement Options:")
        print("    --gamma [float]                      Gamma correction (default: 0.65; <1.0 brightens dark scenes)")
        print("    --brightness [float]                 Brightness multiplier (default: 1.0)")
        print("    --contrast [float]                   Contrast multiplier (default: 1.1)")
        print("    --autocontrast                       Automatically stretch contrast dynamic range")
        print("    --sharpen [float]                    Edge sharpening factor (default: 1.2)")
        print("    --black-point [0-255]                Black clipping point (default: 5)")
        print("    --white-point [0-255]                White clipping point (default: 245)")
        print("    --dither [atkinson|floyd|bayer|none] Dithering algorithm (default: atkinson)")
        print("    --threshold [0-255]                  Threshold for 'none' mode (default: 128)")
        print("    --invert                             Invert black and white")
        print("    --fps [int]                          Target playback FPS (default: 30)")
        print("    --duration [float]                   Process only first X seconds of video")
        print("\nExamples:")
        print("    python convert.py Video.mp4 OLEDVideo --crop-top 436 --crop-bottom 436 --gamma 0.6")
        print("    python convert.py Video.mp4 OLEDVideo --autocrop --fit crop")
        print()
        sys.exit(0)
        
    positional = []
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--dither" and i + 1 < len(sys.argv):
            DITHER = sys.argv[i + 1].lower()
            i += 2
        elif arg == "--fit" and i + 1 < len(sys.argv):
            FIT_MODE = sys.argv[i + 1].lower()
            i += 2
        elif arg == "--crop-top" and i + 1 < len(sys.argv):
            try:
                CROP_TOP = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--crop-bottom" and i + 1 < len(sys.argv):
            try:
                CROP_BOTTOM = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--crop-left" and i + 1 < len(sys.argv):
            try:
                CROP_LEFT = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--crop-right" and i + 1 < len(sys.argv):
            try:
                CROP_RIGHT = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--crop" and i + 1 < len(sys.argv):
            parts = [int(p.strip()) for p in sys.argv[i + 1].split(",") if p.strip().isdigit()]
            if len(parts) == 2:
                CROP_TOP, CROP_BOTTOM = parts[0], parts[1]
            elif len(parts) == 4:
                CROP_LEFT, CROP_TOP, CROP_RIGHT, CROP_BOTTOM = parts[0], parts[1], parts[2], parts[3]
            i += 2
        elif arg == "--autocrop":
            AUTOCROP = True
            i += 1
        elif arg == "--gamma" and i + 1 < len(sys.argv):
            try:
                GAMMA = float(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--brightness" and i + 1 < len(sys.argv):
            try:
                BRIGHTNESS = float(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--autocontrast":
            AUTOCONTRAST = True
            i += 1
        elif arg == "--sharpen" and i + 1 < len(sys.argv):
            try:
                SHARPEN = float(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--contrast" and i + 1 < len(sys.argv):
            try:
                CONTRAST = float(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--black-point" and i + 1 < len(sys.argv):
            try:
                BLACK_POINT = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--white-point" and i + 1 < len(sys.argv):
            try:
                WHITE_POINT = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--fps" and i + 1 < len(sys.argv):
            try:
                FPS = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--duration" and i + 1 < len(sys.argv):
            try:
                DURATION = float(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--threshold" and i + 1 < len(sys.argv):
            try:
                THRESHOLD = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg == "--invert":
            INVERT = True
            i += 1
        elif not arg.startswith("-"):
            positional.append(arg)
            i += 1
        else:
            i += 1

    if len(positional) == 0 and len(sys.argv) == 1:
        # Search root directory for video files
        video_extensions = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        root_videos = []
        for file in os.listdir("."):
            if os.path.isfile(file):
                _, ext = os.path.splitext(file)
                if ext.lower() in video_extensions:
                    root_videos.append(file)
        
        if len(root_videos) == 1:
            INPUT_VIDEO = root_videos[0]
            video_name = os.path.splitext(os.path.basename(INPUT_VIDEO))[0]
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', video_name)
            OUTPUT_PROJECT = f"OLEDVideo_{clean_name}"
            print(f"Auto-detected video file at root: '{INPUT_VIDEO}'")
            print(f"Automatically set target project directory: '{OUTPUT_PROJECT}'")
        elif len(root_videos) > 1:
            root_videos.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            INPUT_VIDEO = root_videos[0]
            video_name = os.path.splitext(os.path.basename(INPUT_VIDEO))[0]
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', video_name)
            OUTPUT_PROJECT = f"OLEDVideo_{clean_name}"
            print(f"[WARNING] Multiple video files detected in root directory: {root_videos}")
            print(f"Auto-detected newest video: '{INPUT_VIDEO}'")
            print(f"Automatically set target project directory: '{OUTPUT_PROJECT}'")

    if len(positional) > 0:
        INPUT_VIDEO = positional[0]
    if len(positional) > 1:
        OUTPUT_PROJECT = positional[1]
    elif len(positional) > 0:
        video_name = os.path.splitext(os.path.basename(INPUT_VIDEO))[0]
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', video_name)
        OUTPUT_PROJECT = f"OLEDVideo_{clean_name}"
    if len(positional) > 2:
        try:
            FPS = int(positional[2])
        except ValueError:
            print(f"[WARNING] Invalid FPS value '{positional[2]}'. Using default: {FPS}")
    if len(positional) > 3:
        try:
            THRESHOLD = int(positional[3])
        except ValueError:
            print(f"[WARNING] Invalid THRESHOLD value '{positional[3]}'. Using default: {THRESHOLD}")

# ==============================================================================
# SYSTEM CHECKS
# ==============================================================================
def check_prerequisites():
    print("Checking prerequisites...")
    
    try:
        from PIL import Image
    except ImportError:
        print("\n[ERROR] Python library 'Pillow' is not installed.")
        print("Please install it: pip install Pillow")
        sys.exit(1)

    ffmpeg_found = False
    if shutil.which("ffmpeg"):
        ffmpeg_found = True
    elif os.path.exists("ffmpeg.exe"):
        ffmpeg_found = True
        
    if not ffmpeg_found:
        print("\n[ERROR] FFmpeg was not found on your system.")
        print("Please install FFmpeg or place 'ffmpeg.exe' in this directory.")
        sys.exit(1)
        
    print("Prerequisites verified successfully.\n")

def get_video_info(video_path):
    if not os.path.exists(video_path):
        print(f"[ERROR] Input video '{video_path}' not found.")
        sys.exit(1)
        
    cmd = ["ffmpeg", "-i", video_path]
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo)
    stderr = result.stderr
    
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr)
    duration_secs = 0.0
    if duration_match:
        hours = int(duration_match.group(1))
        minutes = int(duration_match.group(2))
        seconds = float(duration_match.group(3))
        duration_secs = hours * 3600 + minutes * 60 + seconds
        
    resolution = "Unknown"
    width, height = 0, 0
    fps = 0.0
    video_stream_match = re.search(r"Video:.*?\s(\d+)x(\d+)\s", stderr)
    if video_stream_match:
        width = int(video_stream_match.group(1))
        height = int(video_stream_match.group(2))
        resolution = f"{width}x{height}"
        
    fps_match = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr)
    if fps_match:
        fps = float(fps_match.group(1))
        
    return {
        "duration": duration_secs,
        "resolution": resolution,
        "width": width,
        "height": height,
        "fps": fps
    }

def auto_detect_letterbox(video_path, samples=6):
    """
    Analyzes sample frames across the video to detect letterbox black bars
    or border regions. Returns (crop_top, crop_bottom, crop_left, crop_right).
    """
    info = get_video_info(video_path)
    duration = info.get("duration", 0)
    if duration <= 0:
        return 0, 0, 0, 0
        
    step = duration / (samples + 1)
    sample_times = [step * (i + 1) for i in range(samples)]
    
    temp_dir = tempfile.mkdtemp()
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
    row_stds = []
    for idx, t in enumerate(sample_times):
        out_png = os.path.join(temp_dir, f"sample_{idx}.png")
        cmd = ["ffmpeg", "-ss", f"{t:.2f}", "-i", video_path, "-frames:v", "1", "-update", "1", out_png, "-y"]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        if os.path.exists(out_png):
            try:
                arr = np.array(Image.open(out_png))
                std_r = arr.std(axis=1).mean(axis=1)
                row_stds.append(std_r)
            except Exception:
                pass
                
    shutil.rmtree(temp_dir, ignore_errors=True)
    if not row_stds:
        return 0, 0, 0, 0
        
    avg_std = np.mean(row_stds, axis=0)
    # Rows with std > 5.0 contain dynamic video content (excludes black bars and static captions)
    active = np.where(avg_std > 5.0)[0]
    if len(active) == 0:
        return 0, 0, 0, 0
        
    top = int(active[0])
    bottom = int(len(avg_std) - 1 - active[-1])
    
    # Only report crop if borders exceed 5% of height
    if top < len(avg_std) * 0.05:
        top = 0
    if bottom < len(avg_std) * 0.05:
        bottom = 0
        
    return top, bottom, 0, 0

# ==============================================================================
# DITHERING ALGORITHMS
# ==============================================================================
def atkinson_dither(img_gray, black_point=5, white_point=245, invert=False):
    """
    Applies Atkinson dithering (classic Apple Macintosh halftoning).
    Diffuses 6/8 of quantization error, keeping sharp silhouettes and text.
    """
    arr = np.array(img_gray, dtype=np.float32)
    if white_point > black_point:
        arr = np.clip((arr - black_point) * (255.0 / (white_point - black_point)), 0, 255)
        
    buf = arr.astype(np.int32)
    h, w = buf.shape
    for y in range(h):
        for x in range(w):
            old_val = buf[y, x]
            new_val = 255 if old_val >= 128 else 0
            err = (old_val - new_val) >> 3  # divide by 8
            buf[y, x] = new_val
            if err != 0:
                if x + 1 < w: buf[y, x + 1] += err
                if x + 2 < w: buf[y, x + 2] += err
                if y + 1 < h:
                    if x - 1 >= 0: buf[y + 1, x - 1] += err
                    buf[y + 1, x] += err
                    if x + 1 < w: buf[y + 1, x + 1] += err
                if y + 2 < h: buf[y + 2, x] += err
                
    res = (buf >= 128)
    if invert:
        res = ~res
    return Image.fromarray((res.astype(np.uint8) * 255), mode="L").convert("1")

def bayer_dither(img_gray, black_point=5, white_point=245, invert=False):
    """
    Applies 4x4 Bayer ordered dithering. Temporally stable pattern for video.
    """
    bayer_matrix = np.array([
        [ 0,  8,  2, 10],
        [12,  4, 14,  6],
        [ 3, 11,  1,  9],
        [15,  7, 13,  5]
    ], dtype=np.float32) / 16.0 * 255.0 - 128.0
    
    arr = np.array(img_gray, dtype=np.float32)
    if white_point > black_point:
        arr = np.clip((arr - black_point) * (255.0 / (white_point - black_point)), 0, 255)
        
    h, w = arr.shape
    tiled_matrix = np.tile(bayer_matrix, (h // 4 + 1, w // 4 + 1))[:h, :w]
    res = (arr + tiled_matrix * 0.75 >= 128)
    if invert:
        res = ~res
    return Image.fromarray((res.astype(np.uint8) * 255), mode="L").convert("1")

# ==============================================================================
# IMAGE PROCESSING
# ==============================================================================
def process_frame(img_path, fit_mode, width, height, contrast, threshold, invert,
                  dither="atkinson", sharpen=1.2, black_point=5, white_point=245,
                  crop_top=0, crop_bottom=0, crop_left=0, crop_right=0,
                  gamma=0.65, brightness=1.0, autocontrast=False):
    """
    Crops borders/letterboxes, resizes, sharpens, applies gamma/contrast enhancement,
    and dithers an image. Returns the processed PIL Image (mode '1') and packed bytes for SSD1306.
    """
    img = Image.open(img_path)
    w, h = img.size
    
    # 1. Apply user/letterbox crop if specified
    if crop_top > 0 or crop_bottom > 0 or crop_left > 0 or crop_right > 0:
        box_left = max(0, crop_left)
        box_top = max(0, crop_top)
        box_right = min(w, w - crop_right)
        box_bottom = min(h, h - crop_bottom)
        if box_right > box_left and box_bottom > box_top:
            img = img.crop((box_left, box_top, box_right, box_bottom))
            w, h = img.size

    # 2. Resize and crop/pad to target width & height
    if fit_mode == "crop":
        # Zoom to cover the entire screen edge-to-edge
        scale = max(width / w, height / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        img_fitted = img_resized.crop((left, top, left + width, top + height))
    elif fit_mode == "pad":
        # Fit inside bounds with black borders
        scale = min(width / w, height / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        img_fitted = Image.new("RGB", (width, height), (0, 0, 0))
        left = (width - new_w) // 2
        top = (height - new_h) // 2
        img_fitted.paste(img_resized, (left, top))
    else:  # stretch
        img_fitted = img.resize((width, height), Image.Resampling.LANCZOS)
        
    # 3. Chroma-preserving Grayscale Conversion
    # Standard NTSC Luma (0.299*R + 0.587*G + 0.114*B) crushes red flares and saturated colors by 70%.
    # Blending with max-channel preserves illuminated color details (flares, neons, costumes).
    arr_rgb = np.array(img_fitted, dtype=np.float32)
    luma = 0.299 * arr_rgb[:,:,0] + 0.587 * arr_rgb[:,:,1] + 0.114 * arr_rgb[:,:,2]
    max_c = arr_rgb.max(axis=2)
    blend = (0.5 * max_c + 0.5 * luma).astype(np.uint8)
    img_gray = Image.fromarray(blend, mode="L")
    
    # 4. Edge sharpening
    if sharpen > 0:
        img_gray = img_gray.filter(ImageFilter.UnsharpMask(radius=1.0, percent=int(sharpen * 100), threshold=2))
        
    # 5. Gamma correction (lifts dark shadow details without washing out highlights)
    if gamma != 1.0 and gamma > 0:
        lut = [int(((i / 255.0) ** gamma) * 255.0) for i in range(256)]
        img_gray = img_gray.point(lut)
        
    # 6. Brightness multiplier
    if brightness != 1.0 and brightness > 0:
        enhancer = ImageEnhance.Brightness(img_gray)
        img_gray = enhancer.enhance(brightness)
        
    # 7. Contrast / Autocontrast
    if autocontrast:
        img_gray = ImageOps.autocontrast(img_gray, cutoff=0.5)
    elif contrast != 1.0:
        enhancer = ImageEnhance.Contrast(img_gray)
        img_gray = enhancer.enhance(contrast)
        
    # 8. Dithering / Binarization
    if dither == "atkinson":
        img_bw = atkinson_dither(img_gray, black_point, white_point, invert)
    elif dither == "floyd":
        arr = np.array(img_gray, dtype=np.float32)
        if white_point > black_point:
            arr = np.clip((arr - black_point) * (255.0 / (white_point - black_point)), 0, 255)
        stretched_gray = Image.fromarray(arr.astype(np.uint8), mode="L")
        img_bw = stretched_gray.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
        if invert:
            img_bw = ImageOps.invert(img_bw.convert("L")).convert("1")
    elif dither == "bayer":
        img_bw = bayer_dither(img_gray, black_point, white_point, invert)
    else:
        # Hard thresholding fallback
        pixels = list(img_gray.tobytes())
        bw_pixels = []
        for p in pixels:
            is_above = p >= threshold
            is_on = is_above if not invert else not is_above
            bw_pixels.append(255 if is_on else 0)
        img_bw = Image.new("1", (width, height))
        img_bw.putdata([1 if p == 255 else 0 for p in bw_pixels])
        
    # 9. Pack into SSD1306 bitmap bytes (1 bit per pixel, row-major)
    byte_array = bytearray(img_bw.tobytes())
    return img_bw, byte_array


def generate_ino_file(project_dir):
    project_name = os.path.basename(project_dir)
    ino_path = os.path.join(project_dir, f"{project_name}.ino")
    
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
#define OLED_RESET    -1
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
    delay(10);
  }}
  
  Serial.println("\\n--- ESP32 OLED Video Player Initialization ---");
  
  #if TEST_MODE
    Serial.println("Mode: TEST MODE ENABLED (playing only first 24 frames)");
  #else
    Serial.print("Mode: NORMAL MODE (playing full ");
    Serial.print(TOTAL_FRAMES);
    Serial.println(" frames)");
  #endif
  
  // Initialize I2C bus
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

def generate_preview_html(preview_dir, total_frames, fps, width, height, project_name):
    """
    Generates a browser-based OLED video preview simulator player.
    """
    html_path = os.path.join(preview_dir, "index.html")
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OLED Video Simulator - {project_name}</title>
  <style>
    :root {{
      --bg: #090a0f;
      --card: #131722;
      --border: #232936;
      --accent: #00e5ff;
      --oled-white: #e6ffff;
      --oled-blue: #00b0ff;
      --oled-amber: #ffaa00;
      --oled-green: #00e676;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }}
    body {{
      background: var(--bg);
      color: #e0e6ed;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .player-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 28px;
      width: 100%;
      max-width: 680px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }}
    .title {{ font-size: 1.15rem; font-weight: 700; color: #fff; letter-spacing: 0.5px; }}
    .badge {{
      background: rgba(0, 229, 255, 0.12);
      color: var(--accent);
      border: 1px solid rgba(0, 229, 255, 0.3);
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 0.75rem;
      font-weight: 600;
    }}
    .screen-bezel {{
      background: #000;
      border: 8px solid #1a1e29;
      border-radius: 12px;
      padding: 24px;
      display: flex;
      justify-content: center;
      align-items: center;
      margin-bottom: 24px;
      box-shadow: inset 0 0 20px rgba(0,0,0,0.9), 0 8px 16px rgba(0,0,0,0.5);
    }}
    .screen-canvas {{
      image-rendering: pixelated;
      width: 512px;
      height: 256px;
      background: #000;
      box-shadow: 0 0 24px rgba(0, 229, 255, 0.15);
      border-radius: 4px;
    }}
    .controls {{
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .scrubber-row {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    input[type=range] {{
      flex: 1;
      accent-color: var(--accent);
      cursor: pointer;
    }}
    .time-display {{
      font-size: 0.85rem;
      color: #8a99ad;
      min-width: 90px;
      text-align: right;
    }}
    .buttons-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }}
    .btn-group {{
      display: flex;
      gap: 8px;
    }}
    button {{
      background: #1e2433;
      color: #fff;
      border: 1px solid var(--border);
      padding: 8px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      transition: all 0.2s;
    }}
    button:hover {{
      background: #2b3348;
      border-color: var(--accent);
    }}
    button.primary {{
      background: var(--accent);
      color: #000;
      border: none;
    }}
    button.primary:hover {{
      background: #33ebff;
    }}
    select {{
      background: #1e2433;
      color: #fff;
      border: 1px solid var(--border);
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 0.85rem;
      cursor: pointer;
    }}
    .stats-card {{
      margin-top: 20px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      font-size: 0.8rem;
      color: #8a99ad;
    }}
    .stat-item b {{ color: #fff; display: block; font-size: 0.95rem; margin-top: 2px; }}
  </style>
</head>
<body>
  <div class="player-card">
    <div class="header">
      <div class="title">SSD1306 OLED Simulator</div>
      <div class="badge">128 × 64 Monochrome</div>
    </div>
    
    <div class="screen-bezel">
      <canvas id="screen" class="screen-canvas" width="{width}" height="{height}"></canvas>
    </div>
    
    <div class="controls">
      <div class="scrubber-row">
        <input type="range" id="scrubber" min="1" max="{total_frames}" value="1">
        <div id="timecode" class="time-display">00:00 / 00:00</div>
      </div>
      
      <div class="buttons-row">
        <div class="btn-group">
          <button id="btnPlay" class="primary">▶ Play</button>
          <button id="btnPrev">⏮ -1</button>
          <button id="btnNext">+1 ⏭</button>
        </div>
        
        <div class="btn-group">
          <select id="colorTheme">
            <option value="white">OLED Crisp White</option>
            <option value="blue">OLED Vibrant Blue</option>
            <option value="green">OLED Matrix Green</option>
            <option value="amber">OLED Retro Amber</option>
          </select>
          <select id="playSpeed">
            <option value="0.5">0.5x</option>
            <option value="1" selected>1.0x</option>
            <option value="1.5">1.5x</option>
            <option value="2">2.0x</option>
          </select>
        </div>
      </div>
    </div>
    
    <div class="stats-card">
      <div class="stat-item">Frames: <b id="frameStat">1 / {total_frames}</b></div>
      <div class="stat-item">Target Rate: <b>{fps} FPS</b></div>
      <div class="stat-item">Flash Size: <b>{total_frames * 1024 / 1024:.1f} KB</b></div>
    </div>
  </div>

  <script>
    const totalFrames = {total_frames};
    const baseFps = {fps};
    const canvas = document.getElementById('screen');
    const ctx = canvas.getContext('2d');
    const scrubber = document.getElementById('scrubber');
    const btnPlay = document.getElementById('btnPlay');
    const btnPrev = document.getElementById('btnPrev');
    const btnNext = document.getElementById('btnNext');
    const timecode = document.getElementById('timecode');
    const frameStat = document.getElementById('frameStat');
    const colorTheme = document.getElementById('colorTheme');
    const playSpeed = document.getElementById('playSpeed');

    let currentFrame = 1;
    let isPlaying = true;
    let animTimer = null;
    let speed = 1.0;
    const imgCache = new Map();

    const colors = {{
      white: [230, 255, 255],
      blue: [0, 176, 255],
      green: [0, 230, 118],
      amber: [255, 170, 0]
    }};

    function getFrameUrl(idx) {{
      const pad = String(idx).padStart(3, '0');
      return `frame_${{pad}}.png`;
    }}

    function loadFrame(idx, callback) {{
      if (imgCache.has(idx)) {{
        callback(imgCache.get(idx));
        return;
      }}
      const img = new Image();
      img.onload = () => {{
        imgCache.set(idx, img);
        callback(img);
      }};
      img.src = getFrameUrl(idx);
    }}

    function render(frameIdx) {{
      loadFrame(frameIdx, (img) => {{
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw monochrome image and apply OLED color tint
        ctx.drawImage(img, 0, 0);
        const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imgData.data;
        const tint = colors[colorTheme.value] || colors.white;
        
        for (let i = 0; i < data.length; i += 4) {{
          if (data[i] > 100) {{
            data[i] = tint[0];
            data[i + 1] = tint[1];
            data[i + 2] = tint[2];
          }} else {{
            data[i] = 0;
            data[i + 1] = 0;
            data[i + 2] = 0;
          }}
        }}
        ctx.putImageData(imgData, 0, 0);
      }});

      scrubber.value = frameIdx;
      frameStat.textContent = `${{frameIdx}} / ${{totalFrames}}`;
      
      const curSec = (frameIdx / baseFps).toFixed(1);
      const totalSec = (totalFrames / baseFps).toFixed(1);
      timecode.textContent = `${{curSec}}s / ${{totalSec}}s`;
    }}

    function tick() {{
      if (!isPlaying) return;
      currentFrame = (currentFrame % totalFrames) + 1;
      render(currentFrame);
      const delay = (1000 / (baseFps * speed));
      animTimer = setTimeout(tick, delay);
    }}

    function play() {{
      if (!isPlaying) {{
        isPlaying = true;
        btnPlay.textContent = '⏸ Pause';
        tick();
      }}
    }}

    function pause() {{
      isPlaying = false;
      clearTimeout(animTimer);
      btnPlay.textContent = '▶ Play';
    }}

    btnPlay.addEventListener('click', () => isPlaying ? pause() : play());
    btnNext.addEventListener('click', () => {{
      pause();
      currentFrame = (currentFrame % totalFrames) + 1;
      render(currentFrame);
    }});
    btnPrev.addEventListener('click', () => {{
      pause();
      currentFrame = currentFrame > 1 ? currentFrame - 1 : totalFrames;
      render(currentFrame);
    }});
    scrubber.addEventListener('input', (e) => {{
      pause();
      currentFrame = parseInt(e.target.value);
      render(currentFrame);
    }});
    playSpeed.addEventListener('change', (e) => {{
      speed = parseFloat(e.target.value);
    }});
    colorTheme.addEventListener('change', () => render(currentFrame));

    // Preload next frames
    function preload() {{
      for (let i = 1; i <= Math.min(totalFrames, 30); i++) {{
        loadFrame(i, () => {{}});
      }}
    }}

    preload();
    render(1);
    btnPlay.textContent = '⏸ Pause';
    tick();
  </script>
</body>
</html>
"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

# ==============================================================================
# MAIN PIPELINE
# ==============================================================================
def main():
    global CROP_TOP, CROP_BOTTOM, CROP_LEFT, CROP_RIGHT
    
    parse_arguments()
    check_prerequisites()
    
    # 1. Ensure target project directory exists
    if not os.path.exists(OUTPUT_PROJECT):
        print(f"Target project folder '{OUTPUT_PROJECT}' does not exist. Creating it...")
        os.makedirs(OUTPUT_PROJECT, exist_ok=True)
        
    # 2. Automatically generate the matching .ino sketch file
    generate_ino_file(OUTPUT_PROJECT)
    
    # 3. Locate video file
    video_file = INPUT_VIDEO
    if not os.path.exists(video_file):
        lower_files = {f.lower(): f for f in os.listdir(".")}
        if video_file.lower() in lower_files:
            video_file = lower_files[video_file.lower()]
        else:
            legacy_path = os.path.join(OUTPUT_PROJECT, INPUT_VIDEO)
            if os.path.exists(legacy_path):
                video_file = legacy_path
            else:
                print(f"[ERROR] Input video file '{INPUT_VIDEO}' not found at root or project folder.")
                sys.exit(1)
                
    # 4. Move video file inside project directory if not already there
    dest_video_path = os.path.join(OUTPUT_PROJECT, os.path.basename(video_file))
    if os.path.abspath(video_file) != os.path.abspath(dest_video_path):
        print(f"Moving video file '{video_file}' to '{dest_video_path}'...")
        shutil.move(video_file, dest_video_path)
        video_file = dest_video_path
            
    info = get_video_info(video_file)
    print("--- Video Information ---")
    print(f"File:       {video_file}")
    print(f"Duration:   {info['duration']:.2f} seconds")
    print(f"Resolution: {info['resolution']}")
    print(f"Orig FPS:   {info['fps']:.2f} FPS\n")
    
    # 5. Handle Auto-crop or Letterbox Detection
    if AUTOCROP:
        print("Running automatic letterbox detection across video frames...")
        auto_top, auto_bottom, auto_left, auto_right = auto_detect_letterbox(video_file)
        if auto_top > 0 or auto_bottom > 0:
            if CROP_TOP == 0: CROP_TOP = auto_top
            if CROP_BOTTOM == 0: CROP_BOTTOM = auto_bottom
            print(f"[Auto-Crop] Detected horizontal letterbox: top={auto_top}px, bottom={auto_bottom}px")
        else:
            print("[Auto-Crop] No significant black letterbox bars detected.")
            
    print("--- Crop & Processing Settings ---")
    print(f"Crop Margins: Top={CROP_TOP}px, Bottom={CROP_BOTTOM}px, Left={CROP_LEFT}px, Right={CROP_RIGHT}px")
    print(f"Fit Mode:     {FIT_MODE}")
    print(f"Dither Mode:  {DITHER}")
    print(f"Enhancements: Gamma={GAMMA:.2f}, Contrast={CONTRAST:.2f}, Sharpen={SHARPEN:.2f}, AutoContrast={AUTOCONTRAST}")
    print(f"Range Clip:   BlackPoint={BLACK_POINT}, WhitePoint={WHITE_POINT}\n")

    # Configure output directories
    preview_dir = os.path.join(OUTPUT_PROJECT, "preview")
    if os.path.exists(preview_dir):
        shutil.rmtree(preview_dir)
    os.makedirs(preview_dir, exist_ok=True)
    
    frames_h_path = os.path.join(OUTPUT_PROJECT, "frames.h")
    
    # Temporary directory for extracted frames
    temp_dir = tempfile.mkdtemp()
    
    # Extract frames using FFmpeg
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
        
    frame_files = sorted([f for f in os.listdir(temp_dir) if f.endswith(".png")])
    total_frames = len(frame_files)
    
    if total_frames == 0:
        print("[ERROR] No frames extracted by FFmpeg. Check video file.")
        shutil.rmtree(temp_dir)
        sys.exit(1)
        
    print(f"Extracted {total_frames} frames successfully. Processing, dithering and packing...")
    
    all_packed_frames = []
    preview_images = []
    
    for idx, frame_name in enumerate(frame_files):
        frame_path = os.path.join(temp_dir, frame_name)
        
        img_bw, packed_bytes = process_frame(
            frame_path, 
            FIT_MODE, 
            WIDTH, 
            HEIGHT, 
            CONTRAST, 
            THRESHOLD, 
            INVERT,
            DITHER,
            SHARPEN,
            BLACK_POINT,
            WHITE_POINT,
            CROP_TOP,
            CROP_BOTTOM,
            CROP_LEFT,
            CROP_RIGHT,
            GAMMA,
            BRIGHTNESS,
            AUTOCONTRAST
        )
        
        all_packed_frames.append(packed_bytes)
        preview_images.append(img_bw)
        
        preview_path = os.path.join(preview_dir, f"frame_{idx + 1:03d}.png")
        img_bw.save(preview_path)
        
    # Clean up temp frames
    shutil.rmtree(temp_dir)
    
    # Generate animated GIF preview (2x scale 256x128 for clear viewing)
    print("Generating animated GIF preview...")
    gif_path = os.path.join(preview_dir, "preview.gif")
    gif_frames = [im.resize((WIDTH * 2, HEIGHT * 2), Image.Resampling.NEAREST) for im in preview_images]
    frame_duration_ms = max(10, int(1000 / FPS))
    gif_frames[0].save(
        gif_path,
        save_all=True,
        append_images=gif_frames[1:],
        duration=frame_duration_ms,
        loop=0
    )
    print(f"Animated GIF preview generated: '{gif_path}'")
    
    # Generate Interactive HTML Player
    generate_preview_html(preview_dir, total_frames, FPS, WIDTH, HEIGHT, OUTPUT_PROJECT)
    print(f"Interactive OLED Preview Player generated: '{os.path.join(preview_dir, 'index.html')}'")

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
    print(f"Fit Mode:         {FIT_MODE}")
    print(f"Dither Algorithm: {DITHER} (sharpen={SHARPEN}, contrast={CONTRAST})")
    print(f"Bitmap Size:      {total_bytes} bytes ({total_bytes / 1024.0:.2f} KB)")
    print(f"Preview GIF:      '{gif_path}'")
    print(f"Preview Player:   '{os.path.join(preview_dir, 'index.html')}'")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
