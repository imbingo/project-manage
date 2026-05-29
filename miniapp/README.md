# Project Desk 微信小程序 MVP

该目录是 Project Desk 的原生微信小程序版本，和网页版共用 Supabase 后端表：

- `projects`
- `tasks`
- `task_progress_entries`
- `daily_logs`

`project_workspaces` 仅作为网页版 legacy 兼容来源，小程序不把它作为主存储。

## 如何打开

1. 安装并打开微信开发者工具。
2. 选择 `导入项目`。
3. 项目目录选择仓库中的 `miniapp/`。
4. AppID 可以先使用测试号或你自己的小程序 AppID。
5. 导入后执行一次编译。

## 配置 Supabase

复制配置模板：

```text
miniapp/config.example.js -> miniapp/config.js
```

然后填写：

```javascript
const CONFIG = {
  supabaseUrl: "https://你的项目.supabase.co",
  supabaseAnonKey: "你的 publishable 或 anon key"
};

module.exports = CONFIG;
```

`miniapp/config.js` 已加入 `.gitignore`，不要提交真实配置。小程序端只能使用 Supabase 公开 publishable/anon key，不能写入 `service_role` key、数据库密码或 GitHub token。

## 微信后台 request 合法域名

在微信公众平台的小程序后台配置 request 合法域名：

```text
https://你的项目.supabase.co
```

开发阶段如果暂时无法配置，可以在微信开发者工具中临时勾选“不校验合法域名、web-view、TLS 版本以及 HTTPS 证书”。正式发布前必须配置合法域名。

## 当前功能范围

- 邮箱 + 密码登录 Supabase Auth。
- 登录成功后保存 session/access_token 到小程序本地 storage。
- 退出登录。
- 今日首页：
  - 当前项目选择器
  - 今日日期
  - 未完成任务
  - 逾期任务
  - 快速填日报入口
- 项目列表：
  - 项目名称
  - deadline
  - 一句话总结
  - 计划进度
  - 实际进度
- 项目详情：
  - deadline 剩余/逾期天数
  - TOP 风险
  - 下一步计划
  - 任务列表
- 新增/编辑项目基础信息。
- 新增/编辑任务，字段与网页版兼容：
  - `parent_id`
  - `risk`
  - `title`
  - `responsible`
  - `start_date`
  - `duration`
  - `status`
  - `completed_date`
  - `note`
- 填写日报：
  - 写入 `daily_logs`
  - upsert `task_progress_entries`
  - 根据实际进度回写任务状态和完成日期
  - 延期必须填写原因

## 暂未实现

- 微信 openid 登录。
- 项目删除。
- 公开分享页。
- 甘特图。
- JSON/CSV 导出。
- 多人协作权限。

公开项目链接仍由网页版 `?share=slug` 提供，小程序版本后续再适配。

## 技术说明

- 小程序使用原生页面结构，不依赖浏览器对象。
- 网络请求统一封装在 `utils/supabase.js`。
- 数据映射统一封装在 `utils/models.js`。
- 日期计算统一封装在 `utils/date.js`。
- 不使用 `supabase-js`，当前通过 `wx.request` 调用 Supabase Auth API 和 REST API。
