let authStatus = null;


export function setAccessContext(status) {
  authStatus =
    status && typeof status === "object"
      ? { ...status }
      : null;
}


export function getAccessContext() {
  return authStatus;
}


export function hasOwnerAccess() {
  if (!authStatus) {
    return false;
  }

  if (authStatus.enabled === false) {
    return true;
  }

  return (
    authStatus.authenticated === true &&
    String(
      authStatus.role || ""
    ).trim().toUpperCase() === "OWNER"
  );
}



export function hasTradingAccess() {
  if (!authStatus) {
    return false;
  }

  if (authStatus.enabled === false) {
    return true;
  }

  if (authStatus.authenticated !== true) {
    return false;
  }

  const role = String(
    authStatus.role || "",
  ).trim().toUpperCase();

  return (
    role === "OWNER" ||
    role === "BETA"
  );
}
