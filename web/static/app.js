// Company Analyzer Web Platform & Subscription Manager Frontend

let currentAnalysis = null;
let currentSymbol = "";
let currentPlan = "free";
let currentCurrency = "INR";
let userQuota = { allowed: true, remaining: 3, remaining_today: 3, daily_limit: 3, plan: "free", features: {} };
let revChartInstance = null;
let profitChartInstance = null;

// Get or generate persistent User ID in localStorage
function getUserId() {
  let uid = localStorage.getItem("ca_user_id");
  if (!uid) {
    uid = "usr_" + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
    localStorage.setItem("ca_user_id", uid);
  }
  return uid;
}

// Helper to get remaining quota safely
function getRemainingQuota() {
  if (userQuota.remaining !== undefined && userQuota.remaining !== null) {
    return userQuota.remaining;
  }
  if (userQuota.remaining_today !== undefined && userQuota.remaining_today !== null) {
    return userQuota.remaining_today;
  }
  return 0;
}

// Initialize when DOM loads
document.addEventListener("DOMContentLoaded", () => {
  fetchSubscriptionStatus();
  setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
  const searchInput = document.getElementById("searchInput");
  const searchBtn = document.getElementById("searchBtn");

  searchBtn.addEventListener("click", () => {
    const q = searchInput.value.trim();
    if (q) analyzeTicker(q);
  });

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const q = searchInput.value.trim();
      if (q) analyzeTicker(q);
    }
  });

  // Ticker Pills
  document.querySelectorAll(".ticker-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const t = pill.getAttribute("data-ticker");
      if (t) {
        document.getElementById("searchInput").value = t;
        analyzeTicker(t);
      }
    });
  });
}

// Fetch user subscription status & quota
async function fetchSubscriptionStatus() {
  try {
    const uid = getUserId();
    const res = await fetch(`/api/subscription/status?user_id=${encodeURIComponent(uid)}`);
    if (res.ok) {
      userQuota = await res.json();
      currentPlan = userQuota.plan || "free";
      updateSubscriptionBadge();
    }
  } catch (err) {
    console.error("Failed to load subscription status:", err);
  }
}

// Update Header Subscription Badge & Quota UI
function updateSubscriptionBadge() {
  const badge = document.getElementById("userPlanBadge");
  const quotaText = document.getElementById("userQuotaText");
  const quotaBanner = document.getElementById("quotaBanner");
  const searchInput = document.getElementById("searchInput");
  const remaining = getRemainingQuota();
  const dailyLimit = userQuota.daily_limit || 3;

  if (currentPlan === "free") {
    badge.textContent = "Free Tier";
    badge.className = "text-xs font-bold text-slate-200";
    quotaText.textContent = `${remaining}/${dailyLimit} left`;
    quotaText.classList.remove("hidden");

    if (remaining <= 0 || !userQuota.allowed) {
      if (quotaBanner) quotaBanner.classList.remove("hidden");
      if (searchInput) searchInput.placeholder = "0 free attempts left — Upgrade to Pro to analyze";
    } else {
      if (quotaBanner) quotaBanner.classList.add("hidden");
      if (searchInput) searchInput.placeholder = "Search company or ticker (e.g. NVDA, Apple, TCS.NS)...";
    }
  } else if (currentPlan === "pro") {
    badge.textContent = "Pro Analyst";
    badge.className = "text-xs font-bold text-amber-400";
    quotaText.textContent = "Unlimited";
    quotaText.classList.remove("hidden");
    if (quotaBanner) quotaBanner.classList.add("hidden");
    if (searchInput) searchInput.placeholder = "Search company or ticker (e.g. NVDA, Apple, TCS.NS)...";
  } else if (currentPlan === "enterprise") {
    badge.textContent = "Institutional";
    badge.className = "text-xs font-bold text-cyan-400";
    quotaText.textContent = "Unlimited";
    quotaText.classList.remove("hidden");
    if (quotaBanner) quotaBanner.classList.add("hidden");
    if (searchInput) searchInput.placeholder = "Search company or ticker (e.g. NVDA, Apple, TCS.NS)...";
  }

  // Check chat lock
  updateChatLockState();
}

// Update chat lock state based on plan
function updateChatLockState() {
  const chatLockOverlay = document.getElementById("chatLockOverlay");
  const chatInterface = document.getElementById("chatInterface");
  if (!chatLockOverlay || !chatInterface) return;

  const hasChat = userQuota.features && userQuota.features.has_chat;
  if (currentPlan === "free" && !hasChat) {
    chatLockOverlay.classList.remove("hidden");
    chatInterface.classList.add("hidden");
  } else {
    chatLockOverlay.classList.add("hidden");
    chatInterface.classList.remove("hidden");
  }
}

// Open / Close Pricing Modal
function openPricingModal() {
  document.getElementById("pricingModal").classList.remove("hidden");
}

function closePricingModal() {
  document.getElementById("pricingModal").classList.add("hidden");
}

// Currency toggle for pricing modal
function setPricingCurrency(curr) {
  currentCurrency = curr;
  const inrBtn = document.getElementById("currBtnINR");
  const usdBtn = document.getElementById("currBtnUSD");
  const priceFree = document.getElementById("priceFree");
  const pricePro = document.getElementById("pricePro");
  const priceEnterprise = document.getElementById("priceEnterprise");

  if (curr === "INR") {
    if (inrBtn) inrBtn.className = "px-3 py-1 rounded-lg bg-cyan-600 text-white transition";
    if (usdBtn) usdBtn.className = "px-3 py-1 rounded-lg text-slate-400 hover:text-white transition";
    if (priceFree) priceFree.innerText = "₹0";
    if (pricePro) pricePro.innerText = "₹1,499";
    if (priceEnterprise) priceEnterprise.innerText = "₹3,999";
  } else {
    if (inrBtn) inrBtn.className = "px-3 py-1 rounded-lg text-slate-400 hover:text-white transition";
    if (usdBtn) usdBtn.className = "px-3 py-1 rounded-lg bg-cyan-600 text-white transition";
    if (priceFree) priceFree.innerText = "$0";
    if (pricePro) pricePro.innerText = "$19";
    if (priceEnterprise) priceEnterprise.innerText = "$49";
  }
}

// Format an amount (in subunits, paise/cents) into readable currency
function formatAmount(amountSubunits, currency) {
  const value = Number(amountSubunits) / 100;
  if (currency === "INR") {
    return "₹" + value.toLocaleString("en-IN");
  }
  return "$" + value.toLocaleString("en-US");
}

// Razorpay Checkout Handler
async function payWithRazorpay(planId) {
  try {
    const uid = getUserId();
    // 1. Request Order Creation from Backend
    const res = await fetch("/api/razorpay/create-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan_id: planId,
        user_id: uid,
        currency: currentCurrency
      })
    });

    const orderData = await res.json();
    if (!res.ok) {
      alert(`Razorpay Error: ${orderData.detail || "Unable to create order"}`);
      return;
    }

    // 2. Check if in Sandbox / Mock Demo mode
    if (orderData.mode === "sandbox" || orderData.sandbox === true || !orderData.key_id || orderData.key_id === "rzp_test_mock_key") {
      const confirmed = confirm(
        `⚡ Razorpay Sandbox / Demo Mode\n\n` +
        `Plan: ${orderData.plan_name} (${formatAmount(orderData.amount, orderData.currency)})\n\n` +
        `Razorpay Live API keys not configured yet. Would you like to simulate a successful payment and activate this tier now?`
      );
      if (confirmed) {
        await verifyAndActivatePayment(planId, uid, orderData.order_id, `pay_mock_${Date.now()}`, "mock_signature");
      }
      return;
    }

    // 3. Open Official Razorpay Checkout Modal
    if (typeof Razorpay === "undefined") {
      alert("Razorpay SDK could not be loaded. Please check your internet connection.");
      return;
    }

    const options = {
      key: orderData.key_id,
      amount: orderData.amount,
      currency: orderData.currency,
      name: "Company Analyzer Pro",
      description: `${orderData.plan_name} Monthly Plan`,
      image: "https://cdn-icons-png.flaticon.com/512/2784/2784403.png",
      order_id: orderData.order_id,
      handler: async function (response) {
        // Handle successful payment
        await verifyAndActivatePayment(
          planId,
          uid,
          response.razorpay_order_id,
          response.razorpay_payment_id,
          response.razorpay_signature
        );
      },
      prefill: {
        name: "Valued Investor",
        email: "investor@example.com",
        contact: "9999999999"
      },
      theme: {
        color: "#06b6d4"
      },
      modal: {
        ondismiss: function() {
          console.log("Razorpay checkout modal closed");
        }
      }
    };

    const rzp = new Razorpay(options);
    rzp.on("payment.failed", function (response) {
      alert(`Payment Failed: ${response.error.description || response.error.reason}`);
    });
    rzp.open();

  } catch (err) {
    alert(`Checkout error: ${err.message}`);
  }
}

// Verify payment signature on backend and activate plan
async function verifyAndActivatePayment(planId, userId, orderId, paymentId, signature) {
  try {
    const res = await fetch("/api/razorpay/verify-payment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: userId,
        plan_id: planId,
        razorpay_order_id: orderId,
        razorpay_payment_id: paymentId,
        razorpay_signature: signature
      })
    });

    const data = await res.json();
    if (res.ok && data.status === "success") {
      alert(`🎉 Payment Successful! Your plan is now ${planId.toUpperCase()} with unlimited searches & AI features unlocked.`);
      closePricingModal();
      await fetchSubscriptionStatus();
    } else {
      alert(`Verification failed: ${data.detail || "Invalid signature"}`);
    }
  } catch (err) {
    alert(`Verification error: ${err.message}`);
  }
}

// Stripe Subscription Checkout
async function subscribeStripe(planId) {
  try {
    const uid = getUserId();
    const res = await fetch("/api/subscription/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan_id: planId,
        user_id: uid,
        success_url: window.location.origin,
        cancel_url: window.location.origin
      })
    });

    const data = await res.json();
    if (res.ok) {
      if (data.mode === "sandbox_demo" || data.status === "active" || data.mode === "sandbox") {
        alert(`🎉 Successfully upgraded to ${data.plan_name || planId.toUpperCase()}!`);
        closePricingModal();
        await fetchSubscriptionStatus();
      } else if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } else {
      alert(`Subscription Error: ${data.detail || "Unable to create checkout session"}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

// Instant Sandbox Switch (for testing and immediate demo)
async function switchPlanDemo(planId) {
  try {
    const uid = getUserId();
    const res = await fetch("/api/subscription/demo-upgrade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan_id: planId,
        user_id: uid
      })
    });

    const data = await res.json();
    if (res.ok) {
      alert(`✨ Plan updated: ${data.message}`);
      closePricingModal();
      await fetchSubscriptionStatus();
    } else {
      alert(`Error: ${data.detail || "Failed to switch plan"}`);
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

// Core Analyze Action
async function analyzeTicker(query) {
  const remaining = getRemainingQuota();
  
  // Guard clause: strictly block attempts if user is on Free plan and has 0 remaining attempts
  if (currentPlan === "free" && (!userQuota.allowed || remaining <= 0)) {
    alert("Daily free limit reached (0 attempts remaining today). Please upgrade to Pro for unlimited analyses.");
    openPricingModal();
    return;
  }

  const emptyState = document.getElementById("emptyState");
  const loadingState = document.getElementById("loadingState");
  const dashboard = document.getElementById("dashboard");

  emptyState.classList.add("hidden");
  dashboard.classList.add("hidden");
  loadingState.classList.remove("hidden");
  document.getElementById("loadingMsg").textContent = `Analyzing ${query.toUpperCase()} fundamentals & computing health score...`;

  try {
    const uid = getUserId();
    const res = await fetch(`/api/analyze?query=${encodeURIComponent(query)}&user_id=${encodeURIComponent(uid)}`);
    
    if (res.status === 429) {
      const errData = await res.json();
      loadingState.classList.add("hidden");
      emptyState.classList.remove("hidden");
      userQuota.allowed = false;
      userQuota.remaining = 0;
      userQuota.remaining_today = 0;
      updateSubscriptionBadge();
      alert(errData.detail || "Daily free limit reached. Please upgrade to Pro.");
      openPricingModal();
      return;
    }

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to analyze company");
    }

    const data = await res.json();
    currentAnalysis = data;
    currentSymbol = data.company_data?.profile?.symbol || query.toUpperCase();

    // Update quota
    if (data.quota) {
      userQuota = data.quota;
      currentPlan = userQuota.plan || "free";
      updateSubscriptionBadge();
    }

    renderDashboard(data);

    loadingState.classList.add("hidden");
    dashboard.classList.remove("hidden");

  } catch (err) {
    loadingState.classList.add("hidden");
    emptyState.classList.remove("hidden");
    alert(`Error: ${err.message}`);
  }
}

// Render Dashboard Data
function renderDashboard(data) {
  const cd = data.company_data || {};
  const prof = cd.profile || {};
  const price = cd.price_stats || {};
  const val = cd.valuation || {};
  const margins = cd.profitability || {};
  const bs = cd.balance_sheet || {};
  const targets = cd.analyst_targets || {};
  const scoring = data.scoring || {};
  const curr = price.currency === "USD" ? "$" : `${price.currency || "$"} `;

  // Header Info
  document.getElementById("compName").textContent = prof.name || "N/A";
  document.getElementById("compSymbol").textContent = prof.symbol || "N/A";
  document.getElementById("compExchange").textContent = prof.exchange || "GLOBAL";
  document.getElementById("compSector").innerHTML = `<i class="fa-solid fa-layer-group text-slate-500 mr-1.5"></i>${prof.sector || "N/A"}`;
  document.getElementById("compIndustry").innerHTML = `<i class="fa-solid fa-industry text-slate-500 mr-1.5"></i>${prof.industry || "N/A"}`;
  document.getElementById("compCountry").innerHTML = `<i class="fa-solid fa-globe text-slate-500 mr-1.5"></i>${prof.country || "N/A"}`;
  
  document.getElementById("compPrice").textContent = price.current_price ? `${curr}${price.current_price.toFixed(2)}` : "N/A";
  document.getElementById("compMarketCap").textContent = formatLargeNum(price.market_cap, curr);
  document.getElementById("compEV").textContent = formatLargeNum(val.enterprise_value, curr);

  // Health Score
  document.getElementById("healthScore").textContent = scoring.overall_score ?? "N/A";
  const gradeEl = document.getElementById("healthGrade");
  gradeEl.textContent = scoring.grade || "N/A";
  if (["A+", "A", "A-", "B+"].includes(scoring.grade)) {
    gradeEl.className = "px-2.5 py-0.5 rounded-lg text-sm font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
  } else if (["B", "B-", "C+"].includes(scoring.grade)) {
    gradeEl.className = "px-2.5 py-0.5 rounded-lg text-sm font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20";
  } else {
    gradeEl.className = "px-2.5 py-0.5 rounded-lg text-sm font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20";
  }

  // Valuation Multiples
  document.getElementById("valTrailingPE").textContent = formatNum(val.trailing_pe, "x");
  document.getElementById("valForwardPE").textContent = formatNum(val.forward_pe, "x");
  document.getElementById("valPEG").textContent = formatNum(val.peg_ratio);
  document.getElementById("valPS").textContent = formatNum(val.price_to_sales, "x");
  document.getElementById("valPB").textContent = formatNum(val.price_to_book, "x");
  document.getElementById("valEVEBITDA").textContent = formatNum(val.ev_to_ebitda, "x");
  document.getElementById("valBeta").textContent = formatNum(price.beta);

  // Profitability
  document.getElementById("profRevTTM").textContent = formatLargeNum(margins.revenue_ttm, curr);
  document.getElementById("profRevGrowth").textContent = formatPct(margins.revenue_growth);
  document.getElementById("profGrossMargin").textContent = formatPct(margins.gross_margin);
  document.getElementById("profOpMargin").textContent = formatPct(margins.operating_margin);
  document.getElementById("profNetMargin").textContent = formatPct(margins.profit_margin);
  document.getElementById("profROE").textContent = formatPct(margins.return_on_equity);
  document.getElementById("profFCF").textContent = formatLargeNum(margins.free_cash_flow, curr);

  // Balance Sheet
  document.getElementById("bsCash").textContent = formatLargeNum(bs.total_cash, curr);
  document.getElementById("bsDebt").textContent = formatLargeNum(bs.total_debt, curr);
  document.getElementById("bsNetDebt").textContent = formatLargeNum(bs.net_debt, curr);
  document.getElementById("bsDebtEquity").textContent = formatNum(bs.debt_to_equity, "%");
  document.getElementById("bsCurrentRatio").textContent = formatNum(bs.current_ratio);
  document.getElementById("valDivYield").textContent = formatPct(margins.dividend_yield, true);
  document.getElementById("val52WRange").textContent = `${curr}${price.fifty_two_week_low ?? '-'} - ${curr}${price.fifty_two_week_high ?? '-'}`;

  // Analyst Targets
  document.getElementById("analystRec").textContent = (targets.recommendation_key || "N/A").replace("_", " ").toUpperCase();
  document.getElementById("analystCount").textContent = targets.number_of_analysts ? `(${targets.number_of_analysts} Analysts)` : "";
  document.getElementById("tgtMean").textContent = targets.target_mean_price ? `${curr}${targets.target_mean_price.toFixed(2)}` : "N/A";
  document.getElementById("tgtLow").textContent = targets.target_low_price ? `${curr}${targets.target_low_price.toFixed(2)}` : "N/A";
  document.getElementById("tgtHigh").textContent = targets.target_high_price ? `${curr}${targets.target_high_price.toFixed(2)}` : "N/A";

  // Strengths & Risks
  const strengthsList = document.getElementById("strengthsList");
  strengthsList.innerHTML = "";
  (scoring.strengths || []).forEach(s => {
    const d = document.createElement("div");
    d.className = "flex items-start gap-2";
    d.innerHTML = `<i class="fa-solid fa-check text-emerald-400 mt-0.5"></i><span>${s}</span>`;
    strengthsList.appendChild(d);
  });

  const risksList = document.getElementById("risksList");
  risksList.innerHTML = "";
  (scoring.risks || []).forEach(r => {
    const d = document.createElement("div");
    d.className = "flex items-start gap-2";
    d.innerHTML = `<i class="fa-solid fa-triangle-exclamation text-rose-400 mt-0.5"></i><span>${r}</span>`;
    risksList.appendChild(d);
  });

  // AI Memo Tab Content
  const memoEl = document.getElementById("memoContent");
  if (typeof marked !== "undefined" && data.llm_analysis) {
    memoEl.innerHTML = marked.parse(data.llm_analysis);
  } else {
    memoEl.textContent = data.llm_analysis || "No memo generated.";
  }

  // Render Charts
  renderCharts(cd.historical_financials || {});

  // Reset chat messages
  initChatMessages(prof.name, prof.symbol);
}

// Render Multi-Year Financial Charts with Chart.js
function renderCharts(hist) {
  const inc = hist.income_statement || {};
  const years = Object.keys(inc).reverse(); // oldest to newest

  if (!years.length) return;

  const revData = years.map(y => (inc[y]?.TotalRevenue || 0) / 1e9);
  const netData = years.map(y => (inc[y]?.NetIncome || 0) / 1e9);
  const grossData = years.map(y => (inc[y]?.GrossProfit || 0) / 1e9);
  const opData = years.map(y => (inc[y]?.OperatingIncome || 0) / 1e9);

  // Revenue & Net Income Chart
  const ctx1 = document.getElementById("revChart").getContext("2d");
  if (revChartInstance) revChartInstance.destroy();
  revChartInstance = new Chart(ctx1, {
    type: "bar",
    data: {
      labels: years,
      datasets: [
        {
          label: "Revenue ($B)",
          data: revData,
          backgroundColor: "rgba(6, 182, 212, 0.7)",
          borderColor: "#06b6d4",
          borderWidth: 1.5,
          borderRadius: 6
        },
        {
          label: "Net Income ($B)",
          data: netData,
          backgroundColor: "rgba(16, 185, 129, 0.7)",
          borderColor: "#10b981",
          borderWidth: 1.5,
          borderRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8", font: { size: 11 } } }
      },
      scales: {
        x: { grid: { color: "rgba(51, 65, 85, 0.3)" }, ticks: { color: "#94a3b8" } },
        y: { grid: { color: "rgba(51, 65, 85, 0.3)" }, ticks: { color: "#94a3b8" } }
      }
    }
  });

  // Operating & Gross Profit Chart
  const ctx2 = document.getElementById("profitChart").getContext("2d");
  if (profitChartInstance) profitChartInstance.destroy();
  profitChartInstance = new Chart(ctx2, {
    type: "line",
    data: {
      labels: years,
      datasets: [
        {
          label: "Gross Profit ($B)",
          data: grossData,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.1)",
          tension: 0.3,
          fill: true
        },
        {
          label: "Operating Income ($B)",
          data: opData,
          borderColor: "#10b981",
          backgroundColor: "rgba(16, 185, 129, 0.1)",
          tension: 0.3,
          fill: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#94a3b8", font: { size: 11 } } }
      },
      scales: {
        x: { grid: { color: "rgba(51, 65, 85, 0.3)" }, ticks: { color: "#94a3b8" } },
        y: { grid: { color: "rgba(51, 65, 85, 0.3)" }, ticks: { color: "#94a3b8" } }
      }
    }
  });
}

// Switch UI Tabs
function switchTab(tabId) {
  ["overview", "charts", "memo", "chat"].forEach(id => {
    const panel = document.getElementById(`panel-${id}`);
    const btn = document.getElementById(`tab-${id}`);
    if (id === tabId) {
      panel.classList.remove("hidden");
      btn.classList.add("active-tab");
      btn.classList.remove("text-slate-400");
    } else {
      panel.classList.add("hidden");
      btn.classList.remove("active-tab");
      btn.classList.add("text-slate-400");
    }
  });
}

// Initial Greeting in Chat
function initChatMessages(name, symbol) {
  const container = document.getElementById("chatMessages");
  container.innerHTML = `
    <div class="flex items-start gap-3">
      <div class="w-7 h-7 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-xs shrink-0">
        <i class="fa-solid fa-robot"></i>
      </div>
      <div class="bg-slate-900 border border-slate-800 p-3.5 rounded-2xl text-xs text-slate-200 leading-relaxed max-w-xl">
        Hello! I'm your Financial Research Agent for <strong>${name || symbol}</strong>. Ask me anything about its valuation multiples, debt ratios, margin sustainability, or competitive positioning.
      </div>
    </div>
  `;
}

// Ask Preset Question
function askPreset(text) {
  document.getElementById("chatInput").value = text;
  sendChatMessage();
}

// Send Chat Message
async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const q = input.value.trim();
  if (!q) return;

  const container = document.getElementById("chatMessages");

  // Append user message
  const userDiv = document.createElement("div");
  userDiv.className = "flex items-start gap-3 justify-end";
  userDiv.innerHTML = `
    <div class="bg-cyan-600 text-white p-3.5 rounded-2xl text-xs leading-relaxed max-w-xl shadow-md">
      ${escapeHtml(q)}
    </div>
    <div class="w-7 h-7 rounded-lg bg-slate-800 text-slate-300 flex items-center justify-center text-xs shrink-0">
      <i class="fa-solid fa-user"></i>
    </div>
  `;
  container.appendChild(userDiv);
  input.value = "";
  container.scrollTop = container.scrollHeight;

  // Append thinking bubble
  const thinkDiv = document.createElement("div");
  thinkDiv.className = "flex items-start gap-3";
  thinkDiv.id = "thinkingBubble";
  thinkDiv.innerHTML = `
    <div class="w-7 h-7 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-xs shrink-0">
      <i class="fa-solid fa-robot"></i>
    </div>
    <div class="bg-slate-900 border border-slate-800 p-3.5 rounded-2xl text-xs text-slate-400 flex items-center gap-2">
      <div class="w-3.5 h-3.5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
      <span>Synthesizing fundamental metrics...</span>
    </div>
  `;
  container.appendChild(thinkDiv);
  container.scrollTop = container.scrollHeight;

  try {
    const uid = getUserId();
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: currentSymbol,
        question: q,
        user_id: uid,
        company_data: currentAnalysis?.company_data,
        score_data: currentAnalysis?.scoring
      })
    });

    thinkDiv.remove();

    if (res.status === 403) {
      const err = await res.json();
      openPricingModal();
      alert(err.detail || "Pro Analyst feature. Please upgrade.");
      return;
    }

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to get agent response");
    }

    const data = await res.json();
    const botDiv = document.createElement("div");
    botDiv.className = "flex items-start gap-3";
    
    let formattedText = data.answer;
    if (typeof marked !== "undefined") {
      formattedText = marked.parse(data.answer);
    }

    botDiv.innerHTML = `
      <div class="w-7 h-7 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-xs shrink-0">
        <i class="fa-solid fa-robot"></i>
      </div>
      <div class="bg-slate-900 border border-slate-800 p-3.5 rounded-2xl text-xs text-slate-200 leading-relaxed max-w-xl prose prose-invert">
        ${formattedText}
      </div>
    `;
    container.appendChild(botDiv);
    container.scrollTop = container.scrollHeight;

  } catch (err) {
    if (document.getElementById("thinkingBubble")) {
      document.getElementById("thinkingBubble").remove();
    }
    const errDiv = document.createElement("div");
    errDiv.className = "flex items-start gap-3";
    errDiv.innerHTML = `
      <div class="w-7 h-7 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center text-xs shrink-0">
        <i class="fa-solid fa-triangle-exclamation"></i>
      </div>
      <div class="bg-rose-950/40 border border-rose-800/60 p-3 rounded-xl text-xs text-rose-300">
        ${escapeHtml(err.message)}
      </div>
    `;
    container.appendChild(errDiv);
    container.scrollTop = container.scrollHeight;
  }
}

// Export Report Handler
function exportReport(format) {
  if (!currentSymbol) {
    alert("Please analyze a company first.");
    return;
  }
  window.open(`/api/export?symbol=${encodeURIComponent(currentSymbol)}&format=${format}`, "_blank");
}

// Format Helpers
function formatLargeNum(val, curr = "$") {
  if (val === null || val === undefined || isNaN(val)) return "N/A";
  const abs = Math.abs(val);
  const sign = val < 0 ? "-" : "";
  if (abs >= 1e12) return `${sign}${curr}${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}${curr}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${curr}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${curr}${(abs / 1e3).toFixed(2)}K`;
  return `${sign}${curr}${abs.toFixed(2)}`;
}

function formatNum(val, suffix = "") {
  if (val === null || val === undefined || isNaN(val)) return "N/A";
  return `${Number(val).toFixed(2)}${suffix}`;
}

function formatPct(val, isAlreadyPct = false) {
  if (val === null || val === undefined || isNaN(val)) return "N/A";
  const num = isAlreadyPct ? Number(val) : Number(val) * 100;
  return `${num.toFixed(2)}%`;
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return text.replace(/[&<>"']/g, m => map[m]);
}
