const supabase = require("../../utils/supabase");
const models = require("../../utils/models");
const date = require("../../utils/date");

Page({
  data: {
    projectId: "",
    taskId: "",
    saving: false,
    tasks: [],
    parentNames: ["无父任务"],
    parentIndex: 0,
    riskList: ["H", "M", "L"],
    riskIndex: 1,
    statusList: ["Open", "Ongoing", "Closed"],
    statusIndex: 0,
    form: {
      parentId: "",
      risk: "M",
      title: "",
      responsible: "",
      startDate: date.today(),
      duration: 1,
      status: "Open",
      completedDate: "",
      note: "",
      plannedProgress: 0,
      actualProgress: 0
    }
  },

  onLoad(options) {
    if (!supabase.getSession()?.access_token) {
      wx.redirectTo({ url: "/pages/login/login" });
      return;
    }
    this.setData({ projectId: options.projectId || "", taskId: options.taskId || "" });
    this.loadTask();
  },

  async loadTask() {
    try {
      wx.showLoading({ title: "加载中" });
      const tasks = (await supabase.select("tasks", {
        project_id: supabase.eq(this.data.projectId),
        order: "display_order.asc"
      })).map(models.toTask);
      const selectableParents = tasks.filter((task) => task.id !== this.data.taskId);
      const parentNames = ["无父任务"].concat(selectableParents.map((task) => task.title));
      let form = this.data.form;
      if (this.data.taskId) {
        const current = tasks.find((task) => task.id === this.data.taskId);
        const progress = (await supabase.select("task_progress_entries", {
          task_id: supabase.eq(this.data.taskId),
          order: "entry_date.asc"
        })).map(models.toProgress);
        const latest = models.latestProgress(this.data.taskId, progress);
        form = Object.assign({}, current, {
          plannedProgress: latest.plannedProgress,
          actualProgress: latest.actualProgress
        });
      }
      this.setData({
        tasks: selectableParents,
        parentNames,
        parentIndex: Math.max(0, selectableParents.findIndex((task) => task.id === form.parentId) + 1),
        riskIndex: Math.max(0, this.data.riskList.indexOf(form.risk)),
        statusIndex: Math.max(0, this.data.statusList.indexOf(form.status)),
        form
      });
    } catch (error) {
      wx.showModal({ title: "加载失败", content: error.message, showCancel: false });
    } finally {
      wx.hideLoading();
    }
  },

  onParentChange(event) {
    const index = Number(event.detail.value);
    this.setData({ parentIndex: index, "form.parentId": index === 0 ? "" : this.data.tasks[index - 1].id });
  },

  onRiskChange(event) {
    const index = Number(event.detail.value);
    this.setData({ riskIndex: index, "form.risk": this.data.riskList[index] });
  },

  onStatusChange(event) {
    const index = Number(event.detail.value);
    this.setData({ statusIndex: index, "form.status": this.data.statusList[index] });
  },

  onStartDateChange(event) {
    this.setData({ "form.startDate": event.detail.value });
  },

  onCompletedDateChange(event) {
    this.setData({ "form.completedDate": event.detail.value });
  },

  async saveTask(event) {
    const values = Object.assign({}, this.data.form, event.detail.value, {
      parentId: this.data.form.parentId,
      risk: this.data.form.risk,
      status: this.data.form.status,
      startDate: this.data.form.startDate,
      completedDate: this.data.form.completedDate
    });
    if (!values.title || !values.responsible || !values.startDate) {
      wx.showToast({ title: "请填写必填项", icon: "none" });
      return;
    }
    const session = supabase.getSession();
    const row = models.taskToRow(values, session.user.id, this.data.projectId);
    this.setData({ saving: true });
    try {
      let taskId = this.data.taskId;
      if (taskId) {
        await supabase.update("tasks", taskId, row);
      } else {
        const created = await supabase.insert("tasks", row);
        taskId = created[0].id;
      }
      await supabase.upsert("task_progress_entries", models.progressToRow({
        entryDate: date.today(),
        plannedProgress: values.plannedProgress,
        actualProgress: values.actualProgress
      }, session.user.id, this.data.projectId, taskId), "task_id,entry_date");
      wx.navigateBack();
    } catch (error) {
      wx.showModal({ title: "保存失败", content: error.message, showCancel: false });
    } finally {
      this.setData({ saving: false });
    }
  }
});
