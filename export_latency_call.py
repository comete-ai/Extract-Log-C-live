import csv
import json
import re
from datetime import datetime


def parse_timestamp(ts_str):
    """Convertit un timestamp ISO 8601 en objet datetime en tronquant les nanosecondes aux microsecondes."""
    ts_clean = ts_str.rstrip("Z")
    if "." in ts_clean:
        main_part, frac_part = ts_clean.split(".", 1)
        ts_clean = f"{main_part}.{frac_part[:6]}"
    return datetime.fromisoformat(ts_clean)


def parse_log_to_grouped_csv(log_file_path, output_csv_path):
    # Dictionnaire de stockage des sessions par CallID
    sessions = {}

    with open(log_file_path, "r", encoding="utf-8") as file:
        for line in file:
            if ">>> [DÉTAILS IA]" in line and "{" in line:
                try:
                    timestamp_str = line.split()[0]

                    # Extraction du CallID et de l'Agent ID
                    call_match = re.search(r"\[CallID:\s*(.*?)\]", line)
                    agent_match = re.search(r"\[Agent:\s*(.*?)\]", line)

                    if not call_match:
                        continue

                    call_id = call_match.group(1).strip()
                    agent_id = (
                        agent_match.group(1).strip()
                        if agent_match
                        else "Inconnu"
                    )

                    # Isolation du JSON
                    json_start = line.find("{")
                    if json_start == -1:
                        continue

                    json_str = line[json_start:].strip()
                    data = json.loads(json_str)
                    metadata = data.get("metadata", {})

                    # Initialisation de la session pour ce CallID
                    if call_id not in sessions:
                        sessions[call_id] = {
                            "Call ID": call_id,
                            "Agent ID": agent_id,
                            "Date Debut": timestamp_str,
                            "Date Fin": timestamp_str,
                            "pending_final_line": None,
                            "pending_final_ts": None,
                            "compliances": [],
                            "intents": [],
                        }

                    session = sessions[call_id]
                    session[
                        "Date Fin"
                    ] = (
                        timestamp_str  # Mise à jour continue de la date de fin
                    )
                    current_dt = parse_timestamp(timestamp_str)

                    # Identification du type de ligne
                    has_compliance = (
                        "compliances" in data
                        or metadata.get("type") == "conformity_match"
                    )
                    has_intent = (
                        "intents" in data
                        or metadata.get("type") == "intention_match"
                    )
                    is_final_transcript = (
                        metadata.get("type") == "final"
                        or "transcript" in data
                    ) and not (has_compliance or has_intent)

                    # 1. Mémorisation du transcript "final"
                    if is_final_transcript:
                        session["pending_final_line"] = line.strip()
                        session["pending_final_ts"] = current_dt

                    # 2. Association avec une Conformité
                    elif has_compliance:
                        if session["pending_final_ts"] is not None:
                            delta_sec = (
                                current_dt - session["pending_final_ts"]
                            ).total_seconds()
                            delta_ms = delta_sec * 1000

                            session["compliances"].append(
                                {
                                    "transcript_line": session[
                                        "pending_final_line"
                                    ],
                                    "match_line": line.strip(),
                                    "delta_sec": delta_sec,
                                    "delta_ms": delta_ms,
                                }
                            )

                            session["pending_final_line"] = None
                            session["pending_final_ts"] = None

                    # 3. Association avec une Intention
                    elif has_intent:
                        if session["pending_final_ts"] is not None:
                            delta_sec = (
                                current_dt - session["pending_final_ts"]
                            ).total_seconds()
                            delta_ms = delta_sec * 1000

                            session["intents"].append(
                                {
                                    "transcript_line": session[
                                        "pending_final_line"
                                    ],
                                    "match_line": line.strip(),
                                    "delta_sec": delta_sec,
                                    "delta_ms": delta_ms,
                                }
                            )

                            session["pending_final_line"] = None
                            session["pending_final_ts"] = None

                except (json.JSONDecodeError, ValueError):
                    continue
                except Exception as e:
                    print(f"Error parsing line: {e}")

    # Génération du fichier CSV
    fieldnames = ["Call ID", "Agent ID", "Date Debut", "Date Fin", "Log"]

    with open(
        output_csv_path, "w", newline="", encoding="utf-8-sig"
    ) as csvfile:
        if not sessions:
            writer = csv.DictWriter(csvfile, fieldnames=["Message"])
            writer.writeheader()
            writer.writerow({"Message": "No complete sessions found."})
        else:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for call_id, session in sessions.items():
                log_lines = [f"CALL_ID : {call_id}"]

                all_deltas = []
                comp_deltas = [item["delta_sec"] for item in session["compliances"]]
                intent_deltas = [item["delta_sec"] for item in session["intents"]]

                # Formatting de la section Conformité
                if session["compliances"]:
                    log_lines.append("- Conformité :")
                    for item in session["compliances"]:
                        log_lines.append(item["transcript_line"])
                        log_lines.append(item["match_line"])
                        log_lines.append(
                            f"-> {item['delta_sec']:.3f}s ({item['delta_ms']:.1f}ms)\n"
                        )
                        all_deltas.append(item["delta_sec"])

                # Formatting de la section Intentions
                if session["intents"]:
                    log_lines.append("- Intentions :")
                    for item in session["intents"]:
                        log_lines.append(item["transcript_line"])
                        log_lines.append(item["match_line"])
                        log_lines.append(
                            f"-> {item['delta_sec']:.3f}s ({item['delta_ms']:.1f}ms)\n"
                        )
                        all_deltas.append(item["delta_sec"])

                # Calcul des moyennes
                avg_comp = (
                    f"{sum(comp_deltas) / len(comp_deltas):.3f} s"
                    if comp_deltas
                    else "N/A"
                )
                avg_intent = (
                    f"{sum(intent_deltas) / len(intent_deltas):.3f} s"
                    if intent_deltas
                    else "N/A"
                )
                avg_global = (
                    f"{sum(all_deltas) / len(all_deltas):.3f} s"
                    if all_deltas
                    else "N/A"
                )

                log_lines.append(f"Latence moyenne Conformité : {avg_comp}")
                log_lines.append(f"Latence moyenne Intention  : {avg_intent}")
                log_lines.append(f"Latence moyenne Globale    : {avg_global}")

                formatted_log = "\n".join(log_lines)

                writer.writerow(
                    {
                        "Call ID": session["Call ID"],
                        "Agent ID": session["Agent ID"],
                        "Date Debut": session["Date Debut"],
                        "Date Fin": session["Date Fin"],
                        "Log": formatted_log,
                    }
                )

    print(f"Exported successfully to {output_csv_path}")


if __name__ == "__main__":
    parse_log_to_grouped_csv(
        "log-prod-20260820.log", "Export_Old_Model_20260820.csv"
    )