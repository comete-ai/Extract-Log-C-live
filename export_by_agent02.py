import csv
import json
import re


def parse_log_to_grouped_csv(log_file_path, output_csv_path):
    active_sessions = {}  # Clé : agent_id, Valeur : dictionnaire de session
    completed_sessions = []

    with open(log_file_path, "r", encoding="utf-8") as file:
        for line in file:
            if ">>> [DÉTAILS IA]" in line and "]: {" in line:
                try:
                    # Extraction du timestamp et de l'Agent ID
                    timestamp = line.split(" ")[0]
                    agent_match = re.search(r"\[Agent: (.*?)\]:", line)

                    if not agent_match:
                        continue

                    agent_id = agent_match.group(1)

                    # Isolation et parsing du JSON
                    json_str = line.split("]: ", 1)[1].strip()
                    data = json.loads(json_str)
                    metadata = data.get("metadata", {})

                    # 1. Début de session pour CET agent
                    if metadata.get("status") == "streaming_started":
                        active_sessions[agent_id] = {
                            "Agent ID": agent_id,
                            "Date Debut": timestamp,
                            "Date Fin": None,
                            "Log": [],
                        }
                        continue

                    # 2. Fin de session pour CET agent
                    if data.get("isFinalResponse") is True:
                        if agent_id in active_sessions:
                            session = active_sessions.pop(agent_id)
                            session["Date Fin"] = timestamp
                            completed_sessions.append(session)
                        continue

                    # 3. Capture des événements de la session active de CET agent
                    if agent_id in active_sessions:
                        if (
                            (
                                metadata.get("type") == "final"
                                and "transcript" in data
                            )
                            or ("compliances" in data)
                            or ("intents" in data)
                        ):
                            active_sessions[agent_id]["Log"].append(
                                line.strip()
                            )

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"Error parsing line: {e}")

    # Écriture dans le fichier CSV avec le module natif csv
    fieldnames = ["Agent ID", "Date Debut", "Date Fin", "Log"]

    with open(
        output_csv_path, "w", newline="", encoding="utf-8-sig"
    ) as csvfile:
        if not completed_sessions:
            writer = csv.DictWriter(csvfile, fieldnames=["Message"])
            writer.writeheader()
            writer.writerow({"Message": "No complete sessions found."})
        else:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for session in completed_sessions:
                # Assemblage des lignes de log de la session
                session["Log"] = "\n".join(session["Log"])
                writer.writerow(session)

    print(f"Exported successfully to {output_csv_path}")


if __name__ == "__main__":
    parse_log_to_grouped_csv("log-prod-20260807-02.log", "Sessions_Grouped_20260807_02.csv")