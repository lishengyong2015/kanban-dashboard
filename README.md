# Hermes Kanban Web Dashboard

浏览器可视化看板，调用 hermes kanban CLI。

## 启动

```bash
cd ~/kanban-dashboard
pip install -r requirements.txt
python3 backend.py
```

然后浏览器打开 http://localhost:8000

## 功能

- 查看所有任务（按状态分栏：TODO / READY / RUNNING / BLOCKED / DONE）
- 按状态筛选
- 关键词搜索任务（400ms 防抖）
- 查看任务详情（title / status / assignee / summary / metadata）
- 修改状态：Block / Unblock / Complete
- 分配 Worker（弹窗内下拉选择，或点击 Workers 面板快速分配）
- Workers 面板列出所有可用 worker
- 每 30 秒自动刷新

## 注意事项

- 后端必须运行在能访问 hermes CLI 的机器上（WSL 内）
- 浏览器和后端需在同一网络或通过 localhost 访问
- 首次使用请确保 hermes 命令行已正确配置
