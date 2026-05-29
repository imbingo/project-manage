function parseDate(value) {
  const parts = String(value || "").split("-").map(Number);
  return new Date(parts[0], parts[1] - 1, parts[2]);
}

function today() {
  const date = new Date();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function addDays(value, count) {
  const date = parseDate(value);
  date.setDate(date.getDate() + count);
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

function daysBetween(start, end) {
  return Math.round((parseDate(end).getTime() - parseDate(start).getTime()) / 86400000);
}

function taskEndDate(task) {
  return addDays(task.startDate, Number(task.duration || 1) - 1);
}

function remainingText(deadline) {
  const days = daysBetween(today(), deadline);
  return days >= 0 ? `剩余 ${days} 天` : `逾期 ${Math.abs(days)} 天`;
}

function isOverdue(task) {
  return task.status !== "Closed" && taskEndDate(task) < today();
}

module.exports = {
  addDays,
  daysBetween,
  isOverdue,
  remainingText,
  taskEndDate,
  today
};
