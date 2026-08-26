function createAuthControl(username) {
    if (document.getElementById("bxkAuthControl")) {
        return;
    }

    const control = document.createElement("div");
    control.id = "bxkAuthControl";
    control.className = "bxk-auth-control";

    const user = document.createElement("span");
    user.className = "bxk-auth-user";
    user.textContent = username || "BXK";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "bxk-auth-logout";
    button.textContent = "SIGN OUT";

    button.addEventListener("click", async () => {
        button.disabled = true;
        button.textContent = "SIGNING OUT...";

        try {
            await fetch("/api/auth/logout", {
                method: "POST"
            });
        } finally {
            window.location.replace("/login");
        }
    });

    control.appendChild(user);
    control.appendChild(button);

    document.body.appendChild(control);
}


export async function initializeAuthUi() {
    try {
        const response = await fetch(
            "/api/auth/status",
            {
                cache: "no-store"
            }
        );

        if (!response.ok) {
            return null;
        }

        const data = await response.json();

        if (data.enabled && !data.authenticated) {
            window.location.replace("/login");
            return data;
        }

        if (data.enabled && data.authenticated) {
            createAuthControl(data.username);
        }

        return data;

    } catch (error) {
        console.error(
            "BXK auth UI initialization failed:",
            error
        );

        return null;
    }
}
