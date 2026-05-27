# Project Desk

简洁的项目管理 Web 应用，支持多项目、父子任务、甘特图、日报回写任务进度，以及跨电脑云端同步。

## 当前功能

- 账号登录与云端数据同步
- 多项目切换，每个项目维护截止日、一句话总结、TOP 风险和下一步计划
- 任务台账：父子任务、负责人、计划进度、实际进度、完成日期
- 甘特图：按天查看任务排期，点击日期查看日报
- 日报：绑定任务、回写实际进度、延期原因必填
- 首次登录时自动导入当前浏览器已有的本机数据

## 技术方案

- 前端：静态 HTML / CSS / JavaScript
- 登录与数据库：Supabase Auth + PostgreSQL
- 权限：Supabase Row Level Security，每个账号只能访问自己的工作区
- 部署：GitHub Pages、Netlify 或其他静态托管均可

当前数据库按“每个账号一份 JSON 工作区”保存。这能最快满足单人跨电脑同步。多人协作、变更历史和审批流需要后续改成关系表与权限模型。

## 云端配置

1. 在 [Supabase](https://supabase.com/) 创建一个项目。
2. 打开 Supabase 项目的 `SQL Editor`，执行 [supabase/schema.sql](./supabase/schema.sql)。
3. 在 Supabase 项目的 `Project Settings > API` 复制 `Project URL` 和 `anon` 或 `publishable` key。
4. 编辑 [config.js](./config.js)：

```javascript
window.PROJECT_DESK_CONFIG = {
  supabaseUrl: "https://YOUR_PROJECT.supabase.co",
  supabaseAnonKey: "YOUR_PUBLIC_ANON_OR_PUBLISHABLE_KEY"
};
```

`anon` / `publishable` key 会在网页中公开，这是 Supabase 的正常用法；权限依赖数据库的 RLS 策略。不要把 `service_role` key 写入前端。

## 本地运行

配置完成后，可以直接打开 [index.html](./index.html)。也可以在当前目录启动静态服务器：

```powershell
python -m http.server 8080
```

然后访问 `http://localhost:8080`。

## 在不同电脑使用

1. 将本目录发布到一个可访问的网址，例如 GitHub Pages。
2. 在第一台电脑注册账号并录入数据。
3. 在其他电脑打开同一个网址，用同一账号登录。

所有修改会保存到 Supabase，页面顶部的同步状态会显示 `保存中...` 或 `云端已同步`。

## 发布到 GitHub Pages

本仓库已包含 `.github/workflows/deploy-pages.yml`，推送到 `main` 分支会触发静态站点发布。

首次启用时，在仓库 `Settings > Pages > Build and deployment > Source` 选择 `GitHub Actions`。部署后的预期访问地址为：

```text
https://imbingo.github.io/project-manage/
```

当前目标仓库为私有仓库。GitHub Pages 从私有仓库发布需要支持该功能的 GitHub 套餐，并且发布出来的网站通常是公开可访问的；项目数据仍由登录与 Supabase 行级权限保护。

## 文件说明

- [index.html](./index.html)：页面结构及登录入口
- [styles.css](./styles.css)：界面样式
- [app.js](./app.js)：项目管理交互、登录及云端同步
- [config.js](./config.js)：Supabase 公共连接配置
- [supabase/schema.sql](./supabase/schema.sql)：数据库表和权限策略
