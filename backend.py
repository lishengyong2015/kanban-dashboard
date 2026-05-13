"""
Kanban Web Dashboard Backend
"""
import json
import os
import subprocess
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

app = FastAPI(title="Kanban Web Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HERMES_BIN = os.environ.get("HERMES_BIN", "/home/lsy/.local/bin/hermes")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_kanban(args: list[str]) -> dict:
    """执行 hermes kanban CLI，返回 JSON。命令成功但无 JSON 输出时返回 ok=True。"""
    cmd = [HERMES_BIN, "kanban"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.expanduser("~"))
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        # 命令成功（exit 0）但无 JSON 输出，说明操作已完成
        return {"ok": True, "message": result.stdout.strip()}


# ─── 静态页面 ───────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


# ─── 任务列表 ────────────────────────────────────────────────────────────────

@app.get("/api/tasks")
def list_tasks(status: Optional[str] = None, search: Optional[str] = None):
    args = ["list", "--json"]
    if status:
        args.extend(["--status", status])
    data = run_kanban(args)

    # 统一 id → task_id
    for t in data:
        if "id" in t and "task_id" not in t:
            t["task_id"] = t.pop("id")

    # 内存搜索
    if search:
        kw = search.lower()
        data = [t for t in data if kw in t.get("title", "").lower()]

    return data


# ─── 任务详情 ────────────────────────────────────────────────────────────────

@app.get("/api/task/{task_id}")
def get_task(task_id: str):
    data = run_kanban(["show", task_id, "--json"])
    task = data.get("task", {})
    task["task_id"] = task.pop("id", task_id)
    if data.get("latest_summary"):
        task["summary"] = data["latest_summary"]
    return task


# ─── 任务操作 ────────────────────────────────────────────────────────────────

@app.post("/api/task/{task_id}/complete")
def complete_task(task_id: str, data: dict = {}):
    result = data.get("result", "")
    if result:
        run_kanban(["complete", task_id, "--result", result])
    else:
        run_kanban(["complete", task_id])
    return {"ok": True}


@app.post("/api/task/{task_id}/block")
def block_task(task_id: str):
    run_kanban(["block", task_id])
    return {"ok": True}


@app.post("/api/task/{task_id}/unblock")
def unblock_task(task_id: str):
    run_kanban(["unblock", task_id])
    return {"ok": True}


@app.post("/api/task/{task_id}/assign")
def assign_task(task_id: str, profile: str = Query(...)):
    run_kanban(["assign", task_id, profile])
    return {"ok": True}


# ─── 创建任务 ────────────────────────────────────────────────────────────────

@app.post("/api/tasks")
def create_task(data: dict):
    title = data.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")

    args = [title]

    body_parts = []
    if data.get("body"):
        body_parts.append(data["body"].strip())
    if data.get("acceptance_criteria"):
        body_parts.append("\n\n## 接收准则\n" + data["acceptance_criteria"].strip())
    default_notes = "注意GBK文件不要乱码"
    notes = data.get("notes", default_notes).strip()
    if notes and notes != default_notes:
        body_parts.append("\n\n---\n" + notes)
    elif body_parts or not notes:
        body_parts.append("\n\n---\n" + default_notes)

    if body_parts:
        args.extend(["--body", "\n".join(body_parts)])

    assignee = data.get("assignee")
    if assignee:
        args.extend(["--assignee", assignee])

    skills = data.get("skills")
    if skills:
        for s in skills:
            args.extend(["--skill", s])

    max_retries = data.get("max_retries")
    if max_retries is not None:
        args.extend(["--max-retries", str(max_retries)])

    priority = data.get("priority")
    if priority is not None:
        args.extend(["--priority", str(priority)])

    result = run_kanban(["create"] + args)
    # create 成功返回纯文本，格式: Created task t_xxxx
    if result.get("ok") and "task_id" not in result:
        import re
        m = re.search(r"(t_[a-z0-9]+)", result.get("message", ""))
        task_id = m.group(1) if m else "unknown"
        return {"task_id": task_id, "status": "created"}

    return result


# ─── Worker列表 ─────────────────────────────────────────────────────────────

@app.get("/api/profiles")
def list_profiles():
    cmd = [HERMES_BIN, "profile", "list"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.strip().split("\n")
    profiles = []
    for line in lines[2:]:
        parts = [p.strip() for p in line.split() if p.strip()]
        if len(parts) >= 2:
            profiles.append(parts[0].lstrip("◆"))
    return profiles


# ─── 启动 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
