import os
import sys
import json
import time
import asyncio
import subprocess
from typing import Optional, Tuple
from websockets.exceptions import ConnectionClosed
from threading import Thread
import requests
import websockets

WATCH_PATH = "/Users/floris.fok/.claude/projects/-Users-floris-fok-Library-CloudStorage-OneDrive-Prosus-Naspers-Documents-claudedir-project1/d873fbbc-4e88-43ac-8491-d907bb3c7993.jsonl"
API_ENDPOINT = "https://4634e217c2b6.ngrok-free.app"

def get_file_identity(file_path: str) -> Optional[Tuple[int, int]]:
    """Return (device, inode) identity tuple for the file, or None if not exists."""
    try:
        stat_result = os.stat(file_path)
        return (stat_result.st_dev, stat_result.st_ino)
    except FileNotFoundError:
        return None


def open_file_for_read(file_path: str):
    """Open a file for text reading with UTF-8 encoding, ignoring decode errors."""
    return open(file_path, mode="r", encoding="utf-8", errors="replace")


def send_start_convo(prompt, cwd) -> str:
    """Send the start signal"""
    # Match example_client: POST /session/start with JSON body {"user_prompt": prompt}
    res = requests.post(
        f"{API_ENDPOINT}/session/start",
        json={"user_prompt": prompt},
        timeout=10,
    )
    res.raise_for_status()
    return res.json()["session_id"]

def send_end_convo(session_id, final_out, cwd) -> None:
    # Match example_client: POST /session/end with expected schema
    try:
        res = requests.post(
            f"{API_ENDPOINT}/session/end",
            json={
                "session_id": session_id,
                "final_output": final_out,
                "status": "success",
                "metadata": {
                    "tool_calls": 0,
                    "todos_completed": 0,
                    "files_modified": [],
                },
            },
            timeout=15,
        )
        if res.status_code != 200:
            print(f"Error sending end convo: {res.status_code} {res.text}")
            return
    except Exception as e:
        print(f"Error sending end convo: {e}")
        return

    # Start WebSocket command execution thread after ending the session
    t = Thread(target=git_thread, args=(session_id, cwd))
    t.start()

def process_line(line, session_id, session_started) -> str:

    try:
        line_data = json.loads(line)
    except:
        return
    
    cwd = line_data.get("cwd", '')
    
    if line_data.get('message', {}).get("role", "none") == "user" and not session_started:
        prompt = line_data.get('message', {}).get("content", "Empty Message, ignore")
        session_started = True
        return send_start_convo(prompt, cwd), session_started
    
    elif line_data.get('message', {}).get("role", "none") == "assistant":
        final_message = line_data.get('message', {}).get("content", {})

        if isinstance(final_message, list) and len(final_message) == 1:
            final_message = final_message[0]


        if isinstance(final_message, str):
            send_end_convo(session_id, final_message, cwd)
            session_started = False
            return session_id, session_started
        elif final_message.get("type") == 'text':
            send_end_convo(session_id, final_message['text'], cwd)
            session_started = False
            return session_id, session_started
    
    return session_id, session_started


def git_thread(session_id, cwd):
    """
    Open WebSocket with server and execute commands (match example_client behavior)
    """

    async def run_ws():
        ws_url = f"wss://{API_ENDPOINT.split('://', 1)[1]}/ws/execute"
        try:
            async with websockets.connect(ws_url) as websocket:
                # Notify server that the session has finished (triggers commit workflow)
                await websocket.send(
                    json.dumps({
                        "session_id": session_id,
                        "message_type": "session_finished",
                    })
                )

                while True:
                    message_text = await websocket.recv()
                    print(f"[ws] Received: {message_text}")
                    try:
                        message = json.loads(message_text)
                    except json.JSONDecodeError:
                        print("[ws] Invalid JSON message from server, ignoring")
                        continue

                    # Server may indicate overall success
                    if message.get("finished") is True:
                        print(f"[ws] Session {session_id} completed successfully")
                        break

                    # Execute command if requested
                    if message.get("message_type") == "execute_command":
                        cmd = message.get("command", "")
                        if not cmd:
                            await websocket.send(json.dumps({
                                "message_type": "command_executed",
                                "output": "",
                            }))
                            continue

                        try:
                            result = subprocess.run(
                                cmd,
                                cwd=cwd or None,
                                shell=True,
                                capture_output=True,
                                text=True,
                            )
                            output_text = result.stdout
                        except Exception as e:
                            output_text = f"Command execution error: {e}"

                        await websocket.send(json.dumps({
                            "message_type": "command_executed",
                            "output": output_text,
                        }))

        except Exception as e:
            print(f"[ws] Error: {e}")

    # Run the async websocket client
    asyncio.run(run_ws())

def tail_file_for_new_lines(
    file_path: str,
    poll_interval_seconds: float = 0.25,
) -> None:
    """
    Continuously watch the given file and print each new line as it is appended.

    Behavior:
    - Starts watching from the current end-of-file (does not emit historical lines)
    - Detects file truncation and rotation by checking (device, inode) and size
    - Sleeps briefly between polls to avoid busy-waiting
    - Prints newly appended lines to stdout immediately
    - Optionally mirrors notifications to a local log file
    """

    current_identity = get_file_identity(file_path)
    file_handle = None
    session_started = False
    session_id = ''

    while True:
        try:
            # Reopen the file if needed (first run, rotation, or it did not exist before)
            new_identity = get_file_identity(file_path)
            need_reopen = (
                file_handle is None
                or new_identity is None
                or new_identity != current_identity
            )

            if need_reopen:
                # If file is missing, keep waiting
                if new_identity is None:
                    time.sleep(poll_interval_seconds)
                    continue

                # Close old handle if any, then open new and seek to end (start fresh)
                if file_handle is not None:
                    try:
                        file_handle.close()
                    except Exception:
                        pass

                file_handle = open_file_for_read(file_path)
                file_handle.seek(0, os.SEEK_END)
                current_identity = new_identity

            # Read any newly appended lines
            if file_handle:
                while True:
                    line = file_handle.readline()
                    if line == "":
                        break
                    line_stripped = line.rstrip("\n")
                    print(f"[line] {line_stripped}", flush=True)
                    session_id, session_started = process_line(line_stripped, session_id, session_started)

            time.sleep(poll_interval_seconds)

        except KeyboardInterrupt:
            print("[watch] interrupted by user", flush=True)
            break
        except Exception as unexpected_error:
            # Keep running in face of transient errors; report and pause briefly
            print(f"[watch] error: {unexpected_error}", flush=True)
            time.sleep(max(1.0, poll_interval_seconds))

    # Cleanup
    if file_handle is not None:
        try:
            file_handle.close()
        except Exception:
            pass


def main(argv: list[str]) -> int:
    file_to_watch = WATCH_PATH
    if len(argv) >= 2 and argv[1]:
        file_to_watch = argv[1]

    print(f"[watch] starting watcher for: {file_to_watch}", flush=True)
    tail_file_for_new_lines(file_to_watch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
