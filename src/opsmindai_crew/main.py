#!/usr/bin/env python
import sys
import os
import asyncio
from functools import lru_cache
from threading import Lock
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from opsmindai_crew.crew import OpsmindaiCrewCrew

app = FastAPI(title="Incident Alert Webhook & Crew Runner")

crew_lock = Lock()

@lru_cache
def get_crew():
    return OpsmindaiCrewCrew().crew()

def run_crew(inputs: Dict[str, Any]):
    with crew_lock:
        return get_crew().kickoff(inputs=inputs)

# Expect log_content as a string
class WebhookPayload(BaseModel):
    log_content: str

class RunRequest(BaseModel):
    log_content: str

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/webhook/incident-alert")
async def handle_incident_alert(
    payload: WebhookPayload, background_tasks: BackgroundTasks
):
    def crew_job():
        try:
            run_crew({"log_content": payload.log_content})
        except Exception as e:
            # Optionally log the error or handle it as needed
            import logging
            logging.exception(f"Background incident automation failed: {e}")

    background_tasks.add_task(crew_job)
    return {
        "status": "accepted",
        "message": "Incident automation triggered in the background"
    }

@app.post("/run")
async def run_endpoint(req: RunRequest):
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, lambda: run_crew({"log_content": req.log_content})
        )
        return {"status": "ok", "result": str(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----- CLI helper functions -----
def cli_run():
    print(run_crew({'log_content': 'sample_value'}))

def cli_train():
    inputs = {'log_content': 'sample_value'}
    n_iterations = int(sys.argv[2])
    filename = sys.argv[3]
    with crew_lock:
        get_crew().train(n_iterations=n_iterations, filename=filename, inputs=inputs)

def cli_replay():
    task_id = sys.argv[2]
    with crew_lock:
        get_crew().replay(task_id=task_id)

def cli_test():
    inputs = {'log_content': 'sample_value'}
    n_iterations = int(sys.argv[2])
    model_name = sys.argv[3]
    with crew_lock:
        get_crew().test(n_iterations=n_iterations, openai_model_name=model_name, inputs=inputs)

def print_usage():
    print("Usage:")
    print("  python -m opsmindai_crew.main serve                # Start API server")
    print("  python -m opsmindai_crew.main run                  # Run crew once")
    print("  python -m opsmindai_crew.main train <n> <file>     # Train")
    print("  python -m opsmindai_crew.main replay <task_id>     # Replay")
    print("  python -m opsmindai_crew.main test <n> <model>     # Test")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]
    if command == "serve":
        port = int(os.getenv("PORT", "8080"))
        # Pass the app object directly to avoid module path ambiguity
        uvicorn.run(app, host="0.0.0.0", port=port, reload=bool(os.getenv("RELOAD") == "1"))
    elif command == "run":
        cli_run()
    elif command == "train":
        if len(sys.argv) < 4:
            print("train requires: n_iterations filename")
            sys.exit(1)
        cli_train()
    elif command == "replay":
        if len(sys.argv) < 3:
            print("replay requires: task_id")
            sys.exit(1)
        cli_replay()
    elif command == "test":
        if len(sys.argv) < 4:
            print("test requires: n_iterations model_name")
            sys.exit(1)
        cli_test()
    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)