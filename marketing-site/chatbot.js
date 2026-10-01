(() => {
  const PREVIEW_HOST =
    "bxk-marketing-preview-production.up.railway.app";

  const apiBase =
    window.location.hostname === PREVIEW_HOST
      ? "https://bxk-trader-pro-preview-production.up.railway.app"
      : "https://app.bxktraderpro.com";

  const API_URL = apiBase + "/api/chat";
  const STATUS_URL = API_URL + "/status";
  const history = [];

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  const launcher = el(
    "button",
    "bxk-chat-launcher",
    "Ask BXK AI"
  );
  launcher.type = "button";
  launcher.hidden = true;
  launcher.setAttribute(
    "aria-label",
    "Open BXK AI assistant"
  );

  const panel = el(
    "section",
    "bxk-chat-panel"
  );
  panel.hidden = true;
  panel.setAttribute(
    "aria-label",
    "BXK AI assistant"
  );

  const header = el(
    "div",
    "bxk-chat-header"
  );
  const titleWrap = el(
    "div",
    "bxk-chat-title"
  );
  titleWrap.append(
    el("strong", "", "BXK Assistant"),
    el(
      "span",
      "",
      "Ask about BXK Trader Pro or general questions"
    )
  );

  const close = el(
    "button",
    "bxk-chat-close",
    "×"
  );
  close.type = "button";
  close.setAttribute(
    "aria-label",
    "Close assistant"
  );

  header.append(
    titleWrap,
    close
  );

  const messages = el(
    "div",
    "bxk-chat-messages"
  );

  const welcome = el(
    "div",
    "bxk-chat-message assistant"
  );
  welcome.textContent =
    "Hi. I’m the BXK Assistant. I can answer questions about BXK Trader Pro, explain features and workflows, or help with ordinary general questions.";

  messages.append(welcome);

  const safety = el(
    "div",
    "bxk-chat-safety",
    "Do not enter passwords, brokerage credentials, account numbers, Social Security numbers, or payment-card information."
  );

  const quick = el(
    "div",
    "bxk-chat-quick"
  );

  [
    "What is BXK Trader Pro?",
    "How does broker connection work?",
    "Is Schwab available yet?",
  ].forEach((prompt) => {
    const button = el(
      "button",
      "",
      prompt
    );
    button.type = "button";
    button.addEventListener(
      "click",
      () => sendMessage(prompt)
    );
    quick.append(button);
  });

  const form = el(
    "form",
    "bxk-chat-form"
  );

  const input = document.createElement(
    "textarea"
  );
  input.className = "bxk-chat-input";
  input.maxLength = 2000;
  input.rows = 2;
  input.placeholder =
    "Ask a question…";
  input.setAttribute(
    "aria-label",
    "Ask BXK Assistant"
  );

  const submit = el(
    "button",
    "bxk-chat-send",
    "Send"
  );
  submit.type = "submit";

  form.append(
    input,
    submit
  );

  const footer = el(
    "div",
    "bxk-chat-footer",
    "AI responses can be wrong. Trading information is educational, not personalized investment advice."
  );

  panel.append(
    header,
    messages,
    safety,
    quick,
    form,
    footer
  );

  document.body.append(
    launcher,
    panel
  );

  function addMessage(
    role,
    text
  ) {
    const message = el(
      "div",
      "bxk-chat-message " + role
    );
    message.textContent = text;
    messages.append(message);
    messages.scrollTop =
      messages.scrollHeight;
    return message;
  }

  function pageContext() {
    const main =
      document.querySelector("main");

    if (!main) return "";

    return main.innerText
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 3500);
  }

  async function sendMessage(text) {
    const clean = String(
      text || ""
    ).trim();

    if (!clean) return;

    addMessage("user", clean);
    input.value = "";
    quick.hidden = true;
    submit.disabled = true;

    const loading = addMessage(
      "assistant loading",
      "Thinking…"
    );

    try {
      const response = await fetch(
        API_URL,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            message: clean,
            history:
              history.slice(-8),
            page_url:
              window.location.href,
            page_title:
              document.title,
            page_context:
              pageContext(),
          }),
        }
      );

      const data =
        await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail ||
          "BXK Assistant is temporarily unavailable."
        );
      }

      loading.textContent =
        data.answer;

      history.push(
        {
          role: "user",
          content: clean,
        },
        {
          role: "assistant",
          content: data.answer,
        }
      );

      if (history.length > 8) {
        history.splice(
          0,
          history.length - 8
        );
      }
    } catch (error) {
      loading.textContent =
        error.message ||
        "BXK Assistant is temporarily unavailable.";
      loading.classList.add(
        "error"
      );
    } finally {
      submit.disabled = false;
      input.focus();
    }
  }

  form.addEventListener(
    "submit",
    (event) => {
      event.preventDefault();
      sendMessage(input.value);
    }
  );

  input.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Enter" &&
        !event.shiftKey
      ) {
        event.preventDefault();
        form.requestSubmit();
      }
    }
  );

  launcher.addEventListener(
    "click",
    () => {
      panel.hidden = false;
      launcher.hidden = true;
      input.focus();
    }
  );

  close.addEventListener(
    "click",
    () => {
      panel.hidden = true;
      launcher.hidden = false;
    }
  );

  fetch(
    STATUS_URL,
    {
      cache: "no-store",
    }
  )
    .then((response) =>
      response.ok
        ? response.json()
        : {enabled: false}
    )
    .then((status) => {
      launcher.hidden =
        status.enabled !== true;
    })
    .catch(() => {
      launcher.hidden = true;
    });
})();
