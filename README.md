# Project Desk

多项目管理 Web 应用，部署地址：

<https://imbingo.github.io/project-manage/>

## 已实现能力

- 多项目管理：截止日、一句话总结、TOP 风险、下一步计划
- 任务台账：父子任务、负责人、风险、排期、编辑和删除
- 甘特图：点击日期查看当日计划和实际
- 进度历史：每个任务按日期保存计划进度与实际进度
- 日报联动：日报写入当日计划/实际进度；延期必须填写原因
- 跨设备登录：Supabase Auth
- 密码找回：重置邮件显式回跳线上网站
- 公开展示：项目可启用只读分享链接，不暴露日报或内部备注
- 数据导出：项目完整 JSON 备份、Excel 可打开的任务 CSV
- 移动端视图：手机上优先显示项目摘要、未完成任务和填日报入口

## 重要：数据库升级必须执行一次

旧版本把每个用户的全部数据保存为单行 JSON，存在手机和电脑同时编辑时互相覆盖的风险。当前版本已改为以下关系表：

- `projects`
- `tasks`
- `task_progress_entries`
- `daily_logs`

在执行下面的 SQL 之前，线上站点仍可以用旧表继续读写已有项目，并显示“待升级：兼容模式”；公开只读链接和分表同步会在升级完成后启用。

请在 Supabase Dashboard 中执行一次数据库脚本：

1. 登录 [Supabase Dashboard](https://supabase.com/dashboard)。
2. 进入 `project-manage` 项目。
3. 点击左侧 `SQL Editor`，创建 `New query`。
4. 打开仓库中的 [supabase/schema.sql](./supabase/schema.sql)，完整复制内容。
5. 粘贴到 SQL Editor，点击 `Run`。

该脚本会保留旧的 `project_workspaces` 表。首次登录新版网站时，如果新表还没有项目，网页会自动把旧 JSON 数据导入新表。

## 云端配置

[config.js](./config.js) 已配置线上 Supabase 公共连接参数和确认邮件回跳地址：

```javascript
window.PROJECT_DESK_CONFIG = {
  supabaseUrl: "https://bgchvbxemcyolpqxikvz.supabase.co",
  supabaseAnonKey: "sb_publishable_...",
  siteUrl: "https://imbingo.github.io/project-manage/"
};
```

这里使用的是可公开的 `publishable key`。不要将 `service_role` key 或数据库密码写入前端仓库。

## 公开项目链接

在登录后的 `项目设置` 中勾选 `允许对外只读展示`，保存后点击 `复制公开链接`。

公开页面展示：

- 项目名称和一句话总结
- deadline、计划进度和实际进度
- TOP 风险与下一步计划
- 顶层任务及完成进度

公开页面不展示日报、延期原因、任务备注或子任务细节。

## 部署

仓库已配置 GitHub Pages 工作流：[.github/workflows/deploy-pages.yml](./.github/workflows/deploy-pages.yml)。

向 `main` 分支推送代码后，GitHub Actions 自动发布网站。若 Pages 尚未启用，在仓库 `Settings > Pages` 中将 `Source` 设置为 `GitHub Actions`。

## 本地运行

```powershell
python -m http.server 8080
```

访问 <http://localhost:8080/>。未登录时可使用本机预览模式检查界面，但本机预览数据不会跨设备同步。

## 文件结构

- [index.html](./index.html)：登录、内部工作台和公开展示页
- [styles.css](./styles.css)：桌面及移动端界面样式
- [app.js](./app.js)：登录、关系数据读写、迁移、公开页、导出和交互
- [config.js](./config.js)：线上公开配置
- [supabase/schema.sql](./supabase/schema.sql)：数据库升级和权限脚本
- [HANDOFF.md](./HANDOFF.md)：后续继续开发说明
