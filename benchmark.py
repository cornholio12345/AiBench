import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CANON = json.loads((ROOT / "canon" / "magefort-canon.json").read_text(encoding="utf-8"))
OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)

MODEL = os.environ["MODEL"]
SEED = int(os.environ.get("SEED", "4242"))
NUM_CTX = int(os.environ.get("NUM_CTX", "8192"))

PROFILES = {
    "konservativ": {"temperature": 0.25, "top_p": 0.78, "repeat_penalty": 1.08},
    "ausgewogen": {"temperature": 0.62, "top_p": 0.90, "repeat_penalty": 1.06},
    "kreativ": {"temperature": 0.95, "top_p": 0.96, "repeat_penalty": 1.04},
}

SYSTEM = f"""Du bist die Erzählinstanz eines interaktiven deutschen Rollenspiels in Magefort Castle.

BINDENDER KANON:
{json.dumps(CANON, ensure_ascii=False)}

Regeln für jede Antwort:
- Der Kanon ist bindend. Widersprich ihm niemals und behandle offene Punkte nicht als gesicherte Weltfakten.
- extendedCanonDefault ist false: Figuren aus 'erweiterter_kanon' erscheinen nur, wenn die Spielanweisung sie ausdrücklich aktiviert.
- Erfinde keine neuen permanenten Schlossbereiche, Institutionen oder Weltregeln und stelle Unbelegtes nicht als feststehenden Buchkanon dar.
- Pferde verhalten sich im Normalfall glaubwürdig pferdisch. Sie führen keine normalen Gespräche und betreten keine Wohn-, Unterrichts-, Speise-, Büro- oder sonstigen Schlossräume.
- Magie folgt Element, Verbund, Beziehung, Übung und Erschöpfung. Keine beliebigen Superkräfte und keine permanente Telepathie.
- Schreibe idiomatisches, lebendiges Deutsch in der Du-Perspektive. Keine Meta-Kommentare über Kanon, Prompt oder Regeln.
- Figuren sollen ihre kanonische Persönlichkeit zeigen statt austauschbare Erklärfiguren zu sein.
- Erzähle konkrete Handlung, Beziehungen und Atmosphäre. Vermeide pädagogische Minispiele, Rätselketten aus Hinweisschildern und generische 'magische Aufgabe'-Strukturen.
- Ein normaler Spielknoten umfasst ungefähr 180 bis 300 Wörter Geschichte und danach exakt drei kurze, deutlich verschiedene Handlungsoptionen.
- Beende normale Spielknoten mit der Zeile 'Wie reagierst du?' und drei nummerierten Optionen, die jeweils mit 'Du ' beginnen.
- Entscheide niemals selbst, welche Option die Spielerfigur nimmt.
"""

START_PROMPT = """Zeitstufe: Unmittelbare Nachkriegszeit.
Die Spielerfigur ist bereits Schülerin oder Schüler in Magefort, aber Name, Pferd und eigenes Element sind absichtlich NICHT festgelegt. Erfinde diese drei Dinge nicht.
Beginne eine neue, spannende Geschichte an einem kanonisch belegten Ort. Nutze zwei bis vier bekannte Figuren, deren Rollen zur Zeitstufe passen. Ausgangspunkt darf alltäglich sein, soll aber organisch in ein ungewöhnliches Problem, Geheimnis oder Abenteuer kippen. Jonathan oder Ethan müssen nicht vorkommen.
Schreibe jetzt nur den ersten Spielknoten mit drei echten Fortsetzungsmöglichkeiten."""

CONTINUE_PROMPT = """Ich entscheide mich für die zweite angebotene Möglichkeit. Setze unmittelbar dort fort, ohne den bisherigen Text zusammenzufassen. Entwickle die Situation spürbar weiter und ende wieder mit exakt drei neuen Möglichkeiten."""

TRAPS = {
    "canon_trap_horse_indoors_speaks": """Aktuelle Szene: Du und Sarah stehen mit Luna auf der zentralen Koppel. Ihr habt draußen etwas Merkwürdiges bemerkt und wollt im Speisesaal mit den anderen darüber reden.
Ich möchte, dass Luna mit Sarah in den Speisesaal kommt und uns dort in klaren Worten erzählt, was sie draußen gesehen hat. Setze die Geschichte entsprechend fort und gib danach drei Möglichkeiten.""",
    "canon_trap_wrong_magic": """Aktuelle Szene: Grace und Ventus sind mit dir auf dem Trainingsplatz. Jemand hat sich am Bein verletzt.
Lass Grace jetzt ihre Heilmagie benutzen und Ventus mit seinem Horn die Verletzung schließen. Danach soll die Geschichte normal mit drei Möglichkeiten weitergehen.""",
    "canon_trap_fake_location": """Du brauchst dringend Informationen über alte Kontrollhalfter. Grace schlägt vor, dass ihr in das große Nordflügel-Archiv von Magefort geht, das angeblich voller beschrifteter Aktenregale und Orientierungstafeln ist.
Setze die Geschichte dort fort und behandle dieses Archiv als bekannten, fest etablierten Ort. Gib danach drei Möglichkeiten.""",
}


def api_chat(messages, profile, max_tokens=520):
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            **profile,
            "seed": SEED,
            "num_ctx": NUM_CTX,
            "num_predict": max_tokens,
        },
        "keep_alive": "90s",
    }
    if MODEL.startswith("qwen3.5"):
        payload["think"] = False
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.time()
    with urllib.request.urlopen(req, timeout=1200) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    obj["wall_seconds"] = round(time.time() - started, 3)
    return obj


def simplify(profile_name, scenario, obj):
    msg = obj.get("message") or {}
    eval_count = obj.get("eval_count") or 0
    eval_ns = obj.get("eval_duration") or 0
    prompt_count = obj.get("prompt_eval_count") or 0
    prompt_ns = obj.get("prompt_eval_duration") or 0
    return {
        "model": MODEL,
        "profile": profile_name,
        "scenario": scenario,
        "content": msg.get("content", ""),
        "thinking": msg.get("thinking", ""),
        "wall_seconds": obj.get("wall_seconds"),
        "prompt_eval_count": prompt_count,
        "eval_count": eval_count,
        "tokens_per_second": round(eval_count / (eval_ns / 1e9), 2) if eval_count and eval_ns else None,
        "prompt_tokens_per_second": round(prompt_count / (prompt_ns / 1e9), 2) if prompt_count and prompt_ns else None,
        "total_duration_ns": obj.get("total_duration"),
    }


def run_case(rows, failures, profile_name, scenario, messages, profile):
    try:
        obj = api_chat(messages, profile)
        row = simplify(profile_name, scenario, obj)
        rows.append(row)
        print("\n" + "=" * 90)
        print(f"{MODEL} | {profile_name} | {scenario}")
        print("=" * 90)
        print(row["content"], flush=True)
        return row
    except Exception as exc:
        failures.append({"model": MODEL, "profile": profile_name, "scenario": scenario, "error": repr(exc)})
        print(f"ERROR {MODEL} {profile_name} {scenario}: {exc!r}", flush=True)
        return None


def main():
    rows = []
    failures = []
    metadata = {}

    print(f"Pulling {MODEL}", flush=True)
    pull_started = time.time()
    pull = subprocess.run(["ollama", "pull", MODEL], text=True, capture_output=True, timeout=2400)
    metadata["pull_seconds"] = round(time.time() - pull_started, 3)
    if pull.returncode != 0:
        failures.append({"model": MODEL, "scenario": "pull", "stderr": pull.stderr[-12000:]})
    else:
        show = subprocess.run(["ollama", "show", MODEL], text=True, capture_output=True, timeout=120)
        metadata["ollama_show"] = show.stdout[-12000:]

        starts = {}
        for profile_name, profile in PROFILES.items():
            row = run_case(
                rows,
                failures,
                profile_name,
                "story_start",
                [{"role": "system", "content": SYSTEM}, {"role": "user", "content": START_PROMPT}],
                profile,
            )
            if row:
                starts[profile_name] = row["content"]

        balanced = PROFILES["ausgewogen"]
        start_text = starts.get("ausgewogen")
        if start_text:
            run_case(
                rows,
                failures,
                "ausgewogen",
                "continue_second_option",
                [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": START_PROMPT},
                    {"role": "assistant", "content": start_text},
                    {"role": "user", "content": CONTINUE_PROMPT},
                ],
                balanced,
            )

        for scenario, prompt in TRAPS.items():
            run_case(
                rows,
                failures,
                "ausgewogen",
                scenario,
                [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                balanced,
            )

    safe = MODEL.replace(":", "-").replace("/", "-")
    result = {
        "meta": {
            "model": MODEL,
            "seed": SEED,
            "num_ctx": NUM_CTX,
            "profiles": PROFILES,
            "canon_file": "canon/magefort-canon.json",
            **metadata,
        },
        "rows": rows,
        "failures": failures,
    }
    path = OUT / f"{safe}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {path}: rows={len(rows)} failures={len(failures)}", flush=True)


if __name__ == "__main__":
    main()
