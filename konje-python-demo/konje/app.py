"""KONJE web server: camera + face matching + the web pages.

Open http://localhost:8000 for the simulated glasses view,
and http://localhost:8000/caregiver for the caregiver panel.
"""
import os
import socket
import threading
import time
import urllib.request

import cv2
import numpy as np
from flask import Flask, Response, jsonify, render_template, request

from .face import DETECTOR_FILE, FaceEngine, best_match, similarity
from .store import Store

app = Flask(__name__)
store = Store()
engine = FaceEngine()
engine_lock = threading.Lock()  # the face models must only be used by one request at a time


# ---------------------------------------------------------------- camera ----
class Camera:
    """Reads the camera nonstop in the background and keeps the newest picture.

    KONJE_CAMERA picks the camera: 0 = first camera (default), 1 = second, or a
    web address such as http://192.168.1.20:8080/video for a phone camera app.
    """

    def __init__(self, source):
        self.source = int(source) if source.isdigit() else source
        self.frame = None
        self.error = None
        self.lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        cap = None
        while True:
            if cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(self.source)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                if not cap.isOpened():
                    self.error = f"Cannot open camera {self.source!r}"
                    time.sleep(2)
                    continue
            ok, frame = cap.read()
            if not ok:
                self.error = "Camera stopped sending pictures"
                cap.release()
                cap = None
                time.sleep(1)
                continue
            if frame.shape[1] > 960:  # shrink big frames so the Pi stays fast
                scale = 960 / frame.shape[1]
                frame = cv2.resize(frame, None, fx=scale, fy=scale)
            with self.lock:
                self.frame = frame
                self.error = None

    def latest(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()


camera = Camera(os.environ.get("KONJE_CAMERA", "0"))


def collect_faces(seconds, want):
    """Look at the camera for a short while and return the face embeddings seen.
    Only frames with exactly one clear face are used."""
    embeddings, crowded, deadline = [], 0, time.time() + seconds
    while time.time() < deadline and len(embeddings) < want:
        frame = camera.latest()
        if frame is None:
            time.sleep(0.1)
            continue
        with engine_lock:
            faces = engine.find_faces(frame)
            if len(faces) > 1:
                crowded += 1
                faces = faces[:1]  # use the closest face (the person in front of the wearer)
            if faces:
                embeddings.append(engine.embed(frame, faces[0]))
        time.sleep(0.12)
    return embeddings, crowded


# ------------------------------------------------------------------ pages ----
@app.get("/")
def glasses():
    return render_template("glasses.html")


@app.get("/caregiver")
def caregiver():
    return render_template("caregiver.html")


@app.get("/video")
def video():
    """A live video stream (many JPEG pictures in a row) with boxes around faces."""
    # Each viewer gets its own small face finder, so drawing boxes never blocks "Who is this?"
    detector = cv2.FaceDetectorYN.create(str(DETECTOR_FILE), "", (320, 320), 0.85, 0.3, 20)

    def frames():
        while True:
            frame = camera.latest()
            if frame is None:
                frame = np.zeros((480, 640, 3), np.uint8)
                cv2.putText(frame, camera.error or "Starting camera...", (20, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            else:
                h, w = frame.shape[:2]
                detector.setInputSize((w, h))
                _, faces = detector.detect(frame)
                for f in faces if faces is not None else []:
                    x, y, fw, fh = map(int, f[:4])
                    cv2.rectangle(frame, (x, y), (x + fw, y + fh), (120, 220, 255), 2)
            ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"
            time.sleep(0.08)

    return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ---------------------------------------------------------- recognition ----
def describe(person):
    """Build what the glasses show and say for a recognized person."""
    last = None
    if person["interactions"]:
        last = person["interactions"][-1]["note"]
    elif person["last_seen"]:
        last = "Last visit: " + person["last_seen"].replace("T", " at ")[:-3]
    spoken = person["intro"] or f"This is {person['name']}, your {person['relationship']}."
    if person["reminder"]:
        spoken += " " + person["reminder"]
    return {
        "name": person["name"],
        "relationship": person["relationship"],
        "last": last,
        "reminder": person["reminder"],
        "say": spoken,
    }


@app.post("/api/identify")
def identify():
    """'Who is this?': look for about a second, then match against the directory."""
    if camera.latest() is None:
        return jsonify(status="no_camera", say="The camera is not working.", detail=camera.error)
    embeddings, crowded = collect_faces(seconds=1.2, want=4)
    if not embeddings:
        return jsonify(status="no_face", say="I can't see a face. Please look at the person.")
    avg = np.mean(embeddings, axis=0)
    avg /= np.linalg.norm(avg) + 1e-9
    person, score, runner_up = best_match(avg, store.people())
    scores = {"score": round(score, 3), "runner_up": round(runner_up, 3)}
    if person is None:
        store.log("unknown", f"Person not recognized (best score {score:.2f})")
        return jsonify(status="unknown", say="Person not recognized.", **scores)
    info = describe(person)  # describe first, so "last visit" means the previous one, not now
    store.mark_seen(person["id"])
    return jsonify(status="recognized", id=person["id"], crowded=crowded > 0, **info, **scores)


@app.post("/api/enroll")
def enroll():
    """Add a trusted person. Refuses without recorded consent."""
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    relationship = (body.get("relationship") or "").strip()
    consent_by = (body.get("consent_by") or "").strip()
    if not body.get("consent") or not consent_by:
        return jsonify(ok=False, error="Consent is required: tick the box and write who gave it."), 400
    if not name or not relationship:
        return jsonify(ok=False, error="Name and relationship are required."), 400

    embeddings, crowded = collect_faces(seconds=4, want=6)
    if crowded:
        return jsonify(ok=False, error="More than one face was in view. Only the person being enrolled should be on camera."), 400
    if len(embeddings) < 3:
        return jsonify(ok=False, error="Couldn't see a clear face. Face the camera in good light and try again."), 400
    mean = np.mean(embeddings, axis=0)
    mean /= np.linalg.norm(mean) + 1e-9
    if min(similarity(e, mean) for e in embeddings) < 0.5:
        return jsonify(ok=False, error="The pictures didn't agree with each other. Hold still and try again."), 400
    existing, score, _ = best_match(mean, store.people())
    if existing is not None:
        return jsonify(ok=False, error=f"This face already looks like {existing['name']} (score {score:.2f})."), 400

    person = store.add_person(name, relationship, (body.get("intro") or "").strip(),
                              (body.get("reminder") or "").strip(), consent_by, embeddings)
    return jsonify(ok=True, id=person["id"], photos=len(embeddings))


@app.get("/api/people")
def people():
    return jsonify(store.public_people())


@app.delete("/api/people/<pid>")
def remove(pid):
    return jsonify(ok=store.remove_person(pid))


@app.patch("/api/people/<pid>")
def edit(pid):
    return jsonify(ok=store.update_person(pid, **request.get_json(force=True)))


@app.post("/api/people/<pid>/interaction")
def interaction(pid):
    note = (request.get_json(force=True).get("note") or "").strip()
    return jsonify(ok=bool(note) and store.add_interaction(pid, note))


# ------------------------------------------------- reminders & alerts ----
@app.get("/api/reminders")
def reminders():
    return jsonify(store.reminders())


@app.post("/api/reminders")
def add_reminder():
    body = request.get_json(force=True)
    if not body.get("time") or not body.get("text"):
        return jsonify(ok=False, error="Time and text are required."), 400
    return jsonify(ok=True, reminder=store.add_reminder(body["time"], body["text"].strip()))


@app.delete("/api/reminders/<rid>")
def remove_reminder(rid):
    store.remove_reminder(rid)
    return jsonify(ok=True)


@app.get("/api/due")
def due():
    return jsonify(store.due_reminders())


def send_alert(title, message):
    """Push a notification to the caregiver's phone with the free 'ntfy' app.
    Returns (sent?, explanation)."""
    topic = store.settings().get("alert_topic", "").strip()
    if not topic:
        return False, "No caregiver phone set up yet (Caregiver page → Alerts)."
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=message.encode(), method="POST",
        headers={"Title": title, "Priority": "urgent", "Tags": "rotating_light"})
    try:
        urllib.request.urlopen(req, timeout=8).close()
        return True, "Caregiver alerted."
    except OSError as e:
        return False, f"Could not reach the alert service ({e.__class__.__name__}). Check the internet connection."


@app.post("/api/emergency")
def emergency():
    sent, info = send_alert("KONJE: help requested", "The wearer pressed the emergency button at " + time.strftime("%H:%M") + ".")
    store.log("emergency", "Emergency button pressed. " + info)
    return jsonify(sent=sent, info=info)


@app.post("/api/test-alert")
def test_alert():
    sent, info = send_alert("KONJE test", "This is a test alert. No action needed.")
    return jsonify(sent=sent, info=info)


@app.get("/api/settings")
def get_settings():
    return jsonify(store.settings())


@app.post("/api/settings")
def set_settings():
    topic = (request.get_json(force=True).get("alert_topic") or "").strip()
    store.set_setting("alert_topic", topic)
    return jsonify(ok=True)


@app.get("/api/events")
def events():
    return jsonify(store.events()[:50])


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "this-computer"
    finally:
        s.close()


def main():
    port = int(os.environ.get("KONJE_PORT", "8000"))
    print(f"\n  KONJE is running.\n"
          f"  Glasses view:   http://localhost:{port}\n"
          f"  Caregiver page: http://localhost:{port}/caregiver\n"
          f"  From a phone on the same Wi-Fi: http://{local_ip()}:{port}\n"
          f"  Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=port, threaded=True)
