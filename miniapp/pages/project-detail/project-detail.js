const supabase = require("../../utils/supabase");
const models = require("../../utils/models");
const date = require("../../utils/date");

Page({
  data: {
    isCreate: false,
    isEditing: false,
    saving: false,
    projectId: "",
    project: {},
    form: {
      name: "",
      deadline: date.today(),
      summary: "",
      topRisk: "",
      nextStep: ""
    },
    tasks: []
  },

  onLoad(options) {
    if (!supabase.getSession()?.access_token) {
      wx.redirectTo({ url: "/pages/login/login" });
      return;
    }
    if (options.mode === "create") {
      this.setData({ isCreate: true, isEditing: true });
      return;
    }
    this.setData({ projectId: options.id || "", isEditing: options.edit === "1" });
    this.loadProject();
  },

  async loadProject() {
    try {
      wx.showLoading({ title: "加载中" });
      const projects = await supabase.select("projects", { id: supabase.eq(this.data.projectId) });
      if (!projects.length) throw new Error("项目不存在或无权限访问。");
      const project = models.toProject(projects[0]);
      const tasks = (await supabase.select("tasks", {
        project_id: supabase.eq(project.id),
        order: "display_order.asc"
      })).map(models.toTask);
      const progress = (await supabase.select("task_progress_entries", {
        project_id: supabase.eq(project.id),
        order: "entry_date.asc"
      })).map(models.toProgress);
      const taskCards = tasks.map((task) => {
        const latest = models.latestProgress(task.id, progress);
        return Object.assign(task, latest, { isOverdue: date.isOverdue(task) });
      });
      const latestEntries = taskCards.map((task) => ({ plannedProgress: task.plannedProgress, actualProgress: task.actualProgress }));
      const detail = Object.assign(project, {
        remainingText: date.remainingText(project.deadline),
        isLate: date.daysBetween(date.today(), project.deadline) < 0,
        plannedProgress: models.average(latestEntries.map((entry) => entry.plannedProgress)),
        actualProgress: models.average(latestEntries.map((entry) => entry.actualProgress))
      });
      this.setData({
        project: detail,
        form: {
          name: project.name,
          deadline: project.deadline,
          summary: project.summary,
          topRisk: project.topRisk,
          nextStep: project.nextStep
        },
        tasks: taskCards
      });
    } catch (error) {
      wx.showModal({ title: "加载失败", content: error.message, showCancel: false });
    } finally {
      wx.hideLoading();
    }
  },

  onDeadlineChange(event) {
    this.setData({ "form.deadline": event.detail.value });
  },

  editProject() {
    this.setData({ isEditing: true });
  },

  cancelEdit() {
    if (this.data.isCreate) {
      wx.navigateBack();
      return;
    }
    this.setData({ isEditing: false });
  },

  async saveProject(event) {
    const values = Object.assign({}, this.data.form, event.detail.value);
    if (!values.name || !values.deadline || !values.summary) {
      wx.showToast({ title: "请填写必填项", icon: "none" });
      return;
    }
    values.isPublic = this.data.isCreate ? false : this.data.project.isPublic;
    values.publicSlug = this.data.isCreate ? "" : this.data.project.publicSlug;
    const session = supabase.getSession();
    const row = models.projectToRow(values, session.user.id);
    this.setData({ saving: true });
    try {
      if (this.data.isCreate) {
        const created = await supabase.insert("projects", row);
        wx.redirectTo({ url: `/pages/project-detail/project-detail?id=${created[0].id}` });
      } else {
        await supabase.update("projects", this.data.projectId, row);
        this.setData({ isEditing: false });
        this.loadProject();
      }
    } catch (error) {
      wx.showModal({ title: "保存失败", content: error.message, showCancel: false });
    } finally {
      this.setData({ saving: false });
    }
  },

  createTask() {
    wx.navigateTo({ url: `/pages/task-form/task-form?projectId=${this.data.projectId}` });
  },

  editTask(event) {
    wx.navigateTo({ url: `/pages/task-form/task-form?projectId=${this.data.projectId}&taskId=${event.currentTarget.dataset.id}` });
  }
});
