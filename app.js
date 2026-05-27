const CLOUD_TABLE = "project_workspaces";
const LOCAL_PREVIEW_KEY = "project-desk-local-v4";
const LEGACY_LOCAL_KEY = "project-desk-v3";

const defaultState = {
  selectedProjectId: 1,
  selectedDate: "2026-05-27",
  projects: [
    {
      id: 1,
      name: "官网改版上线",
      deadline: "2026-06-12",
      summary: "官网改版进入联调阶段，当前重点是按期上线并控制发布风险。",
      topRisk: "接口字段与前端展示仍有两处不一致，若本周未冻结会影响联调周期。",
      nextStep: "冻结接口字段，完成联调测试并确认灰度发布预案。",
      tasks: [
        {
          id: 101,
          parentId: null,
          risk: "L",
          title: "项目启动与范围确认",
          owner: "张三",
          startDate: "2026-05-25",
          duration: 2,
          status: "Closed",
          plannedProgress: 100,
          actualProgress: 100,
          completedDate: "2026-05-26",
          note: "启动会纪要和分工已经同步。"
        },
        {
          id: 102,
          parentId: null,
          risk: "M",
          title: "需求冻结",
          owner: "李四",
          startDate: "2026-05-27",
          duration: 4,
          status: "Ongoing",
          plannedProgress: 35,
          actualProgress: 25,
          completedDate: "",
          note: "还剩接口字段确认。"
        },
        {
          id: 103,
          parentId: 102,
          risk: "M",
          title: "页面字段核对",
          owner: "李四",
          startDate: "2026-05-27",
          duration: 2,
          status: "Ongoing",
          plannedProgress: 50,
          actualProgress: 40,
          completedDate: "",
          note: "首页和报价页需要复核。"
        },
        {
          id: 104,
          parentId: 102,
          risk: "H",
          title: "接口字段签字确认",
          owner: "王五",
          startDate: "2026-05-28",
          duration: 2,
          status: "Open",
          plannedProgress: 0,
          actualProgress: 0,
          completedDate: "",
          note: "产品和后端都要确认。"
        },
        {
          id: 105,
          parentId: null,
          risk: "H",
          title: "联调与冒烟测试",
          owner: "赵六",
          startDate: "2026-06-01",
          duration: 5,
          status: "Open",
          plannedProgress: 0,
          actualProgress: 0,
          completedDate: "",
          note: "依赖需求冻结完成。"
        }
      ],
      dailyLogs: [
        {
          id: 1001,
          date: "2026-05-27",
          owner: "李四",
          taskId: 102,
          planText: "完成需求清单主要字段核对",
          actualText: "完成页面字段第一轮比对",
          progressAfter: 25,
          result: "部分完成",
          delayReason: ""
        },
        {
          id: 1002,
          date: "2026-05-27",
          owner: "李四",
          taskId: 103,
          planText: "核对首页和报价页字段",
          actualText: "首页完成，报价页待确认",
          progressAfter: 40,
          result: "部分完成",
          delayReason: ""
        }
      ]
    },
    {
      id: 2,
      name: "客户培训项目",
      deadline: "2026-06-18",
      summary: "客户培训正在准备课程和材料，关键是尽快锁定参训名单。",
      topRisk: "参训名单尚未确认，可能导致教材和排课返工。",
      nextStep: "确认参训名单，完成教材初稿并准备演示环境。",
      tasks: [
        {
          id: 201,
          parentId: null,
          risk: "L",
          title: "培训范围确认",
          owner: "周一",
          startDate: "2026-05-27",
          duration: 3,
          status: "Ongoing",
          plannedProgress: 30,
          actualProgress: 20,
          completedDate: "",
          note: "课程清单正在细化。"
        },
        {
          id: 202,
          parentId: null,
          risk: "M",
          title: "教材准备",
          owner: "吴二",
          startDate: "2026-06-01",
          duration: 6,
          status: "Open",
          plannedProgress: 0,
          actualProgress: 0,
          completedDate: "",
          note: "依赖范围确认。"
        }
      ],
      dailyLogs: []
    }
  ]
};

let appMode = "boot";
let state = structuredClone(defaultState);
let cloudClient = null;
let session = null;
let saveTimer = null;
let saveQueue = Promise.resolve();

function cloneDefaultState() {
  return structuredClone(defaultState);
}

function configuredForCloud() {
  const config = window.PROJECT_DESK_CONFIG || {};
  return Boolean(config.supabaseUrl && config.supabaseAnonKey);
}

function showOnlyCard(cardId) {
  ["loadingCard", "setupCard", "authCard"].forEach((id) => {
    document.getElementById(id).hidden = id !== cardId;
  });
  document.getElementById("accessGate").hidden = false;
  document.getElementById("appPage").hidden = true;
}

function showApplication() {
  document.getElementById("accessGate").hidden = true;
  document.getElementById("appPage").hidden = false;
  render();
}

function setAuthMessage(message, isError = false) {
  const element = document.getElementById("authMessage");
  element.textContent = message || "";
  element.classList.toggle("error", isError);
}

function setSyncStatus(message, stateName = "") {
  const element = document.getElementById("syncStatus");
  element.textContent = message;
  element.dataset.state = stateName;
}

function loadLocalPreviewState() {
  for (const key of [LOCAL_PREVIEW_KEY, LEGACY_LOCAL_KEY]) {
    try {
      const saved = localStorage.getItem(key);
      if (!saved) continue;
      const parsed = JSON.parse(saved);
      if (parsed.projects?.length) return parsed;
    } catch {
      continue;
    }
  }
  return cloneDefaultState();
}

async function initialize() {
  bindEvents();
  if (!configuredForCloud() || !window.supabase?.createClient) {
    showOnlyCard("setupCard");
    return;
  }

  const config = window.PROJECT_DESK_CONFIG;
  cloudClient = window.supabase.createClient(config.supabaseUrl, config.supabaseAnonKey);
  cloudClient.auth.onAuthStateChange((_event, currentSession) => {
    if (!currentSession) {
      session = null;
      appMode = "auth";
      showOnlyCard("authCard");
    }
  });

  const { data, error } = await cloudClient.auth.getSession();
  if (error) {
    showOnlyCard("authCard");
    setAuthMessage(error.message, true);
    return;
  }
  if (data.session) {
    await openCloudWorkspace(data.session);
  } else {
    showOnlyCard("authCard");
  }
}

async function openCloudWorkspace(currentSession) {
  session = currentSession;
  appMode = "cloud";
  setAuthMessage("");
  try {
    const { data, error } = await cloudClient
      .from(CLOUD_TABLE)
      .select("payload")
      .eq("user_id", session.user.id)
      .maybeSingle();
    if (error) throw error;
    if (data?.payload?.projects?.length) {
      state = data.payload;
    } else {
      state = loadLocalPreviewState();
      await saveCloudState();
    }
    document.getElementById("accountLabel").textContent = session.user.email || "";
    setSyncStatus("云端已同步", "saved");
    showApplication();
  } catch (error) {
    appMode = "auth";
    showOnlyCard("authCard");
    setAuthMessage(`无法读取云端工作区：${error.message}。请先执行数据库建表脚本。`, true);
  }
}

function startLocalPreview() {
  appMode = "local";
  state = loadLocalPreviewState();
  document.getElementById("accountLabel").textContent = "本机预览";
  document.getElementById("logoutButton").textContent = "返回登录";
  setSyncStatus("仅保存在本机", "local");
  showApplication();
}

function persistState() {
  if (appMode === "local") {
    localStorage.setItem(LOCAL_PREVIEW_KEY, JSON.stringify(state));
    setSyncStatus("仅保存在本机", "local");
    return;
  }
  if (appMode !== "cloud") return;
  setSyncStatus("保存中...", "saving");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    saveQueue = saveQueue.catch(() => undefined).then(saveCloudState).catch(() => undefined);
  }, 100);
}

async function saveCloudState() {
  if (!session || !cloudClient) return;
  const payload = structuredClone(state);
  const { error } = await cloudClient
    .from(CLOUD_TABLE)
    .upsert({
      user_id: session.user.id,
      payload,
      updated_at: new Date().toISOString()
    });
  if (error) {
    setSyncStatus("保存失败", "error");
    throw error;
  }
  setSyncStatus("云端已同步", "saved");
}

async function signIn(email, password) {
  setAuthMessage("正在登录...");
  const { data, error } = await cloudClient.auth.signInWithPassword({ email, password });
  if (error) {
    setAuthMessage(error.message, true);
    return;
  }
  await openCloudWorkspace(data.session);
}

async function signUp(email, password) {
  setAuthMessage("正在注册...");
  const { data, error } = await cloudClient.auth.signUp({ email, password });
  if (error) {
    setAuthMessage(error.message, true);
    return;
  }
  if (data.session) {
    await openCloudWorkspace(data.session);
  } else {
    setAuthMessage("注册成功。请先在邮箱中完成验证，然后登录。");
  }
}

function currentProject() {
  return state.projects.find((project) => project.id === state.selectedProjectId) || state.projects[0];
}

function parseDateString(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function toDateString(date) {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(value, days) {
  const date = parseDateString(value);
  date.setDate(date.getDate() + days);
  return toDateString(date);
}

function endDateOf(task) {
  return addDays(task.startDate, task.duration - 1);
}

function todayString() {
  return toDateString(new Date());
}

function daysBetween(start, end) {
  return Math.round((parseDateString(end).getTime() - parseDateString(start).getTime()) / 86400000);
}

function average(values) {
  return values.length ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length) : 0;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function orderedTasks(tasks) {
  const map = new Map(tasks.map((task) => [task.id, { ...task, children: [] }]));
  const roots = [];
  for (const task of map.values()) {
    if (task.parentId && map.has(task.parentId)) {
      map.get(task.parentId).children.push(task);
    } else {
      roots.push(task);
    }
  }
  const rows = [];
  function walk(task, depth) {
    rows.push({ ...task, depth });
    task.children
      .sort((a, b) => a.startDate.localeCompare(b.startDate))
      .forEach((child) => walk(child, depth + 1));
  }
  roots.sort((a, b) => a.startDate.localeCompare(b.startDate)).forEach((task) => walk(task, 0));
  return rows;
}

function riskClass(risk) {
  return { H: "risk-h", M: "risk-m", L: "risk-l" }[risk] || "risk-l";
}

function ownersOf(project) {
  return [...new Set(project.tasks.map((task) => task.owner))].sort();
}

function render() {
  const project = currentProject();
  if (!project) return;
  if (!state.selectedDate) state.selectedDate = todayString();
  document.getElementById("projectName").textContent = project.name;
  document.getElementById("projectSummary").textContent = project.summary;
  document.getElementById("publicSummary").textContent = project.summary;
  document.getElementById("projectTopRisk").textContent = project.topRisk;
  document.getElementById("projectNextStep").textContent = project.nextStep;
  document.getElementById("projectDeadline").textContent = project.deadline;
  const remaining = daysBetween(todayString(), project.deadline);
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
  renderTaskParentOptions(project);
  renderOwnerSuggestions(project);
  renderDailyOwnerOptions(project);
  renderDailyTaskOptions(project);
}

function renderProjectSelect() {
  const select = document.getElementById("projectSelect");
  select.innerHTML = state.projects
    .map((project) => `<option value="${project.id}"${project.id === state.selectedProjectId ? " selected" : ""}>${escapeHtml(project.name)}</option>`)
    .join("");
}

function renderFilters(project) {
  const ownerSelect = document.getElementById("ownerFilter");
  const selected = ownerSelect.value || "全部";
  const owners = ["全部", ...ownersOf(project)];
  ownerSelect.innerHTML = owners
    .map((owner) => `<option value="${escapeHtml(owner)}"${owner === selected ? " selected" : ""}>${escapeHtml(owner)}</option>`)
    .join("");
}

function renderMetrics(project) {
  document.getElementById("overallProgress").textContent = `${average(project.tasks.map((task) => Number(task.actualProgress)))}%`;
  document.getElementById("plannedProgress").textContent = `${average(project.tasks.map((task) => Number(task.plannedProgress || 0)))}%`;
  const overdue = project.tasks.filter((task) => task.status !== "Closed" && endDateOf(task) < todayString()).length;
  document.getElementById("overdueCount").textContent = overdue;
}

function filteredTasks(project) {
  const owner = document.getElementById("ownerFilter").value || "全部";
  const status = document.getElementById("statusFilter").value || "全部";
  return orderedTasks(project.tasks).filter((task) => {
    return (owner === "全部" || task.owner === owner) && (status === "全部" || task.status === status);
  });
}

function renderTaskTable(project) {
  const tasks = filteredTasks(project);
  document.getElementById("taskTableBody").innerHTML = tasks.map((task) => `
    <tr>
      <td><span class="risk-pill ${riskClass(task.risk)}">${task.risk}</span></td>
      <td>
        <div class="task-name-cell ${task.depth ? "task-child" : ""}">
          ${task.depth ? `<span class="task-level" style="margin-left:${task.depth * 12}px"></span>` : ""}
          <span>${escapeHtml(task.title)}</span>
        </div>
      </td>
      <td>${escapeHtml(task.owner)}</td>
      <td>${task.startDate}</td>
      <td>${task.duration}</td>
      <td>${endDateOf(task)}</td>
      <td><span class="status-pill">${task.status}</span></td>
      <td class="progress-cell">
        <div class="progress-line plan"><span style="width:${task.plannedProgress || 0}%"></span></div>
        <small>${task.plannedProgress || 0}%</small>
      </td>
      <td class="progress-cell">
        <div class="progress-line"><span style="width:${task.actualProgress}%"></span></div>
        <small>${task.actualProgress}%</small>
      </td>
      <td>${task.completedDate || "-"}</td>
      <td>
        <div class="row-actions">
          <button class="mini-button" data-action="edit-task" data-id="${task.id}">编辑</button>
          <button class="mini-button" data-action="delete-task" data-id="${task.id}">删除</button>
        </div>
      </td>
    </tr>
  `).join("");
}

function buildTimelineDates(tasks) {
  const start = tasks.map((task) => task.startDate).sort()[0];
  const end = tasks.map((task) => endDateOf(task)).sort().at(-1);
  return Array.from({ length: daysBetween(start, end) + 1 }, (_, index) => addDays(start, index));
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
  const dates = buildTimelineDates(tasks);
  header.style.setProperty("--days", dates.length);
  rows.style.setProperty("--days", dates.length);
  header.innerHTML = '<div class="gantt-task-name">任务</div>' + dates.map((date) => `
    <div class="gantt-day">
      <button class="date-button${date === state.selectedDate ? " active" : ""}" data-date="${date}">${date.slice(5)}</button>
    </div>
  `).join("");
  rows.innerHTML = tasks.map((task) => {
    const finishedCells = Math.ceil((task.actualProgress / 100) * task.duration);
    const cells = dates.map((date) => {
      const active = date >= task.startDate && date <= endDateOf(task);
      const taskDay = active ? daysBetween(task.startDate, date) : -1;
      const classes = ["gantt-cell"];
      if (active) classes.push("active");
      if (active && taskDay < finishedCells) classes.push("done");
      if (date === todayString()) classes.push("today");
      if (date === state.selectedDate) classes.push("selected");
      return `<div class="${classes.join(" ")}" data-date="${date}" title="${escapeHtml(task.title)}"></div>`;
    }).join("");
    return `<div class="gantt-row"><div class="gantt-task-name">${escapeHtml(task.title)}</div><div class="gantt-cells">${cells}</div></div>`;
  }).join("");
}

function renderDailySummary(project) {
  const logs = project.dailyLogs.filter((log) => log.date === state.selectedDate);
  const delayed = logs.filter((log) => log.result === "延期").length;
  document.getElementById("dailySummary").innerHTML = `
    <article class="summary-card">
      <span>查看日期</span>
      <strong>${state.selectedDate}</strong>
      <p>点击甘特图日期切换。</p>
    </article>
    <article class="summary-card">
      <span>日报数量</span>
      <strong>${logs.length}</strong>
      <p>${logs.filter((log) => log.taskId).length} 条已关联任务。</p>
    </article>
    <article class="summary-card">
      <span>延期条数</span>
      <strong>${delayed}</strong>
      <p>延期记录必须填写原因。</p>
    </article>
  `;
}

function renderDailyTable(project) {
  const taskMap = new Map(project.tasks.map((task) => [task.id, task.title]));
  const logs = project.dailyLogs.filter((log) => log.date === state.selectedDate);
  document.getElementById("dailyTableBody").innerHTML = logs.length ? logs.map((log) => `
    <tr>
      <td>${escapeHtml(log.owner)}</td>
      <td>${escapeHtml(log.planText)}</td>
      <td>${escapeHtml(log.actualText)}</td>
      <td>${escapeHtml(taskMap.get(log.taskId) || "-")}</td>
      <td>${log.progressAfter}%</td>
      <td><span class="status-pill">${log.result}</span></td>
      <td>${escapeHtml(log.delayReason || "-")}</td>
      <td>
        <div class="row-actions">
          <button class="mini-button" data-action="edit-log" data-id="${log.id}">编辑</button>
          <button class="mini-button" data-action="delete-log" data-id="${log.id}">删除</button>
        </div>
      </td>
    </tr>
  `).join("") : '<tr><td colspan="8" class="empty-state">这一天还没有日报记录。</td></tr>';
}

function renderTaskParentOptions(project) {
  document.getElementById("taskParent").innerHTML = '<option value="">无父任务</option>' + orderedTasks(project.tasks)
    .map((task) => `<option value="${task.id}">${"&nbsp;".repeat(task.depth * 2)}${escapeHtml(task.title)}</option>`)
    .join("");
}

function renderOwnerSuggestions(project) {
  document.getElementById("ownerSuggestions").innerHTML = ownersOf(project)
    .map((owner) => `<option value="${escapeHtml(owner)}"></option>`)
    .join("");
}

function renderDailyOwnerOptions(project) {
  const owners = ownersOf(project);
  document.getElementById("dailyOwner").innerHTML = owners.length
    ? owners.map((owner) => `<option value="${escapeHtml(owner)}">${escapeHtml(owner)}</option>`).join("")
    : '<option value="">暂无负责人</option>';
}

function renderDailyTaskOptions(project) {
  document.getElementById("dailyTask").innerHTML = project.tasks
    .map((task) => `<option value="${task.id}">${escapeHtml(task.title)}</option>`)
    .join("");
}

function openProjectEditor(project) {
  document.getElementById("projectForm").reset();
  document.getElementById("projectIdInput").value = project?.id || "";
  document.getElementById("projectModalTitle").textContent = project ? "项目设置" : "新增项目";
  document.getElementById("projectNameInput").value = project?.name || "";
  document.getElementById("projectDeadlineInput").value = project?.deadline || todayString();
  document.getElementById("projectSummaryInput").value = project?.summary || "";
  document.getElementById("projectTopRiskInput").value = project?.topRisk || "";
  document.getElementById("projectNextStepInput").value = project?.nextStep || "";
  document.getElementById("projectModal").showModal();
}

function openTaskEditor(task) {
  const project = currentProject();
  document.getElementById("taskForm").reset();
  renderTaskParentOptions(project);
  document.getElementById("taskModalTitle").textContent = task ? "编辑任务" : "新增任务";
  document.getElementById("taskIdInput").value = task?.id || "";
  document.getElementById("taskParent").value = task?.parentId || "";
  document.getElementById("taskRisk").value = task?.risk || "M";
  document.getElementById("taskTitle").value = task?.title || "";
  document.getElementById("taskOwner").value = task?.owner || ownersOf(project)[0] || "";
  document.getElementById("taskStart").value = task?.startDate || state.selectedDate || todayString();
  document.getElementById("taskDuration").value = task?.duration || 3;
  document.getElementById("taskStatus").value = task?.status || "Open";
  document.getElementById("taskPlannedProgress").value = task?.plannedProgress ?? 0;
  document.getElementById("taskProgress").value = task?.actualProgress ?? 0;
  document.getElementById("taskCompletedDate").value = task?.completedDate || "";
  document.getElementById("taskNote").value = task?.note || "";
  document.getElementById("taskModal").showModal();
}

function openDailyEditor(log) {
  const project = currentProject();
  document.getElementById("dailyForm").reset();
  renderDailyOwnerOptions(project);
  renderDailyTaskOptions(project);
  document.getElementById("dailyModalTitle").textContent = log ? "编辑日报" : "新增日报";
  document.getElementById("dailyIdInput").value = log?.id || "";
  document.getElementById("dailyDate").value = log?.date || state.selectedDate || todayString();
  document.getElementById("dailyOwner").value = log?.owner || ownersOf(project)[0] || "";
  document.getElementById("dailyTask").value = String(log?.taskId || project.tasks[0]?.id || "");
  document.getElementById("dailyPlanText").value = log?.planText || "";
  document.getElementById("dailyActualText").value = log?.actualText || "";
  document.getElementById("dailyProgressAfter").value = log?.progressAfter ?? 0;
  document.getElementById("dailyResult").value = log?.result || "完成";
  document.getElementById("dailyDelayReason").value = log?.delayReason || "";
  document.getElementById("dailyModal").showModal();
}

function upsertProject(formData) {
  const id = Number(formData.id);
  if (id) {
    Object.assign(state.projects.find((project) => project.id === id), formData);
    return;
  }
  const project = { ...formData, id: Date.now(), tasks: [], dailyLogs: [] };
  state.projects.push(project);
  state.selectedProjectId = project.id;
}

function upsertTask(formData) {
  const project = currentProject();
  const id = Number(formData.id);
  const task = {
    id: id || Date.now(),
    parentId: formData.parentId ? Number(formData.parentId) : null,
    risk: formData.risk,
    title: formData.title,
    owner: formData.owner,
    startDate: formData.startDate,
    duration: Number(formData.duration),
    status: formData.status,
    plannedProgress: Number(formData.plannedProgress),
    actualProgress: Number(formData.actualProgress),
    completedDate: formData.completedDate,
    note: formData.note
  };
  if (task.id === task.parentId) task.parentId = null;
  const index = project.tasks.findIndex((item) => item.id === id);
  if (index >= 0) project.tasks[index] = task;
  else project.tasks.push(task);
}

function applyLogToTask(project, log) {
  const task = project.tasks.find((item) => item.id === Number(log.taskId));
  if (!task) return;
  task.actualProgress = Number(log.progressAfter);
  if (task.actualProgress >= 100) {
    task.status = "Closed";
    task.actualProgress = 100;
    task.completedDate = log.date;
  } else if (task.actualProgress > 0) {
    task.status = "Ongoing";
    task.completedDate = "";
  } else {
    task.status = "Open";
    task.completedDate = "";
  }
}

function recomputeTaskFromLogs(project, taskId) {
  const logs = project.dailyLogs
    .filter((log) => Number(log.taskId) === Number(taskId))
    .sort((a, b) => a.date.localeCompare(b.date));
  if (logs.length) applyLogToTask(project, logs.at(-1));
}

function upsertLog(formData) {
  const project = currentProject();
  const id = Number(formData.id);
  const log = {
    id: id || Date.now(),
    date: formData.date,
    owner: formData.owner,
    taskId: Number(formData.taskId),
    planText: formData.planText,
    actualText: formData.actualText,
    progressAfter: Number(formData.progressAfter),
    result: formData.result,
    delayReason: formData.delayReason
  };
  const index = project.dailyLogs.findIndex((item) => item.id === id);
  if (index >= 0) {
    const previousTaskId = project.dailyLogs[index].taskId;
    project.dailyLogs[index] = log;
    if (previousTaskId !== log.taskId) recomputeTaskFromLogs(project, previousTaskId);
  } else {
    project.dailyLogs.push(log);
  }
  applyLogToTask(project, log);
}

function deleteTask(project, id) {
  const ids = new Set([id]);
  let added = true;
  while (added) {
    added = false;
    project.tasks.forEach((task) => {
      if (task.parentId && ids.has(task.parentId) && !ids.has(task.id)) {
        ids.add(task.id);
        added = true;
      }
    });
  }
  project.tasks = project.tasks.filter((task) => !ids.has(task.id));
  project.dailyLogs = project.dailyLogs.filter((log) => !ids.has(Number(log.taskId)));
}

function bindEvents() {
  document.getElementById("localPreviewButton").addEventListener("click", startLocalPreview);
  document.getElementById("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await signIn(document.getElementById("loginEmail").value.trim(), document.getElementById("loginPassword").value);
  });
  document.getElementById("signupForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await signUp(document.getElementById("signupEmail").value.trim(), document.getElementById("signupPassword").value);
  });
  document.getElementById("logoutButton").addEventListener("click", async () => {
    if (appMode === "local") {
      showOnlyCard(configuredForCloud() ? "authCard" : "setupCard");
      return;
    }
    await cloudClient.auth.signOut();
  });
  document.getElementById("projectSelect").addEventListener("change", (event) => {
    state.selectedProjectId = Number(event.target.value);
    state.selectedDate = currentProject().tasks[0]?.startDate || todayString();
    persistState();
    render();
  });
  document.getElementById("openProjectModal").addEventListener("click", () => openProjectEditor(currentProject()));
  document.getElementById("createProjectButton").addEventListener("click", () => openProjectEditor(null));
  document.getElementById("openTaskModal").addEventListener("click", () => openTaskEditor(null));
  document.getElementById("openDailyModal").addEventListener("click", () => openDailyEditor(null));
  document.getElementById("ownerFilter").addEventListener("change", render);
  document.getElementById("statusFilter").addEventListener("change", render);

  document.querySelectorAll("[data-close]").forEach((button) => {
    button.addEventListener("click", () => document.getElementById(button.dataset.close).close());
  });

  document.getElementById("projectForm").addEventListener("submit", (event) => {
    event.preventDefault();
    upsertProject({
      id: document.getElementById("projectIdInput").value,
      name: document.getElementById("projectNameInput").value.trim(),
      deadline: document.getElementById("projectDeadlineInput").value,
      summary: document.getElementById("projectSummaryInput").value.trim(),
      topRisk: document.getElementById("projectTopRiskInput").value.trim(),
      nextStep: document.getElementById("projectNextStepInput").value.trim()
    });
    persistState();
    document.getElementById("projectModal").close();
    render();
  });

  document.getElementById("taskForm").addEventListener("submit", (event) => {
    event.preventDefault();
    upsertTask({
      id: document.getElementById("taskIdInput").value,
      parentId: document.getElementById("taskParent").value,
      risk: document.getElementById("taskRisk").value,
      title: document.getElementById("taskTitle").value.trim(),
      owner: document.getElementById("taskOwner").value.trim(),
      startDate: document.getElementById("taskStart").value,
      duration: document.getElementById("taskDuration").value,
      status: document.getElementById("taskStatus").value,
      plannedProgress: document.getElementById("taskPlannedProgress").value,
      actualProgress: document.getElementById("taskProgress").value,
      completedDate: document.getElementById("taskCompletedDate").value,
      note: document.getElementById("taskNote").value.trim()
    });
    persistState();
    document.getElementById("taskModal").close();
    render();
  });

  document.getElementById("dailyForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const result = document.getElementById("dailyResult").value;
    const delayReason = document.getElementById("dailyDelayReason").value.trim();
    if (result === "延期" && !delayReason) {
      alert("日报结果为延期时，必须填写延期原因。");
      return;
    }
    upsertLog({
      id: document.getElementById("dailyIdInput").value,
      date: document.getElementById("dailyDate").value,
      owner: document.getElementById("dailyOwner").value,
      taskId: document.getElementById("dailyTask").value,
      planText: document.getElementById("dailyPlanText").value.trim(),
      actualText: document.getElementById("dailyActualText").value.trim(),
      progressAfter: document.getElementById("dailyProgressAfter").value,
      result,
      delayReason
    });
    state.selectedDate = document.getElementById("dailyDate").value;
    persistState();
    document.getElementById("dailyModal").close();
    render();
  });

  document.getElementById("taskTableBody").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const id = Number(button.dataset.id);
    if (button.dataset.action === "edit-task") {
      openTaskEditor(currentProject().tasks.find((task) => task.id === id));
    } else if (button.dataset.action === "delete-task") {
      deleteTask(currentProject(), id);
      persistState();
      render();
    }
  });

  document.getElementById("dailyTableBody").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    const project = currentProject();
    const id = Number(button.dataset.id);
    if (button.dataset.action === "edit-log") {
      openDailyEditor(project.dailyLogs.find((log) => log.id === id));
    } else if (button.dataset.action === "delete-log") {
      const log = project.dailyLogs.find((item) => item.id === id);
      project.dailyLogs = project.dailyLogs.filter((item) => item.id !== id);
      recomputeTaskFromLogs(project, log.taskId);
      persistState();
      render();
    }
  });

  ["ganttHeader", "ganttRows"].forEach((id) => {
    document.getElementById(id).addEventListener("click", (event) => {
      const dated = event.target.closest("[data-date]");
      if (!dated) return;
      state.selectedDate = dated.dataset.date;
      persistState();
      render();
    });
  });
}

initialize();
