# Source acknowledgement and reuse boundary

KONJE is a separate project named after Albert Mejooli's mother. It builds on ideas from **See Through**, a collaborative HopHacks 2026 project built by Albert Mejooli and Amanda Le, maintained at:

https://github.com/A2Hackathon/see-through

Inspected source revision: `bd760fb57e75e918cb141fb634348ba7fae9c3ba`.

## Import policy

- See Through remains unchanged.
- The sparse-cloned originals are in Git-ignored `reference/see-through/` for local development and review, not deployed as-is.
- No root `LICENSE` file appeared in the inspected repository snapshot. Public visibility does not, by itself, grant permission to redistribute code. Obtain permission/clarify rights before copying upstream implementations into the published KONJE repository.
- Check the licensing of InsightFace libraries **and pretrained model weights separately**, and any later runtime/model substitutions, before redistribution or commercial deployment.
- Do not copy See Through's SQLite storage, hardcoded matching threshold, automatic cloud enrichment, raw-frame debug saving, or phone-specific Expo speech integration into the product unmodified.

## Selected references

- `server/face_service.py` — enrollment and similarity matching logic
- `server/frame_selection.py` — quality-based frame selection
- `server/requirements.txt` — historical dependencies, not KONJE's locked dependency set
- `README.md` — upstream context, saved locally as `README.upstream.md`

Original See Through copyright remains with its respective contributors. This acknowledgment is not a license grant.