function toProject(row) {
  return {
    id: row.id,
    ownerId: row.owner_id,
    name: row.name,
    deadline: row.deadline,
    summary: row.summary || "",
    topRisk: row.top_risk || "",
    nextStep: row.next_step || "",
    isPublic: Boolean(row.is_public),
    publicSlug: row.public_slug || "",
    createdAt: row.created_at
  };
}

function projectToRow(project, ownerId) {
  return {
    owner_id: ownerId,
    name: project.name,
    deadline: project.deadline,
    summary: project.summary || "",
    top_risk: project.topRisk || "",
    next_step: project.nextStep || "",
    is_public: Boolean(project.isPublic),
    public_slug: project.publicSlug || makeSlug(project.name)
  };
}

function toTask(row) {
  return {
    id: row.id,
    ownerId: row.owner_id,
    projectId: row.project_id,
    parentId: row.parent_id || "",
    risk: row.risk || "M",
    title: row.title,
    responsible: row.responsible || "",
    startDate: row.start_date,
    duration: Number(row.duration || 1),
    status: row.status || "Open",
    completedDate: row.completed_date || "",
    note: row.note || "",
    displayOrder: row.display_order || 0
  };
}

function taskToRow(task, ownerId, projectId) {
  return {
    owner_id: ownerId,
    project_id: projectId,
    parent_id: task.parentId || null,
    risk: task.risk || "M",
    title: task.title,
    responsible: task.responsible || "",
    start_date: task.startDate,
    duration: Number(task.duration || 1),
    status: task.status || "Open",
    completed_date: task.completedDate || null,
    note: task.note || "",
    display_order: task.displayOrder || Date.now()
  };
}

function toProgress(row) {
  return {
    id: row.id,
    ownerId: row.owner_id,
    projectId: row.project_id,
    taskId: row.task_id,
    entryDate: row.entry_date,
    plannedProgress: Number(row.planned_progress || 0),
    actualProgress: Number(row.actual_progress || 0)
  };
}

function progressToRow(entry, ownerId, projectId, taskId) {
  return {
    owner_id: ownerId,
    project_id: projectId,
    task_id: taskId,
    entry_date: entry.entryDate,
    planned_progress: Number(entry.plannedProgress || 0),
    actual_progress: Number(entry.actualProgress || 0)
  };
}

function toDailyLog(row) {
  return {
    id: row.id,
    ownerId: row.owner_id,
    projectId: row.project_id,
    taskId: row.task_id,
    date: row.log_date,
    responsible: row.responsible || "",
    planText: row.plan_text || "",
    actualText: row.actual_text || "",
    plannedProgress: Number(row.planned_progress || 0),
    actualProgress: Number(row.actual_progress || 0),
    result: row.result || "部分完成",
    delayReason: row.delay_reason || ""
  };
}

function dailyLogToRow(log, ownerId, projectId) {
  return {
    owner_id: ownerId,
    project_id: projectId,
    task_id: log.taskId,
    log_date: log.date,
    responsible: log.responsible || "",
    plan_text: log.planText || "",
    actual_text: log.actualText || "",
    planned_progress: Number(log.plannedProgress || 0),
    actual_progress: Number(log.actualProgress || 0),
    result: log.result || "部分完成",
    delay_reason: log.delayReason || ""
  };
}

function latestProgress(taskId, entries) {
  return entries
    .filter((entry) => entry.taskId === taskId)
    .sort((a, b) => a.entryDate.localeCompare(b.entryDate))
    .pop() || { plannedProgress: 0, actualProgress: 0 };
}

function average(values) {
  return values.length ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length) : 0;
}

function makeSlug(name) {
  const base = String(name || "project").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "project";
  return `${base}-${Date.now().toString(36)}`;
}

module.exports = {
  average,
  dailyLogToRow,
  latestProgress,
  progressToRow,
  projectToRow,
  taskToRow,
  toDailyLog,
  toProgress,
  toProject,
  toTask
};
