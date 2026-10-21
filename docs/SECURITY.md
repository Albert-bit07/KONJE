# KONJE privacy and safety boundaries

This is an engineering prototype, NOT clinical or safety-assured software. It can misidentify real people. Do not rely on it for medical decisions, medication dosing, emergencies, security access, or unattended care.

## Collection and consent

- Enroll only willing, informed volunteers in a supervised setting. Enrollment prompts for a typed consent attestation; it does not yet have authenticated caregiver roles, verified consent forms or renewal/expiry policies.
- Camera capture is on request only. CSI or UVC image bytes remain in process memory and are passed to an optional **local** embedding worker through Linux anonymous memfd; there are no raw JPEG files, cloud photo uploads, or debug captures in this design.
- Zero-face and multiple-face frames should produce `UNCERTAIN`. No bystander identity is fabricated.
- Relationships, names and speech text are stored as approved input. There is no generative inference about previous interactions; 'last meaningful interaction' tracking is deferred.
- Revocation deletes the active local profile. It cannot guarantee secure erasure from SSD/microSD wear leveling, backups, snapshots, swap or future offline devices. A future synchronized system needs acknowledged tombstones and visible offline stale status.

## Encryption and access

- SQLite payloads are encrypted with AES-256-GCM; fresh nonces and authenticated opaque IDs. The key is created with owner-only mode under `~/.config/konje/master.key`, distinct from `~/.local/share/konje/profiles.sqlite3`. SQLite metadata, IDs and row count are not encrypted.
- **Warning:** When the key and database reside on the same microSD card, encryption does **not** protect against physical theft of that card or a compromised OS account. Production would need externally/unsealed keys, signed updates, device hardening and an independent security review.
- The Pi process and model subprocess handle raw frames and plaintext embeddings in RAM. Crash dumps, swap, OS logs or a privileged attacker may access sensitive material. The current code is not hardened against side channels.
- Local CLI commands rely on local OS access; there is no authenticated network caregiver API. Do not expose the command interface remotely without adding authentication and authorization.

## Reliability

- Camera output is bounded (4 MiB per JPEG, 3 frames max); local child processes have bounded stdout and timeouts, and latest-request-wins cancellation.
- Current worker maps model failures to uncertainty; this is safe against false claims but **not sufficient observability** for production. Add error categories and on-device health reporting after measuring actual runtime.
- No liveness/spoof checks, clinical studies, demographic evaluations, objective error-rate targets, uptime guarantees or automatic emergency notifications.

## Model legal status

- No original See Through code, pretrained model weights, real volunteer biometric data or secrets are shipped. The Python sample adapter uses InsightFace APIs if installed, subject to third-party model licensing and technical compatibility. Verify both before use, and do not auto-publish pretrained weights.