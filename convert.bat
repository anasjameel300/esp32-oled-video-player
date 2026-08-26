@echo off
title ESP32 OLED Video Conversion Launcher
echo =====================================================================
echo          ESP32 SSD1306 OLED Video Conversion Pipeline
echo =====================================================================
echo.
echo Select the video project you want to convert to 1-bit OLED frames:
echo.
echo   [1] Video 1 (Video.mp4)    --^> target: OLEDVideo/
echo   [2] Video 2 (video1.mp4)   --^> target: OLEDVideo_Firework/
echo   [3] Video 3 (Video2.mp4)   --^> target: OLEDVideo3/
echo   [4] Custom conversion      --^> Enter paths and settings manually
echo   [5] Exit
echo.
echo =====================================================================
set /p choice="Enter your choice (1-5): "
echo.

if "%choice%"=="1" (
    echo Processing Video 1 (OLEDVideo/video.mp4 --^> OLEDVideo)...
    python convert.py OLEDVideo/video.mp4 OLEDVideo 30 128
) else if "%choice%"=="2" (
    echo Processing Video 2 (OLEDVideo_Firework/video1.mp4 --^> OLEDVideo_Firework)...
    python convert.py OLEDVideo_Firework/video1.mp4 OLEDVideo_Firework 30 128
) else if "%choice%"=="3" (
    echo Processing Video 3 (OLEDVideo3/Video2.mp4 --^> OLEDVideo3)...
    python convert.py OLEDVideo3/Video2.mp4 OLEDVideo3 30 128
) else if "%choice%"=="4" (
    echo === Custom Conversion Parameters ===
    set /p video_path="Enter input video file path (e.g., custom_video.mp4): "
    set /p proj_dir="Enter target project folder (e.g., OLEDVideo): "
    set /p fps_val="Enter target FPS (e.g., 30): "
    set /p thresh_val="Enter threshold (0-255, default 128): "
    echo.
    echo Running custom conversion...
    python convert.py %video_path% %proj_dir% %fps_val% %thresh_val%
) else if "%choice%"=="5" (
    echo Exiting.
    exit /b
) else (
    echo Invalid choice.
)

pause
