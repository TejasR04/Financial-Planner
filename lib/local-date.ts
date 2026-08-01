function localDateParts(date: Date) {
  return {
    year: date.getFullYear(),
    month: String(date.getMonth() + 1).padStart(2, "0"),
    day: String(date.getDate()).padStart(2, "0"),
  };
}

export function localDateKey(date = new Date()) {
  const { year, month, day } = localDateParts(date);
  return `${year}-${month}-${day}`;
}

export function localMonthKey(date = new Date()) {
  const { year, month } = localDateParts(date);
  return `${year}-${month}`;
}
