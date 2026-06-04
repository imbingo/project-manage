const LOCAL_PREVIEW_KEY = "project-desk-local-v5";
const LEGACY_LOCAL_KEYS = ["project-desk-local-v4", "project-desk-v3"];
const TABLES = {
  projects: "projects",
  tasks: "tasks",
  progress: "task_progress_entries",
  logs: "daily_logs",
  legacy: "project_workspaces"
};

const defaultState = {
  selectedProjectId: null,
  selectedDate: "2026-05-27",
  projects: [
    {
      id: "sample-project-1",
      name: "官网改版上线",
      deadline: "2026-06-12",
      summary: "官网改版进入联调阶段，当前重点是按期上线并控制发布风险。",
      topRisk: "接口字段与前端展示仍有两处不一致，若本周未冻结会影响联调周期。",
      nextStep: "冻结接口字段，完成联调测试并确认灰度发布预案。",
      isPublic: false,
      publicSlug: "",
      tasks: [
        {
          id: "sample-task-1",
          parentId: null,
          risk: "L",
          title: "项目启动与范围确认",
          responsible: "张三",
          startDate: "2026-05-25",
          duration: 2,
          status: "Closed",
          completedDate: "2026-05-26",
          note: "启动会纪要和分工已经同步。",
          progressEntries: [{ entryDate: "2026-05-26", plannedProgress: 100, actualProgress: 100 }]
        },
        {
          id: "sample-task-2",
          parentId: null,
          risk: "M",
          title: "需求冻结",
          responsible: "李四",
          startDate: "2026-05-27",
          duration: 4,
          status: "Ongoing",
          completedDate: "",
          note: "还剩接口字段确认。",
          progressEntries: [{ entryDate: "2026-05-27", plannedProgress: 35, actualProgress: 25 }]
        },
        {
          id: "sample-task-3",
          parentId: "sample-task-2",
          risk: "H",
          title: "接口字段签字确认",
          responsible: "王五",
          startDate: "2026-05-28",
          duration: 2,
          status: "Open",
          completedDate: "",
          note: "产品和后端都要确认。",
          progressEntries: [{ entryDate: "2026-05-27", plannedProgress: 0, actualProgress: 0 }]
        }
      ],
      dailyLogs: [
        {
          id: "sample-log-1",
          date: "2026-05-27",
          responsible: "李四",
          taskId: "sample-task-2",
          planText: "完成需求清单主要字段核对",
          actualText: "完成页面字段第一轮比对",
          plannedProgress: 35,
          actualProgress: 25,
          result: "部分完成",
          delayReason: ""
        }
      ]
    }
  ]
};

let state = structuredClone(defaultState);
let appMode = "boot";
let cloudClient = null;
let session = null;
let recoveryMode = false;
let pendingImport = null;

function config() {
  return window.PROJECT_DESK_CONFIG || {};
}

function hasCloudConfig() {
  return Boolean(config().supabaseUrl && config().supabaseAnonKey);
}

function siteUrl() {
  if (config().siteUrl) return config().siteUrl;
  return `${window.location.origin}${window.location.pathname}`;
}

function cloneDefaults() {
  return structuredClone(defaultState);
}

function showGate(cardId) {
  ["loadingCard", "setupCard", "authCard"].forEach((id) => {
    document.getElementById(id).hidden = id !== cardId;
  });
  document.getElementById("accessGate").hidden = false;
  document.getElementById("appPage").hidden = true;
  document.getElementById("publicPage").hidden = true;
}

function showApp() {
  document.getElementById("accessGate").hidden = true;
  document.getElementById("publicPage").hidden = true;
  document.getElementById("appPage").hidden = false;
  render();
}

function showPublicPage() {
  document.getElementById("accessGate").hidden = true;
  document.getElementById("appPage").hidden = true;
  document.getElementById("publicPage").hidden = false;
}

function setAuthMessage(message, error = false) {
  const element = document.getElementById("authMessage");
  element.textContent = message || "";
  element.classList.toggle("error", error);
}

function setSyncStatus(message, status = "") {
  const element = document.getElementById("syncStatus");
  element.textContent = message;
  element.dataset.state = status;
}

function parseDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function dateString(date = new Date()) {
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function addDays(value, count) {
  const date = parseDate(value);
  date.setDate(date.getDate() + count);
  return dateString(date);
}

function daysBetween(start, end) {
  return Math.round((parseDate(end).getTime() - parseDate(start).getTime()) / 86400000);
}

function taskEndDate(task) {
  return addDays(task.startDate, task.duration - 1);
}

function average(values) {
  return values.length ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length) : 0;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function currentProject() {
  return state.projects.find((project) => String(project.id) === String(state.selectedProjectId)) || state.projects[0];
}

function latestProgress(task, onDate = null) {
  const entries = [...(task.progressEntries || [])]
    .filter((entry) => !onDate || entry.entryDate <= onDate)
    .sort((a, b) => a.entryDate.localeCompare(b.entryDate));
  return entries.at(-1) || { plannedProgress: 0, actualProgress: 0 };
}

function orderedTasks(tasks) {
  const map = new Map(tasks.map((task) => [String(task.id), { ...task, children: [] }]));
  const roots = [];
  map.forEach((task) => {
    if (task.parentId && map.has(String(task.parentId))) map.get(String(task.parentId)).children.push(task);
    else roots.push(task);
  });
  const output = [];
  const walk = (task, depth) => {
    output.push({ ...task, depth });
    task.children.sort((a, b) => a.startDate.localeCompare(b.startDate)).forEach((child) => walk(child, depth + 1));
  };
  roots.sort((a, b) => a.startDate.localeCompare(b.startDate)).forEach((task) => walk(task, 0));
  return output;
}

function ownersOf(project) {
  return [...new Set(project.tasks.map((task) => task.responsible))].sort();
}

function riskClass(risk) {
  return { H: "risk-h", M: "risk-m", L: "risk-l" }[risk] || "risk-l";
}

function slugFor(name) {
  const ascii = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${ascii || "project"}-${crypto.randomUUID().slice(0, 8)}`;
}

function loadLocalState() {
  const keys = [LOCAL_PREVIEW_KEY, ...LEGACY_LOCAL_KEYS];
  for (const key of keys) {
    try {
      const saved = localStorage.getItem(key);
      if (!saved) continue;
      const payload = normalizeLegacyPayload(JSON.parse(saved));
      if (payload.projects.length) return payload;
    } catch {
      continue;
    }
  }
  return cloneDefaults();
}

function normalizeLegacyPayload(payload) {
  if (!payload?.projects?.length) return cloneDefaults();
  const projects = payload.projects.map((project) => ({
    id: project.id,
    name: project.name,
    deadline: project.deadline,
    summary: project.summary || "",
    topRisk: project.topRisk || "",
    nextStep: project.nextStep || "",
    isPublic: project.isPublic || false,
    publicSlug: project.publicSlug || "",
    tasks: (project.tasks || []).map((task) => ({
      id: task.id,
      parentId: task.parentId || null,
      risk: task.risk || "M",
      title: task.title,
      responsible: task.responsible || task.owner || "",
      startDate: task.startDate,
      duration: Number(task.duration) || 1,
      status: task.status || "Open",
      completedDate: task.completedDate || "",
      note: task.note || "",
      progressEntries: task.progressEntries || [{
        entryDate: payload.selectedDate || dateString(),
        plannedProgress: Number(task.plannedProgress || 0),
        actualProgress: Number(task.actualProgress || 0)
      }]
    })),
    dailyLogs: (project.dailyLogs || []).map((log) => ({
      id: log.id,
      date: log.date,
      responsible: log.responsible || log.owner || "",
      taskId: log.taskId,
      planText: log.planText || "",
      actualText: log.actualText || "",
      plannedProgress: Number(log.plannedProgress ?? 0),
      actualProgress: Number(log.actualProgress ?? log.progressAfter ?? 0),
      result: log.result,
      delayReason: log.delayReason || ""
    }))
  }));
  return {
    selectedProjectId: payload.selectedProjectId || projects[0].id,
    selectedDate: payload.selectedDate || dateString(),
    projects
  };
}

function clampProgress(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(100, Math.round(number)));
}

function safeDate(value, fallback = dateString()) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || "")) ? String(value) : fallback;
}

function pick(source, ...keys) {
  for (const key of keys) {
    if (source && source[key] !== undefined && source[key] !== null) return source[key];
  }
  return undefined;
}

function unwrapImportPayload(raw) {
  for (const key of [LOCAL_PREVIEW_KEY, ...LEGACY_LOCAL_KEYS]) {
    if (raw?.[key]) {
      const value = typeof raw[key] === "string" ? JSON.parse(raw[key]) : raw[key];
      return { payload: value, format: `localStorage ${key}` };
    }
  }
  if (raw?.payload) return { payload: raw.payload, format: "Supabase legacy payload" };
  if (raw?.data) return { payload: raw.data, format: "Wrapped data" };
  if (raw?.workspace) return { payload: raw.workspace, format: "Wrapped workspace" };
  if (raw?.projects) return { payload: raw, format: "Workspace projects" };
  if (raw?.tasks || raw?.dailyLogs || raw?.daily_logs) return { payload: { projects: [raw] }, format: "Single project" };
  return { payload: raw, format: "Unknown" };
}

function normalizeImportedWorkspace(raw) {
  const unwrapped = unwrapImportPayload(raw);
  const source = unwrapped.payload || {};
  const sourceProjects = Array.isArray(source.projects) ? source.projects : [];
  if (!sourceProjects.length) throw new Error("没有识别到 projects，也没有识别到单项目结构。");
  const diagnostics = [];
  const projects = sourceProjects.map((project, projectIndex) => {
    const projectId = String(pick(project, "id") || crypto.randomUUID());
    const tasks = (pick(project, "tasks") || []).map((task) => {
      const duration = Math.max(1, Number.parseInt(pick(task, "duration"), 10) || 1);
      const risk = ["H", "M", "L"].includes(pick(task, "risk")) ? pick(task, "risk") : "M";
      const status = ["Open", "Ongoing", "Closed"].includes(pick(task, "status")) ? pick(task, "status") : "Open";
      const entries = pick(task, "progressEntries", "progress_entries") || [];
      const normalizedEntries = Array.isArray(entries) ? entries.map((entry) => ({
        entryDate: safeDate(pick(entry, "entryDate", "entry_date"), safeDate(source.selectedDate)),
        plannedProgress: clampProgress(pick(entry, "plannedProgress", "planned_progress")),
        actualProgress: clampProgress(pick(entry, "actualProgress", "actual_progress"))
      })) : [];
      if (!normalizedEntries.length && (task.plannedProgress !== undefined || task.actualProgress !== undefined)) {
        normalizedEntries.push({
          entryDate: safeDate(source.selectedDate),
          plannedProgress: clampProgress(task.plannedProgress),
          actualProgress: clampProgress(task.actualProgress)
        });
      }
      return {
        id: String(pick(task, "id") || crypto.randomUUID()),
        parentId: pick(task, "parentId", "parent_id") || null,
        risk,
        title: String(pick(task, "title", "task", "name") || "未命名任务"),
        responsible: String(pick(task, "responsible", "owner") || ""),
        startDate: safeDate(pick(task, "startDate", "start_date")),
        duration,
        status,
        completedDate: safeDate(pick(task, "completedDate", "completed_date"), "") || "",
        note: String(pick(task, "note", "remark") || ""),
        progressEntries: normalizedEntries
      };
    });
    const taskIds = new Set(tasks.map((task) => String(task.id)));
    const logs = (pick(project, "dailyLogs", "daily_logs") || []).map((log) => {
      const result = String(pick(log, "result") || "部分完成");
      const delayReason = String(pick(log, "delayReason", "delay_reason") || "");
      if (result === "延期" && !delayReason) diagnostics.push(`项目 ${projectIndex + 1} 有延期日报缺少原因，已导入为空，后续保存时需要补充。`);
      return {
        id: String(pick(log, "id") || crypto.randomUUID()),
        date: safeDate(pick(log, "date", "log_date", "entry_date")),
        responsible: String(pick(log, "responsible", "owner") || ""),
        taskId: String(pick(log, "taskId", "task_id") || ""),
        planText: String(pick(log, "planText", "plan_text") || ""),
        actualText: String(pick(log, "actualText", "actual_text") || ""),
        plannedProgress: clampProgress(pick(log, "plannedProgress", "planned_progress")),
        actualProgress: clampProgress(pick(log, "actualProgress", "actual_progress", "progressAfter")),
        result,
        delayReason
      };
    }).filter((log) => taskIds.has(String(log.taskId)));
    return {
      id: projectId,
      name: String(pick(project, "name", "title") || "未命名项目"),
      deadline: safeDate(pick(project, "deadline")),
      summary: String(pick(project, "summary") || ""),
      topRisk: String(pick(project, "topRisk", "top_risk") || ""),
      nextStep: String(pick(project, "nextStep", "next_step") || ""),
      isPublic: Boolean(pick(project, "isPublic", "is_public")),
      publicSlug: String(pick(project, "publicSlug", "public_slug") || ""),
      tasks,
      dailyLogs: logs
    };
  });
  return {
    workspace: {
      selectedProjectId: source.selectedProjectId || source.selected_project_id || projects[0].id,
      selectedDate: safeDate(source.selectedDate || source.selected_date),
      projects
    },
    format: unwrapped.format,
    diagnostics
  };
}

async function initialize() {
  bindEvents();
  if (!hasCloudConfig() || !window.supabase?.createClient) {
    showGate("setupCard");
    return;
  }
  cloudClient = window.supabase.createClient(config().supabaseUrl, config().supabaseAnonKey);

  const shareSlug = new URLSearchParams(location.search).get("share");
  if (shareSlug) {
    await loadPublicProject(shareSlug);
    return;
  }

  cloudClient.auth.onAuthStateChange((event, currentSession) => {
    if (event === "PASSWORD_RECOVERY") {
      recoveryMode = true;
      document.getElementById("newPasswordModal").showModal();
    }
    if (!currentSession && appMode === "cloud") {
      session = null;
      showGate("authCard");
    }
  });

  const { data, error } = await cloudClient.auth.getSession();
  if (error) {
    showGate("authCard");
    setAuthMessage(error.message, true);
  } else if (data.session) {
    await openCloudWorkspace(data.session);
  } else {
    showGate("authCard");
  }
}

async function loadPublicProject(slug) {
  try {
    const { data, error } = await cloudClient.rpc("get_public_project_snapshot", { p_slug: slug });
    if (error) throw error;
    if (!data) throw new Error("该项目未公开或链接无效。");
    document.getElementById("publicProjectName").textContent = data.name;
    document.getElementById("publicProjectSummary").textContent = data.summary;
    document.getElementById("publicDeadline").textContent = data.deadline;
    const days = daysBetween(dateString(), data.deadline);
    document.getElementById("publicRemaining").textContent = days >= 0 ? `剩余 ${days} 天` : `逾期 ${Math.abs(days)} 天`;
    document.getElementById("publicActual").textContent = `${data.actualProgress}%`;
    document.getElementById("publicPlanned").textContent = `${data.plannedProgress}%`;
    document.getElementById("publicClosed").textContent = `${data.closedTasks}/${data.taskCount}`;
    document.getElementById("publicRisk").textContent = data.topRisk;
    document.getElementById("publicNext").textContent = data.nextStep;
    document.getElementById("publicTaskList").innerHTML = data.tasks.map((task) => `
      <article class="public-task-row">
        <strong>${escapeHtml(task.title)}</strong>
        <span>${escapeHtml(task.status)}</span>
        <span>${task.actualProgress}%</span>
      </article>
    `).join("") || '<p class="empty-state">暂无公开任务。</p>';
    showPublicPage();
  } catch (error) {
    showGate("authCard");
    setAuthMessage(`无法打开公开项目：${error.message}`, true);
  }
}

async function openCloudWorkspace(currentSession) {
  session = currentSession;
  appMode = "cloud";
  document.getElementById("accountLabel").textContent = session.user.email || "";
  try {
    await loadCloudState();
    setSyncStatus("云端已同步", "saved");
    showApp();
  } catch (error) {
    if (error.code === "PGRST205" || String(error.message).includes("Could not find the table") || String(error.message).includes("public.projects")) {
      await openLegacyCloudWorkspace();
      return;
    }
    showGate("authCard");
    setAuthMessage(`需要先升级数据库：${error.message}。请在 Supabase SQL Editor 执行仓库中的 supabase/schema.sql。`, true);
  }
}

async function openLegacyCloudWorkspace() {
  const { data, error } = await cloudClient
    .from(TABLES.legacy)
    .select("payload")
    .eq("user_id", session.user.id)
    .maybeSingle();
  if (error) throw error;
  appMode = "legacy-cloud";
  state = data?.payload ? normalizeLegacyPayload(data.payload) : loadLocalState();
  state.selectedProjectId = state.selectedProjectId || state.projects[0]?.id;
  setSyncStatus("待升级：兼容模式", "saving");
  showApp();
}

async function loadCloudState() {
  const { data: projectRows, error } = await cloudClient
    .from(TABLES.projects)
    .select("*")
    .order("created_at", { ascending: true });
  if (error) throw error;
  if (!projectRows.length) {
    const legacy = await fetchLegacyWorkspace();
    await migratePayloadToCloud(legacy || loadLocalState());
    return loadCloudState();
  }
  const { data: taskRows, error: taskError } = await cloudClient.from(TABLES.tasks).select("*").order("display_order");
  if (taskError) throw taskError;
  const { data: progressRows, error: progressError } = await cloudClient.from(TABLES.progress).select("*").order("entry_date");
  if (progressError) throw progressError;
  const { data: logRows, error: logError } = await cloudClient.from(TABLES.logs).select("*").order("log_date");
  if (logError) throw logError;
  state = {
    selectedProjectId: state.selectedProjectId || projectRows[0].id,
    selectedDate: state.selectedDate || dateString(),
    projects: projectRows.map((row) => ({
      id: row.id,
      name: row.name,
      deadline: row.deadline,
      summary: row.summary,
      topRisk: row.top_risk,
      nextStep: row.next_step,
      isPublic: row.is_public,
      publicSlug: row.public_slug,
      tasks: taskRows.filter((task) => task.project_id === row.id).map((task) => ({
        id: task.id,
        parentId: task.parent_id,
        risk: task.risk,
        title: task.title,
        responsible: task.responsible,
        startDate: task.start_date,
        duration: task.duration,
        status: task.status,
        completedDate: task.completed_date || "",
        note: task.note || "",
        progressEntries: progressRows.filter((entry) => entry.task_id === task.id).map((entry) => ({
          entryDate: entry.entry_date,
          plannedProgress: entry.planned_progress,
          actualProgress: entry.actual_progress
        }))
      })),
      dailyLogs: logRows.filter((log) => log.project_id === row.id).map((log) => ({
        id: log.id,
        taskId: log.task_id,
        date: log.log_date,
        responsible: log.responsible,
        planText: log.plan_text,
        actualText: log.actual_text,
        plannedProgress: log.planned_progress,
        actualProgress: log.actual_progress,
        result: log.result,
        delayReason: log.delay_reason || ""
      }))
    }))
  };
  if (!state.projects.some((project) => String(project.id) === String(state.selectedProjectId))) {
    state.selectedProjectId = state.projects[0].id;
  }
}

async function fetchLegacyWorkspace() {
  const { data, error } = await cloudClient.from(TABLES.legacy).select("payload").maybeSingle();
  if (error) return null;
  return data?.payload ? normalizeLegacyPayload(data.payload) : null;
}

async function migratePayloadToCloud(payload) {
  for (const sourceProject of payload.projects) {
    const project = await insertProject({
      name: sourceProject.name,
      deadline: sourceProject.deadline,
      summary: sourceProject.summary,
      topRisk: sourceProject.topRisk,
      nextStep: sourceProject.nextStep,
      isPublic: sourceProject.isPublic,
      publicSlug: sourceProject.publicSlug || slugFor(sourceProject.name)
    });
    const taskIds = new Map();
    for (const sourceTask of orderedTasks(sourceProject.tasks)) {
      const task = await insertTask(project.id, {
        ...sourceTask,
        parentId: sourceTask.parentId ? taskIds.get(String(sourceTask.parentId)) || null : null
      });
      taskIds.set(String(sourceTask.id), task.id);
      for (const entry of sourceTask.progressEntries || []) {
        await upsertProgress(project.id, task.id, entry.entryDate, entry.plannedProgress, entry.actualProgress);
      }
    }
    for (const sourceLog of sourceProject.dailyLogs) {
      const taskId = taskIds.get(String(sourceLog.taskId));
      if (taskId) await insertDailyLog(project.id, taskId, sourceLog);
    }
  }
}

function remapWorkspaceIds(workspace) {
  const projectIds = new Map();
  const taskIds = new Map();
  return {
    selectedProjectId: null,
    selectedDate: workspace.selectedDate || dateString(),
    projects: workspace.projects.map((project) => {
      const newProjectId = crypto.randomUUID();
      projectIds.set(String(project.id), newProjectId);
      const tasks = project.tasks.map((task) => {
        const newTaskId = crypto.randomUUID();
        taskIds.set(String(task.id), newTaskId);
        return { ...task, id: newTaskId };
      });
      tasks.forEach((task, index) => {
        const oldParentId = project.tasks[index].parentId;
        task.parentId = oldParentId ? taskIds.get(String(oldParentId)) || null : null;
      });
      const dailyLogs = project.dailyLogs.map((log) => ({
        ...log,
        id: crypto.randomUUID(),
        taskId: taskIds.get(String(log.taskId)) || log.taskId
      }));
      return {
        ...project,
        id: newProjectId,
        publicSlug: project.publicSlug ? `${project.publicSlug}-${crypto.randomUUID().slice(0, 6)}` : "",
        tasks,
        dailyLogs
      };
    })
  };
}

async function replaceCloudWorkspace(workspace) {
  const { error } = await cloudClient.from(TABLES.projects).delete().neq("id", "00000000-0000-0000-0000-000000000000");
  if (error) throw error;
  await migratePayloadToCloud(workspace);
  await loadCloudState();
}

async function mergeCloudWorkspace(workspace) {
  const remapped = remapWorkspaceIds(workspace);
  await migratePayloadToCloud(remapped);
  await loadCloudState();
}

async function applyImportedWorkspace(mode) {
  if (!pendingImport?.workspace?.projects?.length) throw new Error("请先选择并预览 JSON 文件。");
  const workspace = pendingImport.workspace;
  if (usesDocumentStorage()) {
    if (mode === "replace") {
      state = workspace;
    } else {
      const remapped = remapWorkspaceIds(workspace);
      state.projects.push(...remapped.projects);
      state.selectedProjectId = remapped.projects[0]?.id || state.selectedProjectId;
      state.selectedDate = workspace.selectedDate || state.selectedDate;
    }
    await refreshAfterChange();
    return;
  }
  setSyncStatus("正在导入...", "saving");
  if (mode === "replace") await replaceCloudWorkspace(workspace);
  else await mergeCloudWorkspace(workspace);
  state.selectedProjectId = state.projects[0]?.id || state.selectedProjectId;
  setSyncStatus("云端已同步", "saved");
  render();
}

function persistLocal() {
  localStorage.setItem(LOCAL_PREVIEW_KEY, JSON.stringify(state));
  setSyncStatus("仅保存在本机", "local");
}

function usesDocumentStorage() {
  return appMode === "local" || appMode === "legacy-cloud";
}

async function persistLegacyCloud() {
  const { error } = await cloudClient.from(TABLES.legacy).upsert({
    user_id: session.user.id,
    payload: state,
    updated_at: new Date().toISOString()
  }, { onConflict: "user_id" });
  if (error) throw error;
  setSyncStatus("待升级：兼容模式", "saving");
}

function startLocalPreview() {
  appMode = "local";
  state = loadLocalState();
  state.selectedProjectId = state.selectedProjectId || state.projects[0]?.id;
  document.getElementById("accountLabel").textContent = "本机预览";
  document.getElementById("logoutButton").textContent = "返回登录";
  setSyncStatus("仅保存在本机", "local");
  showApp();
}

async function insertProject(project) {
  const row = {
    owner_id: session.user.id,
    name: project.name,
    deadline: project.deadline,
    summary: project.summary,
    top_risk: project.topRisk,
    next_step: project.nextStep,
    is_public: Boolean(project.isPublic),
    public_slug: project.publicSlug || slugFor(project.name)
  };
  const { data, error } = await cloudClient.from(TABLES.projects).insert(row).select().single();
  if (error) throw error;
  return data;
}

async function insertTask(projectId, task) {
  const row = {
    owner_id: session.user.id,
    project_id: projectId,
    parent_id: task.parentId || null,
    risk: task.risk,
    title: task.title,
    responsible: task.responsible,
    start_date: task.startDate,
    duration: Number(task.duration),
    status: task.status,
    completed_date: task.completedDate || null,
    note: task.note || "",
    display_order: Date.now()
  };
  const { data, error } = await cloudClient.from(TABLES.tasks).insert(row).select().single();
  if (error) throw error;
  return data;
}

async function upsertProgress(projectId, taskId, entryDate, plannedProgress, actualProgress) {
  const { error } = await cloudClient.from(TABLES.progress).upsert({
    owner_id: session.user.id,
    project_id: projectId,
    task_id: taskId,
    entry_date: entryDate,
    planned_progress: Number(plannedProgress),
    actual_progress: Number(actualProgress)
  }, { onConflict: "task_id,entry_date" });
  if (error) throw error;
}

async function insertDailyLog(projectId, taskId, log) {
  const { error } = await cloudClient.from(TABLES.logs).upsert({
    owner_id: session.user.id,
    project_id: projectId,
    task_id: taskId,
    log_date: log.date,
    responsible: log.responsible,
    plan_text: log.planText,
    actual_text: log.actualText,
    planned_progress: Number(log.plannedProgress),
    actual_progress: Number(log.actualProgress),
    result: log.result,
    delay_reason: log.delayReason || ""
  }, { onConflict: "task_id,log_date" });
  if (error) throw error;
}

async function syncCloudTaskStatus(taskId, actualProgress, completedDate) {
  const { error } = await cloudClient.from(TABLES.tasks).update({
    status: actualProgress === 100 ? "Closed" : actualProgress > 0 ? "Ongoing" : "Open",
    completed_date: actualProgress === 100 ? completedDate : null
  }).eq("id", taskId);
  if (error) throw error;
}

async function refreshAfterChange() {
  if (appMode === "cloud") {
    setSyncStatus("保存中...", "saving");
    await loadCloudState();
    setSyncStatus("云端已同步", "saved");
  } else if (appMode === "legacy-cloud") {
    await persistLegacyCloud();
  } else {
    persistLocal();
  }
  render();
}

function selectDate(date) {
  state.selectedDate = date;
  if (appMode === "local") persistLocal();
  render();
}

function openDatePicker() {
  const input = document.getElementById("datePickerInput");
  input.value = state.selectedDate || dateString();
  document.getElementById("datePickerModal").showModal();
  input.focus();
}

function render() {
  const project = currentProject();
  if (!project) return;
  document.getElementById("projectName").textContent = project.name;
  document.getElementById("projectSummary").textContent = project.summary;
  document.getElementById("publicSummary").textContent = project.summary;
  document.getElementById("projectTopRisk").textContent = project.topRisk;
  document.getElementById("projectNextStep").textContent = project.nextStep;
  document.getElementById("projectDeadline").textContent = project.deadline;
  const remaining = daysBetween(dateString(), project.deadline);
  document.getElementById("deadlineCountdown").textContent =
    remaining >= 0 ? `距离 deadline 还剩 ${remaining} 天` : `已超出 deadline ${Math.abs(remaining)} 天`;
  document.getElementById("selectedDateBadge").textContent = `当前查看：${state.selectedDate}`;
  renderProjectSelect();
  renderFilters(project);
  renderMetrics(project);
  renderTaskTable(project);
  renderGantt(project);
  renderDailySummary(project);
  renderDailyTable(project);
  renderMobileTasks(project);
  renderTaskParentOptions(project);
  renderDailyOwnerOptions(project);
  renderDailyTaskOptions(project);
  document.getElementById("ownerSuggestions").innerHTML = ownersOf(project).map((owner) => `<option value="${escapeHtml(owner)}"></option>`).join("");
}

function renderProjectSelect() {
  document.getElementById("projectSelect").innerHTML = state.projects.map((project) =>
    `<option value="${project.id}"${String(project.id) === String(state.selectedProjectId) ? " selected" : ""}>${escapeHtml(project.name)}</option>`
  ).join("");
}

function renderFilters(project) {
  const ownerFilter = document.getElementById("ownerFilter");
  const selected = ownerFilter.value || "全部";
  ownerFilter.innerHTML = ["全部", ...ownersOf(project)].map((owner) =>
    `<option value="${escapeHtml(owner)}"${owner === selected ? " selected" : ""}>${escapeHtml(owner)}</option>`
  ).join("");
}

function filteredTasks(project) {
  const owner = document.getElementById("ownerFilter").value || "全部";
  const status = document.getElementById("statusFilter").value || "全部";
  return orderedTasks(project.tasks).filter((task) =>
    (owner === "全部" || task.responsible === owner) && (status === "全部" || task.status === status)
  );
}

function renderMetrics(project) {
  const progress = project.tasks.map((task) => latestProgress(task));
  document.getElementById("overallProgress").textContent = `${average(progress.map((entry) => entry.actualProgress))}%`;
  document.getElementById("plannedProgress").textContent = `${average(progress.map((entry) => entry.plannedProgress))}%`;
  const overdue = project.tasks.filter((task) => task.status !== "Closed" && taskEndDate(task) < dateString()).length;
  document.getElementById("overdueCount").textContent = overdue;
}

function renderTaskTable(project) {
  document.getElementById("taskTableBody").innerHTML = filteredTasks(project).map((task) => {
    const progress = latestProgress(task);
    return `
      <tr>
        <td><span class="risk-pill ${riskClass(task.risk)}">${task.risk}</span></td>
        <td><div class="task-name-cell ${task.depth ? "task-child" : ""}">${task.depth ? `<span class="task-level" style="margin-left:${task.depth * 12}px"></span>` : ""}<span>${escapeHtml(task.title)}</span></div></td>
        <td>${escapeHtml(task.responsible)}</td>
        <td>${task.startDate}</td>
        <td>${task.duration}</td>
        <td>${taskEndDate(task)}</td>
        <td><span class="status-pill">${task.status}</span></td>
        <td class="progress-cell"><div class="progress-line plan"><span style="width:${progress.plannedProgress}%"></span></div><small>${progress.plannedProgress}%</small></td>
        <td class="progress-cell"><div class="progress-line"><span style="width:${progress.actualProgress}%"></span></div><small>${progress.actualProgress}%</small></td>
        <td>${task.completedDate || "-"}</td>
        <td><div class="row-actions"><button class="mini-button" data-action="edit-task" data-id="${task.id}">编辑</button><button class="mini-button" data-action="delete-task" data-id="${task.id}">删除</button></div></td>
      </tr>`;
  }).join("");
}

function renderGantt(project) {
  const tasks = filteredTasks(project);
  const header = document.getElementById("ganttHeader");
  const rows = document.getElementById("ganttRows");
  if (!tasks.length) {
    header.innerHTML = "";
    rows.innerHTML = '<p class="empty-state">暂无任务</p>';
    return;
  }
  const taskStart = tasks.map((task) => task.startDate).sort()[0];
  const taskEnd = tasks.map((task) => taskEndDate(task)).sort().at(-1);
  const start = state.selectedDate && state.selectedDate < taskStart ? state.selectedDate : taskStart;
  const end = state.selectedDate && state.selectedDate > taskEnd ? state.selectedDate : taskEnd;
  const dates = Array.from({ length: daysBetween(start, end) + 1 }, (_, index) => addDays(start, index));
  header.style.setProperty("--days", dates.length);
  rows.style.setProperty("--days", dates.length);
  header.innerHTML = '<div class="gantt-task-name">任务</div>' + dates.map((date) =>
    `<div class="gantt-day"><button class="date-button${date === state.selectedDate ? " active" : ""}" data-date="${date}">${date.slice(5)}</button></div>`
  ).join("");
  rows.innerHTML = tasks.map((task) => {
    const progress = latestProgress(task).actualProgress;
    const doneCells = Math.ceil((progress / 100) * task.duration);
    return `<div class="gantt-row"><div class="gantt-task-name">${escapeHtml(task.title)}</div><div class="gantt-cells">${dates.map((date) => {
      const active = date >= task.startDate && date <= taskEndDate(task);
      const offset = active ? daysBetween(task.startDate, date) : -1;
      const classes = ["gantt-cell"];
      if (active) classes.push("active");
      if (active && offset < doneCells) classes.push("done");
      if (date === dateString()) classes.push("today");
      if (date === state.selectedDate) classes.push("selected");
      return `<div class="${classes.join(" ")}" data-date="${date}"></div>`;
    }).join("")}</div></div>`;
  }).join("");
}

function renderDailySummary(project) {
  const logs = project.dailyLogs.filter((log) => log.date === state.selectedDate);
  document.getElementById("dailySummary").innerHTML = `
    <article class="summary-card"><span>查看日期</span><strong>${state.selectedDate}</strong><p>点击甘特图日期切换。</p></article>
    <article class="summary-card"><span>日报数量</span><strong>${logs.length}</strong><p>${logs.length} 条已关联任务。</p></article>
    <article class="summary-card"><span>延期条数</span><strong>${logs.filter((log) => log.result === "延期").length}</strong><p>延期记录必须填写原因。</p></article>`;
}

function renderDailyTable(project) {
  const taskMap = new Map(project.tasks.map((task) => [String(task.id), task.title]));
  const logs = project.dailyLogs.filter((log) => log.date === state.selectedDate);
  document.getElementById("dailyTableBody").innerHTML = logs.length ? logs.map((log) => `
    <tr>
      <td>${escapeHtml(log.responsible)}</td><td>${escapeHtml(log.planText)}</td><td>${escapeHtml(log.actualText)}</td>
      <td>${escapeHtml(taskMap.get(String(log.taskId)) || "-")}</td><td>${log.plannedProgress}%</td><td>${log.actualProgress}%</td>
      <td><span class="status-pill">${log.result}</span></td><td>${escapeHtml(log.delayReason || "-")}</td>
      <td><div class="row-actions"><button class="mini-button" data-action="edit-log" data-id="${log.id}">编辑</button><button class="mini-button" data-action="delete-log" data-id="${log.id}">删除</button></div></td>
    </tr>`).join("") : '<tr><td colspan="9" class="empty-state">这一天还没有日报记录。</td></tr>';
}

function renderMobileTasks(project) {
  const openTasks = project.tasks.filter((task) => task.status !== "Closed").slice(0, 6);
  document.getElementById("mobileTaskList").innerHTML = openTasks.map((task) => {
    const progress = latestProgress(task);
    return `<article class="mobile-task"><strong>${escapeHtml(task.title)}</strong><div class="mobile-task-meta"><span>${escapeHtml(task.responsible)} · ${task.status}</span><span>${progress.actualProgress}%</span></div></article>`;
  }).join("") || '<p class="empty-state">当前没有未完成任务。</p>';
}

function renderTaskParentOptions(project) {
  document.getElementById("taskParent").innerHTML = '<option value="">无父任务</option>' + orderedTasks(project.tasks).map((task) =>
    `<option value="${task.id}">${"&nbsp;".repeat(task.depth * 2)}${escapeHtml(task.title)}</option>`
  ).join("");
}

function renderDailyOwnerOptions(project) {
  document.getElementById("dailyOwner").innerHTML = ownersOf(project).map((owner) => `<option value="${escapeHtml(owner)}">${escapeHtml(owner)}</option>`).join("");
}

function renderDailyTaskOptions(project) {
  document.getElementById("dailyTask").innerHTML = project.tasks.map((task) => `<option value="${task.id}">${escapeHtml(task.title)}</option>`).join("");
}

function openProjectEditor(project = null) {
  document.getElementById("projectForm").reset();
  document.getElementById("projectIdInput").value = project?.id || "";
  document.getElementById("projectModalTitle").textContent = project ? "项目设置" : "新增项目";
  document.getElementById("projectNameInput").value = project?.name || "";
  document.getElementById("projectDeadlineInput").value = project?.deadline || dateString();
  document.getElementById("projectSummaryInput").value = project?.summary || "";
  document.getElementById("projectTopRiskInput").value = project?.topRisk || "";
  document.getElementById("projectNextStepInput").value = project?.nextStep || "";
  document.getElementById("projectPublicInput").checked = Boolean(project?.isPublic);
  document.getElementById("copyShareLinkButton").disabled = !project?.isPublic;
  document.getElementById("deleteProjectButton").hidden = !project;
  document.getElementById("deleteProjectButton").disabled = Boolean(project) && state.projects.length <= 1;
  document.getElementById("deleteProjectButton").title = state.projects.length <= 1 ? "至少保留一个项目" : "";
  document.getElementById("projectModal").showModal();
}

function openTaskEditor(task = null) {
  const project = currentProject();
  const progress = task ? latestProgress(task) : { plannedProgress: 0, actualProgress: 0 };
  document.getElementById("taskForm").reset();
  renderTaskParentOptions(project);
  document.getElementById("taskModalTitle").textContent = task ? "编辑任务" : "新增任务";
  document.getElementById("taskIdInput").value = task?.id || "";
  document.getElementById("taskParent").value = task?.parentId || "";
  document.getElementById("taskRisk").value = task?.risk || "M";
  document.getElementById("taskTitle").value = task?.title || "";
  document.getElementById("taskOwner").value = task?.responsible || ownersOf(project)[0] || "";
  document.getElementById("taskStart").value = task?.startDate || state.selectedDate;
  document.getElementById("taskDuration").value = task?.duration || 3;
  document.getElementById("taskStatus").value = task?.status || "Open";
  document.getElementById("taskPlannedProgress").value = progress.plannedProgress;
  document.getElementById("taskProgress").value = progress.actualProgress;
  document.getElementById("taskCompletedDate").value = task?.completedDate || "";
  document.getElementById("taskNote").value = task?.note || "";
  document.getElementById("taskModal").showModal();
}

function openDailyEditor(log = null) {
  const project = currentProject();
  document.getElementById("dailyForm").reset();
  renderDailyOwnerOptions(project);
  renderDailyTaskOptions(project);
  document.getElementById("dailyModalTitle").textContent = log ? "编辑日报" : "新增日报";
  document.getElementById("dailyIdInput").value = log?.id || "";
  document.getElementById("dailyDate").value = log?.date || state.selectedDate;
  document.getElementById("dailyOwner").value = log?.responsible || ownersOf(project)[0] || "";
  document.getElementById("dailyTask").value = String(log?.taskId || project.tasks[0]?.id || "");
  document.getElementById("dailyPlanText").value = log?.planText || "";
  document.getElementById("dailyActualText").value = log?.actualText || "";
  document.getElementById("dailyPlannedProgress").value = log?.plannedProgress ?? 0;
  document.getElementById("dailyProgressAfter").value = log?.actualProgress ?? 0;
  document.getElementById("dailyResult").value = log?.result || "部分完成";
  document.getElementById("dailyDelayReason").value = log?.delayReason || "";
  document.getElementById("dailyModal").showModal();
}

async function saveProjectFromForm() {
  const existing = currentProject();
  const id = document.getElementById("projectIdInput").value;
  const values = {
    name: document.getElementById("projectNameInput").value.trim(),
    deadline: document.getElementById("projectDeadlineInput").value,
    summary: document.getElementById("projectSummaryInput").value.trim(),
    topRisk: document.getElementById("projectTopRiskInput").value.trim(),
    nextStep: document.getElementById("projectNextStepInput").value.trim(),
    isPublic: document.getElementById("projectPublicInput").checked,
    publicSlug: (id ? state.projects.find((project) => String(project.id) === id)?.publicSlug : "") || slugFor(document.getElementById("projectNameInput").value)
  };
  if (usesDocumentStorage()) {
    if (id) Object.assign(state.projects.find((project) => String(project.id) === id), values);
    else {
      const project = { ...values, id: crypto.randomUUID(), tasks: [], dailyLogs: [] };
      state.projects.push(project);
      state.selectedProjectId = project.id;
    }
  } else if (id) {
    const { error } = await cloudClient.from(TABLES.projects).update({
      name: values.name, deadline: values.deadline, summary: values.summary, top_risk: values.topRisk,
      next_step: values.nextStep, is_public: values.isPublic, public_slug: values.publicSlug
    }).eq("id", id);
    if (error) throw error;
  } else {
    const row = await insertProject(values);
    state.selectedProjectId = row.id;
  }
  await refreshAfterChange();
}

async function deleteCurrentProject() {
  const project = currentProject();
  if (!project) return;
  if (state.projects.length <= 1) {
    alert("至少需要保留一个项目。请先新增项目，再删除当前项目。");
    return;
  }
  const confirmed = confirm(`删除项目“${project.name}”会同时删除该项目下所有任务、日报、进度记录和公开链接。此操作不可撤销，确认删除？`);
  if (!confirmed) return;
  if (usesDocumentStorage()) {
    state.projects = state.projects.filter((item) => String(item.id) !== String(project.id));
    state.selectedProjectId = state.projects[0]?.id || null;
    state.selectedDate = currentProject()?.tasks[0]?.startDate || dateString();
  } else {
    const { error } = await cloudClient.from(TABLES.projects).delete().eq("id", project.id);
    if (error) throw error;
    const fallback = state.projects.find((item) => String(item.id) !== String(project.id));
    state.selectedProjectId = fallback?.id || null;
    state.selectedDate = fallback?.tasks[0]?.startDate || dateString();
  }
  await refreshAfterChange();
  document.getElementById("projectModal").close();
}

async function saveTaskFromForm() {
  const project = currentProject();
  const id = document.getElementById("taskIdInput").value;
  const values = {
    parentId: document.getElementById("taskParent").value || null,
    risk: document.getElementById("taskRisk").value,
    title: document.getElementById("taskTitle").value.trim(),
    responsible: document.getElementById("taskOwner").value.trim(),
    startDate: document.getElementById("taskStart").value,
    duration: Number(document.getElementById("taskDuration").value),
    status: document.getElementById("taskStatus").value,
    completedDate: document.getElementById("taskCompletedDate").value,
    note: document.getElementById("taskNote").value.trim()
  };
  const planned = Number(document.getElementById("taskPlannedProgress").value);
  const actual = Number(document.getElementById("taskProgress").value);
  if (usesDocumentStorage()) {
    let task;
    if (id) {
      task = project.tasks.find((item) => String(item.id) === id);
      Object.assign(task, values);
    } else {
      task = { ...values, id: crypto.randomUUID(), progressEntries: [] };
      project.tasks.push(task);
    }
    task.progressEntries.push({ entryDate: state.selectedDate, plannedProgress: planned, actualProgress: actual });
  } else {
    let taskId = id;
    if (id) {
      const { error } = await cloudClient.from(TABLES.tasks).update({
        parent_id: values.parentId || null, risk: values.risk, title: values.title, responsible: values.responsible,
        start_date: values.startDate, duration: values.duration, status: values.status,
        completed_date: values.completedDate || null, note: values.note
      }).eq("id", id);
      if (error) throw error;
    } else {
      const row = await insertTask(project.id, values);
      taskId = row.id;
    }
    await upsertProgress(project.id, taskId, state.selectedDate, planned, actual);
  }
  await refreshAfterChange();
}

async function saveLogFromForm() {
  const project = currentProject();
  const id = document.getElementById("dailyIdInput").value;
  const log = {
    id: id || crypto.randomUUID(),
    taskId: document.getElementById("dailyTask").value,
    date: document.getElementById("dailyDate").value,
    responsible: document.getElementById("dailyOwner").value,
    planText: document.getElementById("dailyPlanText").value.trim(),
    actualText: document.getElementById("dailyActualText").value.trim(),
    plannedProgress: Number(document.getElementById("dailyPlannedProgress").value),
    actualProgress: Number(document.getElementById("dailyProgressAfter").value),
    result: document.getElementById("dailyResult").value,
    delayReason: document.getElementById("dailyDelayReason").value.trim()
  };
  if (log.result === "延期" && !log.delayReason) throw new Error("日报结果为延期时，必须填写延期原因。");
  if (usesDocumentStorage()) {
    const index = project.dailyLogs.findIndex((item) => String(item.id) === id);
    if (index >= 0) {
      const oldLog = project.dailyLogs[index];
      const oldTask = project.tasks.find((item) => String(item.id) === String(oldLog.taskId));
      oldTask.progressEntries = oldTask.progressEntries.filter((entry) => entry.entryDate !== oldLog.date);
      project.dailyLogs[index] = log;
    } else {
      project.dailyLogs.push(log);
    }
    const task = project.tasks.find((item) => String(item.id) === String(log.taskId));
    task.progressEntries.push({ entryDate: log.date, plannedProgress: log.plannedProgress, actualProgress: log.actualProgress });
    task.status = log.actualProgress === 100 ? "Closed" : log.actualProgress > 0 ? "Ongoing" : "Open";
    task.completedDate = log.actualProgress === 100 ? log.date : "";
  } else {
    const oldLog = id ? project.dailyLogs.find((item) => String(item.id) === id) : null;
    if (oldLog) {
      const { error } = await cloudClient.from(TABLES.logs).update({
        task_id: log.taskId,
        log_date: log.date,
        responsible: log.responsible,
        plan_text: log.planText,
        actual_text: log.actualText,
        planned_progress: log.plannedProgress,
        actual_progress: log.actualProgress,
        result: log.result,
        delay_reason: log.delayReason
      }).eq("id", oldLog.id);
      if (error) throw error;
      if (String(oldLog.taskId) !== String(log.taskId) || oldLog.date !== log.date) {
        const { error: removeOldError } = await cloudClient.from(TABLES.progress).delete().eq("task_id", oldLog.taskId).eq("entry_date", oldLog.date);
        if (removeOldError) throw removeOldError;
      }
    } else {
      await insertDailyLog(project.id, log.taskId, log);
    }
    await upsertProgress(project.id, log.taskId, log.date, log.plannedProgress, log.actualProgress);
    await syncCloudTaskStatus(log.taskId, log.actualProgress, log.date);
  }
  state.selectedDate = log.date;
  await refreshAfterChange();
}

function download(name, type, content) {
  const blob = new Blob([content], { type });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

function exportJson() {
  const project = currentProject();
  const payload = {
    version: "project-desk-workspace-v6",
    exportedAt: new Date().toISOString(),
    workspace: state
  };
  download(`${project.name}-workspace-${dateString()}.json`, "application/json;charset=utf-8", JSON.stringify(payload, null, 2));
}

function exportCsv() {
  const project = currentProject();
  const rows = [["任务", "负责人", "风险", "开始日期", "结束日期", "状态", "计划进度%", "实际进度%", "完成日期"]];
  project.tasks.forEach((task) => {
    const progress = latestProgress(task);
    rows.push([task.title, task.responsible, task.risk, task.startDate, taskEndDate(task), task.status, progress.plannedProgress, progress.actualProgress, task.completedDate]);
  });
  const csv = rows.map((row) => row.map((cell) => `"${String(cell || "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
  download(`${project.name}-tasks-${dateString()}.csv`, "text/csv;charset=utf-8", `\ufeff${csv}`);
}

function ganttDateRange(project) {
  const starts = project.tasks.map((task) => task.startDate).filter(Boolean);
  const ends = project.tasks.map((task) => taskEndDate(task)).filter(Boolean);
  const start = starts.length ? starts.sort()[0] : dateString();
  const end = ends.length ? ends.sort().at(-1) : addDays(start, 13);
  const total = Math.min(Math.max(daysBetween(start, end) + 1, 14), 120);
  return Array.from({ length: total }, (_, index) => addDays(start, index));
}

function excelCell(value, attrs = "") {
  return `<td ${attrs}>${escapeHtml(value ?? "")}</td>`;
}

function excelHeader(value) {
  return `<th>${escapeHtml(value ?? "")}</th>`;
}

function exportExcel() {
  const project = currentProject();
  const progress = project.tasks.map((task) => latestProgress(task));
  const dates = ganttDateRange(project);
  const remaining = daysBetween(dateString(), project.deadline);
  const taskRows = orderedTasks(project.tasks).map((task) => {
    const p = latestProgress(task);
    return `<tr>${[
      task.risk,
      `${"　".repeat(task.depth || 0)}${task.title}`,
      task.responsible,
      task.startDate,
      task.duration,
      taskEndDate(task),
      task.status,
      p.plannedProgress,
      p.actualProgress,
      task.completedDate,
      task.note
    ].map((cell) => excelCell(cell)).join("")}</tr>`;
  }).join("");
  const dailyRows = project.dailyLogs.map((log) => {
    const task = project.tasks.find((item) => String(item.id) === String(log.taskId));
    return `<tr>${[
      log.date,
      log.responsible,
      task?.title || "",
      log.planText,
      log.actualText,
      log.plannedProgress,
      log.actualProgress,
      log.result,
      log.delayReason
    ].map((cell) => excelCell(cell)).join("")}</tr>`;
  }).join("");
  const ganttRows = orderedTasks(project.tasks).map((task) => {
    const end = taskEndDate(task);
    const p = latestProgress(task);
    const cells = dates.map((date) => {
      const active = date >= task.startDate && date <= end;
      const done = task.completedDate && date >= task.startDate && date <= task.completedDate;
      const style = active
        ? `style="background:${done ? "#86efac" : "#bfdbfe"};text-align:center;"`
        : `style="background:#ffffff;"`;
      return excelCell(active ? (done ? "■" : "□") : "", style);
    }).join("");
    return `<tr>${excelCell(task.title)}${excelCell(task.responsible)}${excelCell(task.risk)}${excelCell(`${p.actualProgress}%`)}${cells}</tr>`;
  }).join("");
  const html = `<!doctype html><html><head><meta charset="utf-8" />
    <style>
      body{font-family:Arial,'Microsoft YaHei',sans-serif;color:#111827}
      h1{font-size:22px} h2{font-size:16px;margin-top:24px}
      table{border-collapse:collapse;margin-bottom:18px;width:100%}
      th{background:#e5e7eb;font-weight:700}
      th,td{border:1px solid #9ca3af;padding:6px 8px;font-size:12px;vertical-align:top}
      .kpi td:nth-child(odd){background:#f3f4f6;font-weight:700;width:120px}
    </style></head><body>
    <h1>${escapeHtml(project.name)} 项目管理表</h1>
    <h2>项目概览</h2>
    <table class="kpi">
      <tr>${excelCell("Deadline")}${excelCell(project.deadline)}${excelCell("剩余/逾期")}${excelCell(remaining >= 0 ? `剩余 ${remaining} 天` : `逾期 ${Math.abs(remaining)} 天`)}</tr>
      <tr>${excelCell("实际进度")}${excelCell(`${average(progress.map((entry) => entry.actualProgress))}%`)}${excelCell("计划进度")}${excelCell(`${average(progress.map((entry) => entry.plannedProgress))}%`)}</tr>
      <tr>${excelCell("一句话总结")}${excelCell(project.summary, 'colspan="3"')}</tr>
      <tr>${excelCell("TOP 风险")}${excelCell(project.topRisk, 'colspan="3"')}</tr>
      <tr>${excelCell("下一步计划")}${excelCell(project.nextStep, 'colspan="3"')}</tr>
    </table>
    <h2>任务台账</h2>
    <table><tr>${["风险","任务","负责人","开始","工期","结束","状态","计划%","实际%","实际完成日","备注"].map(excelHeader).join("")}</tr>${taskRows}</table>
    <h2>日报记录</h2>
    <table><tr>${["日期","负责人","关联任务","计划完成","实际完成","计划%","实际%","结果","延期原因"].map(excelHeader).join("")}</tr>${dailyRows}</table>
    <h2>甘特图</h2>
    <table><tr>${["任务","负责人","风险","实际%"].map(excelHeader).join("")}${dates.map((date) => excelHeader(date.slice(5))).join("")}</tr>${ganttRows}</table>
    </body></html>`;
  download(`${project.name}-project-table-${dateString()}.xls`, "application/vnd.ms-excel;charset=utf-8", `\ufeff${html}`);
}

async function copyShareLink() {
  const project = currentProject();
  if (appMode === "legacy-cloud") {
    alert("公开链接功能将在执行数据库升级脚本后启用。");
    return;
  }
  if (!project.isPublic) {
    alert("请先勾选“允许对外只读展示”并保存项目。");
    return;
  }
  const url = `${siteUrl()}?share=${encodeURIComponent(project.publicSlug)}`;
  await navigator.clipboard.writeText(url);
  alert("公开链接已复制。");
}

function importSummaryText(workspace) {
  const projectCount = workspace.projects.length;
  const taskCount = workspace.projects.reduce((sum, project) => sum + project.tasks.length, 0);
  const logCount = workspace.projects.reduce((sum, project) => sum + project.dailyLogs.length, 0);
  return `识别到 ${projectCount} 个项目、${taskCount} 个任务、${logCount} 条日报。`;
}

async function previewImportFile(file) {
  if (!file) return;
  try {
    const text = await file.text();
    const parsed = JSON.parse(text);
    pendingImport = normalizeImportedWorkspace(parsed);
    document.getElementById("importPreview").hidden = false;
    document.getElementById("importSummary").textContent = importSummaryText(pendingImport.workspace);
    document.getElementById("importDiagnostics").textContent = [
      `识别格式：${pendingImport.format}`,
      ...(pendingImport.diagnostics.length ? pendingImport.diagnostics : ["未发现需要人工处理的兼容问题。"])
    ].join("\n");
    document.getElementById("confirmImportButton").disabled = false;
  } catch (error) {
    pendingImport = null;
    document.getElementById("importPreview").hidden = false;
    document.getElementById("importSummary").textContent = "导入失败";
    document.getElementById("importDiagnostics").textContent = error.message;
    document.getElementById("confirmImportButton").disabled = true;
  }
}

function bindEvents() {
  document.getElementById("localPreviewButton").addEventListener("click", startLocalPreview);
  document.getElementById("authLocalPreviewButton").addEventListener("click", startLocalPreview);
  document.getElementById("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    setAuthMessage("正在登录...");
    const { data, error } = await cloudClient.auth.signInWithPassword({
      email: document.getElementById("loginEmail").value.trim(),
      password: document.getElementById("loginPassword").value
    });
    if (error) setAuthMessage(error.message, true);
    else await openCloudWorkspace(data.session);
  });
  document.getElementById("signupForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const { data, error } = await cloudClient.auth.signUp({
      email: document.getElementById("signupEmail").value.trim(),
      password: document.getElementById("signupPassword").value,
      options: { emailRedirectTo: siteUrl() }
    });
    if (error) setAuthMessage(error.message, true);
    else if (data.session) await openCloudWorkspace(data.session);
    else setAuthMessage("注册邮件已发送，请在邮箱确认后登录。");
  });
  document.getElementById("forgotPasswordButton").addEventListener("click", () => document.getElementById("resetPasswordModal").showModal());
  document.getElementById("resetPasswordForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const { error } = await cloudClient.auth.resetPasswordForEmail(document.getElementById("resetEmail").value.trim(), { redirectTo: siteUrl() });
    if (error) setAuthMessage(error.message, true);
    else {
      document.getElementById("resetPasswordModal").close();
      setAuthMessage("重置邮件已发送，请打开邮件中的链接。");
    }
  });
  document.getElementById("newPasswordForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const { error } = await cloudClient.auth.updateUser({ password: document.getElementById("newPassword").value });
    if (error) alert(error.message);
    else {
      recoveryMode = false;
      document.getElementById("newPasswordModal").close();
      alert("密码已更新。");
    }
  });
  document.getElementById("logoutButton").addEventListener("click", async () => {
    if (appMode === "local") showGate(hasCloudConfig() ? "authCard" : "setupCard");
    else await cloudClient.auth.signOut();
  });
  document.getElementById("projectSelect").addEventListener("change", (event) => {
    state.selectedProjectId = event.target.value;
    state.selectedDate = currentProject().tasks[0]?.startDate || dateString();
    if (appMode === "local") persistLocal();
    render();
  });
  document.getElementById("ownerFilter").addEventListener("change", render);
  document.getElementById("statusFilter").addEventListener("change", render);
  document.getElementById("openProjectModal").addEventListener("click", () => openProjectEditor(currentProject()));
  document.getElementById("createProjectButton").addEventListener("click", () => openProjectEditor());
  document.getElementById("openTaskModal").addEventListener("click", () => openTaskEditor());
  document.getElementById("openDailyModal").addEventListener("click", () => openDailyEditor());
  document.getElementById("mobileOpenDaily").addEventListener("click", () => openDailyEditor());
  document.getElementById("importButton").addEventListener("click", () => {
    pendingImport = null;
    document.getElementById("importFileInput").value = "";
    document.getElementById("importPreview").hidden = true;
    document.getElementById("confirmImportButton").disabled = true;
    document.getElementById("importModal").showModal();
  });
  document.getElementById("exportButton").addEventListener("click", () => document.getElementById("exportModal").showModal());
  document.getElementById("selectedDateBadge").addEventListener("click", openDatePicker);
  document.getElementById("exportJsonButton").addEventListener("click", exportJson);
  document.getElementById("exportCsvButton").addEventListener("click", exportCsv);
  document.getElementById("exportExcelButton").addEventListener("click", exportExcel);
  document.getElementById("importFileInput").addEventListener("change", (event) => previewImportFile(event.target.files[0]));
  document.getElementById("confirmImportButton").addEventListener("click", async () => {
    try {
      const mode = document.querySelector("input[name='importMode']:checked")?.value || "merge";
      await applyImportedWorkspace(mode);
      document.getElementById("importModal").close();
      alert("导入完成。");
    } catch (error) {
      alert(error.message);
    }
  });
  document.getElementById("copyShareLinkButton").addEventListener("click", copyShareLink);
  document.getElementById("deleteProjectButton").addEventListener("click", async () => {
    try { await deleteCurrentProject(); } catch (error) { alert(error.message); }
  });
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => document.getElementById(button.dataset.close).close()));
  document.getElementById("projectForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try { await saveProjectFromForm(); document.getElementById("projectModal").close(); } catch (error) { alert(error.message); }
  });
  document.getElementById("taskForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try { await saveTaskFromForm(); document.getElementById("taskModal").close(); } catch (error) { alert(error.message); }
  });
  document.getElementById("dailyForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try { await saveLogFromForm(); document.getElementById("dailyModal").close(); } catch (error) { alert(error.message); }
  });
  document.getElementById("datePickerForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const date = document.getElementById("datePickerInput").value;
    if (!date) return;
    document.getElementById("datePickerModal").close();
    selectDate(date);
  });
  document.getElementById("taskTableBody").addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const project = currentProject();
    const task = project.tasks.find((item) => String(item.id) === button.dataset.id);
    if (button.dataset.action === "edit-task") openTaskEditor(task);
    if (button.dataset.action === "delete-task" && confirm("删除任务会同时删除子任务、日报和进度记录。确认删除？")) {
      if (usesDocumentStorage()) {
        const ids = new Set([String(task.id)]);
        let foundChild = true;
        while (foundChild) {
          foundChild = false;
          project.tasks.forEach((item) => {
            if (ids.has(String(item.parentId)) && !ids.has(String(item.id))) {
              ids.add(String(item.id));
              foundChild = true;
            }
          });
        }
        project.tasks = project.tasks.filter((item) => !ids.has(String(item.id)));
        project.dailyLogs = project.dailyLogs.filter((log) => !ids.has(String(log.taskId)));
      } else {
        const { error } = await cloudClient.from(TABLES.tasks).delete().eq("id", task.id);
        if (error) return alert(error.message);
      }
      await refreshAfterChange();
    }
  });
  document.getElementById("dailyTableBody").addEventListener("click", async (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const project = currentProject();
    const log = project.dailyLogs.find((item) => String(item.id) === button.dataset.id);
    if (button.dataset.action === "edit-log") openDailyEditor(log);
    if (button.dataset.action === "delete-log") {
      if (usesDocumentStorage()) {
        project.dailyLogs = project.dailyLogs.filter((item) => String(item.id) !== String(log.id));
        const task = project.tasks.find((item) => String(item.id) === String(log.taskId));
        task.progressEntries = task.progressEntries.filter((entry) => entry.entryDate !== log.date);
      } else {
        const { error } = await cloudClient.from(TABLES.logs).delete().eq("id", log.id);
        if (error) return alert(error.message);
        const { error: progressError } = await cloudClient.from(TABLES.progress).delete().eq("task_id", log.taskId).eq("entry_date", log.date);
        if (progressError) return alert(progressError.message);
        const { data: latest, error: latestError } = await cloudClient
          .from(TABLES.progress)
          .select("actual_progress,entry_date")
          .eq("task_id", log.taskId)
          .order("entry_date", { ascending: false })
          .limit(1)
          .maybeSingle();
        if (latestError) return alert(latestError.message);
        await syncCloudTaskStatus(log.taskId, latest?.actual_progress || 0, latest?.entry_date || null);
      }
      await refreshAfterChange();
    }
  });
  ["ganttHeader", "ganttRows"].forEach((id) => document.getElementById(id).addEventListener("click", (event) => {
    const target = event.target.closest("[data-date]");
    if (!target) return;
    selectDate(target.dataset.date);
  }));
}

initialize();
