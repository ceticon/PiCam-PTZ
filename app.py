#!/usr/bin/env python3

"""
==================================================
PiCam-PTZ
==================================================

Raspberry Pi 5
Camera Module 3
PCA9685 Servo Controller

Features:
- Live MJPEG video
- Pan / Tilt control
- Servo status API
- Full resolution photo capture
- Photo gallery
- Photo download
- Photo deletion

==================================================
"""

import io
import logging
import threading

from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_from_directory,
    abort,
    url_for
)

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

from servo import ServoController


# ==========================================
# CONFIGURATION
# ==========================================

HOST = "0.0.0.0"
PORT = 5000

VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720

PHOTO_WIDTH = 4608
PHOTO_HEIGHT = 2592

BASE_DIR = Path(__file__).resolve().parent

PHOTO_DIR = BASE_DIR / "photos"

PHOTO_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================
# FLASK
# ==========================================

app = Flask(__name__)

app.json.compact = False

logging.basicConfig(
    level=logging.INFO
)


# ==========================================
# STREAMING OUTPUT
# ==========================================

class StreamingOutput(io.BufferedIOBase):

    def __init__(self):

        self.frame = None

        self.condition = threading.Condition()

        self.frame_number = 0

    def write(self, buf):

        with self.condition:

            self.frame = bytes(buf)

            self.frame_number += 1

            self.condition.notify_all()

        return len(buf)


output = StreamingOutput()


# ==========================================
# CAMERA
# ==========================================

camera_lock = threading.Lock()

camera = Picamera2()

video_config = camera.create_video_configuration(
    main={
        "size": (
            VIDEO_WIDTH,
            VIDEO_HEIGHT
        )
    }
)

still_config = camera.create_still_configuration(
    main={
        "size": (
            PHOTO_WIDTH,
            PHOTO_HEIGHT
        ),
        "format": "RGB888"
    }
)

camera.configure(video_config)


def start_video():

    camera.start_recording(
        MJPEGEncoder(),
        FileOutput(output)
    )

    print("Camera streaming started")


start_video()


# ==========================================
# SERVO CONTROLLER
# ==========================================

servos = ServoController()

print("Servo controller initialized")


# ==========================================
# MAIN PAGE
# ==========================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ==========================================
# VIDEO STREAM
# ==========================================

def generate_frames():

    last_frame_number = -1

    while True:

        with output.condition:

            output.condition.wait_for(
                lambda: (
                    output.frame_number
                    != last_frame_number
                ),
                timeout=10
            )

            if (
                output.frame_number
                == last_frame_number
            ):
                continue

            frame = output.frame

            last_frame_number = (
                output.frame_number
            )

        if frame is None:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: "
            + str(len(frame)).encode()
            + b"\r\n\r\n"
            + frame
            + b"\r\n"
        )


@app.route("/video_feed")
def video_feed():

    return Response(
        generate_frames(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        )
    )


# ==========================================
# SERVO STATUS
# ==========================================

@app.route(
    "/api/status",
    methods=["GET"]
)
def servo_status():

    return jsonify(
        servos.get_status()
    )


# ==========================================
# PAN CONTROL
# ==========================================

@app.route(
    "/api/pan",
    methods=["POST"]
)
def set_pan():

    data = request.get_json(
        silent=True
    )

    if (
        not isinstance(data, dict)
        or "angle" not in data
    ):

        return jsonify({
            "error": "Missing angle"
        }), 400

    try:

        angle = float(
            data["angle"]
        )

        servos.set_pan(angle)

        return jsonify({
            "success": True,
            "status": servos.get_status()
        })

    except (
        ValueError,
        TypeError
    ) as error:

        return jsonify({
            "error": str(error)
        }), 400


# ==========================================
# TILT CONTROL
# ==========================================

@app.route(
    "/api/tilt",
    methods=["POST"]
)
def set_tilt():

    data = request.get_json(
        silent=True
    )

    if (
        not isinstance(data, dict)
        or "angle" not in data
    ):

        return jsonify({
            "error": "Missing angle"
        }), 400

    try:

        angle = float(
            data["angle"]
        )

        servos.set_tilt(angle)

        return jsonify({
            "success": True,
            "status": servos.get_status()
        })

    except (
        ValueError,
        TypeError
    ) as error:

        return jsonify({
            "error": str(error)
        }), 400


# ==========================================
# CENTER SERVOS
# ==========================================

@app.route(
    "/api/center",
    methods=["POST"]
)
def center_servos():

    servos.center()

    return jsonify({
        "success": True,
        "status": servos.get_status()
    })


# ==========================================
# TAKE PHOTO
# ==========================================

@app.route(
    "/api/photo",
    methods=["POST"]
)
def take_photo():

    # Prevent simultaneous photo captures.

    if not camera_lock.acquire(
        blocking=False
    ):

        return jsonify({
            "success": False,
            "error": "Camera is busy"
        }), 409

    filename = datetime.now().strftime(
        "%Y-%m-%d_%H%M%S_%f.jpg"
    )

    filepath = PHOTO_DIR / filename

    try:

        print(
            f"Taking photo: {filename}"
        )

        # Stop live MJPEG recording.

        camera.stop_recording()

        # Capture full-resolution JPEG.

        camera.switch_mode_and_capture_file(
            still_config,
            str(filepath)
        )

        # Restart live video.

        start_video()

        print(
            f"Photo saved: {filepath}"
        )

        return jsonify({
            "success": True,
            "filename": filename,
            "url": url_for(
                "view_photo",
                filename=filename
            ),
            "resolution": {
                "width": PHOTO_WIDTH,
                "height": PHOTO_HEIGHT
            }
        })

    except Exception as error:

        app.logger.exception(
            "Photo capture failed"
        )

        # Try to restore video streaming.

        try:

            camera.stop()

            camera.configure(
                video_config
            )

            start_video()

        except Exception:

            app.logger.exception(
                "Could not restore camera streaming"
            )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    finally:

        camera_lock.release()


# ==========================================
# VIEW PHOTO
# ==========================================

@app.route(
    "/photos/<path:filename>"
)
def view_photo(filename):

    return send_from_directory(
        PHOTO_DIR,
        filename
    )


# ==========================================
# PHOTO GALLERY
# ==========================================

@app.route("/gallery")
def gallery():

    photos = []

    for filepath in PHOTO_DIR.iterdir():

        if not filepath.is_file():
            continue

        if filepath.suffix.lower() not in (
            ".jpg",
            ".jpeg"
        ):
            continue

        stat = filepath.stat()

        photos.append({
            "filename": filepath.name,
            "url": url_for(
                "view_photo",
                filename=filepath.name
            ),
            "size_mb": round(
                stat.st_size / (
                    1024 * 1024
                ),
                2
            ),
            "timestamp": stat.st_mtime
        })

    # Newest photos first.

    photos.sort(
        key=lambda photo: (
            photo["timestamp"]
        ),
        reverse=True
    )

    return render_template(
        "gallery.html",
        photos=photos
    )


# ==========================================
# DOWNLOAD PHOTO
# ==========================================

@app.route(
    "/api/photo/download/<path:filename>",
    methods=["GET"]
)
def download_photo(filename):

    return send_from_directory(
        PHOTO_DIR,
        filename,
        as_attachment=True
    )


# ==========================================
# DELETE PHOTO
# ==========================================

@app.route(
    "/api/photo/delete/<path:filename>",
    methods=["DELETE"]
)
def delete_photo(filename):

    # Only allow filenames without paths.

    if (
        filename in (".", "..")
        or Path(filename).name != filename
        or "\\" in filename
        or not filename.lower().endswith(
            (".jpg", ".jpeg")
        )
    ):

        abort(400)

    filepath = PHOTO_DIR / filename

    if not filepath.is_file():

        abort(404)

    try:

        filepath.unlink()

        print(
            f"Photo deleted: {filename}"
        )

        return jsonify({
            "success": True,
            "filename": filename
        })

    except OSError as error:

        app.logger.exception(
            "Could not delete photo"
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    try:

        print("")
        print("================================")
        print("           PiCam-PTZ")
        print("================================")
        print(f"Web server port: {PORT}")
        print(
            f"Video: "
            f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"
        )
        print(
            f"Photos: "
            f"{PHOTO_WIDTH}x{PHOTO_HEIGHT}"
        )
        print("Pan:  PCA9685 channel 0")
        print("Tilt: PCA9685 channel 1")
        print(f"Photo directory: {PHOTO_DIR}")
        print("================================")
        print("")

        app.run(
            host=HOST,
            port=PORT,
            debug=False,
            threaded=True,
            use_reloader=False
        )

    except KeyboardInterrupt:

        print(
            "\nStopping PiCam-PTZ"
        )

    finally:

        servos.release()

        with camera_lock:

            try:

                camera.stop_recording()

            except Exception:

                pass

            camera.close()

        print(
            "PiCam-PTZ stopped"
        )