const supabase = require("../../utils/supabase");
const models = require("../../utils/models");
const date = require("../../utils/date");

Page({
  data: {
    today: date.today(),
    projects: [],
    projectNames: [],
    selectedProjectIndex: 0,
    currentProject: {},
    openTasks: [],
    overdueTasks: []
  },

  onShow() {
    if (!supabase.getSession()?.access_token) {
      wx.redirectTo({ url: "/pages/login/login" });
      return;
    }
    this.loadData();
  },

  async loadData() {
    try {
      wx.showLoading({ title: "加载中" });
      const projectRows = await supabase.select("projects", { order: "created_at.asc" });
      const projects = await Promise.all(projectRows.map((row) => this.buildProjectCard(models.toProject(row))));
      const storedProjectId = wx.getStorageSync("selectedProjectId");
      const index = Math.max(0, projects.findIndex((project) => project.id === storedProjectId));
      this.applyProject(projects, index);
    } catch (error) {
      wx.showModal({ title: "加载失败", content: error.message, showCancel: false });
    } finally {
      wx.hideLoading();
    }
  },

  async buildProjectCard(project) {
    const tasks = (await supabase.select("tasks", {
      project_id: supabase.eq(project.id),
      order: "display_order.asc"
    })).map(models.toTask);
    const progress = (await supabase.select("task_progress_entries", {
      project_id: supabase.eq(project.id),
      order: "entry_date.asc"
    })).map(models.toProgress);
    const latest = tasks.map((task) => models.latestProgress(task.id, progress));
    return Object.assign(project, {
      plannedProgress: models.average(latest.map((entry) => entry.plannedProgress)),
      actualProgress: models.average(latest.map((entry) => entry.actualProgress)),
      tasks: tasks.map((task) => {
        const entry = models.latestProgress(task.id, progress);
        return Object.assign(task, entry);
      })
    });
  },

  applyProject(projects, index) {
    const currentProject = projects[index] || {};
    const openTasks = (currentProject.tasks || []).filter((task) => task.status !== "Closed");
    const overdueTasks = openTasks.filter(date.isOverdue);
    if (currentProject.id) wx.setStorageSync("selectedProjectId", currentProject.id);
    this.setData({
      projects,
      projectNames: projects.map((project) => project.name),
      selectedProjectIndex: index,
      currentProject,
      openTasks,
      overdueTasks
    });
  },

  onProjectChange(event) {
    this.applyProject(this.data.projects, Number(event.detail.value));
  },

  openCurrentProject() {
    if (!this.data.currentProject.id) return;
    wx.navigateTo({ url: `/pages/project-detail/project-detail?id=${this.data.currentProject.id}` });
  },

  openProject(event) {
    wx.navigateTo({ url: `/pages/project-detail/project-detail?id=${event.currentTarget.dataset.id}` });
  },

  createProject() {
    wx.navigateTo({ url: "/pages/project-detail/project-detail?mode=create" });
  },

  openTask(event) {
    wx.navigateTo({ url: `/pages/task-form/task-form?projectId=${this.data.currentProject.id}&taskId=${event.currentTarget.dataset.id}` });
  },

  openDailyForm() {
    wx.navigateTo({ url: `/pages/daily-form/daily-form?projectId=${this.data.currentProject.id}` });
  },

  openDailyForTask(event) {
    if (!this.data.currentProject.id) return;
    wx.navigateTo({ url: `/pages/daily-form/daily-form?projectId=${this.data.currentProject.id}&taskId=${event.currentTarget.dataset.id}` });
  },

  async logout() {
    try {
      await supabase.signOut();
    } catch (error) {
      supabase.clearSession();
    }
    getApp().clearSession();
    wx.redirectTo({ url: "/pages/login/login" });
  }
});
