import argparse, hashlib, json, os, re, time, urllib.request
from pathlib import Path

PROFILES = {
    "konservativ": {"temperature": 0.25, "top_p": 0.78, "repeat_penalty": 1.08},
    "ausgewogen": {"temperature": 0.62, "top_p": 0.90, "repeat_penalty": 1.06},
    "kreativ": {"temperature": 0.95, "top_p": 0.96, "repeat_penalty": 1.04},
}
OPTIONS = [2, 1, 3, 2, 3, 1, 2, 1, 3]
TRAPS = {
    "canon_trap_horse_indoors_speaks": """Aktuelle Szene: Du und Sarah stehen mit Luna auf der zentralen Koppel. Ihr habt draußen etwas Merkwürdiges bemerkt und wollt im Speisesaal mit den anderen darüber reden.\nIch möchte, dass Luna mit Sarah in den Speisesaal kommt und uns dort in klaren Worten erzählt, was sie draußen gesehen hat. Setze die Geschichte entsprechend fort und gib danach drei Möglichkeiten.""",
    "canon_trap_wrong_magic": """Aktuelle Szene: Grace und Ventus sind mit dir auf dem Trainingsplatz. Jemand hat sich am Bein verletzt.\nLass Grace jetzt ihre Heilmagie benutzen und Ventus mit seinem Horn die Verletzung schließen. Danach soll die Geschichte normal mit drei Möglichkeiten weitergehen.""",
    "canon_trap_fake_location": """Du brauchst dringend Informationen über alte Kontrollhalfter. Grace schlägt vor, dass ihr in das große Nordflügel-Archiv von Magefort geht, das angeblich voller beschrifteter Aktenregale und Orientierungstafeln ist.\nSetze die Geschichte dort fort und behandle dieses Archiv als bekannten, fest etablierten Ort. Gib danach drei Möglichkeiten.""",
}
START = """Zeitstufe: Unmittelbare Nachkriegszeit.
Die Spielerfigur ist bereits Schülerin oder Schüler in Magefort, aber Name, Pferd und eigenes Element sind absichtlich NICHT festgelegt. Erfinde diese drei Dinge nicht.
Beginne eine neue, spannende Geschichte an einem kanonisch belegten Ort. Nutze zwei bis vier bekannte Figuren, deren Rollen zur Zeitstufe passen. Ausgangspunkt darf alltäglich sein, soll aber organisch in ein ungewöhnliches Problem, Geheimnis oder Abenteuer kippen. Jonathan oder Ethan müssen nicht vorkommen.
Schreibe jetzt nur den ersten Spielknoten mit drei echten Fortsetzungsmöglichkeiten. Schreibe klar für ungefähr 10-Jährige, ohne kindische oder verniedlichende Sprache."""


def system_prompt(canon):
    return f"""Du bist die Erzählinstanz eines interaktiven deutschen Rollenspiels in Magefort Castle.

BINDENDER KANON:
{json.dumps(canon, ensure_ascii=False)}

Regeln für jede Antwort:
- Der Kanon ist bindend. Widersprich ihm niemals und behandle offene Punkte nicht als gesicherte Weltfakten.
- extendedCanonDefault ist false: Figuren aus 'erweiterter_kanon' erscheinen nur, wenn die Spielanweisung sie ausdrücklich aktiviert.
- Erfinde keine neuen permanenten Schlossbereiche, Institutionen oder Weltregeln und stelle Unbelegtes nicht als feststehenden Buchkanon dar.
- Pferde verhalten sich im Normalfall glaubwürdig pferdisch. Sie führen keine normalen Gespräche und betreten keine Wohn-, Unterrichts-, Speise-, Büro- oder sonstigen Schlossräume.
- Magie folgt Element, Verbund, Beziehung, Übung und Erschöpfung. Keine beliebigen Superkräfte und keine permanente Telepathie.
- Schreibe idiomatisches, lebendiges Deutsch in der Du-Perspektive. Keine Meta-Kommentare über Kanon, Prompt oder Regeln.
- Zielgruppe sind ungefähr 10-jährige Leserinnen und Leser. Die Sprache muss leicht verständlich, klar und konkret sein, aber niemals infantil, verniedlichend oder herablassend.
- Bevorzuge kurze bis mittellange Sätze und geläufige Wörter. Schwierige oder magische Begriffe sind erlaubt, wenn ihre Bedeutung aus dem Zusammenhang verständlich wird.
- Vermeide unnötige Schachtelsätze, abstraktes Amtsdeutsch, überladene Metaphern und künstlich erwachsene Prosa. Vereinfache dabei nicht Handlung, Gefühle oder Figuren zu Babysprache.
- Figuren sollen ihre kanonische Persönlichkeit zeigen statt austauschbare Erklärfiguren zu sein.
- Erzähle konkrete Handlung, Beziehungen und Atmosphäre. Vermeide pädagogische Minispiele, Rätselketten aus Hinweisschildern und generische 'magische Aufgabe'-Strukturen.
- Ein normaler Spielknoten umfasst ungefähr 180 bis 300 Wörter Geschichte und danach exakt drei kurze, deutlich verschiedene Handlungsoptionen.
- Beende normale Spielknoten mit der Zeile 'Wie reagierst du?' und drei nummerierten Optionen, die jeweils mit 'Du ' beginnen.
- Entscheide niemals selbst, welche Option die Spielerfigur nimmt.
- Behalte über längere Spielverläufe alle bereits etablierten Fakten, Beziehungen, Orte, Verletzungen, Gegenstände und offenen Probleme konsistent bei.
"""


def cont(choice, step):
    return f"""Ich wähle Möglichkeit {choice} aus deiner letzten Antwort.
Setze unmittelbar dort fort, ohne den bisherigen Verlauf zusammenzufassen oder zurückzusetzen. Dies ist Spielknoten {step} eines längeren zusammenhängenden Abenteuers. Entwickle Konsequenzen aus bisherigen Entscheidungen und bereits etablierten Fakten weiter. Behalte die leicht verständliche, aber nicht infantile Sprache für ungefähr 10-Jährige bei. Ende wieder mit exakt drei neuen, deutlich verschiedenen Möglichkeiten."""


def read_metrics(text):
    story = text.split("Wie reagierst du?", 1)[0]
    words = re.findall(r"[A-Za-zÄÖÜäöüß]+(?:-[A-Za-zÄÖÜäöüß]+)*", story)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", story) if re.search(r"[A-Za-zÄÖÜäöüß]", s)]
    lengths = [len(re.findall(r"[A-Za-zÄÖÜäöüß]+(?:-[A-Za-zÄÖÜäöüß]+)*", s)) for s in sentences]
    lengths = [x for x in lengths if x]
    if not words:
        return {"word_count": 0, "sentence_count": 0, "avg_sentence_words": None, "pct_sentences_over_20_words": None, "lix": None}
    avg = sum(lengths) / len(lengths) if lengths else None
    long_words = 100.0 * sum(len(w) > 6 for w in words) / len(words)
    return {
        "word_count": len(words), "sentence_count": len(lengths),
        "avg_sentence_words": round(avg, 2) if avg is not None else None,
        "pct_sentences_over_20_words": round(100.0 * sum(x > 20 for x in lengths) / len(lengths), 2) if lengths else None,
        "lix": round(avg + long_words, 2) if avg is not None else None,
    }


def sha(canon):
    raw = json.dumps(canon, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def atomic_save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def find_row(rows, profile, scenario):
    return next((r for r in rows if r.get("profile") == profile and r.get("scenario") == scenario), None)


def load_state(path, model, canon):
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("meta", {}).get("model") not in (None, model):
            raise RuntimeError("checkpoint model mismatch")
        old = data.get("meta", {}).get("canon_sha256")
        if old and old != sha(canon):
            raise RuntimeError("checkpoint canon mismatch")
    else:
        data = {"meta": {}, "rows": [], "failures": []}
    data.setdefault("rows", []); data.setdefault("failures", []); data.setdefault("meta", {})
    data["meta"].update({
        "format_version": 2, "checkpointing": "atomic-after-each-turn+cache",
        "model": model, "seed": 4242, "num_ctx": 8192, "story_steps": 10,
        "option_sequence": OPTIONS, "profiles": PROFILES, "canon_sha256": sha(canon),
        "language_target": "leicht verständlich für ungefähr 10-Jährige, aber nicht infantil",
    })
    return data


def chat(model, messages, profile):
    payload = {"model": model, "messages": messages, "stream": False,
               "options": {**profile, "seed": 4242, "num_ctx": 8192, "num_predict": 520},
               "keep_alive": "5m"}
    if model.lower().startswith(("qwen3", "qwen3.5")):
        payload["think"] = False
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=1200) as resp:
        obj = json.loads(resp.read().decode())
    obj["wall_seconds"] = round(time.time() - t, 3)
    return obj


def story_messages(state, system, profile, step):
    msgs = [{"role":"system","content":system},{"role":"user","content":START}]
    if step == 1:
        return msgs, None
    for prev in range(1, step):
        row = find_row(state["rows"], profile, f"story_step_{prev:02d}")
        if not row:
            raise RuntimeError(f"missing checkpoint {profile}/story_step_{prev:02d}")
        msgs.append({"role":"assistant","content":row["content"]})
        nxt = prev + 1
        choice = OPTIONS[(nxt - 2) % len(OPTIONS)]
        msgs.append({"role":"user","content":cont(choice, nxt)})
    return msgs, OPTIONS[(step - 2) % len(OPTIONS)]


def save_response(state, path, model, profile, scenario, messages, sampling, step=None, choice=None):
    if find_row(state["rows"], profile, scenario):
        print(f"SKIP {profile}/{scenario}")
        return
    state["failures"] = [f for f in state["failures"] if not (f.get("profile") == profile and f.get("scenario") == scenario)]
    try:
        obj = chat(model, messages, sampling)
        msg = obj.get("message") or {}; content = msg.get("content", "")
        ec = obj.get("eval_count") or 0; ed = obj.get("eval_duration") or 0
        pc = obj.get("prompt_eval_count") or 0; pd = obj.get("prompt_eval_duration") or 0
        state["rows"].append({
            "model":model,"profile":profile,"scenario":scenario,"story_step":step,"chosen_option":choice,
            "content":content,"readability":read_metrics(content),"thinking":msg.get("thinking", ""),
            "wall_seconds":obj.get("wall_seconds"),"prompt_eval_count":pc,"eval_count":ec,
            "tokens_per_second":round(ec/(ed/1e9),2) if ec and ed else None,
            "prompt_tokens_per_second":round(pc/(pd/1e9),2) if pc and pd else None,
            "total_duration_ns":obj.get("total_duration"),
        })
        state["meta"]["last_checkpoint_epoch"] = time.time(); atomic_save(path, state)
        print(f"DONE {profile}/{scenario}; checkpoint={path}")
        print(content)
    except Exception as exc:
        state["failures"].append({"model":model,"profile":profile,"scenario":scenario,"story_step":step,"chosen_option":choice,"error":repr(exc)})
        state["meta"]["last_checkpoint_epoch"] = time.time(); atomic_save(path, state)
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--canon", required=True); ap.add_argument("--out", default="results")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--step", type=int); mode.add_argument("--trap", choices=list(TRAPS))
    ap.add_argument("--profile", choices=list(PROFILES))
    args = ap.parse_args()
    if args.step is not None and (args.profile is None or not 1 <= args.step <= 10):
        ap.error("--step requires --profile and step 1..10")
    canon = json.loads(Path(args.canon).read_text(encoding="utf-8")); system = system_prompt(canon)
    path = Path(args.out) / f"{args.model.replace(':','-').replace('/','-')}.json"
    state = load_state(path, args.model, canon); atomic_save(path, state)
    if args.step is not None:
        scenario = f"story_step_{args.step:02d}"; msgs, choice = story_messages(state, system, args.profile, args.step)
        save_response(state, path, args.model, args.profile, scenario, msgs, PROFILES[args.profile], args.step, choice)
    else:
        save_response(state, path, args.model, "ausgewogen", args.trap,
                      [{"role":"system","content":system},{"role":"user","content":TRAPS[args.trap]}], PROFILES["ausgewogen"])

if __name__ == "__main__": main()
