# PiCam-PTZ 📷

PiCam-PTZ is a web-controlled pan-and-tilt camera built with a Raspberry Pi 5, a Raspberry Pi Camera Module 3, two micro servos, and a PCA9685 servo driver.

The Flask web interface provides live video streaming, pan/tilt controls, high-resolution photo capture, Full HD video recording, and separate photo and video galleries.

The interface can be accessed from a desktop computer, tablet, or smartphone connected to the same network.

## Features

- Live MJPEG camera stream in the browser (1280 × 720).
- Web-based pan and tilt control.
- Center command for returning the camera to its default position.
- Adjustable servo limits and movement settings in `config.json`.
- Smooth, incremental servo movement.
- Automatic servo release to reduce idle buzzing and heat.
- High-resolution still-photo capture (4608 × 2592).
- Photo gallery with download and delete options.
- Full HD video recording (1920 × 1080 at 30 fps).
- H.264 video encoding.
- Automatic conversion from H.264 to MP4 using FFmpeg.
- Start/stop recording controls.
- Blinking REC indicator and recording timer.
- Configurable recording duration.
- Video gallery with playback, download, and delete options.
- Responsive web interface for desktop, tablet, and mobile devices.

**Project status:** Live streaming, PTZ control, photo capture, video recording, and both galleries are implemented.

---

## Hardware Requirements

PiCam-PTZ uses a Raspberry Pi 5, a Camera Module 3, and two micro servos controlled through a PCA9685 PWM driver.

### Hardware List

The following components were used to build the project.

#### Electrokit

| Article No. | Component | Qty | Unit Price (SEK) | Total (SEK) |
|---|---|---:|---:|---:|
| 41020240 | Raspberry Pi Camera Module 3 | 1 | 271.20 | 271.20 |
| 41013136 | Analog Micro Servo 1.8 kg, 0.12 s | 2 | 39.20 | 78.40 |
| 41035663 | 16-Channel Servo Driver (PCA9685) | 1 | 159.20 | 159.20 |
| 41020800 | Raspberry Pi 5, 4 GB | 1 | 1,127.20 | 1,127.20 |
| 41019070 | 5 V DC, 2.4 A Power Supply (12 W) | 1 | 79.20 | 79.20 |
| 41020803 | Raspberry Pi 5 Case with Fan | 1 | 119.20 | 119.20 |
| 41020806 | Raspberry Pi 5 USB-C PD Power Supply (27 W) | 1 | 143.20 | 143.20 |
| | **Subtotal** | | | **1,977.60** |

#### Amazon

| Component | Qty | Total (SEK) |
|---|---:|---:|
| SanDisk Extreme 128 GB microSDXC Card + SD Adapter | 1 | 374.00 |

**Total hardware cost: 2,351.60 SEK**

*Prices are provided for reference and may change.*

### 3D Printed Parts

The pan/tilt camera mount is 3D printed.

- **Model:** Servo Pan Tilt – Raspberry Pi Camera
- **Designer:** japersik
- **Source:** Thingiverse, model 4710301

Model page: https://www.thingiverse.com/thing:4710301

The mount holds the Raspberry Pi Camera Module 3 and two micro servos, allowing horizontal (pan) and vertical (tilt) movement.

---

## Wiring

The PCA9685 communicates with the Raspberry Pi 5 using I²C.

### Raspberry Pi to PCA9685

| PCA9685 | Raspberry Pi 5 |
|---|---|
| VCC | 3.3 V |
| GND | GND |
| SDA | GPIO2 (Physical Pin 3) |
| SCL | GPIO3 (Physical Pin 5) |

### Servo Connections

| PCA9685 Channel | Function |
|---|---|
| Channel 0 | Pan |
| Channel 1 | Tilt |

### Servo Power Supply

The servos are powered by a separate regulated 5 V DC power supply connected to the PCA9685 servo power input (V+).

The external servo power supply and the Raspberry Pi must share a common ground.

**Important:** Do not power the servos directly from the Raspberry Pi GPIO pins.

Always verify the PCA9685 board's power connections before switching on the system.

---

## Software Requirements

- Raspberry Pi OS (64-bit).
- Python 3.
- Python virtual environment (`venv`).
- Picamera2.
- Flask.
- Adafruit CircuitPython ServoKit.
- PCA9685 dependencies.
- FFmpeg.
- I²C enabled on the Raspberry Pi.

The application has been developed on Raspberry Pi OS using Python 3.13.5 and a virtual environment named `myenv`.

---

## Installation

### 1. Install System Packages

Update the Raspberry Pi:

```bash
sudo apt update
sudo apt upgrade
```

Install the required system packages:

```bash
sudo apt install python3-picamera2 python3-flask python3-venv ffmpeg i2c-tools
```

### 2. Clone the Repository

Using SSH:

```bash
git clone git@github.com:ceticon/PiCam-PTZ.git
cd PiCam-PTZ
```

### 3. Create a Virtual Environment

Create the virtual environment with access to system-installed Python packages:

```bash
python3 -m venv --system-site-packages myenv
```

Activate it:

```bash
source myenv/bin/activate
```

The `--system-site-packages` option allows the virtual environment to access Picamera2 and other packages installed through Raspberry Pi OS.

### 4. Install Python Dependencies

Install the packages listed in `requirements.txt`:

```bash
python -m pip install -r requirements.txt
```

The current `requirements.txt` contains:

```text
Flask==3.1.1
adafruit-circuitpython-servokit==1.3.24
```

Adafruit ServoKit automatically installs its required dependencies.

### 5. Enable I²C

Open the Raspberry Pi configuration tool:

```bash
sudo raspi-config
```

Navigate to:

**Interface Options → I2C → Enable**

Reboot if required.

### 6. Verify the PCA9685

Run:

```bash
i2cdetect -y 1
```

The PCA9685 should normally appear at address `0x40`.

### 7. Verify Python Libraries

Activate the virtual environment and run:

```bash
python -c 'import flask; import picamera2; import adafruit_servokit; print("Alla bibliotek OK!")'
```

Expected output:

```text
Alla bibliotek OK!
```

---

## Configuration

Servo settings are stored in `config.json`.

The current configuration is:

```json
{
  "pan": {
    "channel": 0,
    "min": 20,
    "max": 160,
    "center": 90
  },
  "tilt": {
    "channel": 1,
    "min": 20,
    "max": 160,
    "center": 90
  },
  "servo": {
    "step_size": 1.0,
    "step_delay": 0.03,
    "min_pulse": 1000,
    "max_pulse": 2000,
    "auto_release": true,
    "release_delay": 1.0
  }
}
```

Adjust the angle limits to match your mechanical assembly.

Incorrect limits may cause a servo to push against a physical stop.

Pulse-width settings should also be compatible with the servos used.

---

## Running PiCam-PTZ

Navigate to the project directory:

```bash
cd ~/Projects/PiCam-PTZ
```

Activate the virtual environment:

```bash
source myenv/bin/activate
```

Start the application:

```bash
python app.py
```

Open the web interface from another device on the same network:

```text
http://picam-ptz:5000/
```

If hostname resolution is unavailable, use the Raspberry Pi's IP address instead.

---

## Web Interface

The web interface provides:

- Live camera streaming.
- Pan and tilt controls.
- Adjustable camera positioning.
- Center positioning.
- High-resolution photo capture.
- Video recording.
- Recording duration selection.
- Recording status and timer.
- Links to photo and video galleries.

The interface is designed for use on desktop computers, tablets, and smartphones.

---

## Photo Capture

The Raspberry Pi Camera Module 3 supports high-resolution still images.

PiCam-PTZ captures photos at:

**4608 × 2592 pixels**

Photos are stored in:

```text
photos/
```

Each photo receives a timestamp-based filename.

Example:

```text
2026-10-25_170904_775550.jpg
```

### Photo Gallery

The photo gallery is available at:

```text
/gallery
```

Features:

- Thumbnail overview.
- View captured photos.
- Download photos.
- Delete photos.

The `photos/` directory is excluded from Git using `.gitignore`.

---

## Video Recording

PiCam-PTZ supports Full HD video recording.

### Video Settings

| Parameter | Value |
|---|---|
| Resolution | 1920 × 1080 |
| Frame rate | 30 fps |
| Encoder | H.264 |
| Output format | MP4 |
| Conversion tool | FFmpeg |

### Recording Process

1. The user starts recording from the web interface.
2. Picamera2 records video using the H.264 encoder.
3. Video data is initially saved in H.264 format.
4. When recording stops, FFmpeg converts the recording into an MP4 container.
5. The original H.264 file is deleted after successful conversion.
6. The MP4 file is available in the video gallery.

The conversion uses stream copying, avoiding unnecessary re-encoding.

### Recording Controls

The web interface includes:

- Start recording button.
- Stop recording button.
- Blinking REC indicator.
- Elapsed recording timer.
- Recording status information.
- Configurable recording duration.

Available recording durations:

| Duration | Time |
|---|---|
| 30 seconds | 00:30 |
| 60 seconds | 01:00 |
| 300 seconds | 05:00 |
| 600 seconds | 10:00 |
| 1800 seconds | 30:00 |
| 3600 seconds | 60:00 |

### Video Storage

Videos are stored in:

```text
videos/
```

Example filename:

```text
video_20261026_224903_888788.mp4
```

The `videos/` directory is excluded from Git using `.gitignore`.

---

## Video Gallery

The video gallery is available at:

```text
/videos
```

Features:

- Overview of recorded videos.
- Video playback directly in the browser.
- Download recordings.
- Delete recordings.
- Display video filenames and file sizes.

Videos are stored locally on the Raspberry Pi.

---

## Servo Auto-Release

Servos may buzz and warm up when continuously supplied with a positioning signal, even while stationary.

PiCam-PTZ supports independent automatic release of the pan and tilt servos.

### How It Works

1. A movement command sets a new target angle.
2. The servo moves toward that target in small steps.
3. After reaching its target, the configured release delay begins.
4. When the delay expires, the servo PWM signal is disabled.
5. The servo is activated again when a new movement command is received.

This reduces idle buzzing and heat.

**Important:** Releasing the PWM signal also removes active holding torque.

If the camera mount needs a servo to maintain its position against gravity or other forces, disable auto-release or modify the mechanical design.

---

## Project Structure

```text
PiCam-PTZ/
├── app.py                  # Flask application and camera handling
├── servo.py                # Pan/tilt servo controller
├── config.json             # Servo configuration
├── requirements.txt        # Python dependencies
├── .gitignore              # Git exclusions
├── README.md               # Project documentation
│
├── static/
│   ├── script.js           # Main web interface
│   ├── style.css           # Web interface styling
│   └── videos.js           # Video gallery functions
│
├── templates/
│   ├── index.html          # Camera and PTZ interface
│   ├── gallery.html        # Photo gallery
│   └── videos.html         # Video gallery
│
├── photos/                 # Captured photos (not tracked by Git)
├── videos/                 # Recorded videos (not tracked by Git)
│
├── docs/
│   └── images/             # Project photos and screenshots
│
└── myenv/                  # Python virtual environment (not tracked by Git)
```

The `docs/images/` directory is intended for project photos and screenshots and can be added when images are available.

Backup and test files are excluded from Git.

---

## Security Notes

PiCam-PTZ is intended for use on a trusted local network.

The application does not currently provide a complete authentication and authorization system.

Before exposing the application outside the local network, implement appropriate security measures.

The application and its dependencies are tailored to Raspberry Pi hardware.

Running PiCam-PTZ on a regular desktop computer will require hardware-specific modifications.

---

## Planned Improvements

Possible future improvements include:

- Automatic startup using systemd.
- Automatic restart if the application crashes.
- Additional camera settings.
- Improved recording management.
- Optional authentication.
- Improved mobile interface.

---

## Repository

**GitHub:** ceticon/PiCam-PTZ

---

## License

No license has been specified yet.

---

**PiCam-PTZ – Raspberry Pi Pan/Tilt Camera Project**