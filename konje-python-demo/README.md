# KONJE hackathon demo

KONJE (Keeping Our Names, Journeys, and Experiences) is a consent-based "memory glasses" demo for people with early-stage dementia.

Point a camera at an enrolled family member, press **Who is this?** (or say it out loud), and the simulated glasses display shows and speaks their name, relationship, last visit and a reminder.

## What it does

| MVP item | Where |
|---|---|
| Camera as the glasses' camera | Laptop webcam, a USB webcam on the Pi, or a phone camera app |
| Enroll trusted people **with recorded consent** | Caregiver page (refuses without the consent box and a name) |
| Face matching that returns name and relationship | `konje/face.py` (same YuNet + SFace models as Albert's repo) |
| Confidence threshold, "Person not recognized" | `MATCH_THRESHOLD` / `MATCH_MARGIN` in `konje/face.py` |
| Simulated glasses display and spoken announcement | Glasses page (`/`) |
| Voice command "Who is this?" | 🎤 button (works in Chrome) |
| Encrypted directory, kept on the device | `data/directory.enc` + `data/secret.key`; nothing goes to the cloud |
| Previous interactions, last visit | Caregiver page → "Add visit note" |
| Medication and appointment reminders | Caregiver page → Reminders |
| Emergency button that alerts the caregiver's phone | Glasses page → EMERGENCY (uses the free **ntfy** phone app) |
| Large text, sound on/off | Glasses page, top right |
| Remove a person (deletes their face data) | Caregiver page → Remove |

## Run it on a Mac

Open **Terminal**, go to this folder, then run:

```bash
./start.sh
```

The first run installs the libraries, which takes a few minutes. Then open **http://localhost:8000** in Chrome. The first time, macOS asks whether Terminal may use the camera: say **Allow**, stop the app with `Ctrl+C`, and run `./start.sh` again.

If the wrong camera opens (for example your iPhone instead of the laptop camera), run `KONJE_CAMERA=1 ./start.sh`.

## Demo script

1. Open the **Caregiver** page and enroll three volunteers, one at a time. Tick consent, then have the person face the camera for 4 seconds.
2. Add a visit note and a reminder for one of them.
3. Go back to the glasses view. Each volunteer steps in front of the camera, and you press **Who is this?**
4. Someone *not* enrolled steps in. The glasses say **"Person not recognized"**.
5. Press **EMERGENCY**. The caregiver's phone buzzes.
6. Remove one volunteer, show they're no longer recognized, and point out that the consent and removal are in the activity log.

## Run it on the Raspberry Pi 5

1. **Flash the SD card.** Use the ThinkPad's SD slot with the adapter. Install **Raspberry Pi Imager** from raspberrypi.com/software and choose:
   - Device: *Raspberry Pi 5*
   - OS: *Raspberry Pi OS (64-bit)*
   - Storage: the SD card

   When it asks to customize settings, click **Edit settings** and set:
   - hostname `konje`
   - a username and password
   - your Wi-Fi name and password
   - on the **Services** tab, **Enable SSH** (password login)
2. Put the card in the Pi, plug in USB-C power and wait about 2 minutes.
3. From the Mac's Terminal, copy this folder to the Pi. Replace `YOURNAME` with the username you set:

   ```bash
   rsync -av --exclude .venv --exclude data ./ YOURNAME@konje.local:~/konje-demo/
   ```
4. Log in to the Pi and start KONJE:

   ```bash
   ssh YOURNAME@konje.local
   cd ~/konje-demo && ./start.sh
   ```
5. On the Mac or a phone on the same Wi-Fi, open **http://konje.local:8000**. The Pi is the "glasses brain"; the browser is the display and speaker.

**Camera for the Pi:** plug in a USB webcam (default `KONJE_CAMERA=0`). Without one, use a phone "IP camera" app that streams video and give the app's address, for example `KONJE_CAMERA=http://192.168.1.20:8080/video ./start.sh`.
