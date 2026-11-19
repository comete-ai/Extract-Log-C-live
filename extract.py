import re
import csv
import json

log_file_path = "backend-prod.log"  # Remplace par le nom de ton fichier log
output_csv_path = "sessions_appels.csv"

# Regex pour repérer les événements clés
re_start = re.compile(r"(\d{2}:\d{2}:\d{2}).*POST .*/api/v1/sessions/")
re_agent = re.compile(r"(\d{2}:\d{2}:\d{2}).*\[SIGNALR\] L'agent ([a-f0-9\-]+) écoute")
re_end = re.compile(r"(\d{2}:\d{2}:\d{2}).*POST .*/api/v1/sessions/([a-f0-9\-]+)/end")
re_ia_details = re.compile(r">>> \[DÉTAILS IA FIN D'APPEL\] (\{.*\})")

sessions = []
current_session = None

with open(log_file_path, "r", encoding="utf-8") as f:
    for line in f:
        # Début de session
        match_start = re_start.search(line)
        if match_start:
            if current_session:
                sessions.append(current_session)
            current_session = {
                "start_time": match_start.group(1),
                "end_time": "",
                "agent_id": "",
                "session_id": "",
                "logs": [line.strip()],
                "ia_details": ""
            }
            continue

        if current_session:
            current_session["logs"].append(line.strip())

            # Agent ID via SignalR
            match_agent = re_agent.search(line)
            if match_agent and not current_session["agent_id"]:
                current_session["agent_id"] = match_agent.group(2)

            # Fin de session & Session ID
            match_end = re_end.search(line)
            if match_end:
                current_session["end_time"] = match_end.group(1)
                current_session["session_id"] = match_end.group(2)

            # Détails IA
            match_ia = re_ia_details.search(line)
            if match_ia:
                current_session["ia_details"] = match_ia.group(1)

    if current_session:
        sessions.append(current_session)

# Export vers CSV (compatible Excel)
with open(output_csv_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow(["Agent ID", "Session ID", "Heure Début", "Heure Fin", "Détails IA (JSON)", "Logs Bruts Complet"])
    
    for s in sessions:
        writer.writerow([
            s["agent_id"],
            s["session_id"],
            s["start_time"],
            s["end_time"],
            s["ia_details"],
            "\n".join(s["logs"])
        ])

print(f"Extraction terminée ! Fichier généré : {output_csv_path}")