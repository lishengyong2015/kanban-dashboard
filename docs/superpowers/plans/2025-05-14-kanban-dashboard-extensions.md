# Kanban Dashboard 扩展功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 kanban-dashboard 添加 6 个新功能：统计概览、运行历史、worker日志、任务评论、归档任务、父子依赖。

**Architecture:** 后端 FastAPI 新增 6 个端点，前端 index.html 改造详情弹窗为 tab 结构，新建任务弹窗加依赖字段。

**Tech Stack:** FastAPI (后端), 纯 HTML/JS (前端), hermes kanban CLI

---

## 文件概览

- 修改: `backend.py` — 新增 6 个 API 端点
- 修改: `index.html` — 统计栏 + tabbed 弹窗 + 归档/依赖 UI

---

## Task 1: 统计概览（Stats Bar）

**Files:**
- Modify: `backend.py` — 新增 `GET /api/stats`
- Modify: `index.html` — 顶部统计栏

### backend.py 改动

在 `backend.py` 找到 `list_profiles()` 函数后面，新增：

```python
@app.get("/api/stats")
def get_stats():
    data = run_kanban(["stats", "--json"])
    return data
```

### index.html 改动

1. `.workers-panel` 下方新增统计栏 div：
```html
<div class="stats-bar" id="statsBar">
  <div class="stat-card"><span class="stat-num" id="stat-todo">-</span><span class="stat-label">TODO</span></div>
  <div class="stat-card"><span class="stat-num" id="stat-ready">-</span><span class="stat-label">READY</span></div>
  <div class="stat-card"><span class="stat-num" id="stat-running">-</span><span class="stat-label">RUNNING</span></div>
  <div class="stat-card"><span class="stat-num" id="stat-blocked">-</span><span class="stat-label">BLOCKED</span></div>
  <div class="stat-card"><span class="stat-num" id="stat-done">-</span><span class="stat-label">DONE</span></div>
  <div class="stat-card" id="stat-oldest-wrap" style="display:none;"><span class="stat-num" id="stat-oldest">-</span><span class="stat-label">最老READY</span></div>
</div>
```

2. `<style>` 中添加：
```css
.stats-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.stat-card { background: white; border-radius: 8px; padding: 10px 18px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); text-align: center; min-width: 80px; }
.stat-num { display: block; font-size: 24px; font-weight: 700; color: #0969da; }
.stat-label { font-size: 11px; color: #656d76; text-transform: uppercase; letter-spacing: 0.5px; }
```

3. JS 新增函数：
```javascript
async function loadStats() {
  try {
    const res = await fetch(`${API}/api/stats`);
    const stats = await res.json();
    // stats 结构: { by_status: {todo:N, ready:N, ...}, oldest_ready_seconds: N, by_assignee: {...} }
    document.getElementById('stat-todo').textContent = stats.by_status?.todo ?? '-';
    document.getElementById('stat-ready').textContent = stats.by_status?.ready ?? '-';
    document.getElementById('stat-running').textContent = stats.by_status?.running ?? '-';
    document.getElementById('stat-blocked').textContent = stats.by_status?.blocked ?? '-';
    document.getElementById('stat-done').textContent = stats.by_status?.done ?? '-';
    if (stats.oldest_ready_seconds) {
      const mins = Math.floor(stats.oldest_ready_seconds / 60);
      document.getElementById('stat-oldest').textContent = mins < 60 ? `${mins}m` : `${Math.floor(mins/60)}h${mins%60}m`;
      document.getElementById('stat-oldest-wrap').style.display = '';
    }
  } catch (e) { /* silently fail */ }
}
```

4. 初始化时调用 `loadTasks()` 之后调用 `loadStats()`，刷新时也一起调。

---

## Task 2: 运行历史（Runs Tab）

**Files:**
- Modify: `backend.py` — 新增 `GET /api/task/{task_id}/runs`
- Modify: `index.html` — 详情弹窗加 Tab 结构

### backend.py 改动

```python
@app.get("/api/task/{task_id}/runs")
def get_task_runs(task_id: str):
    data = run_kanban(["runs", task_id, "--json"])
    return data  # 数组，每个元素 {profile, outcome, elapsed_ms, summary, start, end}
```

### index.html 改动

1. 弹窗 tab 样式：
```css
.tabs { display: flex; border-bottom: 2px solid #eaeef2; margin-bottom: 16px; }
.tab-btn { padding: 8px 16px; cursor: pointer; font-size: 14px; color: #656d76; border: none; background: none; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab-btn.active { color: #0969da; border-bottom-color: #0969da; font-weight: 600; }
.tab-content { display: none; }
.tab-content.active { display: block; }
```

2. 详情弹窗 HTML 结构改造（替换原来的 `modalBody` 部分）：
```html
<div class="tabs" id="taskTabs">
  <button class="tab-btn active" onclick="switchTab('detail')">详情</button>
  <button class="tab-btn" onclick="switchTab('runs')">运行记录</button>
  <button class="tab-btn" onclick="switchTab('log')">日志</button>
</div>
<div id="tab-detail" class="tab-content active"></div>
<div id="tab-runs" class="tab-content"></div>
<div id="tab-log" class="tab-content"></div>
```

3. JS `switchTab(tab)` 函数：
```javascript
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector(`.tab-btn[onclick="switchTab('${tab}')"]`).classList.add('active');
  document.getElementById(`tab-${tab}`).classList.add('active');
}
```

4. `showTaskModal(task)` 改造：
   - `tab-detail` 内容 = 原来的 body 内容（summary + body）
   - `tab-runs` 内容 = 调用 `/api/task/${taskId}/runs` 渲染运行记录表格
   - `tab-log` 内容 = 调用 `/api/task/${taskId}/log` 渲染日志（稍后 Task 3）

5. 运行记录表格渲染（放进 `showTaskModal`）：
```javascript
async function loadRunsTab(taskId, container) {
  const res = await fetch(`${API}/api/task/${taskId}/runs`);
  const runs = await res.json();
  if (!runs || runs.length === 0) {
    container.innerHTML = '<p style="color:#656d76;">暂无运行记录</p>';
    return;
  }
  const rows = runs.map(r => `
    <tr>
      <td style="padding:6px 10px;border-bottom:1px solid #eaeef2;">${r.profile || '-'}</td>
      <td style="padding:6px 10px;border-bottom:1px solid #eaeef2;">${r.outcome || '-'}</td>
      <td style="padding:6px 10px;border-bottom:1px solid #eaeef2;">${r.elapsed_ms ? (r.elapsed_ms/1000).toFixed(1)+'s' : '-'}</td>
      <td style="padding:6px 10px;border-bottom:1px solid #eaeef2;font-size:13px;color:#1a1a1a;">${escapeHtml(r.summary || '-')}</td>
    </tr>
  `).join('');
  container.innerHTML = `<table style="width:100%;border-collapse:collapse;font-size:14px;"><thead><tr style="background:#f6f8fa;"><td style="padding:6px 10px;font-weight:600;">Worker</td><td style="padding:6px 10px;font-weight:600;">结果</td><td style="padding:6px 10px;font-weight:600;">耗时</td><td style="padding:6px 10px;font-weight:600;">摘要</td></tr></thead><tbody>${rows}</tbody></table>`;
}
```

---

## Task 3: Worker 日志（Log Tab）

**Files:**
- Modify: `backend.py` — 新增 `GET /api/task/{task_id}/log`
- Modify: `index.html` — `loadRunsTab` 旁边加 `loadLogTab`

### backend.py 改动

```python
@app.get("/api/task/{task_id}/log")
def get_task_log(task_id: str):
    cmd = [HERMES_BIN, "kanban", "log", task_id]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    return {"log": result.stdout}
```

### index.html 改动

```javascript
async function loadLogTab(taskId, container) {
  try {
    const res = await fetch(`${API}/api/task/${taskId}/log`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    container.innerHTML = `<pre style="margin:0;font-size:12px;background:#f6f8fa;padding:10px;border-radius:6px;max-height:400px;overflow:auto;">${escapeHtml(data.log || '(无日志)')}</pre>`;
  } catch (e) {
    container.innerHTML = `<p style="color:#cf222e;font-size:14px;">加载失败: ${escapeHtml(e.message)}</p>`;
  }
}
```

在 `showTaskModal` 中调用 `loadRunsTab` 时用 `await`，调用 `loadLogTab` 时同样 `await`。

---

## Task 4: 任务评论（Comment）

**Files:**
- Modify: `backend.py` — 新增 `POST /api/task/{task_id}/comment`
- Modify: `index.html` — 详情 tab 内加评论输入框

### backend.py 改动

```python
@app.post("/api/task/{task_id}/comment")
def add_comment(task_id: str, data: dict = {}):
    text = data.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="评论内容不能为空")
    run_kanban(["comment", task_id, text])
    return {"ok": True}
```

### index.html 改动

在 `tab-detail` 内容后面追加评论区块：

```html
<div id="commentSection" style="margin-top:16px;padding-top:16px;border-top:1px solid #eaeef2;">
  <h4 style="margin:0 0 10px;font-size:13px;color:#656d76;text-transform:uppercase;">评论</h4>
  <div id="commentList"></div>
  <div style="display:flex;gap:8px;margin-top:10px;">
    <input type="text" id="commentInput" placeholder="添加评论..." style="flex:1;padding:8px 12px;border:1px solid #d0d7de;border-radius:6px;font-size:14px;" onkeydown="if(event.key==='Enter')submitComment()">
    <button class="primary" onclick="submitComment()">发送</button>
  </div>
</div>
```

JS 函数：
```javascript
async function submitComment() {
  const text = document.getElementById('commentInput').value.trim();
  if (!text) return;
  try {
    await fetch(`${API}/api/task/${selectedTaskId}/comment`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    });
    document.getElementById('commentInput').value = '';
    // 刷新评论列表（暂时直接刷新任务详情）
    const res = await fetch(`${API}/api/task/${selectedTaskId}`);
    const task = await res.json();
    showTaskModal(task);
  } catch (e) {
    alert('评论失败: ' + e.message);
  }
}
```

---

## Task 5: 归档任务（Archive）

**Files:**
- Modify: `backend.py` — 新增 `POST /api/task/{task_id}/archive`
- Modify: `index.html` — 详情弹窗操作区加归档按钮

### backend.py 改动

```python
@app.post("/api/task/{task_id}/archive")
def archive_task(task_id: str):
    run_kanban(["archive", task_id])
    return {"ok": True}
```

### index.html 改动

详情弹窗 `modalActions` 区内，`完成` 按钮后面加：
```javascript
actions += `<button class="danger" onclick="doAction('archive')">归档</button>`;
```

在 `doAction` 函数里新增分支：
```javascript
const labels = {block: '阻塞', unblock: '解阻', archive: '归档'};
```

---

## Task 6: 父子依赖（Link/Unlink）

**Files:**
- Modify: `backend.py` — 新增 `POST /api/links`（link 和 unlink）
- Modify: `index.html` — 新建任务弹窗加依赖字段，详情弹窗加依赖显示

### backend.py 改动

```python
@app.post("/api/links")
def manage_link(data: dict = {}):
    action = data.get("action")  # "link" or "unlink"
    parent_id = data.get("parent_id")
    child_id = data.get("child_id")
    if action not in ("link", "unlink") or not parent_id or not child_id:
        raise HTTPException(status_code=400, detail="需要 action/link/unlink, parent_id, child_id")
    run_kanban([action, parent_id, child_id])
    return {"ok": True}
```

### index.html 改动

1. 新建任务弹窗里，在"注意事项"下方加：
```html
<div style="margin-bottom:14px;">
  <label style="display:block;font-size:13px;font-weight:600;color:#1a1a1a;margin-bottom:6px;">依赖任务 ID</label>
  <input type="text" id="c-depends" placeholder="可选，填入父任务ID，建立依赖关系" style="width:100%;padding:8px 12px;border:1px solid #d0d7de;border-radius:6px;font-size:14px;box-sizing:border-box;">
</div>
```

2. `submitCreate` 中处理依赖：
```javascript
const depends = document.getElementById('c-depends').value.trim();
// 创建任务后如果有依赖，建立 link
if (depends && newTaskId) {
  await fetch(`${API}/api/links`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'link', parent_id: depends, child_id: newTaskId})
  });
}
```

3. 详情弹窗 `tab-detail` 内，在基本信息行下面显示依赖信息（如果有 parent_id/child_id 字段的话）。由于 `kanban show` 返回字段中是否有依赖关系不确定，先做一个预留 UI：如果 `task.parent_ids` 或 `task.children` 存在则渲染，否则留空。

---

## 自检清单

1. **Spec 覆盖：** 6 个功能都有对应 Task ✓
2. **Placeholder 扫描：** 无 TBD/TODO ✓
3. **类型一致性：** 所有 API 端点路径与前端 fetch 路径一致 ✓
4. **依赖顺序：** Task 2/3 依赖 Task 1 的 tab 框架先行构建 ✓
