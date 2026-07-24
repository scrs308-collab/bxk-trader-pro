export const el = (id) => document.getElementById(id);

export function setText(id, value, fallback = "--") {
  const element = el(id);

  if (!element) {
    return;
  }

  const isMissing =
    value === null ||
    value === undefined ||
    value === "";

  element.textContent = isMissing
    ? fallback
    : value;
}

export function safeNumber(value, fallback = 0) {
  const number = Number(value);

  return Number.isFinite(number)
    ? number
    : fallback;
}

export function nowTime() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatMoney(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  return `$${number.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

export function formatSignedMoney(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  const sign = number > 0 ? "+" : "";

  return `${sign}$${number.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })}`;
}

export function formatNumber(value, decimals = 2) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  return number.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}

export function formatSignedNumber(value, decimals = 2) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "--";
  }

  const sign = number > 0 ? "+" : "";

  return `${sign}${number.toFixed(decimals)}`;
}

export function getStatusIcon(value) {
  const text = String(value || "").toLowerCase();

  if (text.includes("bull")) return "📈";
  if (text.includes("bear")) return "📉";

  if (
    text.includes("ideal") ||
    text.includes("healthy") ||
    text.includes("good") ||
    text.includes("trade")
  ) {
    return "🟢";
  }

  if (
    text.includes("outside") ||
    text.includes("avoid") ||
    text.includes("no trade")
  ) {
    return "🔴";
  }

  if (
    text.includes("high") ||
    text.includes("elevated")
  ) {
    return "⚡";
  }

  if (text.includes("low")) return "🟡";

  if (
    text.includes("normal") ||
    text.includes("neutral") ||
    text.includes("mixed")
  ) {
    return "⚪";
  }

  if (text.includes("wait")) return "●";

  return "•";
}
