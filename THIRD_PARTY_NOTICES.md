# Third-party notices

Inventory date: 2026-10-24. This is a release-boundary inventory, not a complete
software bill of materials or a legal certification. Preserve upstream license
files and notices when distributing their components. Dependency versions are
recorded in `backend/uv.lock` and `frontend/package-lock.json`.

## Framework and assets

- Original Shionarium framework: Apache-2.0; see `LICENSE`, `NOTICE`, and
  `LICENSE_SCOPE.md`.
- Kenney room assets: CC0 1.0; see the supplied asset licenses.
- VRM1 technical sample (no longer bundled): model-specific embedded VRM 1.0 metadata; preserve
  `assets/models/vrm/LICENSE.three-vrm.txt` and inspect the model metadata.
- SeedSan sample (no longer bundled): recorded UniVRM MIT source notice in
  `assets/models/vrm/LICENSE.UniVRM.txt`; retain it with the sample.
- Live2D Haru/Hiyori sample files, Cubism Core runtime and AliciaSolid model:
  excluded from current framework source and default frontend build. Existing
  local copies do not establish licensing rights. See `assets/LICENSE.md`.

## Optional voice components

- The locked `piper-tts` 1.8.0 PyPI metadata declares `GPL-3.0-or-later`.
  It belongs to the `local-voice` extra, not the basic dependency set. GPL permits
  commercial use; obligations depend on how the software is modified, combined
  and conveyed. Merely installing Piper does not change the license of every
  file in this repository.
- The optional `zh_CN-huayan-medium` voice's upstream MODEL_CARD identifies its
  dataset license as `Unknown`. The framework does not supply permission to
  commercially use or redistribute that voice. Voice/model rights are separate
  from the Piper executable's license.
- `edge-tts` is a separate optional client. Its code license does not by itself
  grant unrestricted rights to the online service, its availability, voices or
  generated output. Check applicable service terms separately.
- ASR models, FFmpeg binaries, tokenizers, embedding weights and other downloaded
  components need their own notices and model/service terms reviewed before
  redistributing a customized product. They are not covered by Apache-2.0 merely
  because an installer downloads them.

## Independently installed plugins

The GitHub source links and fixed revisions in the marketplace are provenance
and version information, not license grants. Inspect each plugin's license,
dependencies and assets before redistribution. Do not assume that a public
repository has an open-source license. The framework never relicenses plugins.

## Review sources

- https://www.apache.org/licenses/LICENSE-2.0
- https://pypi.org/pypi/piper-tts/1.8.0/json
- https://github.com/OHF-Voice/piper1-gpl
- https://huggingface.co/rhasspy/piper-voices/blob/main/zh/zh_CN/huayan/medium/MODEL_CARD
- Live2D official agreements linked in `assets/LICENSE.md`.

Future release preparation should inventory transitive dependencies and retain
their license texts in the actual distribution. This document does not claim
that such an exhaustive dependency audit has been completed.

## 2026-10-25 release review

Frontend license notices are retained in third_party/FRONTEND-NOTICES.txt and
emitted as THIRD_PARTY_NOTICES.txt in production builds. The MIT wrapper
pixi-live2d-display embeds Cubism Web Framework, which retains Live2D's Open
Software License and SDK release conditions. Removing Core/models does not
relicense that framework or remove those commercial release conditions.

QQ clients and gateways are not bundled. SnowLuma is source-available under
non-commercial terms with proprietary native components. Its EULA section 5.4
requires prior written authorization for automated deployment and commercial
use. The automatic installer is disabled; users manually install an appropriately
licensed OneBot gateway. See https://github.com/SnowLuma/SnowLuma/blob/main/EULA.md
and https://github.com/Live2D/CubismWebFramework/blob/develop/LICENSE.md.
