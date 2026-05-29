const supabase = require("../../utils/supabase");
const models = require("../../utils/models");
const date = require("../../utils/date");

Page({
  data: {
    saving: false,
    projects: [],
    tasks: [],
    projectNames: [],
    taskNames: [],
    projectIndex: 0,
    taskIndex: 0,
    resultList: ["完成", "部分完成", "延期"],
    resultIndex: 1,
    form: {
      projectId: "",
      taskId: "",
      date: date.today(),
      responsible: "",
      planText: "",
      actualText: "",
      plannedProgress: 0,
      actualProgress: 0,
      result: "部分完成",
      delayReason: ""
    }
  },

  onLoad(options) {
    if (!supabase.getSession()?.access_token) {
      wx.redirectTo({ url: "/pages/login/login" });
      return;
    }
    this.loadProjects(options.projectId || "", options.taskId || "");
  },

  async loadProjects(projectId, taskId) {
    try {
      wx.showLoading({ title: "加载中" });
      const projects = (await supabase.select("projects", { order: "created_at.asc" })).map(models.toProject);
      const projectIndex = Math.max(0, projects.findIndex((project) => project.id === projectId));
      this.setData({
        projects,
        projectNames: projects.map((project) => project.name),
        projectIndex
      });
      await this.loadTasks(projects[projectIndex]?.id || "", taskId);
    } catch (error) {
      wx.showModal({ title: "加载失败", content: error.message, showCancel: false });
    } finally {
      wx.hideLoading();
    }
  },

  async loadTasks(projectId, taskId) {
    if (!projectId) return;
    const tasks = (await supabase.select("tasks", {
      project_id: supabase.eq(projectId),
      order: "display_order.asc"
    })).map(models.toTask);
    const taskIndex = Math.max(0, tasks.findIndex((task) => task.id === taskId));
    this.setData({
      tasks,
      taskNames: tasks.map((item) => item.title),
      taskIndex,
      "form.projectId": projectId
    });
    await this.applyTaskSelection(taskIndex, tasks);
  },

  async onProjectChange(event) {
    const projectIndex = Number(event.detail.value);
    const projectId = this.data.projects[projectIndex]?.id || "";
    this.setData({ projectIndex, taskIndex: 0 });
    await this.loadTasks(projectId, "");
  },

  async onTaskChange(event) {
    const taskIndex = Number(event.detail.value);
    await this.applyTaskSelection(taskIndex);
  },

  async applyTaskSelection(taskIndex, sourceTasks) {
    const tasks = sourceTasks || this.data.tasks;
    const task = tasks[taskIndex] || {};
    let latest = { plannedProgress: 0, actualProgress: 0 };
    if (task.id) latest = await this.loadLatestProgress(task.id);
    this.setData({
      taskIndex,
      "form.taskId": task.id || "",
      "form.responsible": task.responsible || "",
      "form.plannedProgress": latest.plannedProgress,
      "form.actualProgress": latest.actualProgress
    });
  },

  async loadLatestProgress(taskId) {
    const rows = (await supabase.select("task_progress_entries", {
      task_id: supabase.eq(taskId),
      order: "entry_date.desc",
      limit: 1
    })).map(models.toProgress);
    return rows[0] || { plannedProgress: 0, actualProgress: 0 };
  },

  onDateChange(event) {
    this.setData({ "form.date": event.detail.value });
  },

  onResultChange(event) {
    const resultIndex = Number(event.detail.value);
    this.setData({ resultIndex, "form.result": this.data.resultList[resultIndex] });
  },

  async saveDaily(event) {
    const values = Object.assign({}, this.data.form, event.detail.value, {
      projectId: this.data.form.projectId,
      taskId: this.data.form.taskId,
      date: this.data.form.date,
      result: this.data.form.result
    });
    if (!values.projectId || !values.taskId || !values.responsible || !values.planText || !values.actualText) {
      wx.showToast({ title: "请填写必填项", icon: "none" });
      return;
    }
    if (values.result === "延期" && !values.delayReason) {
      wx.showToast({ title: "延期必须填写原因", icon: "none" });
      return;
    }

    const session = supabase.getSession();
    this.setData({ saving: true });
    try {
      await supabase.upsert("daily_logs", models.dailyLogToRow(values, session.user.id, values.projectId), "task_id,log_date");
      await supabase.upsert("task_progress_entries", models.progressToRow({
        entryDate: values.date,
        plannedProgress: values.plannedProgress,
        actualProgress: values.actualProgress
      }, session.user.id, values.projectId, values.taskId), "task_id,entry_date");
      await supabase.update("tasks", values.taskId, {
        status: Number(values.actualProgress) === 100 ? "Closed" : Number(values.actualProgress) > 0 ? "Ongoing" : "Open",
        completed_date: Number(values.actualProgress) === 100 ? values.date : null
      });
      wx.navigateBack();
    } catch (error) {
      wx.showModal({ title: "保存失败", content: error.message, showCancel: false });
    } finally {
      this.setData({ saving: false });
    }
  }
});
