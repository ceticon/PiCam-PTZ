PiCam-PTZ 📷
PiCam-PTZ is a web-controlled pan-and-tilt camera built with a Raspberry Pi 5, a Raspberry Pi Camera Module 3, two servos, and a PCA9685 servo driver.
The Flask web interface provides a live camera stream, pan/tilt controls, still-photo capture, and a photo gallery. It can be opened from another device on the same network.
Features
Live MJPEG camera stream in the browser (configured for 1280 × 720).
Web-based pan and tilt control, including a center command.
Adjustable servo limits and movement settings in `config.json`.
Smooth, incremental servo movement.
Automatic servo release: PWM output is disabled after a servo reaches its target and the configured delay expires, reducing idle buzzing and heat.
Still-photo capture using the Camera Module 3's high-resolution mode.
Photo gallery with download and delete options.
Flask-based interface usable from a desktop, tablet, or phone.
> **Status:** Live streaming, PTZ control, still photos, and the photo gallery are implemented. Video recording is a planned enhancement, not part of this release.
Hardware
Component	Description
Single-board computer	Raspberry Pi 5 (tested with 4 GB RAM)
Camera	Raspberry Pi Camera Module 3 (IMX708)
Servo controller	PCA9685, connected via I²C
Pan servo	PCA9685 channel 0
Tilt servo	PCA9685 channel 1
Servo power	Separate regulated 5 V supply
Mount	Pan/tilt assembly, including 3D-printed parts
Important: Power the servos from a suitable external 5 V supply rather than from the Raspberry Pi's GPIO power pins. The Raspberry Pi and servo supply must share a common ground. Double-check the PCA9685 board's power connections before switching on.
Software requirements
Raspberry Pi OS (64-bit)
Python 3 and `venv`
Camera Module 3 support through Picamera2 / Raspberry Pi's camera stack
Flask
Adafruit CircuitPython ServoKit and its PCA9685 dependencies
I²C enabled on the Raspberry Pi
The application has been developed on Raspberry Pi OS with a virtual environment named `myenv`.
Installation
Clone the repository:
```bash
git clone git@github.com:ceticon/PiCam-PTZ.git
cd PiCam-PTZ
```
Create and activate a virtual environment:
```bash
python3 -m venv --system-site-packages myenv
source myenv/bin/activate
```
Install the main Python packages:
```bash
python -m pip install flask adafruit-circuitpython-servokit
```
Picamera2 is commonly installed through Raspberry Pi OS packages:
```bash
sudo apt update
sudo apt install python3-picamera2
```
The virtual environment uses `--system-site-packages` so it can access system-installed camera packages. Depending on the Raspberry Pi OS image, additional system packages or permissions may be required.
Enable I²C using `sudo raspi-config` (under Interface Options), then reboot if prompted.
Check that the PCA9685 is detected (typically at address `0x40`):
```bash
sudo apt install i2c-tools
i2cdetect -y 1
```
Configuration
Servo settings are stored in `config.json`. The current configuration is:
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
Adjust the angle limits to match your own mechanical assembly. Incorrect limits can cause a servo to push against a physical stop. Pulse-width settings should also be compatible with the servos you use.
Running PiCam-PTZ
From the project directory:
```bash
source myenv/bin/activate
python app.py
```
Open the web interface from another device on the same network, using the Raspberry Pi's hostname or IP address:
```text
http://picam-ptz:5000/
```
If hostname resolution is unavailable, use the Raspberry Pi's IP address instead.
Web interface
Watch the live video stream.
Move the camera horizontally (pan) and vertically (tilt).
Return the camera to its configured center position.
Capture a high-resolution still photo.
Open the photo gallery to view, download, or delete captured images.
The application stores photos locally in `photos/`. This folder is excluded from Git via `.gitignore`.
Project structure
```text
PiCam-PTZ/
├── app.py                  # Flask application and camera handling
├── servo.py                # Pan/tilt servo controller
├── config.json             # Servo configuration
├── .gitignore
├── README.md
├── static/
│   ├── script.js           # Web interface behavior
│   └── style.css           # Web interface styling
├── templates/
│   ├── index.html          # Camera and PTZ interface
│   └── gallery.html        # Photo gallery
├── photos/                 # Captured photos (not tracked by Git)
└── myenv/                  # Python virtual environment (not tracked by Git)
```
Servo auto-release
Servos may buzz and warm up when continuously supplied with a positioning signal, even while stationary. PiCam-PTZ supports independent automatic release of the pan and tilt servos:
A movement command sets a new target angle.
The servo moves toward that target in small steps.
After the servo arrives and the configured `release_delay` has elapsed, its PWM signal is disabled.
The servo is driven again when a new movement command is received.
This reduces idle buzzing and heat, but releasing the PWM also removes active holding torque. If the camera mount needs a servo to hold position against gravity or other forces, disable auto-release or change the mechanical design accordingly.
Planned improvements
Full HD (1920 × 1080) video recording, targeting 30 fps.
Start/stop recording controls and a recording indicator.
Video gallery with download and delete actions.
Configurable recording duration.
Notes
This project is intended for use on a trusted local network. Before exposing it outside your LAN, add suitable authentication and access controls.
The application and its dependencies are tailored to Raspberry Pi hardware; running it on a regular desktop computer will require hardware-specific changes.
Repository
GitHub: ceticon/PiCam-PTZ