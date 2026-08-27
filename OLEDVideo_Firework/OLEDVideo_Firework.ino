/*
 * ESP32 SSD1306 OLED Video Player
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

void setup() {
  Serial.begin(115200);
  while (!Serial) {
    delay(10); // Wait for serial port to connect (mainly for native USB boards)
  }
  
  Serial.println("\n--- ESP32 OLED Video Player Initialization ---");
  
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
  // SSD1306 generally supports up to 400kHz standard, but many models work perfectly up to 800kHz on ESP32.
  // 800kHz is recommended to achieve a stable 24 FPS (rendering takes ~13ms instead of ~26ms at 400kHz).
  Serial.println("Setting I2C clock to Fast Mode (800 kHz)...");
  Wire.setClock(800000); 

  // Initialize display
  if (!display.begin(SSD1306_SWITCHCAPVCC, SCREEN_ADDRESS)) {
    Serial.println(F("[ERROR] SSD1306 allocation failed. Check wiring and address (0x3C)."));
    while (true) {
      // Loop forever on failure
      delay(1000);
    }
  }
  
  Serial.println("SSD1306 initialized successfully.");
  
  // Set Display Clock Divide Ratio/Oscillator Frequency (Command 0xD5)
  // Maximize internal oscillator frequency to eliminate camera banding and flicker
  display.ssd1306_command(0xD5);
  display.ssd1306_command(0xF0);

  display.clearDisplay();
  display.display();
  
  last_fps_report_time = millis();
}

void loop() {
  // Determine number of frames to play
  int frame_limit = TEST_MODE ? TEST_FRAMES : TOTAL_FRAMES;
  
  for (int i = 0; i < frame_limit; i++) {
    uint32_t frame_start_us = micros();
    
    // Clear back buffer
    display.clearDisplay();
    
    // Draw current frame from PROGMEM
    // Coordinates: (0,0), Data pointer: video_frames[i], Dimensions: 128x64, Color: SSD1306_WHITE (pixel ON)
    display.drawBitmap(0, 0, video_frames[i], SCREEN_WIDTH, SCREEN_HEIGHT, SSD1306_WHITE);
    
    // Transfer buffer to OLED screen over I2C
    display.display();
    
    uint32_t render_end_us = micros();
    uint32_t render_time_us = render_end_us - frame_start_us;
    
    frames_rendered++;
    
    // Diagnostic stats tracking (every 1 second)
    uint32_t current_time_ms = millis();
    if (current_time_ms - last_fps_report_time >= 1000) {
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
      Serial.print(" Hz");
      
      // Warn if rendering is too slow to sustain target FPS
      if (render_time_us > FRAME_PERIOD_US) {
        Serial.print(" [WARNING: I2C bottleneck! Speed too slow for 24 FPS]");
      }
      Serial.println();
    }
    
    // Frame rate control
    uint32_t elapsed_us = micros() - frame_start_us;
    if (elapsed_us < FRAME_PERIOD_US) {
      // Calculate remaining microseconds to hit target FPS
      uint32_t delay_us = FRAME_PERIOD_US - elapsed_us;
      delayMicroseconds(delay_us);
    } else {
      // Rendering took longer than target frame interval. 
      // Do not delay at all; run as fast as possible.
      // Yield to prevent watchdog reset on ESP32 core
      yield();
    }
  }
}
