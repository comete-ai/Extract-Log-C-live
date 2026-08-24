import json
import pandas as pd
import openpyxl
from openpyxl.styles import Alignment, PatternFill, Font, Border, Side
import re

def parse_log_to_grouped_excel(log_file_path, output_excel_path):
    sessions = []
    current_session = None

    with open(log_file_path, 'r', encoding='utf-8') as file:
        for line in file:
            # We are only interested in lines with >>> [DÉTAILS IA] and a JSON payload
            if ">>> [DÉTAILS IA]" in line and "]: {" in line:
                try:
                    # Isolate Timestamp and Agent ID
                    timestamp = line.split(" ")[0]
                    agent_match = re.search(r'\[Agent: (.*?)\]:', line)
                    agent_id = agent_match.group(1) if agent_match else "Unknown"
                    
                    json_str = line.split("]: ", 1)[1].strip()
                    data = json.loads(json_str)
                    metadata = data.get("metadata", {})
                    
                    # Session Start
                    if metadata.get("status") == "streaming_started":
                        current_session = {
                            "Agent ID": agent_id,
                            "Date Debut": timestamp,
                            "Date Fin": None,
                            "Log": [] 
                        }
                        continue
                        
                    # Session End
                    if data.get("isFinalResponse") is True:
                        if current_session is not None:
                            current_session["Date Fin"] = timestamp
                            sessions.append(current_session)
                            current_session = None
                        continue

                    # Harvest the exact unaltered line during active session
                    if current_session is not None:
                        if (metadata.get("type") == "final" and "transcript" in data) or \
                           ("compliances" in data) or \
                           ("intents" in data):
                            # line.strip() just removes the trailing newline character, 
                            # preserving the exact structure of the line.
                            current_session["Log"].append(line.strip())

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    print(f"Error parsing line: {e}")

    # Process logs into a single string separated by newlines so it wraps cleanly in Excel
    for s in sessions:
        s["Log"] = "\n".join(s["Log"])

    df = pd.DataFrame(sessions)
    
    # Export and format
    with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
        if df.empty:
            df = pd.DataFrame([{"Message": "No complete sessions found."}])
        df.to_excel(writer, sheet_name="Sessions", index=False)

    style_excel(output_excel_path)
    print(f"Exported successfully to {output_excel_path}")


def style_excel(file_path):
    wb = openpyxl.load_workbook(file_path)
    ws = wb.active
    
    # Aesthetics
    border = Border(left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
                    top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9'))
    
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="333f4f", end_color="333f4f", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
        
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = border
            # THIS allows the log block to break lines inside the cell beautifully 
            cell.alignment = Alignment(vertical="top", wrap_text=True) 

    ws.column_dimensions['A'].width = 40 # Agent ID
    ws.column_dimensions['B'].width = 30 # Date Debut
    ws.column_dimensions['C'].width = 30 # Date Fin
    ws.column_dimensions['D'].width = 150 # Log
    
    wb.save(file_path)

if __name__ == "__main__":
    parse_log_to_grouped_excel("backend-prod.log", "Sessions_Grouped.xlsx")