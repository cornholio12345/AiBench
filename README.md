# AiBench

Temporary reproducible benchmark for small local LLMs as the narrator of a German branching Magefort RPG.

The benchmark measures the raw material needed for later judging in three dimensions:

- canon adherence
- German language quality
- creativity / immersion

Each model receives the same Magefort canon, seed and scenario set. Three sampling profiles generate independent story openings; the balanced profile additionally gets a continuation test and three adversarial canon tests.

Results are stored as short-lived GitHub Actions artifacts. This repository contains no application secrets.
