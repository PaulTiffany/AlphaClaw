<p align="center">
  <img src="assets/brand/alphaclaw-logo.png" alt="AlphaClaw" width="360">
</p>

# AlphaClaw — the video

**Multimodal in. Symbolic out.** · 2:42 · BGI Commons HyperSprint #1

| | |
|---|---|
| **YouTube** | https://youtu.be/IIjwI9CX4Vs |
| **Vimeo** | https://vimeo.com/1222418041 |

Narrated by Derek Tiffany. Every figure on screen is read from a committed artifact in
this repository — nothing in the video is illustrative.

## What it covers

```text
perceive  ->  symbolize  ->  reason
```

1. **The waste.** Eight steps of reasoning about one image costs most agents eight
   multimodal calls, because the loop re-sends the picture every turn.
2. **The move.** AlphaClaw looks once. The handoff carries a standing instruction:
   *you did not see an image; don't pretend you did.*
3. **The apparatus.** OmegaClaw runs stock and pinned, in a fresh container per episode.
   Everything that bounds, meters or stops it lives outside, on the host.
4. **The boundary.** At depth 1 the architecture costs 2.7% *more* — the floor of where
   perceive-once applies. Published alongside the wins.
5. **The check.** `python3 scripts/verify_research_checkpoint.py` — no API key, no cost,
   no containers.

## Figures used on screen

Every number below is read from `RESEARCH.md` and re-derivable from the frozen artifacts.

| claim | source |
|---|---|
| 87.5% multimodal inference avoided at N=8 | V3-B avoidance table |
| +37.1% measured saving at N=8 | OpenRouter receipts |
| &minus;2.7% at N=1 | OpenRouter receipts |
| 20 completed successes · 4 availability failures · 0 wrong answers | V3-B run outcomes |
| V3-A did not isolate a unique cause | V3-A synthesis |

**V2** (substitution) ran through stock OmegaClaw in containers with ThreadKeeper.
**V3-B** (the economics above) is a direct three-arm provider comparison and does *not*
involve OmegaClaw. The video states this distinction rather than blurring the two
populations.

## Credits

**License:** [CC BY 4.0](LICENSE-MEDIA) — share and adapt with credit.

Narration and edit: Derek Tiffany.
Music: [prettyjohn1](https://pixabay.com/users/prettyjohn1-54616349/) via Pixabay,
[Pixabay Content License](https://pixabay.com/service/license-summary/).
Logo: project social image.
