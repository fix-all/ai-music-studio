# Third-party notices

Original AI Music Studio source code is licensed under MIT (see LICENSE). Dependencies, external tools, models and SoundFonts retain their upstream licenses. They are not relicensed by this repository.

## Included upstream reference material

Files named `acestep-*v0.1.8*` under `docs/evidence/` are unmodified reference snapshots from [ACE-Step/ACE-Step-1.5 v0.1.8](https://github.com/ACE-Step/ACE-Step-1.5/tree/v0.1.8), commit `dce621408bee8c31b4fcf4811682eb9359e1bc94`. They remain under the upstream MIT license, reproduced in `docs/evidence/acestep-LICENSE.txt`. The saved API model download helper is used by the offline guard regression test. Other upstream license files and public release/model metadata retain their original notices and attribution.

## Downloaded separately

| Resource | Upstream license / notice | Distribution here |
|---|---|---|
| FluidSynth 2.6.1 | LGPL-2.1; see upstream LICENSE and `docs/evidence/FluidSynth-LICENSE.txt` | Official binaries downloaded by bootstrap; not committed |
| FFmpeg 9.0.2, Gyan Essentials | This selected build enables GPL/version3; bundled libraries have their own notices | Build downloaded separately from the provider linked by ffmpeg.org; not committed |
| TimGM6mb 1.3 SF2 | GPL-2, Tim Brechbill / David Bolton; see `docs/evidence/TimGM6mb-copyright.txt` and `GPL-2.0.txt` | SF2 downloaded from Debian official mirror; not committed |
| ACE-Step main weights / optional 0.6B LM | Official model cards identify MIT; check the chosen revision and its notices | Not downloaded by core setup or distributed here |
| NumPy / SciPy / soundfile / mido / PyYAML / pyloudnorm and transitive dependencies | Respective package licenses, retained in installed distributions | Installed separately via uv.lock |

Sources, fixed download hashes and model revisions are documented in `docs/engines.md`, `config/studio.yaml` and `scripts/bootstrap.ps1`. Adding a new sample library or model requires its own source, author, license and integrity record. Generated audio and original samples are not included in the public source repository.
