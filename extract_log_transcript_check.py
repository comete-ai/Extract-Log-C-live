import json
import re
import pandas as pd

log_file_path = "log-prod-20260903.log"
output_excel_path = "export_transcripts_20260903.xlsx"

# Regex pour éliminer les caractères de contrôle non valides en XML/Excel
ILLEGAL_CHARACTERS_RE = re.compile(
    r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x84\x86-\x9F]"
)


def sanitize_text(text):
    if isinstance(text, str):
        return ILLEGAL_CHARACTERS_RE.sub("", text)
    return text


rows = []

with open(log_file_path, "r", encoding="utf-8") as file:
    for line in file:
        call_id_match = re.search(r"\[CallID:\s*([^\]]+)\]", line)
        call_id = call_id_match.group(1).strip() if call_id_match else None

        json_match = re.search(r"(\{.*\})", line)
        if not json_match:
            continue

        try:
            payload = json.loads(json_match.group(1))
            metadata = payload.get("metadata", {})

            if metadata.get("type") == "final":
                raw_transcript = payload.get("transcript")
                clean_transcript = sanitize_text(raw_transcript)

                rows.append({
                    "CallID": call_id,
                    "Emetteur": payload.get("speaker", "AGENT_SPEAKER"),
                    "id": metadata.get("transcript_id"),
                    "type": "transcript",
                    "evidence_text": clean_transcript,
                    "ai_score": (
                        float(metadata["confidence"])
                        if "confidence" in metadata
                        else None
                    ),
                    "start_ms": (
                        int(metadata["start_ms"])
                        if str(metadata.get("start_ms", "")).isdigit()
                        else 0
                    ),
                })
        except (json.JSONDecodeError, ValueError):
            continue

df = pd.DataFrame(rows)

if not df.empty:
    # Sélection des 10 premiers CallID uniques dans l'ordre d'apparition
    first_10_call_ids = df["CallID"].dropna().unique()[:10]

    # Filtrage du DataFrame sur ces 10 appels
    df = df[df["CallID"].isin(first_10_call_ids)]

    # Regroupement par CallID et tri chronologique
    df = df.sort_values(by=["CallID", "start_ms"]).drop(columns=["start_ms"])

df.to_excel(output_excel_path, index=False)