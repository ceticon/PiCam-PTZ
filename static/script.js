"use strict";

/*
 * ==========================================
 * PiCam-PTZ
 * Raspberry Pi 5 + Camera Module 3
 *
 * Features:
 * - Pan / Tilt control
 * - Direction buttons
 * - Position sliders
 * - Center function
 * - Servo status
 * - Full-resolution photo capture
 * ==========================================
 */


// ==========================================
// CONFIGURATION
// ==========================================

const API = {
    status: "/api/status",
    pan: "/api/pan",
    tilt: "/api/tilt",
    center: "/api/center",
    photo: "/api/photo"
};

const STEP = 5;
const STATUS_INTERVAL = 500;


// ==========================================
// HTML ELEMENTS
// ==========================================

// Pan / Tilt sliders
const panSlider = document.getElementById("pan-slider");
const tiltSlider = document.getElementById("tilt-slider");

// Slider values
const panValue = document.getElementById("pan-value");
const tiltValue = document.getElementById("tilt-value");

// Servo status
const panPosition = document.getElementById("pan-position");
const tiltPosition = document.getElementById("tilt-position");

const panTarget = document.getElementById("pan-target");
const tiltTarget = document.getElementById("tilt-target");

// Direction buttons
const panLeftButton = document.getElementById("pan-left");
const panRightButton = document.getElementById("pan-right");

const tiltUpButton = document.getElementById("tilt-up");
const tiltDownButton = document.getElementById("tilt-down");

const centerButton = document.getElementById("center");

// Photo elements
const photoButton = document.getElementById("take-photo");
const photoStatus = document.getElementById("photo-status");

const photoPreview = document.getElementById("photo-preview");
const photoImage = document.getElementById("photo-image");
const photoLink = document.getElementById("photo-link");
const photoFilename = document.getElementById("photo-filename");


// ==========================================
// SERVO VARIABLES
// ==========================================

let panAngle = 90;
let tiltAngle = 90;

let panMin = 60;
let panMax = 120;

let tiltMin = 60;
let tiltMax = 120;

let panDragging = false;
let tiltDragging = false;

// Queue commands separately for each servo.
let panRequest = Promise.resolve();
let tiltRequest = Promise.resolve();

// Prevent status polling from overwriting
// a command that has not reached Flask yet.
let panPending = 0;
let tiltPending = 0;


// ==========================================
// API FUNCTIONS
// ==========================================

async function postJSON(url, data = {}) {

    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    });

    const result = await response.json();

    if (!response.ok) {
        throw new Error(
            result.error || `HTTP ${response.status}`
        );
    }

    return result;
}


// ==========================================
// UTILITIES
// ==========================================

function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, value));
}

function formatAngle(value) {

    if (value === null || value === undefined) {
        return "--";
    }

    return `${Number(value).toFixed(1)}°`;
}

function updatePanDisplay() {
    panSlider.value = panAngle;
    panValue.textContent = Math.round(panAngle);
}

function updateTiltDisplay() {
    tiltSlider.value = tiltAngle;
    tiltValue.textContent = Math.round(tiltAngle);
}


// ==========================================
// PAN CONTROL
// ==========================================

function setPan(angle) {

    panAngle = clamp(
        Number(angle),
        panMin,
        panMax
    );

    updatePanDisplay();

    const target = panAngle;

    panPending++;

    panRequest = panRequest
        .catch(() => {})
        .then(() => postJSON(API.pan, {
            angle: target
        }))
        .catch(error => {
            console.error("Pan error:", error);
        })
        .finally(() => {
            panPending--;
        });

    return panRequest;
}


// ==========================================
// TILT CONTROL
// ==========================================

function setTilt(angle) {

    tiltAngle = clamp(
        Number(angle),
        tiltMin,
        tiltMax
    );

    updateTiltDisplay();

    const target = tiltAngle;

    tiltPending++;

    tiltRequest = tiltRequest
        .catch(() => {})
        .then(() => postJSON(API.tilt, {
            angle: target
        }))
        .catch(error => {
            console.error("Tilt error:", error);
        })
        .finally(() => {
            tiltPending--;
        });

    return tiltRequest;
}


// ==========================================
// DIRECTION BUTTONS
// ==========================================

panLeftButton.addEventListener("click", () => {
    setPan(panAngle - STEP);
});

panRightButton.addEventListener("click", () => {
    setPan(panAngle + STEP);
});

tiltUpButton.addEventListener("click", () => {
    setTilt(tiltAngle + STEP);
});

tiltDownButton.addEventListener("click", () => {
    setTilt(tiltAngle - STEP);
});


// ==========================================
// SLIDER CONTROL
// ==========================================

panSlider.addEventListener("pointerdown", () => {
    panDragging = true;
});

tiltSlider.addEventListener("pointerdown", () => {
    tiltDragging = true;
});

function stopDragging() {
    panDragging = false;
    tiltDragging = false;
}

window.addEventListener("pointerup", stopDragging);
window.addEventListener("pointercancel", stopDragging);

panSlider.addEventListener("input", () => {
    setPan(panSlider.value);
});

tiltSlider.addEventListener("input", () => {
    setTilt(tiltSlider.value);
});


// ==========================================
// CENTER SERVOS
// ==========================================

centerButton.addEventListener("click", async () => {

    centerButton.disabled = true;

    try {

        // Finish queued slider commands first.
        await Promise.all([
            panRequest,
            tiltRequest
        ]);

        const result = await postJSON(API.center);

        panAngle = Number(result.status.pan_target);
        tiltAngle = Number(result.status.tilt_target);

        updatePanDisplay();
        updateTiltDisplay();

    } catch (error) {

        console.error("Center error:", error);

    } finally {

        centerButton.disabled = false;

    }

});


// ==========================================
// SERVO STATUS
// ==========================================

async function updateStatus() {

    try {

        const response = await fetch(API.status, {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const status = await response.json();

        // Servo limits from config.json
        // through Flask.
        panMin = Number(status.pan_min);
        panMax = Number(status.pan_max);

        tiltMin = Number(status.tilt_min);
        tiltMax = Number(status.tilt_max);

        panSlider.min = panMin;
        panSlider.max = panMax;

        tiltSlider.min = tiltMin;
        tiltSlider.max = tiltMax;

        // Display current commanded positions.
        panPosition.textContent = formatAngle(status.pan);
        tiltPosition.textContent = formatAngle(status.tilt);

        // Display target positions.
        panTarget.textContent = formatAngle(status.pan_target);
        tiltTarget.textContent = formatAngle(status.tilt_target);

        // Do not overwrite slider while dragging
        // or while commands are still pending.
        if (
            !panDragging &&
            panPending === 0 &&
            status.pan_target !== null
        ) {
            panAngle = Number(status.pan_target);
            updatePanDisplay();
        }

        if (
            !tiltDragging &&
            tiltPending === 0 &&
            status.tilt_target !== null
        ) {
            tiltAngle = Number(status.tilt_target);
            updateTiltDisplay();
        }

    } catch (error) {

        console.error("Status error:", error);

    }

}


// ==========================================
// PHOTO CAPTURE
// ==========================================

photoButton.addEventListener("click", async () => {

    photoButton.disabled = true;
    photoButton.textContent = "📸 Fotograferar...";

    photoStatus.textContent =
        "Tar högupplöst bild, vänta...";

    try {

        const response = await fetch(API.photo, {
            method: "POST"
        });

        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(
                result.error || "Fotograferingen misslyckades"
            );
        }

        // Show the saved photo.
        photoImage.src = result.url;
        photoLink.href = result.url;

        photoFilename.textContent = result.filename;

        photoPreview.hidden = false;

        photoStatus.textContent =
            "✅ Bilden har sparats!";

        console.log(
            "Photo saved:",
            result.filename
        );

    } catch (error) {

        console.error("Photo error:", error);

        photoStatus.textContent =
            "❌ Kunde inte ta bilden: " + error.message;

    } finally {

        photoButton.disabled = false;
        photoButton.textContent = "📸 Ta kort";

    }

});


// ==========================================
// INITIALIZATION
// ==========================================

async function initialize() {

    await updateStatus();

    setInterval(
        updateStatus,
        STATUS_INTERVAL
    );

    console.log("PiCam-PTZ initialized");
    console.log("Pan / Tilt controls ready");
    console.log("Photo capture ready");

}

initialize();