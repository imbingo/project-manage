# Project Desk Local

本目录是 Project Desk 的本地单机 Python 桌面版。它不需要登录、不连接 Supabase，数据保存在本机 JSON 文件中，适合公司电脑离线使用或后续打包成 Windows exe。

## 运行

在 PyCharm 中打开仓库后，选择 `local_desktop/main.py` 运行。首次运行前安装依赖：

```powershell
cd local_desktop
python -m pip install -r requirements.txt
python main.py
```

默认数据位置：

```text
%APPDATA%/ProjectDeskLocal/workspace.json
```

每次保存会在：

```text
%APPDATA%/ProjectDeskLocal/backups/
```

生成一份备份。

## 当前功能

- 本地单机运行，不需要登录。
- 首页布局参考网页版：topbar、deadline/进度指标卡、摘要/风险/下一步卡片、任务台账、甘特图、日报记录。
- 导入网页版 JSON，兼容：
  - workspace JSON
  - 单项目 JSON
  - Supabase legacy `payload`
  - `data/workspace/payload` 包裹结构
  - `project-desk-local-v5/v4`、`project-desk-v3` 旧 localStorage 导出结构
- 自动归一 snake_case/camelCase 字段，例如 `top_risk/topRisk`、`parent_id/parentId`、`start_date/startDate`。
- 导出完整 JSON 备份。
- 导出任务 CSV，Excel 可打开，UTF-8 BOM。
- 导出 `.xlsx` 项目管理表，包含项目概览、任务台账、日报记录和甘特图。
- “打开数据目录”可直接打开本地数据文件夹。

## 打包 exe

```powershell
cd local_desktop
.\build_exe.bat
```

输出：

```text
local_desktop/dist/ProjectDeskLocal/ProjectDeskLocal.exe
```

## 与网页版差异

- 本地版第一版重点是离线查看、导入、备份和 Excel 输出。
- 暂未实现完整新增/编辑弹窗；复杂编辑仍建议先在网页版完成，再导入本地版。
- 不支持 Supabase 云同步、公开分享链接、小程序端能力。

## 后续建议

- 补齐项目/任务/日报编辑弹窗。
- 增加导入预览时的“合并/覆盖”选择。
- 增加表格内联编辑和自动保存。
- 增加更完整的甘特图交互，例如点击日期查看当日日报。
