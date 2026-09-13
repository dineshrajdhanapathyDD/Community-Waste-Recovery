/*
 * Good Neighbor Agent — frontend logic.
 *
 * Flow:
 *   1. Read window.WORKSHOP_CONFIG (from config.js).
 *   2. If it still has placeholder values, run in DEMO MODE (mocked replies).
 *   3. Otherwise: sign in via Amazon Cognito (SRP) to get a JWT access token.
 *   4. Send each message to the AgentCore Runtime with the JWT as a Bearer
 *      token; the runtime's custom JWT authorizer validates it.
 *   5. Render the agent's Markdown reply (tables included).
 *
 * MIT License — Copyright (c) 2026 Dineshraj Dhanapathy@DD
 */
(function () {
  "use strict";

  const CFG = window.WORKSHOP_CONFIG || {};

  // ---- Detect demo mode ---------------------------------------------------
  // If any critical value is missing or still a "YOUR_..." placeholder, we
  // can't reach AWS, so we mock the agent so the UI is still explorable.
  function isPlaceholder(v) {
    return !v || String(v).startsWith("YOUR_");
  }
  const DEMO_MODE =
    isPlaceholder(CFG.COGNITO_USER_POOL_ID) ||
    isPlaceholder(CFG.COGNITO_CLIENT_ID) ||
    isPlaceholder(CFG.AGENTCORE_RUNTIME_ARN);

  // ---- DOM refs -----------------------------------------------------------
  const el = (id) => document.getElementById(id);
  const loginView = el("login-view");
  const chatView = el("chat-view");
  const emailForm = el("email-form");
  const otpForm = el("otp-form");
  const emailSubmit = el("email-submit");
  const otpSubmit = el("otp-submit");
  const otpBack = el("otp-back");
  const otpSentTo = el("otp-sent-to");
  const loginError = el("login-error");
  const logoutBtn = el("logout-btn");
  const messages = el("messages");
  const chatForm = el("chat-form");
  const chatInput = el("chat-input");
  const sendBtn = el("send-btn");
  const modeBadge = el("mode-badge");
  const suggestions = el("suggestions");

  // Holds the Cognito access token (JWT) once signed in.
  let accessToken = null;

  // ---- Mode badge ---------------------------------------------------------
  const HAS_BACKEND = !!(CFG.BACKEND_API_URL && !isPlaceholder(CFG.BACKEND_API_URL));
  if (!DEMO_MODE) {
    modeBadge.textContent = "Connected to AWS";
    modeBadge.className = "badge badge-live";
  } else if (HAS_BACKEND) {
    // Full agent runtime not configured, but the real backend tools API is —
    // answers come from live AWS data, not mocks.
    modeBadge.textContent = "Live backend data";
    modeBadge.className = "badge badge-live";
    el("login-demo-hint").textContent =
      "Answering from the deployed AWS backend. Enter any email, then use code 123456 to sign in.";
  } else {
    modeBadge.textContent = "Demo mode";
    modeBadge.className = "badge badge-demo";
    el("login-demo-hint").textContent =
      "config.js has placeholder values, so this runs in demo mode. Enter any email, then use code 123456 to explore the UI. Deploy with launchAgent.sh to connect real AWS.";
  }

  // ---- "How it works" modal ----------------------------------------------
  el("how-btn").addEventListener("click", () => el("how-modal").classList.remove("hidden"));
  el("how-close").addEventListener("click", () => el("how-modal").classList.add("hidden"));
  el("how-modal").addEventListener("click", (e) => {
    if (e.target.id === "how-modal") el("how-modal").classList.add("hidden");
  });

  // ---- Cognito passwordless email OTP -------------------------------------
  // Uses Cognito's native USER_AUTH flow with the EMAIL_OTP factor. Cognito
  // sends the 6-digit code itself using the pool's email configuration
  // (COGNITO_DEFAULT — no SES, no Lambda). We drive the raw Cognito IDP HTTPS
  // API directly (InitiateAuth + RespondToAuthChallenge) so we don't depend on
  // SDK support for the newer USER_AUTH flow.
  //
  // Between the two steps we hold Cognito's `Session` string, which ties the
  // code the user types back to the challenge Cognito issued.
  let pendingSession = null; // Cognito challenge Session between step 1 and 2
  let pendingEmail = null;

  function cognitoIdpUrl() {
    return `https://cognito-idp.${CFG.COGNITO_REGION}.amazonaws.com/`;
  }

  async function cognitoIdpCall(target, body) {
    const res = await fetch(cognitoIdpUrl(), {
      method: "POST",
      headers: {
        "Content-Type": "application/x-amz-json-1.1",
        "X-Amz-Target": `AWSCognitoIdentityProviderService.${target}`,
      },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.message || data.__type || `Request failed (${res.status})`;
      throw new Error(msg);
    }
    return data;
  }

  // Step 1: ask Cognito to email a one-time code to this address.
  async function requestEmailCode(email) {
    if (DEMO_MODE) {
      pendingEmail = email;
      await new Promise((r) => setTimeout(r, 400));
      return;
    }
    // USER_AUTH lets the client pick a factor; we prefer EMAIL_OTP.
    const init = await cognitoIdpCall("InitiateAuth", {
      AuthFlow: "USER_AUTH",
      ClientId: CFG.COGNITO_CLIENT_ID,
      AuthParameters: {
        USERNAME: email,
        PREFERRED_CHALLENGE: "EMAIL_OTP",
      },
    });

    // Cognito replies with the EMAIL_OTP challenge and a Session token.
    if (init.ChallengeName !== "EMAIL_OTP" && init.ChallengeName !== "SELECT_CHALLENGE") {
      throw new Error(
        `Unexpected challenge from Cognito: ${init.ChallengeName || "none"}. ` +
          "Make sure the app client allows USER_AUTH and the pool has email OTP enabled."
      );
    }

    // If Cognito asked us to SELECT a factor first, select EMAIL_OTP explicitly.
    if (init.ChallengeName === "SELECT_CHALLENGE") {
      const sel = await cognitoIdpCall("RespondToAuthChallenge", {
        ClientId: CFG.COGNITO_CLIENT_ID,
        ChallengeName: "SELECT_CHALLENGE",
        Session: init.Session,
        ChallengeResponses: {
          USERNAME: email,
          ANSWER: "EMAIL_OTP",
        },
      });
      pendingSession = sel.Session;
    } else {
      pendingSession = init.Session;
    }
    pendingEmail = email;
  }

  // Step 2: submit the code the user received; returns the JWT access token.
  async function verifyEmailCode(code) {
    if (DEMO_MODE) {
      await new Promise((r) => setTimeout(r, 400));
      if (code.trim() !== "123456") {
        throw new Error("Incorrect code. In demo mode the code is 123456.");
      }
      return "demo-token";
    }
    const resp = await cognitoIdpCall("RespondToAuthChallenge", {
      ClientId: CFG.COGNITO_CLIENT_ID,
      ChallengeName: "EMAIL_OTP",
      Session: pendingSession,
      ChallengeResponses: {
        USERNAME: pendingEmail,
        EMAIL_OTP_CODE: code.trim(),
      },
    });
    if (!resp.AuthenticationResult || !resp.AuthenticationResult.AccessToken) {
      throw new Error("Sign-in did not complete. Please request a new code.");
    }
    return resp.AuthenticationResult.AccessToken;
  }

  // ---- AgentCore Runtime invoke ------------------------------------------
  // The runtime endpoint expects the ARN URL-encoded in the path. The Cognito
  // JWT goes in the Authorization header (the runtime was configured with a
  // customJWTAuthorizer + an "Authorization" header allowlist).
  async function invokeAgent(prompt) {
    if (DEMO_MODE) return demoReply(prompt);

    const arn = encodeURIComponent(CFG.AGENTCORE_RUNTIME_ARN);
    const url =
      `${CFG.AGENTCORE_ENDPOINT}/runtimes/${arn}/invocations?qualifier=DEFAULT`;

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ prompt }),
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Agent request failed (${res.status}). ${text}`);
    }

    const data = await res.json();
    // agent.py returns { output: { text }, metadata: {...} }
    return (data && data.output && data.output.text) || JSON.stringify(data);
  }

  // ---- Demo replies -------------------------------------------------------
  // If BACKEND_API_URL is configured, answer from the REAL deployed backend
  // (the SAM stack). Otherwise fall back to fully offline mocked responses.
  const BACKEND_API_URL = (CFG.BACKEND_API_URL || "").replace(/\/$/, "");

  async function backendGet(path) {
    const res = await fetch(`${BACKEND_API_URL}${path}`);
    if (!res.ok) throw new Error(`Backend ${path} -> ${res.status}`);
    return res.json();
  }

  function mdTable(headers, rows) {
    const head = `| ${headers.join(" | ")} |`;
    const sep = `| ${headers.map(() => "---").join(" | ")} |`;
    const body = rows.map((r) => `| ${r.join(" | ")} |`).join("\n");
    return `${head}\n${sep}\n${body}`;
  }

  // Query the live backend and compose a Markdown answer from real data.
  async function backendReply(prompt) {
    const p = (prompt || "").toLowerCase();

    if (p.includes("volunteer") || p.includes("driver") || p.includes("vehicle")) {
      const vols = await backendGet("/volunteers?available=true");
      const vehicles = await backendGet("/vehicles");
      const vrows = vols.volunteers.map((v) => [v.full_name, v.location, v.available ? "yes" : "no"]);
      const table = mdTable(["Volunteer", "Location", "Available"], vrows);
      return `${table}\n\n${vols.count} volunteer(s) available now, and ${vehicles.count} vehicle(s) in the fleet. *(Live data from the deployed AWS backend.)*`;
    }

    if (p.includes("pantry") || p.includes("stock") || p.includes("shortage") || p.includes("low")) {
      const pantry = await backendGet("/pantry");
      const rows = pantry.pantry_items.map((i) => [
        i.resource_name, i.org_name, String(i.quantity_on_hand), i.is_low ? "⚠️ low" : "ok",
      ]);
      const table = mdTable(["Item", "Partner", "On hand", "Status"], rows.slice(0, 5));
      const low = pantry.pantry_items.filter((i) => i.is_low).length;
      return `${table}\n\n${pantry.count} stock line(s), ${low} below their low-stock threshold. *(Live data from the deployed AWS backend.)*`;
    }

    if (p.includes("need") || p.includes("request") || p.includes("food bank")) {
      const needs = await backendGet("/needs");
      const rows = needs.needs.map((n) => [n.org_name, n.resource_name, n.quantity_needed, n.priority]);
      const table = mdTable(["Organization", "Needs", "Quantity", "Priority"], rows.slice(0, 5));
      return `${table}\n\n${needs.count} open request(s) across the network. *(Live data from the deployed AWS backend.)*`;
    }

    if (p.includes("produce") || p.includes("surplus") || p.includes("pick") || p.includes("donat")) {
      const surplus = await backendGet("/");
      const rows = surplus.listings.map((l) => [
        l.donor_name, l.category, l.quantity, new Date(l.pickup_by).toLocaleDateString(),
      ]);
      const table = mdTable(["Donor", "Category", "Quantity", "Pickup by"], rows.slice(0, 5));
      return `${table}\n\n${surplus.count} surplus listing(s) posted. *(Live data from the deployed AWS backend.)*`;
    }

    if (p.includes("guideline") || p.includes("safe") || p.includes("accept") || p.includes("window")) {
      const type = p.includes("accept") ? "Acceptance" : p.includes("handl") ? "Handling" : "Window";
      const g = await backendGet(`/guidelines?guideline_type=${type}`);
      return `**${type} guidelines**\n\n${g.guideline_details}\n\n*(Live data from the deployed AWS backend.)*`;
    }

    // No keyword matched: show what real data is available.
    const surplus = await backendGet("/");
    const needs = await backendGet("/needs");
    return (
      `I can answer from live community data. Right now there are **${surplus.count} surplus listings** ` +
      `and **${needs.count} open requests**. Try asking about surplus produce, recipient needs, ` +
      `pantry levels, available volunteers, or donation guidelines. *(Live data from the deployed AWS backend.)*`
    );
  }

  // Fully offline mock (used only when no BACKEND_API_URL is configured).
  function mockReply(prompt) {
    const p = (prompt || "").toLowerCase();
    return new Promise((resolve) => {
      setTimeout(() => {
        if (p.includes("produce") || p.includes("food bank") || p.includes("pick")) {
          resolve(
            "| Food bank | Area | Needs |\n| --- | --- | --- |\n" +
              "| North Side Food Bank | North Side | Fresh produce |\n\n" +
              "Maria (van) is available near the north side.\n\n*(Offline demo data — set BACKEND_API_URL for live results.)*"
          );
        } else {
          resolve(
            "I'm in offline demo mode. Set BACKEND_API_URL in config.js to answer " +
              "from the deployed AWS backend.\n\n*(Offline demo data.)*"
          );
        }
      }, 500);
    });
  }

  // Entry point used by invokeAgent() when not calling the full agent runtime.
  function demoReply(prompt) {
    if (BACKEND_API_URL) {
      return backendReply(prompt).catch(
        (e) => `⚠️ Couldn't reach the backend: ${e.message}`
      );
    }
    return mockReply(prompt);
  }

  // ---- Animation helper ---------------------------------------------------
  // Re-trigger a CSS entrance animation on an element that was just un-hidden
  // (toggling `hidden` alone won't replay the animation).
  function animateIn(node, keyframe) {
    if (!node) return;
    node.style.animation = "none";
    // Force reflow so the browser registers the reset before we re-apply.
    void node.offsetWidth;
    node.style.animation = `${keyframe} 0.45s cubic-bezier(0.22, 1, 0.36, 1) both`;
  }

  // ---- Chat rendering -----------------------------------------------------
  function addMessage(role, text, opts) {
    opts = opts || {};
    const wrap = document.createElement("div");
    wrap.className = `msg msg-${role}`;
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (opts.markdown) {
      bubble.innerHTML = window.marked.parse(text);
    } else {
      bubble.textContent = text;
    }
    wrap.appendChild(bubble);
    messages.appendChild(wrap);
    messages.scrollTop = messages.scrollHeight;
    return bubble;
  }

  function addTyping() {
    const wrap = document.createElement("div");
    wrap.className = "msg msg-agent";
    wrap.id = "typing";
    wrap.innerHTML = '<div class="bubble typing"><span></span><span></span><span></span></div>';
    messages.appendChild(wrap);
    messages.scrollTop = messages.scrollHeight;
  }
  function removeTyping() {
    const t = el("typing");
    if (t) t.remove();
  }

  // ---- Suggestion chips ---------------------------------------------------
  const SUGGESTIONS = [
    "A grocer has 40 lbs of produce to pick up by Friday — which food bank needs it, and who could drive it?",
    "Which volunteers and vehicles are available right now?",
    "What are the current pantry stock levels?",
  ];
  function renderSuggestions() {
    suggestions.innerHTML = "";
    SUGGESTIONS.forEach((s) => {
      const chip = document.createElement("button");
      chip.className = "chip";
      chip.textContent = s;
      chip.addEventListener("click", () => {
        chatInput.value = s;
        chatInput.focus();
        autoGrow();
      });
      suggestions.appendChild(chip);
    });
  }

  // ---- Login flow (step 1: email → code) ----------------------------------
  emailForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.classList.add("hidden");
    emailSubmit.disabled = true;
    emailSubmit.textContent = "Sending…";
    try {
      const email = el("email").value.trim();
      await requestEmailCode(email);
      // Reveal the code step with an entrance animation.
      emailForm.classList.add("hidden");
      otpForm.classList.remove("hidden");
      animateIn(otpForm, "popIn");
      otpSentTo.textContent = DEMO_MODE
        ? `Demo mode: enter code 123456 for ${email}.`
        : `We sent a code to ${email}. Enter it below.`;
      el("otp").focus();
    } catch (err) {
      loginError.textContent = err.message || String(err);
      loginError.classList.remove("hidden");
    } finally {
      emailSubmit.disabled = false;
      emailSubmit.textContent = "Send code";
    }
  });

  // Step 2: verify the code and sign in.
  otpForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.classList.add("hidden");
    otpSubmit.disabled = true;
    otpSubmit.textContent = "Verifying…";
    try {
      const code = el("otp").value;
      accessToken = await verifyEmailCode(code);
      showChat();
    } catch (err) {
      loginError.textContent = err.message || String(err);
      loginError.classList.remove("hidden");
    } finally {
      otpSubmit.disabled = false;
      otpSubmit.textContent = "Verify & sign in";
    }
  });

  // "Use a different email" — go back to step 1.
  otpBack.addEventListener("click", () => {
    loginError.classList.add("hidden");
    pendingSession = null;
    pendingEmail = null;
    el("otp").value = "";
    otpForm.classList.add("hidden");
    emailForm.classList.remove("hidden");
    el("email").focus();
  });

  function showChat() {
    loginView.classList.add("hidden");
    chatView.classList.remove("hidden");
    animateIn(chatView.querySelector(".chat-wrap"), "fadeIn");
    logoutBtn.classList.remove("hidden");
    renderSuggestions();
    if (!messages.childElementCount) {
      addMessage(
        "agent",
        "Hi! I help this community recover surplus and get it to people who can use it. " +
          "Ask me about surplus listings, recipient needs, pantry levels, volunteers, or donation guidelines.",
        { markdown: true }
      );
    }
    chatInput.focus();
  }

  logoutBtn.addEventListener("click", () => {
    accessToken = null;
    pendingSession = null;
    pendingEmail = null;
    messages.innerHTML = "";
    chatView.classList.add("hidden");
    logoutBtn.classList.add("hidden");
    // Reset to the email step.
    otpForm.classList.add("hidden");
    el("otp").value = "";
    el("email").value = "";
    emailForm.classList.remove("hidden");
    loginView.classList.remove("hidden");
  });

  // ---- Send flow ----------------------------------------------------------
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    addMessage("user", text);
    chatInput.value = "";
    autoGrow();
    sendBtn.disabled = true;
    addTyping();

    try {
      const reply = await invokeAgent(text);
      removeTyping();
      addMessage("agent", reply, { markdown: true });
    } catch (err) {
      removeTyping();
      addMessage("agent", "⚠️ " + (err.message || String(err)));
    } finally {
      sendBtn.disabled = false;
      chatInput.focus();
    }
  });

  // ---- Textarea auto-grow + Enter to send --------------------------------
  function autoGrow() {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 160) + "px";
  }
  chatInput.addEventListener("input", autoGrow);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.requestSubmit();
    }
  });
})();
