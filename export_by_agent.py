import re
import os
import csv
import json

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ==============================================================================
# CONFIGURATION
# ==============================================================================
LOG_FILE_PATH = "backend-prod.log"
# OUTPUT_DIR = "export_agents"
OUTPUT_CSV_PATH = "sessions_groupees.csv"

# Expressions régulières
RE_SESSION_ID = re.compile(r'/api/v1/sessions/([a-f0-9\-]{36})', re.IGNORECASE)
RE_AGENT_ID = re.compile(r'(?:\[SIGNALR\] L\'agent|Agent:)\s*([a-f0-9\-]{36})', re.IGNORECASE)
RE_INTERACTION_ID = re.compile(r'\[Bridge\]\s*Session gRPC terminée pour\s*([a-f0-9a-zA-Z]+)', re.IGNORECASE)
RE_TIMESTAMP = re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z|\d{2}:\d{2}:\d{2}(?:\.\d+)?)')

def is_valid_ai_response(line_lower):
    """Vérifie si la ligne contient une réponse IA valide à conserver."""
    if ">>> [détails ia" not in line_lower and ">>> [details ia" not in line_lower:
        return False
    
    # Exclure catégoriquement les partielles
    if '"type": "partial"' in line_lower or '"type":"partial"' in line_lower:
        return False

    # Motifs validants : Transcript final, Conformité, Intention ou Fin d'appel
    valid_indicators = [
        '"type": "final"', '"type":"final"',
        '"compliances"', 'conformity_match',
        '"intents"', 'intention_match',
        'fin d\'appel'
    ]
    
    return any(indicator in line_lower for indicator in valid_indicators)


def process_and_group_logs():
    if not os.path.exists(LOG_FILE_PATH):
        print(f"❌ Erreur : Le fichier '{LOG_FILE_PATH}' est introuvable.")
        return

    sessions = {}
    current_session_id = None
    current_agent_id = ""
    pending_lines = []

    print(f"🔄 Traitement et filtrage des sessions avec retours IA depuis '{LOG_FILE_PATH}'...")

    with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue

            line_lower = line_str.lower()

            # 1. FILTRAGE : Exclure immédiatement les transcriptions partielles du flux
            if '"type": "partial"' in line_lower or '"type":"partial"' in line_lower:
                continue

            # 2. Détection ID interaction gRPC
            match_interaction = RE_INTERACTION_ID.search(line_str)
            interaction_id = match_interaction.group(1) if match_interaction else None

            # 3. Détection Agent ID
            match_agent = RE_AGENT_ID.search(line_str)
            if match_agent:
                current_agent_id = match_agent.group(1)

            # 4. Détection Session ID
            match_session = RE_SESSION_ID.search(line_str)
            if match_session:
                detected_session_id = match_session.group(1)
                
                if detected_session_id != current_session_id:
                    current_session_id = detected_session_id

                if current_session_id not in sessions:
                    sessions[current_session_id] = {
                        "date_time": "",
                        "agent_id": current_agent_id,
                        "interaction_id": "",
                        "has_ia_response": False,
                        "lines": []
                    }
                    if pending_lines:
                        sessions[current_session_id]["lines"].extend(pending_lines)
                        pending_lines = []

            # 5. Qualification et stockage dans la session courante
            if current_session_id:
                # Vérifie si cette ligne est un retour IA valide
                if is_valid_ai_response(line_lower):
                    sessions[current_session_id]["has_ia_response"] = True

                if interaction_id and not sessions[current_session_id]["interaction_id"]:
                    sessions[current_session_id]["interaction_id"] = interaction_id
                
                if current_agent_id and not sessions[current_session_id]["agent_id"]:
                    sessions[current_session_id]["agent_id"] = current_agent_id

                time_match = RE_TIMESTAMP.search(line_str)
                if time_match and not sessions[current_session_id]["date_time"]:
                    sessions[current_session_id]["date_time"] = time_match.group(1)

                sessions[current_session_id]["lines"].append(line_str)
            else:
                pending_lines.append(line_str)

    # 6. Écriture du CSV (sessions avec retours IA uniquement)
    valid_sessions_count = 0
    print(f"💾 Génération du CSV : '{OUTPUT_CSV_PATH}'...")

    with open(OUTPUT_CSV_PATH, "w", newline="", encoding="utf-8-sig") as f_out:
        writer = csv.writer(f_out, delimiter=";")
        
        # En-têtes
        writer.writerow(["Date/Heure", "Agent ID", "Session ID", "Contenu", "ID interaction"])

        for sess_id, sess_data in sessions.items():
            # Condition stricte : La session doit comporter au moins 1 retour IA valide
            if sess_data["has_ia_response"]:
                contenu_fusionne = "\n".join(sess_data["lines"])

                writer.writerow([
                    sess_data["date_time"],
                    sess_data["agent_id"],
                    sess_id,
                    contenu_fusionne,
                    sess_data["interaction_id"]
                ])
                valid_sessions_count += 1

    print(f"🎉 Terminé !")
    print(f"   • Sessions analysées : {len(sessions)}")
    print(f"   • Sessions enregistrées (avec réponses IA) : {valid_sessions_count}")

if __name__ == "__main__":
    process_and_group_logs()