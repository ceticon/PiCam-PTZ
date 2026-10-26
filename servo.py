#!/usr/bin/env python3

"""
PiCam-PTZ
Servo controller using PCA9685

Features:
- Configuration from config.json
- Smooth servo movement
- Non-blocking control
- Pan and Tilt
- Center function
- Thread-safe operation
- Automatic servo pulse release
- Independent release timers for pan and tilt
"""

import json
import math
import threading
import time
from pathlib import Path

from adafruit_servokit import ServoKit


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"

I2C_ADDRESS = 0x40


# ==========================================
# SERVO CONTROLLER
# ==========================================

class ServoController:

    def __init__(self):

        print("Loading servo configuration...")

        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            self.config = json.load(file)

        self.pan_config = self.config["pan"]
        self.tilt_config = self.config["tilt"]
        self.servo_config = self.config["servo"]

        self.step_size = float(
            self.servo_config["step_size"]
        )

        self.step_delay = float(
            self.servo_config["step_delay"]
        )

        self.auto_release = self.servo_config.get(
            "auto_release", True
        )

        self.release_delay = float(
            self.servo_config.get("release_delay", 1.0)
        )

        if (
            not math.isfinite(self.step_size)
            or not math.isfinite(self.step_delay)
            or self.step_size <= 0
            or self.step_delay <= 0
        ):
            raise ValueError(
                "step_size and step_delay must be finite and > 0"
            )

        if (
            not math.isfinite(self.release_delay)
            or self.release_delay < 0
        ):
            raise ValueError(
                "release_delay must be finite and >= 0"
            )

        min_pulse = int(
            self.servo_config["min_pulse"]
        )

        max_pulse = int(
            self.servo_config["max_pulse"]
        )

        print("Initializing PCA9685...")

        self.kit = ServoKit(
            channels=16,
            address=I2C_ADDRESS
        )

        self.pan_servo = self.kit.servo[
            self.pan_config["channel"]
        ]

        self.tilt_servo = self.kit.servo[
            self.tilt_config["channel"]
        ]

        self.pan_servo.set_pulse_width_range(
            min_pulse,
            max_pulse
        )

        self.tilt_servo.set_pulse_width_range(
            min_pulse,
            max_pulse
        )

        # Current commanded positions.
        # These are not measured physical positions.
        self.pan_angle = None
        self.tilt_angle = None

        # Desired positions
        self.pan_target = None
        self.tilt_target = None

        # Time when each target was reached
        self.pan_arrived_at = None
        self.tilt_arrived_at = None

        # True when PWM output is disabled
        self.pan_released = True
        self.tilt_released = True

        self.lock = threading.RLock()
        self.stop_event = threading.Event()

        self.worker = threading.Thread(
            target=self._movement_loop,
            daemon=True
        )

        self.worker.start()

        print("Servo controller initialized")
        print(f"Auto release: {self.auto_release}")
        print(f"Release delay: {self.release_delay} s")

    # ======================================
    # LIMIT ANGLE
    # ======================================

    def limit_angle(self, angle, config):

        angle = float(angle)

        if not math.isfinite(angle):
            raise ValueError("Angle must be finite")

        return max(
            float(config["min"]),
            min(float(config["max"]), angle)
        )

    # ======================================
    # PAN CONTROL
    # ======================================

    def set_pan(self, angle):

        angle = self.limit_angle(
            angle,
            self.pan_config
        )

        with self.lock:

            # Do not reactivate an already released
            # servo when the target is unchanged.
            if (
                self.pan_released
                and self.pan_angle is not None
                and abs(angle - self.pan_angle) < 0.0001
            ):
                return

            self.pan_target = angle

            # A new target invalidates the old arrival time.
            if (
                self.pan_angle is None
                or abs(angle - self.pan_angle) > 0.0001
            ):
                self.pan_arrived_at = None

        print(f"Pan target: {angle:.1f}°")

    # ======================================
    # TILT CONTROL
    # ======================================

    def set_tilt(self, angle):

        angle = self.limit_angle(
            angle,
            self.tilt_config
        )

        with self.lock:

            if (
                self.tilt_released
                and self.tilt_angle is not None
                and abs(angle - self.tilt_angle) < 0.0001
            ):
                return

            self.tilt_target = angle

            if (
                self.tilt_angle is None
                or abs(angle - self.tilt_angle) > 0.0001
            ):
                self.tilt_arrived_at = None

        print(f"Tilt target: {angle:.1f}°")

    # ======================================
    # CENTER
    # ======================================

    def center(self):

        print("Centering servos...")

        self.set_pan(
            self.pan_config["center"]
        )

        self.set_tilt(
            self.tilt_config["center"]
        )

    # ======================================
    # MOVE ONE STEP
    # ======================================

    def _move_step(self, current, target):

        if target is None:
            return current

        if current is None:
            return target

        difference = target - current

        if abs(difference) <= self.step_size:
            return target

        if difference > 0:
            return current + self.step_size

        return current - self.step_size

    # ======================================
    # UPDATE ONE SERVO
    # ======================================

    def _update_servo(
        self,
        servo,
        current,
        target,
        arrived_at,
        released,
        name,
        now
    ):

        if target is None:
            return current, arrived_at, released

        # ----------------------------------
        # SERVO NEEDS TO MOVE
        # ----------------------------------

        if (
            current is None
            or abs(target - current) > 0.0001
        ):

            new_angle = self._move_step(
                current,
                target
            )

            servo.angle = new_angle

            current = new_angle
            released = False

            # Start timer only when target is reached.
            if abs(target - current) <= 0.0001:

                arrived_at = now

                print(
                    f"{name} reached target: "
                    f"{current:.1f}°"
                )

            else:
                arrived_at = None

            return current, arrived_at, released

        # ----------------------------------
        # SERVO HAS REACHED TARGET
        # ----------------------------------

        if not released:

            if arrived_at is None:
                arrived_at = now

            if (
                self.auto_release
                and now - arrived_at >= self.release_delay
            ):

                servo.angle = None
                released = True

                print(f"{name} servo released")

        return current, arrived_at, released

    # ======================================
    # BACKGROUND MOVEMENT LOOP
    # ======================================

    def _movement_loop(self):

        print("Servo movement thread started")

        while not self.stop_event.is_set():

            now = time.monotonic()

            with self.lock:

                # PAN
                (
                    self.pan_angle,
                    self.pan_arrived_at,
                    self.pan_released
                ) = self._update_servo(
                    servo=self.pan_servo,
                    current=self.pan_angle,
                    target=self.pan_target,
                    arrived_at=self.pan_arrived_at,
                    released=self.pan_released,
                    name="PAN",
                    now=now
                )

                # TILT
                (
                    self.tilt_angle,
                    self.tilt_arrived_at,
                    self.tilt_released
                ) = self._update_servo(
                    servo=self.tilt_servo,
                    current=self.tilt_angle,
                    target=self.tilt_target,
                    arrived_at=self.tilt_arrived_at,
                    released=self.tilt_released,
                    name="TILT",
                    now=now
                )

            self.stop_event.wait(self.step_delay)

        print("Servo movement thread stopped")

    # ======================================
    # STATUS
    # ======================================

    def get_status(self):

        with self.lock:

            return {
                "pan": self.pan_angle,
                "tilt": self.tilt_angle,

                "pan_target": self.pan_target,
                "tilt_target": self.tilt_target,

                "pan_min": self.pan_config["min"],
                "pan_max": self.pan_config["max"],

                "tilt_min": self.tilt_config["min"],
                "tilt_max": self.tilt_config["max"],

                "pan_released": self.pan_released,
                "tilt_released": self.tilt_released,

                "auto_release": self.auto_release,
                "release_delay": self.release_delay
            }

    # ======================================
    # RELEASE SERVOS
    # ======================================

    def release(self):

        print("Stopping servo controller...")

        self.stop_event.set()
        self.worker.join()

        with self.lock:

            self.pan_servo.angle = None
            self.tilt_servo.angle = None

            self.pan_angle = None
            self.tilt_angle = None

            self.pan_target = None
            self.tilt_target = None

            self.pan_arrived_at = None
            self.tilt_arrived_at = None

            self.pan_released = True
            self.tilt_released = True

        print("Servos released")


# ==========================================
# MAIN - TEST MODE
# ==========================================

if __name__ == "__main__":

    controller = ServoController()

    try:

        print("\nPiCam-PTZ Servo Test")
        print("-------------------")

        controller.center()
        time.sleep(2)

        print("\nTesting PAN")

        controller.set_pan(85)
        time.sleep(1)

        controller.set_pan(95)
        time.sleep(1)

        controller.set_pan(90)
        time.sleep(2)

        print("\nTesting TILT")

        controller.set_tilt(85)
        time.sleep(1)

        controller.set_tilt(95)
        time.sleep(1)

        controller.set_tilt(90)
        time.sleep(2)

        print("\nServo test completed")

        print(json.dumps(
            controller.get_status(),
            indent=4
        ))

    except KeyboardInterrupt:

        print("\nTest interrupted")

    finally:

        controller.release()