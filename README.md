# AiBench

Reproducible benchmark for local Ollama LLMs as the narrator of a German branching Magefort RPG.

Each GitHub model runs the same Magefort canon, seed and decision sequence with three sampling profiles:

- konservativ: temperature 0.25
- ausgewogen: temperature 0.62
- kreativ: temperature 0.95

Each profile plays 10 connected RPG turns. Three adversarial canon traps run afterwards. The generation prompt targets clear German that is easy to understand for roughly 10-year-olds without becoming infantil, cutesy or patronizing.

Evaluation dimensions are canon adherence (50%), German language quality including age-appropriate clarity (25%), and creativity / immersion (25%). Speed and readability metrics are recorded as additional diagnostics.

## Resume behavior

`benchmark.py` atomically updates the model JSON after every successful turn. The GitHub workflow also saves the `results` directory to an Actions cache after every turn. A failed/retried job or a later run on the same benchmark PR restores the newest cache and skips already completed turns, so normally at most the currently generating turn is lost.

Final results are uploaded as short-lived GitHub Actions artifacts. This repository contains no application secrets.
