# Asset sources and distribution boundaries

Reviewed: 2026-10-24. This inventory covers the resources listed here, not every
transitive dependency or historical Git revision. Apache-2.0 does not relicense
third-party assets.

| Asset | License/source evidence | Framework distribution policy |
| --- | --- | --- |
| `shionarium.ico` | Original neutral framework icon | Apache-2.0 |
| `room/kenney_*` | Kenney CC0 1.0; supplied `License.txt` files and `room/LICENSE.Kenney.txt` | Included under original terms |
| `models/vrm/VRM1_Constraint_Twist_Sample.vrm` | pixiv / three-vrm; embedded VRM 1.0 metadata and `LICENSE.three-vrm.txt` | Not included; user-supplied only |
| `models/fbx/SeedSan.fbx` | UniVRM sample; recorded repository MIT notice in `models/vrm/LICENSE.UniVRM.txt` | Not included; historical notice retained |
| `live2d/CubismSamples/Haru` and `Hiyori` | Live2D Free Material License and individual character terms | Not included in current public source or default frontend build |
| `models/vrm/AliciaSolid_vrm-0.51.vrm` | Incomplete or conflicting model-specific provenance in the old inventory | Not included; no assurance of private-use or redistribution rights |
| `frontend/public/vendor/live2dcubismcore.min.js` | Live2D proprietary runtime agreement, distinct from model licenses | Not included; obtain separately from the official SDK |

## Local compatibility

Model binaries are user-supplied. The default model catalogs are empty.
Historical notices remain for attribution; they do not imply that models are bundled.
Previously held files remain local and Git-ignored; missing files must be
obtained with appropriate permission. The default build does not copy local
Cubism Core even when the developer has placed it in `public/vendor`.

This cleanup does not rewrite Git history. Historical revisions may contain
removed files. Do not treat old revisions or working directories containing
ignored models as a clean release.

## Official sources

- Kenney: https://kenney.nl/assets
- three-vrm: https://github.com/pixiv/three-vrm
- UniVRM: https://github.com/vrm-c/UniVRM
- Live2D materials: https://www.live2d.com/eula/live2d-free-material-license-agreement_en.html
- Live2D characters: https://www.live2d.com/eula/live2d-sample-model-terms_en.html
- Live2D runtime: https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html

Use the applicable upstream terms. Distribution inside a work and redistribution
of raw material are different questions. Hiyori Momose also has a character-design
restriction. This inventory does not grant blanket commercial-use clearance.

See `THIRD_PARTY_NOTICES.md` and `docs/guides/asset-licensing.md` for optional voice
components and other release boundaries.
