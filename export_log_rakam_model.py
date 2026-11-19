import json
import openpyxl


def parse_log_to_excel(log_file_path, output_excel_path):
    rows = []

    with open(log_file_path, "r", encoding="utf-8") as file:
        for line in file:
            if ">>> [DÉTAILS IA]" in line and "]: {" in line:
                try:
                    # Isolation et parsing du payload JSON
                    json_str = line.split("]: ", 1)[1].strip()
                    data = json.loads(json_str)
                    metadata = data.get("metadata", {})

                    # 1. Traitement des INTENTS
                    if "intents" in data:
                        intents_list = data.get("intents", [])
                        for intent in intents_list:
                            rows.append(
                                {
                                    "id": intent.get("intentId", ""),
                                    "type": "intents",
                                    "criterion": metadata.get(
                                        "intention_name",
                                        metadata.get("intention_code", ""),
                                    ),
                                    "ai_detection": (
                                        "matched"
                                        if intent
                                        else "not_matched"
                                    ),
                                    "ai_score": intent.get(
                                        "confidence",
                                        metadata.get("confidence", ""),
                                    ),
                                    "evidence_text": metadata.get(
                                        "trigger_phrase", ""
                                    ),
                                    "matched_trigger": metadata.get(
                                        "matched_text", ""
                                    ),
                                }
                            )

                    # 2. Traitement des COMPLIANCES
                    elif "compliances" in data:
                        compliances_list = data.get("compliances", [])
                        for compliance in compliances_list:
                            is_respected = compliance.get("isRespected", False)
                            rows.append(
                                {
                                    "id": compliance.get("ruleId", ""),
                                    "type": "compliances",
                                    "criterion": metadata.get(
                                        "tag_label", metadata.get("tag_id", "")
                                    ),
                                    "ai_detection": (
                                        "matched"
                                        if is_respected
                                        else "not_matched"
                                    ),
                                    "ai_score": metadata.get("confidence", ""),
                                    "evidence_text": "",
                                    "matched_trigger": metadata.get(
                                        "evidence", ""
                                    ),
                                }
                            )

                    # 3. Traitement du TRANSCRIPT
                    elif "transcript" in data:
                        rows.append(
                            {
                                "id": metadata.get("transcript_id", ""),
                                "type": "transcript",
                                "criterion": data.get(
                                    "speaker", "AGENT_SPEAKER"
                                ),
                                "ai_detection": "matched",
                                "ai_score": metadata.get("confidence", ""),
                                "evidence_text": "",
                                "matched_trigger": "",
                            }
                        )

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"Erreur lors du traitement de la ligne : {e}")

    # Génération du fichier Excel (.xlsx)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Détails IA"

    headers = [
        "id",
        "type",
        "criterion",
        "ai_detection",
        "ai_score",
        "evidence_text",
        "matched_trigger",
    ]
    ws.append(headers)

    for row in rows:
        ws.append(
            [
                row["id"],
                row["type"],
                row["criterion"],
                row["ai_detection"],
                row["ai_score"],
                row["evidence_text"],
                row["matched_trigger"],
            ]
        )

    wb.save(output_excel_path)
    print(
        f"Fichier Excel généré avec succès : {output_excel_path} ({len(rows)} lignes enregistrées)"
    )


if __name__ == "__main__":
    parse_log_to_excel("log-prod-20260901_03.log", "Rapport_IA_20260901.xlsx")