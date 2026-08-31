const translations = {
  ru: {
    pageTitle: "Rialo Edge Log — проверяемая телеметрия",
    heroEyebrow: "ПРОВЕРЯЕМАЯ IOT-ТЕЛЕМЕТРИЯ",
    heroTitleOne: "ПРОВЕРЯЕМАЯ",
    heroTitleTwo: "ТЕЛЕМЕТРИЯ",
    heroCopy: "Rialo Edge Log показывает, менялась ли телеметрия после публикации. ESP8266 подписывает каждое измерение, локальный шлюз объединяет показания в батчи, а их SHA-256 digest записывается в Rialo. Выберите устройство и запустите проверку — браузер сам сравнит архив с записью в сети.",
    proofStreamTitle: "ЖИВАЯ ЛЕНТА RIALO",
    proofStreamHint: "ПОСЛЕДНИЕ ПОДТВЕРЖДЁННЫЕ ТРАНЗАКЦИИ",
    proofStreamLoading: "ЗАГРУЖАЮ ТРАНЗАКЦИИ…",
    proofStreamEmpty: "ПОДТВЕРЖДЁННЫХ ТРАНЗАКЦИЙ ПОКА НЕТ",
    networkEyebrow: "СОСТОЯНИЕ RIALO DEVNET",
    networkTitle: "Запись доказательств",
    networkLoading: "ЗАПРОС RPC…",
    networkOnline: "RIALO RPC ДОСТУПЕН",
    networkUnavailable: "RIALO RPC НЕДОСТУПЕН",
    networkLow: "МАЛО RLO",
    networkCopy: "Просмотр и проверка бесплатны. RLO списываются с кошелька проекта только при записи digest нового батча.",
    networkBalance: "Баланс отправителя",
    networkAnchors: "Записей за 24 часа",
    networkSpend: "Расчётный расход за сутки",
    networkReserve: "Расчётный запас",
    networkPayer: "Публичный fee payer",
    networkEstimate: "Прогноз основан на интервале последних батчей и комиссии последней транзакции.",
    networkError: "Баланс временно не удалось получить",
    days: "дн.",
    devicesEyebrow: "ЗАРЕГИСТРИРОВАННЫЕ УСТРОЙСТВА",
    devicesTitle: "Устройства",
    refresh: "Обновить архив",
    emptyTitle: "В архиве пока нет устройств",
    emptyCopy: "Первое устройство появится после автоматической публикации батча.",
    deviceOnline: "ONLINE",
    deviceStale: "STALE",
    deviceOffline: "OFFLINE",
    justNow: "только что",
    back: "← Все устройства",
    historyEyebrow: "ИСТОРИЯ УСТРОЙСТВА",
    historyTitle: "История устройства",
    copyLink: "Скопировать ссылку",
    copyDone: "Ссылка скопирована",
    metricBatches: "Подтверждённых батчей",
    metricReadings: "Показаний",
    metricFirst: "Первый sequence",
    metricLast: "Последний sequence",
    tableStatus: "Подтверждение",
    tableTime: "Время",
    tableRange: "Диапазон",
    tableReadings: "Показаний",
    tableAverage: "Средняя °C",
    previousPage: "← Назад",
    nextPage: "Вперёд →",
    pageLabel: "Страница {current} из {total}",
    proofEyebrow: "ИСТОРИЧЕСКОЕ ДОКАЗАТЕЛЬСТВО",
    proofTitle: "Проверка периода",
    chartTitle: "Температура за период",
    checkOne: "1. Браузер проверяет подписи ESP8266",
    checkTwo: "2. Браузер пересчитывает SHA-256",
    checkThree: "3. Браузер читает workflow из Rialo",
    verifyButton: "Проверить независимо",
    downloadProof: "Скачать proof-файл",
    fileEyebrow: "ПРОВЕРКА СКАЧАННОГО ФАЙЛА",
    fileTitle: "Проверить proof-файл",
    fileChoose: "Выберите JSON или перетащите его сюда",
    fileHint: "Подойдёт файл, скачанный из истории любого батча",
    filePrivacy: "Файл проверяется только в браузере и не отправляется на сервер.",
    fileReading: "Читаю файл и проверяю доказательство…",
    fileTooLarge: "Файл слишком большой. Максимальный размер — 5 МБ.",
    fileVerified: "Proof-файл подлинный: подписи, SHA-256 digest и запись в Rialo совпадают.",
    fileFailed: "Proof-файл не прошёл проверку.",
    fileName: "Файл",
    failureReason: "Причина",
    chainEyebrow: "ДОКАЗАТЕЛЬСТВО В СЕТИ",
    chainTitle: "Сверка архива с Rialo Devnet",
    chainConfirmed: "ПОДТВЕРЖДЕНО В RIALO DEVNET",
    archiveDigest: "Digest из архива",
    chainDigest: "Digest из Rialo",
    notChecked: "Ещё не запрошен",
    transactionLabel: "Транзакция",
    openExplorer: "Открыть в RialoScan ↗",
    blockPending: "Блок будет прочитан при проверке",
    rpcNote: "Браузер сам проверяет подписи и читает данные через публичный RPC RialoScan. Готовый результат проверки не берётся с сервера архива.",
    howEyebrow: "КАК РАБОТАЕТ ПРОВЕРКА",
    howTitle: "Проверка не зависит от владельца архива",
    stepOneTitle: "Архив показывает данные",
    stepOneCopy: "Сервер хранит показания и время, чтобы историю можно было открыть в браузере.",
    stepTwoTitle: "Rialo хранит отпечаток",
    stepTwoCopy: "В сети хранится digest батча. Если архив изменить, значения перестанут совпадать.",
    stepThreeTitle: "Портал сравнивает",
    stepThreeCopy: "Если хотя бы одно значение изменится, проверка покажет красное предупреждение.",
    limitsEyebrow: "ГРАНИЦЫ ДОКАЗАТЕЛЬСТВА",
    limitsTitle: "Что доказано — и что нет",
    limitsProves: "ДОКАЗЫВАЕТ",
    provesSignatures: "Показания подписаны ключом зарегистрированного устройства.",
    provesIntegrity: "Опубликованный батч не менялся после записи.",
    provesChain: "Digest совпадает с исторической записью в Rialo.",
    limitsDoesNotProve: "НЕ ДОКАЗЫВАЕТ",
    doesNotProveCalibration: "Датчик был правильно откалиброван и установлен.",
    doesNotProveReality: "Измеренное физическое значение само по себе истинно.",
    doesNotProveCompromise: "Устройство не было скомпрометировано до подписания.",
    footerNote: "Проект проверяет неизменность записей, но не точность самого датчика. Это независимый open-source эксперимент для Rialo Devnet, не связанный с Rialo Labs или Subzero Labs.",
    badResponse: "Некорректный ответ архива",
    archiveUnavailable: "Архив недоступен",
    archiveOnline: "АРХИВ ДОСТУПЕН",
    batches: "батчей",
    view: "Посмотреть →",
    verified: "ПОДТВЕРЖДЕНО",
    fingerprint: "Отпечаток публичного ключа",
    factDevice: "Устройство",
    factReadings: "Показаний",
    factSource: "Источник",
    sourceSimulated: "СИМУЛЯТОР",
    sourcePhysical: "ФИЗИЧЕСКИЙ ДАТЧИК",
    verifying: "Браузер проверяет подписи, пересчитывает digest и читает Rialo Devnet…",
    verifiedHeading: "✓ ДАННЫЕ НЕ ИЗМЕНЯЛИСЬ",
    mismatchHeading: "✕ ОБНАРУЖЕНО НЕСООТВЕТСТВИЕ",
    incompleteHeading: "! ПРОВЕРКА НЕ ЗАВЕРШЕНА",
    verifiedMessage: "Проверка пройдена: подписи устройства, рассчитанный digest и состояние workflow в Rialo совпадают.",
    tamperedMessage: "Архивные данные не совпадают с подписями устройства или исторической записью в Rialo.",
    invalidReceiptMessage: "Сохранённая Rialo receipt неполна или относится к другому батчу.",
    chainUnavailableMessage: "Локальная целостность подтверждена, но сейчас не удалось получить исторические данные из Rialo.",
    browserSignatures: "подписей ESP8266 проверено в браузере",
    browserDigest: "SHA-256 пересчитан из опубликованных показаний",
    browserTransaction: "транзакция найдена в Rialo Devnet",
    browserWorkflow: "workflow содержит тот же digest",
    archiveRecheck: "сервер архива повторно подтвердил proof",
    blockLabel: "Блок",
    recordedAtLabel: "записано",
    feeLabel: "комиссия",
    sequence: "sequence",
    temperature: "температура",
  },
  en: {
    pageTitle: "Rialo Edge Log — Verifiable Telemetry",
    heroEyebrow: "VERIFIABLE IOT TELEMETRY",
    heroTitleOne: "VERIFIABLE",
    heroTitleTwo: "TELEMETRY",
    heroCopy: "Rialo Edge Log shows whether telemetry has changed since publication. An ESP8266 signs each measurement, a local gateway groups readings into batches, and each batch's SHA-256 digest is recorded on Rialo. Select a device and run the check — the browser compares the archive with the on-chain record.",
    proofStreamTitle: "LIVE RIALO STREAM",
    proofStreamHint: "LATEST CONFIRMED TRANSACTIONS",
    proofStreamLoading: "LOADING TRANSACTIONS…",
    proofStreamEmpty: "NO CONFIRMED TRANSACTIONS YET",
    networkEyebrow: "RIALO DEVNET STATUS",
    networkTitle: "Proof anchoring",
    networkLoading: "QUERYING RPC…",
    networkOnline: "RIALO RPC ONLINE",
    networkUnavailable: "RIALO RPC UNAVAILABLE",
    networkLow: "LOW RLO BALANCE",
    networkCopy: "Browsing and verification are free. Only the project wallet spends RLO when a new batch digest is recorded.",
    networkBalance: "Sender balance",
    networkAnchors: "Anchors in 24 hours",
    networkSpend: "Estimated daily spend",
    networkReserve: "Estimated reserve",
    networkPayer: "Public fee payer",
    networkEstimate: "The forecast uses the latest batch interval and the most recent transaction fee.",
    networkError: "Balance is temporarily unavailable",
    days: "days",
    devicesEyebrow: "REGISTERED DEVICES",
    devicesTitle: "Devices",
    refresh: "Refresh archive",
    emptyTitle: "No devices have been published yet",
    emptyCopy: "The first device will appear after a verified batch is published automatically.",
    deviceOnline: "ONLINE",
    deviceStale: "STALE",
    deviceOffline: "OFFLINE",
    justNow: "just now",
    back: "← All devices",
    historyEyebrow: "DEVICE HISTORY",
    historyTitle: "Device history",
    copyLink: "Copy device link",
    copyDone: "Link copied",
    metricBatches: "Verified batches",
    metricReadings: "Readings",
    metricFirst: "First sequence",
    metricLast: "Latest sequence",
    tableStatus: "Verification",
    tableTime: "Recorded at",
    tableRange: "Sequence range",
    tableReadings: "Readings",
    tableAverage: "Average °C",
    previousPage: "← Previous",
    nextPage: "Next →",
    pageLabel: "Page {current} of {total}",
    proofEyebrow: "HISTORICAL PROOF",
    proofTitle: "Period verification",
    chartTitle: "Temperature during this period",
    checkOne: "1. Browser verifies ESP8266 signatures",
    checkTwo: "2. Browser recalculates SHA-256",
    checkThree: "3. Browser reads the Rialo workflow",
    verifyButton: "Verify independently",
    downloadProof: "Download proof file",
    fileEyebrow: "DOWNLOADED FILE CHECK",
    fileTitle: "Verify a proof file",
    fileChoose: "Choose a JSON file or drop it here",
    fileHint: "Use a proof file downloaded from any batch in the archive",
    filePrivacy: "The file is checked in your browser and is not uploaded to the server.",
    fileReading: "Reading the file and verifying its proof…",
    fileTooLarge: "The file is too large. Maximum size: 5 MB.",
    fileVerified: "The proof file is authentic: its signatures, SHA-256 digest, and Rialo record match.",
    fileFailed: "The proof file failed verification.",
    fileName: "File",
    failureReason: "Reason",
    chainEyebrow: "ON-CHAIN EVIDENCE",
    chainTitle: "Archive comparison with Rialo Devnet",
    chainConfirmed: "CONFIRMED ON RIALO DEVNET",
    archiveDigest: "Archive digest",
    chainDigest: "Rialo digest",
    notChecked: "Not requested yet",
    transactionLabel: "Transaction",
    openExplorer: "Open in RialoScan ↗",
    blockPending: "Block data will be read during verification",
    rpcNote: "The browser verifies the signatures and reads the public RialoScan RPC itself. It does not rely on a result supplied by the archive server.",
    howEyebrow: "HOW VERIFICATION WORKS",
    howTitle: "Verification does not rely on the archive operator",
    stepOneTitle: "The archive serves the readings",
    stepOneCopy: "The server stores readings and timestamps so the device history can be opened in a browser.",
    stepTwoTitle: "Rialo stores the fingerprint",
    stepTwoCopy: "Rialo stores the batch digest. If the archive changes, the two values no longer match.",
    stepThreeTitle: "The portal compares both records",
    stepThreeCopy: "If any value differs, verification returns a clear integrity warning.",
    limitsEyebrow: "PROOF BOUNDARIES",
    limitsTitle: "What this proves — and what it does not",
    limitsProves: "PROVES",
    provesSignatures: "Readings were signed by the registered device key.",
    provesIntegrity: "The published batch has not changed since anchoring.",
    provesChain: "The digest matches the historical record on Rialo.",
    limitsDoesNotProve: "DOES NOT PROVE",
    doesNotProveCalibration: "The sensor was calibrated and installed correctly.",
    doesNotProveReality: "The measured physical value itself was true.",
    doesNotProveCompromise: "The device was not compromised before signing.",
    footerNote: "The project verifies record integrity, not sensor accuracy. It is an independent open-source Rialo Devnet experiment and is not affiliated with Rialo Labs or Subzero Labs.",
    badResponse: "The archive returned an invalid response",
    archiveUnavailable: "Archive unavailable",
    archiveOnline: "ARCHIVE ONLINE",
    batches: "batches",
    view: "Inspect →",
    verified: "VERIFIED",
    fingerprint: "Public key fingerprint",
    factDevice: "Device",
    factReadings: "Readings",
    factSource: "Source",
    sourceSimulated: "SIMULATED",
    sourcePhysical: "PHYSICAL SENSOR",
    verifying: "The browser is verifying signatures, recalculating the digest, and reading Rialo Devnet…",
    verifiedHeading: "✓ DATA HAS NOT BEEN ALTERED",
    mismatchHeading: "✕ INTEGRITY MISMATCH DETECTED",
    incompleteHeading: "! VERIFICATION INCOMPLETE",
    verifiedMessage: "Verification passed: the device signatures, calculated digest, and historical Rialo workflow match.",
    tamperedMessage: "The archived data does not match the device signatures or the historical Rialo workflow.",
    invalidReceiptMessage: "The stored Rialo receipt is incomplete or belongs to a different batch.",
    chainUnavailableMessage: "Local integrity is valid, but the historical Rialo state is currently unavailable.",
    browserSignatures: "ESP8266 signatures verified in the browser",
    browserDigest: "SHA-256 recalculated from the published readings",
    browserTransaction: "transaction found on Rialo Devnet",
    browserWorkflow: "workflow contains the same digest",
    archiveRecheck: "archive server independently rechecked the proof",
    blockLabel: "Block",
    recordedAtLabel: "recorded",
    feeLabel: "fee",
    sequence: "sequence",
    temperature: "temperature",
  },
};

let initialPageLoad = true;

function forcePageTop() {
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
  window.scrollTo({ top: 0, left: 0, behavior: "auto" });
}

if ("scrollRestoration" in window.history) {
  window.history.scrollRestoration = "manual";
}
window.addEventListener("pageshow", () => {
  forcePageTop();
  window.requestAnimationFrame(forcePageTop);
  window.setTimeout(forcePageTop, 100);
});

const requestedLanguage = new URLSearchParams(window.location.search).get("lang");
const savedLanguage = window.localStorage.getItem("rialo-edge-log-language");
const state = {
  devices: [],
  batches: [],
  proofStream: [],
  batchPage: 1,
  batchPageSize: 10,
  network: null,
  selectedDeviceId: null,
  selectedBatchId: null,
  selectedBatch: null,
  language: requestedLanguage === "en" || requestedLanguage === "ru"
    ? requestedLanguage
    : savedLanguage === "en" ? "en" : "ru",
};

const elements = {
  proofStreamTrack: document.querySelector("#proof-stream-track"),
  deviceGrid: document.querySelector("#device-grid"),
  deviceEmpty: document.querySelector("#device-empty"),
  history: document.querySelector("#history-section"),
  rows: document.querySelector("#batch-rows"),
  detail: document.querySelector("#detail-panel"),
  detailFacts: document.querySelector("#detail-facts"),
  detailResult: document.querySelector("#detail-result"),
  chart: document.querySelector("#temperature-chart"),
  chartTooltip: document.querySelector("#chart-tooltip"),
  average: document.querySelector("#detail-average"),
  archiveDigest: document.querySelector("#archive-digest"),
  chainDigest: document.querySelector("#chain-digest"),
  digestMatch: document.querySelector("#digest-match"),
  transactionLink: document.querySelector("#transaction-link"),
  transactionValue: document.querySelector("#transaction-value"),
  workflowLink: document.querySelector("#workflow-link"),
  workflowValue: document.querySelector("#workflow-value"),
  programLink: document.querySelector("#program-link"),
  programValue: document.querySelector("#program-value"),
  blockValue: document.querySelector("#block-value"),
  networkStatus: document.querySelector("#network-status"),
  networkBalance: document.querySelector("#network-balance"),
  networkAnchors: document.querySelector("#network-anchors"),
  networkSpend: document.querySelector("#network-spend"),
  networkReserve: document.querySelector("#network-reserve"),
  networkPayer: document.querySelector("#network-payer"),
  networkNote: document.querySelector("#network-note"),
  pagination: document.querySelector("#batch-pagination"),
  previousPage: document.querySelector("#previous-page"),
  nextPage: document.querySelector("#next-page"),
  pageLabel: document.querySelector("#page-label"),
  proofFileInput: document.querySelector("#proof-file-input"),
  proofDropZone: document.querySelector("#proof-drop-zone"),
  proofFileResult: document.querySelector("#proof-file-result"),
};

function t(key) {
  return translations[state.language][key];
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({ error: t("badResponse") }));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function formatTemperature(value) {
  return typeof value === "number" ? `${value.toFixed(3)} °C` : "—";
}

function formatRlo(value, maximumFractionDigits = 6) {
  if (value == null) return "—";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  return `${amount.toLocaleString(state.language === "en" ? "en-US" : "ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits,
  })} RLO`;
}

function formatRelativeTime(value) {
  const timestamp = Date.parse(value || "");
  if (!Number.isFinite(timestamp)) return "—";
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (elapsedSeconds < 60) return t("justNow");
  const formatter = new Intl.RelativeTimeFormat(
    state.language === "en" ? "en-US" : "ru-RU",
    { numeric: "always", style: "short" },
  );
  if (elapsedSeconds < 3600) return formatter.format(-Math.floor(elapsedSeconds / 60), "minute");
  if (elapsedSeconds < 86400) return formatter.format(-Math.floor(elapsedSeconds / 3600), "hour");
  return formatter.format(-Math.floor(elapsedSeconds / 86400), "day");
}

function devicePresence(value) {
  const timestamp = Date.parse(value || "");
  const elapsedMs = Number.isFinite(timestamp) ? Math.max(0, Date.now() - timestamp) : Infinity;
  if (elapsedMs <= 10 * 60 * 1000) return { className: "online", label: t("deviceOnline") };
  if (elapsedMs <= 30 * 60 * 1000) return { className: "stale", label: t("deviceStale") };
  return { className: "offline", label: t("deviceOffline") };
}

function renderNetworkStatus() {
  const network = state.network;
  const badgeText = elements.networkStatus.querySelector("span");
  elements.networkStatus.classList.toggle("warning", !network || network.low_balance);
  badgeText.textContent = !network
    ? t("networkUnavailable")
    : network.low_balance ? t("networkLow") : t("networkOnline");
  elements.networkBalance.textContent = network ? formatRlo(network.balance_rlo, 9) : "—";
  elements.networkAnchors.textContent = network
    ? String(network.anchored_transactions_24h)
    : "—";
  elements.networkSpend.textContent = network
    ? formatRlo(network.estimated_spend_24h_rlo, 9)
    : "—";
  const days = network?.estimated_days_remaining;
  elements.networkReserve.textContent = days != null && Number.isFinite(Number(days))
    ? `${Math.floor(Number(days)).toLocaleString(state.language === "en" ? "en-US" : "ru-RU")} ${t("days")}`
    : "—";
  elements.networkPayer.textContent = network ? short(network.fee_payer, 12) : "—";
  elements.networkPayer.title = network?.fee_payer || "";
  elements.networkNote.textContent = network ? t("networkEstimate") : t("networkError");
}

async function loadNetworkStatus() {
  const badgeText = elements.networkStatus.querySelector("span");
  elements.networkStatus.classList.remove("warning");
  badgeText.textContent = t("networkLoading");
  try {
    state.network = await requestJson("/api/network-status");
  } catch (_error) {
    state.network = null;
  }
  renderNetworkStatus();
}

function formatDate(value) {
  if (!value) return "—";
  const parsed = new Date(value);
  const locale = state.language === "en" ? "en-GB" : "ru-RU";
  return Number.isNaN(parsed.valueOf()) ? value : parsed.toLocaleString(locale);
}

function short(value, size = 8) {
  if (!value) return "—";
  return value.length > size * 2 ? `${value.slice(0, size)}…${value.slice(-size)}` : value;
}

function groupedSignature(value) {
  return String(value || "").match(/.{1,4}/g)?.join(" ") || "—";
}

function proofStreamItem(batch, interactive = true) {
  const item = document.createElement(interactive ? "a" : "span");
  item.className = "proof-stream-item";
  if (interactive) {
    item.href = explorerUrl("transaction", batch.transaction_signature);
    item.target = "_blank";
    item.rel = "noopener";
    item.setAttribute(
      "aria-label",
      `${t("transactionLabel")} ${batch.transaction_signature}, sequence ${batch.first_sequence}–${batch.last_sequence}`,
    );
  }
  const label = document.createElement("b");
  label.textContent = "TX";
  const signature = document.createElement("code");
  signature.textContent = groupedSignature(batch.transaction_signature);
  const sequence = document.createElement("span");
  sequence.textContent = `SEQ ${batch.first_sequence}–${batch.last_sequence}`;
  const recorded = document.createElement("time");
  recorded.dateTime = batch.created_at_utc || "";
  recorded.textContent = formatDate(batch.created_at_utc);
  item.title = batch.transaction_signature;
  item.append(label, signature, sequence, recorded);
  return item;
}

function renderProofStream() {
  elements.proofStreamTrack.replaceChildren();
  if (!state.proofStream.length) {
    const message = document.createElement("span");
    message.className = "proof-stream-message";
    message.textContent = t("proofStreamEmpty");
    elements.proofStreamTrack.append(message);
    return;
  }

  const entries = [...state.proofStream];
  while (entries.length < 4) entries.push(...state.proofStream);
  const visibleEntries = entries.slice(0, Math.max(4, state.proofStream.length));
  const primary = document.createElement("div");
  primary.className = "proof-stream-group";
  const duplicate = document.createElement("div");
  duplicate.className = "proof-stream-group";
  duplicate.setAttribute("aria-hidden", "true");
  for (const batch of visibleEntries) {
    primary.append(proofStreamItem(batch));
    duplicate.append(proofStreamItem(batch, false));
  }
  elements.proofStreamTrack.style.setProperty(
    "--proof-stream-duration",
    `${Math.max(58, visibleEntries.length * 15)}s`,
  );
  elements.proofStreamTrack.append(primary, duplicate);
}

async function loadProofStream() {
  try {
    const payload = await requestJson("/api/batches");
    state.proofStream = (Array.isArray(payload.batches) ? payload.batches : [])
      .filter((batch) => batch.transaction_signature)
      .slice(0, 8);
  } catch (_error) {
    state.proofStream = [];
  }
  renderProofStream();
}

function statusNode(label = t("verified")) {
  const span = document.createElement("span");
  span.className = "status anchored";
  span.textContent = label;
  return span;
}

function setResult(result) {
  const good = result.status === "RIALO_VERIFIED";
  const bad = ["TAMPERED", "INVALID_RECEIPT"].includes(result.status);
  elements.detailResult.className = `result ${good ? "ok" : bad ? "bad" : "warn"}`;
  elements.detailResult.replaceChildren();
  const heading = document.createElement("div");
  heading.className = "result-head";
  heading.textContent = good
    ? t("verifiedHeading")
    : bad ? t("mismatchHeading") : t("incompleteHeading");
  const message = document.createElement("p");
  const localizedMessages = {
    TAMPERED: t("tamperedMessage"),
    INVALID_RECEIPT: t("invalidReceiptMessage"),
    CHAIN_UNAVAILABLE: t("chainUnavailableMessage"),
  };
  message.textContent = good
    ? t("verifiedMessage")
    : localizedMessages[result.status] || result.message;
  elements.detailResult.append(heading, message);
  if (Array.isArray(result.checks) && result.checks.length) {
    const checks = document.createElement("ul");
    checks.className = "result-checks";
    for (const value of result.checks) {
      const item = document.createElement("li");
      item.textContent = value;
      checks.append(item);
    }
    elements.detailResult.append(checks);
  }
  elements.detailResult.hidden = false;
}

function setProofFileResult(result) {
  const good = result.status === "RIALO_VERIFIED";
  const bad = ["TAMPERED", "INVALID_RECEIPT"].includes(result.status);
  elements.proofFileResult.className = `result ${good ? "ok" : bad ? "bad" : "warn"}`;
  elements.proofFileResult.replaceChildren();

  const heading = document.createElement("div");
  heading.className = "result-head";
  heading.textContent = good
    ? t("verifiedHeading")
    : bad ? t("mismatchHeading") : t("incompleteHeading");
  const message = document.createElement("p");
  message.textContent = good ? t("fileVerified") : t("fileFailed");
  elements.proofFileResult.append(heading, message);

  const checks = [];
  if (result.fileName) checks.push(`${t("fileName")}: ${result.fileName}`);
  if (good) {
    checks.push(`${result.signaturesVerified} ${t("browserSignatures")}`);
    checks.push(t("browserDigest"), t("browserTransaction"), t("browserWorkflow"));
  } else if (result.message) {
    checks.push(`${t("failureReason")}: ${result.message}`);
  }
  if (checks.length) {
    const list = document.createElement("ul");
    list.className = "result-checks";
    for (const value of checks) {
      const item = document.createElement("li");
      item.textContent = value;
      list.append(item);
    }
    elements.proofFileResult.append(list);
  }
  elements.proofFileResult.hidden = false;
}

async function verifyProofFile(file) {
  if (!file) return;
  elements.proofFileResult.hidden = false;
  elements.proofFileResult.className = "result warn";
  elements.proofFileResult.textContent = t("fileReading");
  if (file.size > 5 * 1024 * 1024) {
    setProofFileResult({
      status: "INVALID_RECEIPT",
      fileName: file.name,
      message: t("fileTooLarge"),
    });
    return;
  }
  try {
    if (!window.RialoVerifier) throw new Error("Browser verifier was not loaded");
    const bundle = window.RialoVerifier.parseProofBundle(await file.text());
    const result = await window.RialoVerifier.verifyProofBundle(bundle);
    setProofFileResult({ ...result, fileName: file.name });
  } catch (error) {
    setProofFileResult({
      status: error?.code || "CHAIN_UNAVAILABLE",
      fileName: file.name,
      message: error?.message || t("chainUnavailableMessage"),
    });
  } finally {
    elements.proofFileInput.value = "";
  }
}

function setUrl(deviceId = null, batchId = null) {
  const url = new URL(window.location.href);
  url.search = "";
  if (state.language === "en") url.searchParams.set("lang", "en");
  if (deviceId) url.searchParams.set("device", deviceId);
  if (batchId) url.searchParams.set("batch", batchId);
  window.history.replaceState({}, "", url);
}

function deviceCard(device) {
  const button = document.createElement("button");
  button.className = "device-card";
  button.type = "button";
  const header = document.createElement("span");
  header.className = "device-card-head";
  const presence = devicePresence(device.latest_batch_utc);
  const presenceLabel = document.createElement("span");
  presenceLabel.className = `status device-presence ${presence.className}`;
  presenceLabel.textContent = `${presence.label} · ${formatRelativeTime(device.latest_batch_utc)}`;
  header.append(presenceLabel);
  const id = document.createElement("strong");
  id.textContent = device.device_id;
  const temperature = document.createElement("b");
  temperature.textContent = formatTemperature(device.latest_temperature_c);
  const meta = document.createElement("span");
  meta.className = "device-card-meta";
  meta.textContent = `${batchCountLabel(device.batch_count)} · seq ${device.last_sequence} · ${formatDate(device.latest_batch_utc)}`;
  const fingerprint = document.createElement("code");
  fingerprint.textContent = `key ${short(device.public_key_fingerprint, 10)}`;
  button.append(header, id, temperature, meta, fingerprint);
  button.addEventListener("click", () => selectDevice(device.device_id));
  return button;
}

function batchCountLabel(value) {
  if (state.language === "en") return `${value} ${value === 1 ? "batch" : "batches"}`;
  const lastTwo = value % 100;
  const last = value % 10;
  const word = lastTwo >= 11 && lastTwo <= 14
    ? "батчей"
    : last === 1 ? "батч" : last >= 2 && last <= 4 ? "батча" : "батчей";
  return `${value} ${word}`;
}

function renderDevices() {
  elements.deviceGrid.replaceChildren(...state.devices.map(deviceCard));
  elements.deviceEmpty.hidden = state.devices.length !== 0;
}

async function loadDevices() {
  try {
    const payload = await requestJson("/api/devices");
    state.devices = payload.devices;
    renderDevices();
    const parameters = new URLSearchParams(window.location.search);
    const requested = parameters.get("device");
    if (requested && state.devices.some((device) => device.device_id === requested)) {
      await selectDevice(requested, false, false);
      const batch = parameters.get("batch");
      if (batch) await showBatch(batch, false, false);
    }
  } catch (error) {
    elements.deviceEmpty.hidden = false;
    elements.deviceEmpty.replaceChildren();
    const text = document.createElement("strong");
    text.textContent = `${t("archiveUnavailable")}: ${error.message}`;
    elements.deviceEmpty.append(text);
  } finally {
    if (initialPageLoad) {
      initialPageLoad = false;
      forcePageTop();
      window.requestAnimationFrame(forcePageTop);
      window.setTimeout(forcePageTop, 100);
    }
  }
}

function tableCell(label, content, className = "") {
  const cell = document.createElement("td");
  cell.dataset.label = label;
  cell.className = className;
  if (content instanceof Node) cell.append(content);
  else cell.textContent = content;
  return cell;
}

function updateDeviceMetrics() {
  const readings = state.batches.reduce((total, batch) => total + Number(batch.reading_count || 0), 0);
  const first = state.batches.map((batch) => Number(batch.first_sequence)).filter(Number.isFinite);
  const last = state.batches.map((batch) => Number(batch.last_sequence)).filter(Number.isFinite);
  document.querySelector("#metric-batches").textContent = state.batches.length;
  document.querySelector("#metric-readings").textContent = readings;
  document.querySelector("#metric-first").textContent = first.length ? Math.min(...first) : "—";
  document.querySelector("#metric-last").textContent = last.length ? Math.max(...last) : "—";
}

function renderBatches() {
  elements.rows.replaceChildren();
  const pageCount = Math.max(1, Math.ceil(state.batches.length / state.batchPageSize));
  state.batchPage = Math.min(Math.max(state.batchPage, 1), pageCount);
  const pageStart = (state.batchPage - 1) * state.batchPageSize;
  const visibleBatches = state.batches.slice(pageStart, pageStart + state.batchPageSize);
  for (const batch of visibleBatches) {
    const inspect = document.createElement("button");
    inspect.className = "row-button";
    inspect.type = "button";
    inspect.textContent = t("view");
    inspect.addEventListener("click", () => showBatch(batch.batch_id));
    const row = document.createElement("tr");
    row.append(
      tableCell(t("tableStatus"), statusNode()),
      tableCell(t("tableTime"), formatDate(batch.created_at_utc)),
      tableCell(t("tableRange"), `${batch.first_sequence}–${batch.last_sequence}`, "mono"),
      tableCell(t("tableReadings"), String(batch.reading_count), "mono"),
      tableCell(t("tableAverage"), formatTemperature(batch.temperature?.average), "mono"),
      tableCell("", inspect),
    );
    elements.rows.append(row);
  }
  elements.pagination.hidden = pageCount <= 1;
  elements.previousPage.disabled = state.batchPage <= 1;
  elements.nextPage.disabled = state.batchPage >= pageCount;
  elements.pageLabel.textContent = t("pageLabel")
    .replace("{current}", String(state.batchPage))
    .replace("{total}", String(pageCount));
  updateDeviceMetrics();
}

async function selectDevice(deviceId, updateUrl = true, scrollToHistory = true) {
  const device = state.devices.find((item) => item.device_id === deviceId);
  if (!device) return;
  const payload = await requestJson(`/api/devices/${encodeURIComponent(deviceId)}`);
  state.selectedDeviceId = deviceId;
  state.batches = payload.batches;
  state.batchPage = 1;
  document.querySelector("#history-title").textContent = deviceId;
  document.querySelector("#device-fingerprint").textContent = `${t("fingerprint")}: ${device.public_key_fingerprint}`;
  renderBatches();
  elements.history.hidden = false;
  elements.detail.hidden = true;
  if (updateUrl) setUrl(deviceId);
  if (scrollToHistory) {
    elements.history.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function fact(label, value, title = "") {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = value || "—";
  description.title = title || value || "";
  wrapper.append(term, description);
  return wrapper;
}

function explorerUrl(kind, value) {
  const path = kind === "transaction" ? "tx" : "address";
  return `https://devnet.rialoscan.org/${path}/${encodeURIComponent(value)}`;
}

function resetChainEvidence(batch) {
  elements.archiveDigest.textContent = batch.digest || "—";
  elements.archiveDigest.title = batch.digest || "";
  elements.chainDigest.textContent = t("notChecked");
  elements.chainDigest.title = "";
  elements.digestMatch.textContent = "?";
  elements.digestMatch.className = "";

  elements.transactionValue.textContent = batch.transaction_signature || "—";
  elements.transactionValue.title = batch.transaction_signature || "";
  elements.transactionLink.href = batch.transaction_signature
    ? explorerUrl("transaction", batch.transaction_signature)
    : "#";
  elements.workflowValue.textContent = batch.workflow_address || "—";
  elements.workflowValue.title = batch.workflow_address || "";
  elements.workflowLink.href = batch.workflow_address
    ? explorerUrl("address", batch.workflow_address)
    : "#";
  elements.programValue.textContent = batch.program_id || "—";
  elements.programValue.title = batch.program_id || "";
  elements.programLink.href = batch.program_id
    ? explorerUrl("address", batch.program_id)
    : "#";
  elements.blockValue.textContent = t("blockPending");
}

function formatFeeKelvin(value) {
  const kelvin = Number(value);
  if (!Number.isFinite(kelvin)) return null;
  const rlo = kelvin / 1_000_000_000;
  return `${rlo.toLocaleString("en-US", { maximumFractionDigits: 9 })} RLO`;
}

function formatChainTime(value) {
  const timestamp = Number(value);
  if (!Number.isFinite(timestamp)) return null;
  const milliseconds = timestamp > 10_000_000_000 ? timestamp : timestamp * 1000;
  const parsed = new Date(milliseconds);
  if (Number.isNaN(parsed.valueOf())) return null;
  return parsed.toLocaleString(state.language === "en" ? "en-GB" : "ru-RU");
}

function showChainEvidence(result) {
  elements.chainDigest.textContent = result.onchainDigest;
  elements.chainDigest.title = result.onchainDigest;
  const matches = result.localDigest === result.onchainDigest;
  elements.digestMatch.textContent = matches ? "=" : "≠";
  elements.digestMatch.className = matches ? "match" : "mismatch";
  const metadata = [];
  if (result.blockHeight != null) metadata.push(`${t("blockLabel")} ${result.blockHeight}`);
  const recordedAt = formatChainTime(result.blockTime);
  if (recordedAt) metadata.push(`${t("recordedAtLabel")} ${recordedAt}`);
  const fee = formatFeeKelvin(result.feeKelvin);
  if (fee) metadata.push(`${t("feeLabel")} ${fee}`);
  elements.blockValue.textContent = metadata.join(" · ") || t("blockPending");
}

function renderChart(readings) {
  const samples = readings
    .filter((reading) => Number.isFinite(Number(reading.temperature_c)))
    .map((reading) => ({
      sequence: reading.sequence,
      temperature: Number(reading.temperature_c),
    }));
  elements.chart.replaceChildren();
  elements.chartTooltip.hidden = true;
  elements.chart.onpointermove = null;
  elements.chart.onpointerleave = null;
  if (!samples.length) return;

  const width = 640;
  const height = 220;
  const pad = 22;
  const minimum = Math.min(...samples.map((sample) => sample.temperature));
  const maximum = Math.max(...samples.map((sample) => sample.temperature));
  const range = maximum - minimum;
  const points = samples.map((sample, index) => {
    const x = pad + (index / Math.max(samples.length - 1, 1)) * (width - pad * 2);
    const y = range === 0
      ? height / 2
      : height - pad - ((sample.temperature - minimum) / range) * (height - pad * 2);
    return { ...sample, x, y };
  });
  const ns = "http://www.w3.org/2000/svg";

  for (let index = 0; index < 5; index += 1) {
    const line = document.createElementNS(ns, "line");
    const y = pad + index * ((height - pad * 2) / 4);
    line.setAttribute("x1", pad);
    line.setAttribute("x2", width - pad);
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    line.setAttribute("stroke", "#28343b");
    elements.chart.append(line);
  }

  const area = document.createElementNS(ns, "path");
  const path = points.map((point, index) => `${index ? "L" : "M"}${point.x},${point.y}`).join(" ");
  area.setAttribute("d", `${path} L${points.at(-1).x},${height - pad} L${points[0].x},${height - pad} Z`);
  area.setAttribute("fill", "rgba(112,230,196,.08)");
  elements.chart.append(area);

  const polyline = document.createElementNS(ns, "polyline");
  polyline.setAttribute("points", points.map((point) => `${point.x},${point.y}`).join(" "));
  polyline.setAttribute("fill", "none");
  polyline.setAttribute("stroke", "#70e6c4");
  polyline.setAttribute("stroke-width", "3");
  polyline.setAttribute("stroke-linejoin", "round");
  polyline.setAttribute("stroke-linecap", "round");
  elements.chart.append(polyline);

  const circles = points.map((point) => {
    const circle = document.createElementNS(ns, "circle");
    circle.classList.add("chart-point");
    circle.setAttribute("cx", point.x);
    circle.setAttribute("cy", point.y);
    circle.setAttribute("r", "4");
    circle.setAttribute("fill", "#10161a");
    circle.setAttribute("stroke", "#70e6c4");
    circle.setAttribute("stroke-width", "2");
    const title = document.createElementNS(ns, "title");
    title.textContent = `${t("sequence")} ${point.sequence}: ${point.temperature.toFixed(3)} °C`;
    circle.append(title);
    elements.chart.append(circle);
    return circle;
  });

  const guide = document.createElementNS(ns, "line");
  guide.classList.add("chart-guide");
  guide.setAttribute("y1", pad);
  guide.setAttribute("y2", height - pad);
  guide.setAttribute("stroke", "rgba(255,255,255,.22)");
  guide.setAttribute("stroke-dasharray", "4 5");
  guide.hidden = true;
  elements.chart.append(guide);

  elements.chart.onpointermove = (event) => {
    const bounds = elements.chart.getBoundingClientRect();
    const chartX = ((event.clientX - bounds.left) / bounds.width) * width;
    let nearestIndex = 0;
    let nearestDistance = Infinity;
    points.forEach((point, index) => {
      const distance = Math.abs(point.x - chartX);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearestIndex = index;
      }
    });
    const point = points[nearestIndex];
    circles.forEach((circle, index) => {
      circle.setAttribute("r", index === nearestIndex ? "7" : "4");
      circle.setAttribute("fill", index === nearestIndex ? "#70e6c4" : "#10161a");
    });
    guide.hidden = false;
    guide.setAttribute("x1", point.x);
    guide.setAttribute("x2", point.x);
    const cardBounds = elements.chart.parentElement.getBoundingClientRect();
    elements.chartTooltip.textContent = `${t("sequence")}: ${point.sequence} · ${t("temperature")}: ${point.temperature.toFixed(3)} °C`;
    elements.chartTooltip.style.left = `${event.clientX - cardBounds.left}px`;
    elements.chartTooltip.style.top = `${event.clientY - cardBounds.top}px`;
    elements.chartTooltip.hidden = false;
  };
  elements.chart.onpointerleave = () => {
    guide.hidden = true;
    elements.chartTooltip.hidden = true;
    circles.forEach((circle) => {
      circle.setAttribute("r", "4");
      circle.setAttribute("fill", "#10161a");
    });
  };
}

async function showBatch(batchId, updateUrl = true, scrollToDetail = true) {
  const batch = await requestJson(`/api/batches/${encodeURIComponent(batchId)}`);
  if (state.selectedDeviceId && batch.device_id !== state.selectedDeviceId) return;
  state.selectedBatchId = batchId;
  state.selectedBatch = batch;
  document.querySelector("#detail-title").textContent = `${formatDate(batch.created_at_utc)} · seq ${batch.first_sequence}–${batch.last_sequence}`;
  elements.average.textContent = formatTemperature(batch.temperature?.average);
  elements.detailFacts.replaceChildren(
    fact(t("factDevice"), batch.device_id),
    fact("SHA-256 digest", short(batch.digest, 12), batch.digest),
    fact("Rialo transaction", short(batch.transaction_signature, 12), batch.transaction_signature),
    fact("Workflow", short(batch.workflow_address, 12), batch.workflow_address),
    fact(t("factReadings"), String(batch.reading_count)),
    fact(t("factSource"), batch.simulated ? t("sourceSimulated") : t("sourcePhysical")),
  );
  renderChart(batch.readings || []);
  resetChainEvidence(batch);
  elements.detailResult.hidden = true;
  elements.detail.hidden = false;
  if (updateUrl) setUrl(state.selectedDeviceId, batchId);
  if (scrollToDetail) {
    elements.detail.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

async function verifySelected() {
  if (!state.selectedBatchId || !state.selectedBatch?.proof_bundle) return;
  elements.detailResult.hidden = false;
  elements.detailResult.className = "result warn";
  elements.detailResult.textContent = t("verifying");
  const serverCheck = requestJson(
      `/api/batches/${encodeURIComponent(state.selectedBatchId)}/verify`,
      { method: "POST" },
    );
  const browserCheck = Promise.resolve().then(() => {
    if (!window.RialoVerifier) throw new Error("Browser verifier was not loaded");
    return window.RialoVerifier.verifyProofBundle(state.selectedBatch.proof_bundle);
  });
  const [serverResult, browserResult] = await Promise.allSettled([
    serverCheck,
    browserCheck,
  ]);

  if (browserResult.status === "fulfilled") {
    const browser = browserResult.value;
    showChainEvidence(browser);
    const serverVerified = serverResult.status === "fulfilled"
      && serverResult.value.status === "RIALO_VERIFIED";
    const checks = [
      `${browser.signaturesVerified}/${state.selectedBatch.reading_count} ${t("browserSignatures")}`,
      t("browserDigest"),
      t("browserTransaction"),
      t("browserWorkflow"),
    ];
    if (serverVerified) checks.push(t("archiveRecheck"));
    setResult({ ...browser, checks });
    return;
  }

  const error = browserResult.reason;
  const code = error && error.code ? error.code : "CHAIN_UNAVAILABLE";
  if (code === "TAMPERED" || code === "INVALID_RECEIPT") {
    elements.digestMatch.textContent = "≠";
    elements.digestMatch.className = "mismatch";
  }
  setResult({ status: code, message: error?.message || t("chainUnavailableMessage") });
}

function downloadSelectedProof() {
  const bundle = state.selectedBatch?.proof_bundle;
  if (!bundle || !window.RialoVerifier) return;
  const content = window.RialoVerifier.serializeProofBundle(bundle);
  const blob = new Blob([content], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${state.selectedBatch.batch_id}-proof.json`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function applyLanguage(language, remember = true, updateAddress = true) {
  state.language = language;
  document.documentElement.lang = language;
  document.title = t("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  for (const code of ["en", "ru"]) {
    const button = document.querySelector(`#lang-${code}`);
    const active = code === language;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }
  if (remember) window.localStorage.setItem("rialo-edge-log-language", language);
  renderDevices();
  renderBatches();
  renderProofStream();
  renderNetworkStatus();
  if (state.selectedDeviceId) {
    const device = state.devices.find((item) => item.device_id === state.selectedDeviceId);
    document.querySelector("#history-title").textContent = state.selectedDeviceId;
    if (device) {
      document.querySelector("#device-fingerprint").textContent = `${t("fingerprint")}: ${device.public_key_fingerprint}`;
    }
  }
  if (state.selectedBatchId) await showBatch(state.selectedBatchId, false, false);
  if (updateAddress) setUrl(state.selectedDeviceId, state.selectedBatchId);
}

document.querySelector("#lang-en").addEventListener("click", () => applyLanguage("en"));
document.querySelector("#lang-ru").addEventListener("click", () => applyLanguage("ru"));
document.querySelector("#refresh-btn").addEventListener("click", () => {
  loadDevices();
  loadNetworkStatus();
  loadProofStream();
});
elements.previousPage.addEventListener("click", () => {
  state.batchPage -= 1;
  renderBatches();
});
elements.nextPage.addEventListener("click", () => {
  state.batchPage += 1;
  renderBatches();
});
document.querySelector("#back-devices").addEventListener("click", () => {
  state.selectedDeviceId = null;
  state.selectedBatchId = null;
  state.selectedBatch = null;
  elements.history.hidden = true;
  elements.detail.hidden = true;
  setUrl();
  document.querySelector("#devices-title").scrollIntoView({ behavior: "smooth" });
});
document.querySelector("#close-detail").addEventListener("click", () => {
  elements.detail.hidden = true;
  state.selectedBatchId = null;
  state.selectedBatch = null;
  setUrl(state.selectedDeviceId);
});
document.querySelector("#verify-btn").addEventListener("click", verifySelected);
document.querySelector("#download-proof-btn").addEventListener("click", downloadSelectedProof);
elements.proofFileInput.addEventListener("change", () => {
  verifyProofFile(elements.proofFileInput.files?.[0]);
});
elements.proofDropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    elements.proofFileInput.click();
  }
});
for (const eventName of ["dragenter", "dragover"]) {
  elements.proofDropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.proofDropZone.classList.add("dragging");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  elements.proofDropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    elements.proofDropZone.classList.remove("dragging");
  });
}
elements.proofDropZone.addEventListener("drop", (event) => {
  verifyProofFile(event.dataTransfer?.files?.[0]);
});
document.querySelector("#copy-link-btn").addEventListener("click", async (event) => {
  const url = new URL(window.location.href);
  url.search = "";
  if (state.language === "en") url.searchParams.set("lang", "en");
  url.searchParams.set("device", state.selectedDeviceId);
  await navigator.clipboard.writeText(url.toString());
  event.currentTarget.textContent = t("copyDone");
  setTimeout(() => { event.currentTarget.textContent = t("copyLink"); }, 1800);
});

applyLanguage(state.language, false, false);
loadDevices();
loadNetworkStatus();
loadProofStream();
window.setInterval(renderDevices, 60_000);
