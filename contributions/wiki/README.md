# Wiki contributor intake

Files under `generated/` are deterministic review artifacts compiled from AlphaClaw Wiki pages that contain the marker `alphaclaw-wiki-intake:v1` and explicitly say `Ready for review: yes`.

Do not hand-edit generated records. Revise the source Wiki page and save it again. The compiler records the Wiki commit, Git author metadata, source path, and SHA-256 of the exact Markdown.

The Wiki is an observation interface, not an execution surface: Wiki text is parsed as bounded data and is never evaluated as shell, Python, MeTTa, YAML, or JSON code.
