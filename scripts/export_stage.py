"""Create a public JSONL export from Stage generation outputs."""

import argparse
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    root = Path(args.input_dir)
    folders = sorted(
        path for path in root.iterdir()
        if path.is_dir() and (path / "customer.json").exists()
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)

    dialogue_count = turn_count = stage_count = 0
    with output.open("w", encoding="utf-8") as handle:
        for public_index, folder in enumerate(folders, start=1):
            data = json.loads((folder / "customer.json").read_text(encoding="utf-8"))
            graph = data.get("graph", [])
            stages = []
            turns = []
            global_turn = 0
            for stage_index, stage in enumerate(graph, start=1):
                stage_type = str(stage.get("stage_type", "")).strip()
                stage_record = {
                    "stage_index": stage_index,
                    "stage": stage_type,
                }
                for key in ("applied_max_turns", "stopping_reason", "success_achieved"):
                    if key in stage:
                        stage_record[key] = stage[key]
                stages.append(stage_record)
                for turn in data.get("session_%d" % stage_index, []):
                    text = str(turn.get("clean_text", turn.get("text", ""))).strip()
                    speaker = str(turn.get("speaker", "")).strip()
                    if not text or not speaker:
                        continue
                    turns.append({
                        "turn_id": global_turn,
                        "stage_index": stage_index,
                        "stage": stage_type,
                        "speaker": speaker,
                        "text": text,
                    })
                    global_turn += 1

            speakers = []
            for turn in turns:
                if turn["speaker"] not in speakers:
                    speakers.append(turn["speaker"])
            client_name = str(data.get("name", "")).strip()
            adviser_name = next((name for name in speakers if name != client_name), "")
            record = {
                "dialogue_id": "stage_%03d" % public_index,
                "method": "Stage",
                "client_name": client_name,
                "adviser_name": adviser_name,
                "stages": stages,
                "turns": turns,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            dialogue_count += 1
            turn_count += len(turns)
            stage_count += len(graph)

    print("dialogues=%d stages=%d turns=%d" % (dialogue_count, stage_count, turn_count))


if __name__ == "__main__":
    main()
