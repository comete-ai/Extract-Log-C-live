import csv
import json
import re
from datetime import datetime


def parse_timestamp(ts_str):
    """Convertit un timestamp ISO 8601 en datetime en ajustant la précision aux microsecondes."""
    ts_clean = ts_str.rstrip("Z")
    if "." in ts_clean:
        main_part, frac_part = ts_clean.split(".", 1)
        ts_clean = f"{main_part}.{frac_part[:6]}"
    return datetime.fromisoformat(ts_clean)


def parse_log_to_grouped_csv(log_file_path, output_csv_path):
    # Stockage des sessions indexées par CallID (ou AgentID si CallID absent)
    sessions = {}

    stats = {
        "lines_read": 0,
        "ia_lines_found": 0,
        "json_parsed": 0,
        "sessions_found": 0,
    }

    with open(log_file_path, "r", encoding="utf-8") as file:
        for line in file:
            stats["lines_read"] += 1

            if "DÉTAILS IA" in line and "{" in line:
                stats["ia_lines_found"] += 1

                try:
                    timestamp_str = line.split()[0]

                    # Extraction du CallID et de l'Agent ID
                    call_match = re.search(r"\[CallID:\s*(.*?)\]", line)
                    agent_match = re.search(r"\[Agent:\s*(.*?)\]", line)

                    call_id = call_match.group(1).strip() if call_match else "Inconnu"
                    agent_id = agent_match.group(1).strip() if agent_match else "Inconnu"

                    # Identifiant unique de session (CallID en priorité)
                    session_key = call_id if call_id != "Inconnu" else agent_id

                    # Extraction du JSON
                    json_start = line.find("{")
                    if json_start == -1:
                        continue

                    json_str = line[json_start:].strip()
                    data = json.loads(json_str)
                    stats["json_parsed"] += 1

                    metadata = data.get("metadata", {})

                    # Initialisation de la session si première rencontre avec ce CallID
                    if session_key not in sessions:
                        sessions[session_key] = {
                            "Call ID": call_id,
                            "Agent ID": agent_id,
                            "Date Debut": timestamp_str,
                            "Date Fin": timestamp_str,
                            "Log": [],
                            "pending_final_ts": None,
                            "pending_final_text": None,
                            "latencies": [],
                        }
                        stats["sessions_found"] += 1

                    session = sessions[session_key]
                    session["Date Fin"] = timestamp_str  # Mise à jour continue de la fin
                    current_dt = parse_timestamp(timestamp_str)

                    # Identification des types de messages
                    is_final_transcript = (
                        metadata.get("type") == "final" or "transcript" in data
                    )
                    has_compliance = (
                        "compliances" in data or metadata.get("type") == "conformity_match"
                    )
                    has_intent = (
                        "intents" in data or metadata.get("type") == "intention_match"
                    )

                    # 1. Traitement des Transcripts Finals
                    if is_final_transcript and not (has_compliance or has_intent):
                        session["pending_final_ts"] = current_dt
                        session["pending_final_text"] = data.get("transcript", "")
                        session["Log"].append(line.strip())

                    # 2. Traitement des Compliances / Intents
                    elif has_compliance or has_intent:
                        event_type = "compliance" if has_compliance else "intent"

                        # Libellé explicatif selon le type d'événement
                        if has_compliance:
                            tag_label = metadata.get("tag_label", "")
                            label = f"Match: {tag_label}" if tag_label else session.get("pending_final_text", "")
                        else:
                            intent_name = metadata.get("intention_name", "")
                            label = f"Match: {intent_name}" if intent_name else session.get("pending_final_text", "")

                        if session["pending_final_ts"] is not None:
                            delta_sec = (current_dt - session["pending_final_ts"]).total_seconds()
                            delta_ms = delta_sec * 1000

                            session["latencies"].append(
                                {
                                    "event": event_type,
                                    "transcript": session["pending_final_text"] or label,
                                    "delta_sec": delta_sec,
                                    "delta_ms": delta_ms,
                                }
                            )

                            # Réinitialisation après association
                            session["pending_final_ts"] = None
                            session["pending_final_text"] = None

                        session["Log"].append(line.strip())

                    else:
                        session["Log"].append(line.strip())

                except (json.JSONDecodeError, ValueError):
                    continue
                except Exception:
                    continue

    print("\n--- RAPPORT DE DIAGNOSTIC ---")
    print(f"Lignes lues au total      : {stats['lines_read']}")
    print(f"Lignes avec 'DÉTAILS IA'  : {stats['ia_lines_found']}")
    print(f"JSON valides extraits     : {stats['json_parsed']}")
    print(f"Sessions (CallID) trouvées: {stats['sessions_found']}")
    print("-----------------------------\n")

    fieldnames = [
        "Call ID",
        "Agent ID",
        "Date Debut",
        "Date Fin",
        "Latence Moyenne Compliance (s)",
        "Latence Moyenne Intent (s)",
        "Latence Moyenne Globale (s)",
        "Détails Latences",
        "Log",
    ]

    with open(output_csv_path, "w", newline="", encoding="utf-8-sig") as csvfile:
        if not sessions:
            writer = csv.DictWriter(csvfile, fieldnames=["Message"])
            writer.writeheader()
            writer.writerow({"Message": "Aucune session trouvée dans le fichier log."})
        else:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for session in sessions.values():
                latencies = session["latencies"]

                if latencies:
                    comp_lats = [l["delta_sec"] for l in latencies if l["event"] == "compliance"]
                    intent_lats = [l["delta_sec"] for l in latencies if l["event"] == "intent"]

                    avg_comp_str = f"{sum(comp_lats) / len(comp_lats):.3f}" if comp_lats else "N/A"
                    avg_intent_str = f"{sum(intent_lats) / len(intent_lats):.3f}" if intent_lats else "N/A"
                    avg_global_str = f"{sum(l['delta_sec'] for l in latencies) / len(latencies):.3f}"

                    details_lines = []
                    details_csv = []
                    for i, l in enumerate(latencies, 1):
                        tag = l["event"].upper()
                        info = f"[{tag}] '{l['transcript']}' -> {l['delta_sec']:.3f}s ({l['delta_ms']:.1f}ms)"
                        details_lines.append(f"  {i}. {info}")
                        details_csv.append(f"{i}. {info}")

                    details_str = " | ".join(details_csv)

                    latency_summary_block = (
                        "\n\n==================================================\n"
                        "--- INFORMATIONS DE LATENCE (Final Transcript -> Compliance/Intent) ---\n"
                        + "\n".join(details_lines)
                        + "\n\n"
                        f"Latence Moyenne Compliance : {avg_comp_str} s\n"
                        f"Latence Moyenne Intent     : {avg_intent_str} s\n"
                        f"Latence Moyenne Globale    : {avg_global_str} s\n"
                        "=================================================="
                    )
                else:
                    avg_comp_str = "N/A"
                    avg_intent_str = "N/A"
                    avg_global_str = "N/A"
                    details_str = "Aucune latence détectée"
                    latency_summary_block = ""

                full_log = "\n".join(session["Log"]) + latency_summary_block

                writer.writerow(
                    {
                        "Call ID": session["Call ID"],
                        "Agent ID": session["Agent ID"],
                        "Date Debut": session["Date Debut"],
                        "Date Fin": session["Date Fin"],
                        "Latence Moyenne Compliance (s)": avg_comp_str,
                        "Latence Moyenne Intent (s)": avg_intent_str,
                        "Latence Moyenne Globale (s)": avg_global_str,
                        "Détails Latences": details_str,
                        "Log": full_log,
                    }
                )

    print(f"Export effectué dans : {output_csv_path}")


if __name__ == "__main__":
    parse_log_to_grouped_csv("log-prod-20260903.log", "Sessions_logs_latency_20260903.csv")