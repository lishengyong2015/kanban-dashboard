# Worker 信息查看与修改 — 实现计划

**Goal:** 点击 Workers 面板的标签 → 弹窗查看 Worker 详情、编辑 SOUL.md、启停 Gateway

**Architecture:** 后端新增 5 个 REST 接口，前端新增 Worker 详情弹窗，复用现有弹窗组件

---

## 文件结构

- `backend.py` — 新增 5 个接口
- `index.html` — 新增 Worker 弹窗 HTML/CSS/JS

---

## Task 1: 后端 — GET /api/profile/{name}

**文件:** `backend.py`（现有 Worker 列表接口下方）

```python
@app.get("/api/profile/{name}")
def get_profile(name: str):
    """返回 profile 详细信息"""
    # hermes profile show {name}
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

    # 额外：SOUL.md 内容
    soul_path = os.path.expanduser(f"~/.hermes/profiles/{name}/SOUL.md")
    info["soul_exists"] = os.path.exists(soul_path)
    info["soul_content"] = ""
    if info["soul_exists"]:
        with open(soul_path) as f:
            info["soul_content"] = f.read()

    return info
```

- [ ] 写接口，验证：`curl http://localhost:50000/api/profile/default`

---

## Task 2: 后端 — PUT /api/profile/{name}/soul

**文件:** `backend.py`（Task 1 下方）

```python
@app.put("/api/profile/{name}/soul")
def update_soul(name: str, data: dict = Body(...)):
    soul_path = os.path.expanduser(f"~/.hermes/profiles/{name}/SOUL.md")
    with open(soul_path, "w") as f:
        f.write(data.get("content", ""))
    return {"ok": True, "path": soul_path}
```

- [ ] 写接口，验证：读取 + 写入 + 再读取确认

---

## Task 3: 后端 — 启停和重命名

**文件:** `backend.py`（Task 2 下方）

```python
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
```

- [ ] 验证 start/stop（可能需要先确认 gateway 命令参数）

---

## Task 4: 前端 — Worker 详情弹窗 HTML + CSS

**文件:** `index.html`

**弹窗 HTML**（放在现有 modal 后面）:
```html
<div id="workerModal">
  <div class="modal-content" style="width:540px;">
    <div class="modal-header">
      <div>
        <div class="modal-id" id="wmName"></div>
        <span class="badge" id="wmStatus"></span>
      </div>
      <button class="close-btn" onclick="closeWorkerModal()">×</button>
    </div>
    <div class="modal-info" style="margin-bottom:12px;">
      <div class="modal-info-item">模型: <strong id="wmModel">-</strong></div>
      <div class="modal-info-item">Skills: <strong id="wmSkills">-</strong></div>
      <div class="modal-info-item">.env: <strong id="wmEnv">-</strong></div>
      <div class="modal-info-item">SOUL.md: <strong id="wmSoulExists">-</strong></div>
    </div>
    <div class="modal-section">
      <h4>SOUL.md <span style="font-weight:normal;font-size:11px;color:#656d76;">（可编辑）</span></h4>
      <textarea id="wmSoulContent" rows="12"
        style="width:100%;font-family:monospace;font-size:13px;
               border:1px solid #d0d7de;border-radius:6px;padding:10px;
               resize:vertical;box-sizing:border-box;"></textarea>
    </div>
    <div class="modal-actions">
      <button class="primary" onclick="saveSoul()">保存SOUL.md</button>
      <button id="btnStartGateway" class="primary" onclick="startGateway()"
        style="display:none;">启动Gateway</button>
      <button id="btnStopGateway" class="danger" onclick="stopGateway()"
        style="display:none;">停止Gateway</button>
      <button onclick="renameProfile()">重命名</button>
    </div>
  </div>
</div>
```

**CSS**（`<style>` 区块添加）:
```css
#workerModal { display:none; position:fixed; top:0; left:0; right:0; bottom:0;
               background:rgba(0,0,0,0.5); align-items:center; justify-content:center;
               z-index:1002; }
#workerModal.active { display:flex; }
```

- [ ] 添加 HTML 和 CSS

---

## Task 5: 前端 — Worker 弹窗 JS 逻辑

**文件:** `index.html`（`</script>` 前面添加）

```javascript
let currentWorker = null;

function openWorkerModal(name) {
  currentWorker = name;
  document.getElementById('workerModal').classList.add('active');
  loadWorkerDetail(name);
}

function closeWorkerModal() {
  document.getElementById('workerModal').classList.remove('active');
  currentWorker = null;
}

async function loadWorkerDetail(name) {
  const res = await fetch(`${API}/api/profile/${name}`);
  const d = await res.json();
  document.getElementById('wmName').textContent = d.name;
  const status = d.gateway || 'unknown';
  document.getElementById('wmStatus').textContent = status;
  document.getElementById('wmStatus').className = `badge badge-${status === 'running' ? 'done' : 'blocked'}`;
  document.getElementById('wmModel').textContent = d.model || '-';
  document.getElementById('wmSkills').textContent = d.skills || '-';
  document.getElementById('wmEnv').textContent = d.env === 'exists' ? '存在 ✓' : '不存在';
  document.getElementById('wmSoulExists').textContent = d.soul_exists ? '存在 ✓' : '不存在';
  document.getElementById('wmSoulContent').value = d.soul_content || '';
  document.getElementById('btnStartGateway').style.display = status !== 'running' ? '' : 'none';
  document.getElementById('btnStopGateway').style.display = status === 'running' ? '' : 'none';
}

async function saveSoul() {
  const content = document.getElementById('wmSoulContent').value;
  await fetch(`${API}/api/profile/${currentWorker}/soul`, {
    method: 'PUT', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({content})
  });
  alert('SOUL.md 已保存');
}

async function startGateway() {
  await fetch(`${API}/api/profile/${currentWorker}/start`, {method:'POST'});
  loadWorkerDetail(currentWorker);
}
async function stopGateway() {
  await fetch(`${API}/api/profile/${currentWorker}/stop`, {method:'POST'});
  loadWorkerDetail(currentWorker);
}
async function renameProfile() {
  const newName = prompt('新名称:');
  if (!newName) return;
  const r = await fetch(`${API}/api/profile/${currentWorker}/rename`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({new_name: newName})
  });
  if (r.ok) { closeWorkerModal(); loadProfiles(); }
  else { alert('重命名失败: ' + (await r.text()).detail); }
}
```

- [ ] Workers 标签点击改为 `onclick="openWorkerModal('${p}')"`
- [ ] 验证弹窗打开、数据加载、保存 SOUL.md

---

## Task 6: 提交
