"""
Kanban Web Dashboard Backend
"""
import json
import os
import re
import subprocess
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Body
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


# ─── 可用模型列表 ─────────────────────────────────────────────────────────────

@app.get("/api/models")
def list_models():
    """返回配置中可用的大模型列表"""
    import yaml
    config_path = os.path.expanduser("~/.hermes/config.yaml")
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception:
        return [{"id": "MiniMax-M2.7-highspeed", "name": "MiniMax-M2.7-highspeed"}]

    models = []
    # 全局默认
    if config.get("model", {}).get("default"):
        mid = config["model"]["default"]
        models.append({"id": mid, "name": mid})
    # 各 provider 的 default_model
    for prov, prov_data in config.get("providers", {}).items():
        dm = prov_data.get("default_model")
        if dm and dm not in [m["id"] for m in models]:
            models.append({"id": dm, "name": f"{dm} ({prov})"})
    return models


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


@app.get("/api/tasks/pending")
def list_pending_tasks():
    """返回未完成的任务（供依赖下拉选择）"""
    data = run_kanban(["list", "--json"])
    pending = [t for t in data if t.get("status") not in ("done", "archived")]
    for t in pending:
        if "id" in t and "task_id" not in t:
            t["task_id"] = t.pop("id")
    return [{"task_id": t["task_id"], "title": t.get("title", ""), "status": t.get("status", "")} for t in pending]

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

    # 读取下一个 T 号
    counter_file = os.path.expanduser("~/.hermes/kanban_task_numbers.txt")
    try:
        with open(counter_file, "r") as f:
            lines = f.readlines()
        counter = 0
        for line in lines:
            if line.startswith("counter="):
                counter = int(line.split("=")[1].strip())
                break
        next_num = counter + 1
        t_number = f"T{next_num}"
    except Exception:
        t_number = "T?"

    # 构造成 kanban-task-workflow 格式的 body
    success_criteria_raw = data.get("success_criteria", "").strip()
    success_criteria_lines = [l.strip() for l in success_criteria_raw.split("\n") if l.strip()]

    body_parts = []
    body_parts.append(f"task_number: {t_number}")
    body_parts.append(f"task_title: {title}")
    body_parts.append(f"source: 用户直接创建")
    body_parts.append(f"notify_target: feishu:oc_fc755b43e929c9ccd5f88dee623818fb")
    body_parts.append(f"current_phase: phase0")
    body_parts.append(f"retreat_count: 0")
    body_parts.append(f"review_track: light")
    body_parts.append("")

    if data.get("body"):
        body_parts.append(data["body"].strip())
    if success_criteria_lines:
        body_parts.append("")
        body_parts.append("success_criteria:")
        for sc in success_criteria_lines:
            body_parts.append(f"  - {sc}")

    # 大模型选择 → 写入 body
    model = data.get("model", "").strip()
    if model:
        body_parts.append("")
        body_parts.append(f"model: {model}")

    full_body = "\n".join(body_parts)

    # 构建 hermes kanban create 命令参数
    args = [title, "--body", full_body]

    assignee = data.get("assignee")
    if assignee:
        args.extend(["--assignee", assignee])

    # 始终带上 kanban-task-workflow skill
    args.extend(["--skill", "kanban-task-workflow"])

    max_retries = data.get("max_retries")
    if max_retries is not None:
        args.extend(["--max-retries", str(max_retries)])

    priority = data.get("priority")
    if priority is not None:
        args.extend(["--priority", str(priority)])

    # 项目路径 → --workspace dir:<path>
    workspace = data.get("workspace", "").strip()
    if workspace:
        args.extend(["--workspace", f"dir:{workspace}"])
        body_parts.append(f"project_path: {workspace}")

    # 依赖 → --parent
    depends = data.get("depends", "").strip()
    if depends:
        args.extend(["--parent", depends])

    result = run_kanban(["create"] + args)

    # 更新 counter
    try:
        with open(counter_file, "r") as f:
            content = f.read()
        new_content = re.sub(r'(?<=counter=)\d+', str(next_num), content)
        if new_content != content:
            with open(counter_file, "w") as f:
                f.write(new_content)
    except Exception:
        pass

    # 解析 task_id（可能已在 result 中，也可能需从 message 提取）
    task_id = result.get("task_id")
    if not task_id:
        m = re.search(r"(t_[a-z0-9]+)", result.get("message", ""))
        task_id = m.group(1) if m else "unknown"

    return {"task_id": task_id, "status": "created", "task_number": t_number}


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


# ─── Worker详情 ─────────────────────────────────────────────────────────────

@app.get("/api/profile/{name}")
def get_profile(name: str):
    """返回 profile 详细信息"""
    result = subprocess.run([HERMES_BIN, "profile", "show", name],
                           capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=404, detail="Profile not found")

    lines = result.stdout.strip().split("\n")
    info = {"name": name}
    for line in lines:
        if ":" in line:
            key, val = line.split(":", 1)
            info[key.strip().lower().replace(" ", "_")] = val.strip()

    # SOUL.md 内容（default profile 在 ~/.hermes/SOUL.md，其他在 profiles/{name}/SOUL.md）
    if name == "default":
        soul_path = os.path.expanduser(f"~/.hermes/SOUL.md")
    else:
        soul_path = os.path.expanduser(f"~/.hermes/profiles/{name}/SOUL.md")
    info["soul_exists"] = os.path.exists(soul_path)
    info["soul_content"] = ""
    if info["soul_exists"]:
        with open(soul_path) as f:
            info["soul_content"] = f.read()

    return info


@app.put("/api/profile/{name}/soul")
def update_soul(name: str, data: dict = Body(...)):
    if name == "default":
        soul_path = os.path.expanduser("~/.hermes/SOUL.md")
    else:
        soul_path = os.path.expanduser(f"~/.hermes/profiles/{name}/SOUL.md")
    with open(soul_path, "w") as f:
        f.write(data.get("content", ""))
    return {"ok": True, "path": soul_path}


@app.post("/api/profile/{name}/start")
def start_gateway(name: str):
    r = subprocess.run([HERMES_BIN, "gateway", "start", "-p", name],
                      capture_output=True, text=True)
    return {"ok": r.returncode == 0, "output": r.stdout + r.stderr}


@app.post("/api/profile/{name}/stop")
def stop_gateway(name: str):
    r = subprocess.run([HERMES_BIN, "gateway", "stop", "-p", name],
                      capture_output=True, text=True)
    return {"ok": r.returncode == 0, "output": r.stdout + r.stderr}


@app.post("/api/profile/{name}/rename")
def rename_profile(name: str, data: dict = Body(...)):
    new_name = data.get("new_name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="new_name required")
    r = subprocess.run([HERMES_BIN, "profile", "rename", name, new_name],
                      capture_output=True, text=True)
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr)
    return {"ok": True}


# ─── 统计概览 ──────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    data = run_kanban(["stats", "--json"])
    return data


# ─── 运行历史 ──────────────────────────────────────────────────────────────

@app.get("/api/task/{task_id}/runs")
def get_task_runs(task_id: str):
    data = run_kanban(["runs", task_id, "--json"])
    return data


# ─── Worker 日志 ────────────────────────────────────────────────────────────

@app.get("/api/task/{task_id}/log")
def get_task_log(task_id: str):
    cmd = [HERMES_BIN, "kanban", "log", task_id]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.expanduser("~"))
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    return {"log": result.stdout}


# ─── 任务评论 ────────────────────────────────────────────────────────────────

@app.post("/api/task/{task_id}/comment")
def add_comment(task_id: str, data: dict = {}):
    text = data.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="评论内容不能为空")
    run_kanban(["comment", task_id, text])
    return {"ok": True}


# ─── 归档任务 ────────────────────────────────────────────────────────────────

@app.post("/api/task/{task_id}/archive")
def archive_task(task_id: str):
    run_kanban(["archive", task_id])
    return {"ok": True}


# ─── 父子依赖 ────────────────────────────────────────────────────────────────

@app.post("/api/links")
def manage_link(data: dict = {}):
    action = data.get("action")  # "link" or "unlink"
    parent_id = data.get("parent_id")
    child_id = data.get("child_id")
    if action not in ("link", "unlink") or not parent_id or not child_id:
        raise HTTPException(status_code=400, detail="需要 action (link/unlink), parent_id, child_id")
    run_kanban([action, parent_id, child_id])
    return {"ok": True}


# ─── 启动 ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=50000)
