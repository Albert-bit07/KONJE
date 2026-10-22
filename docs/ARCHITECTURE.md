# KONJE architecture, invariants, and later synchronization

## Current implementation: one process, several internal modules

```text
keyboard (GPIO button later)
   -> Scheduler [generation counter, 1 active + 1 pending max]
   -> On-demand Pi CSI camera / USB V4L2 adapter
      -> 1-3 frames via in-memory bounded pipes and memfd, no JPEG files
   -> optional local Python face embedding worker [no identity DB/key]
      -> sharpest usable frame, one face, normalized embedding or UNCERTAIN
   -> C++ recognition policy [cosine score + runner-up margin, never probability]
      -> encrypted SQLite directory, fresh read for every decision
   -> exact approved introduction (no LLM)
      -> optional offline text-to-speech via espeak-ng stdin
```

Pi 5 RAM gives room to *measure* a native ONNX Runtime or OpenCV DNN C++ adapter later. Do not assume lower latency or accuracy without checking the ARM64 runtime/model and profiling. Current per-request Python model startup could be slow; replace only after measuring.

## Core invariants

1. A new request increments a process-local generation. At most one request is pending; an older pending request is replaced. Each capture, worker and speech stage checks current generation and is terminated on supersession/timeout.
2. Never publish a past request after a newer request. `c`/`q` invalidates active work. Requests are not replayed after crashes. Restart-local numeric IDs are not globally unique; future sync needs durable session/operation IDs.
3. No unsupervised identification. Embedding worker outputs only an embedding or `UNCERTAIN`, never an identity. C++ never announces a person unless the matching policy accepts one encrypted, approved profile.
4. Recheck the directory immediately before speaking so a local revoke blocks subsequent speech. There is no global revocation barrier with offline devices yet.
5. Read and match enrolled profiles locally; no face frames, embeddings or identities are sent to remote endpoints. Camera snapshots and speech text cross only a local process boundary.
6. Raw camera images are bounded to 4 MiB each and 3 per request. They traverse a versioned `KONJE1` binary frame protocol through Linux memfd, then buffers are released. No debug images are saved.
7. Fail closed when a camera, worker, speaker or model is unavailable. More human-factor studies, demographic error evaluation and threat mitigation are needed before assisting real users.

## Versioned frame IPC

`"KONJE1"` (6 bytes), one byte frame count (1–3), then repeated `<length:uint32 little-endian><JPEG bytes>`. Raw bytes are bounded and checked. The Python worker decodes and quality-ranks the burst, then runs face analysis on one selected frame. This avoids three model loads per recognition request. Enrollment makes three distinct captures and averages unit embeddings if consistent.

## Later caregiver synchronization: contract, NOT existing code

Only after local operations are reliable:

- Each caregiver mutation must contain `{profile_id, version, update_id, expires_at, digest}` plus an authenticated encrypted payload. Use monotonic versions and device-scoped replay protection; do not trust device wall-clock order for conflict resolution.
- Persist an applied version and payload atomically. Acknowledgment must identify the actual installed `{device, profile, version, digest}`, **not simply HTTP 200**.
- `update_id` deduplicates retried delivery. Older versions cannot overwrite newer ones. Revocation tombstones take precedence over stale updates and must remain durable without retaining full biometric payload.
- Expiry must be checked during use. An offline device must clearly show revocations awaiting sync, and cannot claim to have applied an unseen revocation.
- Define ownership and conflicts between caregiver edits explicitly; do not use blind last-writer-wins.
- Failure tests must cover partitions, duplicate/out-of-order messages, stale ACKs, power loss around database commit/ACK, wrong keys and reconnect storms.

We will not add a synchronization microservice, Kafka/Raft, Temporal or a cloud database until a real requirement justifies it. Choreo Log lessons are useful for a correct update ledger, not a reason to add a consensus cluster to this tabletop prototype.
## Model-space compatibility (October 2026)

Enrollment now requires `KONJE_MODEL_ID`, a stable identifier for the embedding model, weights and preprocessing version. Every encrypted profile carries the ID (payload schema v2); matching returns uncertain if the active policy ID is absent or any enrolled profile has a different ID. Prior schema-v1 encrypted profiles cannot be used as-is and must be re-enrolled with an explicitly identified model; never silently reinterpret them. For simulated tests, use `KONJE_MODEL_ID=mock-model-v1`.

**Limitation:** The identifier is currently operator-provided, not cryptographically bound to the ONNX weights or preprocessing binary. It guards accidental backend switching only when configured correctly. Before real use, compute it from reviewed model weights plus preprocessing code/version, pin that value during enrollment and inference, and reject changes until validation and re-enrollment. Keep keys and biometric profiles off GitHub.
