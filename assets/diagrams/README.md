# Diagrams

Hand-authored SVG. No build step, no external references, no embedded fonts — each file
is a self-contained fragment that renders directly in GitHub markdown.

| file | claim it makes |
|---|---|
| `perceive-once.svg` | the baseline re-sends the image every turn; AlphaClaw perceives once and reasons over text |
| `trust-boundary.svg` | bounds, metering and stop authority run on the host, outside the container holding the reasoner |
| `measurement-path.svg` | the raw provider receipt is written first; ThreadKeeper is a second, isolated witness |

Palette follows the project social image: deep navy `#080E15`, electric blue `#31A9F0`
for the path under discussion, crab red `#F04B36` for the cost being avoided.

Each diagram carries `role="img"` and an `aria-label` stating the same claim as its
caption, so the argument survives for readers who cannot see the picture.
