#!/usr/bin/env python3
"""PiCam-PTZ: live view, PTZ, photos, and H.264 recording with MP4 conversion."""

import io
import logging
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request, send_from_directory, url_for
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder, MJPEGEncoder
from picamera2.outputs import FileOutput
from servo import ServoController

HOST = "0.0.0.0"
PORT = 5000
VIDEO_WIDTH, VIDEO_HEIGHT = 1280, 720
RECORD_WIDTH, RECORD_HEIGHT = 1920, 1080
RECORD_FPS = 30
RECORD_BITRATE = 10_000_000
DEFAULT_RECORD_SECONDS = 60
MAX_RECORD_SECONDS = 3600
PHOTO_WIDTH, PHOTO_HEIGHT = 4608, 2592
BASE_DIR = Path(__file__).resolve().parent
PHOTO_DIR = BASE_DIR / "photos"
VIDEO_DIR = BASE_DIR / "videos"
PHOTO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.json.compact = False
logging.basicConfig(level=logging.INFO)


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
camera_lock = threading.RLock()
record_lock = threading.Lock()
camera = Picamera2()

# The camera runs one 1080p main stream for recording and one 720p lores
# stream for the browser. Both encoders share the same Picamera2 instance.
video_config = camera.create_video_configuration(
    main={"size": (RECORD_WIDTH, RECORD_HEIGHT), "format": "YUV420"},
    lores={"size": (VIDEO_WIDTH, VIDEO_HEIGHT), "format": "YUV420"},
    controls={"FrameRate": RECORD_FPS},
    buffer_count=6,
)
still_config = camera.create_still_configuration(
    main={"size": (PHOTO_WIDTH, PHOTO_HEIGHT), "format": "RGB888"}
)
camera.configure(video_config)

stream_encoder = MJPEGEncoder()
stream_encoder.name = "lores"
record_encoder = None
record_filename = None
record_started = None
record_duration = None
record_timer = None
recording = False
record_error = None


def start_stream():
    camera.start_encoder(stream_encoder, FileOutput(output))
    camera.start()
    app.logger.info("Camera streaming started")


start_stream()
servos = ServoController()
app.logger.info("Servo controller initialized")


def _record_status():
    with record_lock:
        elapsed = time.monotonic() - record_started if recording else 0
        return {
            "recording": recording,
            "filename": record_filename,
            "elapsed_seconds": round(elapsed, 1),
            "duration_seconds": record_duration,
            "error": record_error,
        }


def _stop_recording():
    global record_encoder, record_filename, record_started
    global record_duration, record_timer, recording, record_error

    # Hold the recording lock through conversion, so no second recording
    # can start while the first file is being finalized.
    with record_lock:
        if not recording:
            return False

        timer = record_timer
        record_timer = None
        if timer is not None:
            timer.cancel()

        raw_path = VIDEO_DIR / record_filename
        mp4_path = raw_path.with_suffix(".mp4")

        try:
            with camera_lock:
                camera.stop_encoder(record_encoder)

            if not raw_path.is_file() or raw_path.stat().st_size == 0:
                raise RuntimeError(f"No video data was saved: {raw_path}")

            # Copy H.264 into MP4 without re-encoding.
            # -framerate provides timestamps for the raw H.264 input.
            command = [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-y", "-framerate", str(RECORD_FPS),
                "-i", str(raw_path),
                "-c:v", "copy", "-movflags", "+faststart",
                str(mp4_path),
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                raise RuntimeError(
                    "FFmpeg conversion failed: " + result.stderr.strip()
                )
            if not mp4_path.is_file() or mp4_path.stat().st_size == 0:
                raise RuntimeError("MP4 output is missing or empty")

            # Delete raw recording only after a valid nonempty MP4 exists.
            raw_path.unlink()
            record_filename = mp4_path.name
            record_error = None
            app.logger.info(
                "MP4 ready: %s (%d bytes)",
                mp4_path.name, mp4_path.stat().st_size
            )
        except Exception as error:
            record_error = str(error)
            app.logger.exception(
                "Recording finalization failed; raw H.264 retained if available"
            )
            # Preserve raw H.264 for troubleshooting and manual recovery.
            raise
        finally:
            recording = False
            record_encoder = None
            record_started = None
            record_duration = None

        return True


def _timer_stop_recording():
    try:
        _stop_recording()
    except Exception:
        app.logger.exception("Automatic recording stop failed")


@app.route("/")
def index():
    return render_template("index.html")


def generate_frames():
    last_frame_number = -1
    while True:
        with output.condition:
            output.condition.wait_for(
                lambda: output.frame_number != last_frame_number, timeout=10
            )
            if output.frame_number == last_frame_number:
                continue
            frame = output.frame
            last_frame_number = output.frame_number
        if frame is None:
            continue
        yield (
            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
            + str(len(frame)).encode()
            + b"\r\n\r\n"
            + frame
            + b"\r\n"
        )


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/api/status")
def servo_status():
    return jsonify(servos.get_status())


@app.route("/api/pan", methods=["POST"])
def set_pan():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "angle" not in data:
        return jsonify({"error": "Missing angle"}), 400
    try:
        servos.set_pan(float(data["angle"]))
        return jsonify({"success": True, "status": servos.get_status()})
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400


@app.route("/api/tilt", methods=["POST"])
def set_tilt():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "angle" not in data:
        return jsonify({"error": "Missing angle"}), 400
    try:
        servos.set_tilt(float(data["angle"]))
        return jsonify({"success": True, "status": servos.get_status()})
    except (ValueError, TypeError) as error:
        return jsonify({"error": str(error)}), 400


@app.route("/api/center", methods=["POST"])
def center_servos():
    servos.center()
    return jsonify({"success": True, "status": servos.get_status()})


@app.route("/api/video/status")
def video_recording_status():
    return jsonify(_record_status())


@app.route("/api/video/start", methods=["POST"])
def start_recording():
    global record_encoder, record_filename, record_started
    global record_duration, record_timer, recording, record_error
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Expected JSON object"}), 400
    try:
        duration = int(data.get("duration", DEFAULT_RECORD_SECONDS))
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid duration"}), 400
    if not 1 <= duration <= MAX_RECORD_SECONDS:
        return jsonify({"success": False, "error": "Duration must be 1-3600 seconds"}), 400

    with record_lock:
        if recording:
            return jsonify({"success": False, "error": "Already recording"}), 409
        if not camera_lock.acquire(blocking=False):
            return jsonify({"success": False, "error": "Camera is busy"}), 409
        try:
            filename = datetime.now().strftime("video_%Y%m%d_%H%M%S_%f.h264")
            encoder = H264Encoder(bitrate=RECORD_BITRATE)
            encoder.name = "main"
            camera.start_encoder(
                encoder, FileOutput(str(VIDEO_DIR / filename))
            )
            record_encoder = encoder
            record_filename = filename
            record_started = time.monotonic()
            record_duration = duration
            record_error = None
            recording = True
            record_timer = threading.Timer(duration, _timer_stop_recording)
            record_timer.daemon = True
            record_timer.start()
            app.logger.info("Recording started: %s", filename)
        except Exception as error:
            app.logger.exception("Could not start recording")
            return jsonify({"success": False, "error": str(error)}), 500
        finally:
            camera_lock.release()
    return jsonify({"success": True, **_record_status()})


@app.route("/api/video/stop", methods=["POST"])
def stop_recording():
    try:
        stopped = _stop_recording()
    except Exception as error:
        app.logger.exception("Could not stop recording")
        return jsonify({"success": False, "error": str(error)}), 500
    if not stopped:
        return jsonify({"success": False, "error": "Not recording"}), 409
    return jsonify({"success": True, **_record_status()})


@app.route("/api/photo", methods=["POST"])
def take_photo():
    # Acquire record_lock first so recording cannot start during photo capture.
    with record_lock:
        if recording:
            return jsonify({"success": False, "error": "Recording in progress"}), 409
        if not camera_lock.acquire(blocking=False):
            return jsonify({"success": False, "error": "Camera is busy"}), 409
    filename = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f.jpg")
    filepath = PHOTO_DIR / filename
    try:
        camera.stop_encoder(stream_encoder)
        camera.switch_mode_and_capture_file(still_config, str(filepath))
        camera.stop()
        camera.configure(video_config)
        start_stream()
        return jsonify({
            "success": True,
            "filename": filename,
            "url": url_for("view_photo", filename=filename),
            "resolution": {"width": PHOTO_WIDTH, "height": PHOTO_HEIGHT},
        })
    except Exception as error:
        app.logger.exception("Photo capture failed")
        try:
            camera.stop()
            camera.configure(video_config)
            start_stream()
        except Exception:
            app.logger.exception("Could not restore camera streaming")
        return jsonify({"success": False, "error": str(error)}), 500
    finally:
        camera_lock.release()


@app.route("/photos/<path:filename>")
def view_photo(filename):
    return send_from_directory(PHOTO_DIR, filename)


@app.route("/gallery")
def gallery():
    photos = []
    for filepath in PHOTO_DIR.iterdir():
        if not filepath.is_file() or filepath.suffix.lower() not in (".jpg", ".jpeg"):
            continue
        stat = filepath.stat()
        photos.append({
            "filename": filepath.name,
            "url": url_for("view_photo", filename=filepath.name),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "timestamp": stat.st_mtime,
        })
    photos.sort(key=lambda photo: photo["timestamp"], reverse=True)
    return render_template("gallery.html", photos=photos)


@app.route("/api/photo/download/<path:filename>")
def download_photo(filename):
    return send_from_directory(PHOTO_DIR, filename, as_attachment=True)


@app.route("/api/photo/delete/<path:filename>", methods=["DELETE"])
def delete_photo(filename):
    if (
        filename in (".", "..")
        or Path(filename).name != filename
        or "\\" in filename
        or not filename.lower().endswith((".jpg", ".jpeg"))
    ):
        abort(400)
    filepath = PHOTO_DIR / filename
    if not filepath.is_file():
        abort(404)
    try:
        filepath.unlink()
        return jsonify({"success": True, "filename": filename})
    except OSError as error:
        app.logger.exception("Could not delete photo")
        return jsonify({"success": False, "error": str(error)}), 500


def _valid_video_filename(filename):
    return (
        filename not in (".", "..")
        and Path(filename).name == filename
        and "\\\\" not in filename
        and filename.lower().endswith(".mp4")
    )


@app.route("/videos")
def video_gallery():
    videos = []
    for filepath in VIDEO_DIR.glob("*.mp4"):
        if not filepath.is_file():
            continue
        stat = filepath.stat()
        videos.append({
            "filename": filepath.name,
            "url": url_for("view_video", filename=filepath.name),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "timestamp": stat.st_mtime,
        })
    videos.sort(key=lambda video: video["timestamp"], reverse=True)
    return render_template("videos.html", videos=videos)


@app.route("/videos/<filename>")
def view_video(filename):
    if not _valid_video_filename(filename):
        abort(400)
    return send_from_directory(VIDEO_DIR, filename, mimetype="video/mp4", conditional=True)


@app.route("/api/video/download/<filename>")
def download_video(filename):
    if not _valid_video_filename(filename):
        abort(400)
    return send_from_directory(VIDEO_DIR, filename, as_attachment=True)


@app.route("/api/video/delete/<filename>", methods=["DELETE"])
def delete_video(filename):
    if not _valid_video_filename(filename):
        abort(400)
    with record_lock:
        # Avoid deleting the current recording or output being finalized.
        if recording or (record_filename and Path(record_filename).stem == Path(filename).stem):
            if recording:
                return jsonify({"success": False, "error": "Inspelning pågår"}), 409
        filepath = VIDEO_DIR / filename
        if not filepath.is_file():
            abort(404)
        try:
            filepath.unlink()
        except OSError as error:
            return jsonify({"success": False, "error": str(error)}), 500
    return jsonify({"success": True, "filename": filename})


if __name__ == "__main__":
    try:
        print("PiCam-PTZ | Web port:", PORT)
        print("Live:", VIDEO_WIDTH, "x", VIDEO_HEIGHT)
        print("Record:", RECORD_WIDTH, "x", RECORD_HEIGHT, "@", RECORD_FPS, "fps")
        print("Photos:", PHOTO_DIR)
        print("Videos:", VIDEO_DIR)
        app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("Stopping PiCam-PTZ")
    finally:
        try:
            _stop_recording()
        except Exception:
            app.logger.exception("Could not finalize recording")
        servos.release()
        with camera_lock:
            try:
                camera.stop_encoder(stream_encoder)
            except Exception:
                pass
            try:
                camera.stop()
            except Exception:
                pass
            camera.close()
