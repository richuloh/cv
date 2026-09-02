(() => {
  "use strict";

  const token = new URLSearchParams(window.location.search).get("token") || "";
  const root = document.querySelector("#editor-root");
  const saveButton = document.querySelector("#save-button");
  const exportButton = document.querySelector("#export-button");
  const saveState = document.querySelector("#save-state");
  const progress = document.querySelector("#progress");
  const progressLog = document.querySelector("#progress-log");
  const toast = document.querySelector("#toast");

  let content = null;
  let activeTab = "profile";
  let dirty = false;

  const TARGET_NAME_VARIANTS = new Set(["richul oh", "oh richul", "r oh", "oh r"]);

  function normalizeName(raw) {
    return String(raw || "").toLowerCase().replace(/,/g, " ").split(/\s+/).filter(Boolean).join(" ");
  }

  function isAutoLead(work) {
    const contributors = work.contributors || [];
    if (!contributors.length) return false;
    return TARGET_NAME_VARIANTS.has(normalizeName(contributors[0].name));
  }

  const basicFields = [
    { key: "name", label: "표시 이름" },
    { key: "name_secondary", label: "보조 이름" },
    { key: "role", label: "현재 직책" },
    { key: "affiliation", label: "현재 소속" },
    { key: "tagline", label: "한 줄 소개", wide: true },
    { key: "bio", label: "소개글", multiline: true, wide: true },
    { key: "focus", label: "연구 관심 분야", multiline: true, wide: true, array: true, help: "한 줄에 하나씩 입력" },
  ];

  const sectionSchemas = [
    {
      key: "experience", title: "경력", description: "현재 소속을 가장 위에 두세요.", summary: "title",
      fields: [field("title", "직책"), field("organization", "기관"), field("period", "기간"), field("detail", "세부 내용", true)],
    },
    {
      key: "education", title: "학력", description: "최근 학력부터 입력하세요.", summary: "title",
      fields: [field("title", "학위·과정"), field("organization", "학교"), field("period", "기간"), field("detail", "세부 내용", true)],
    },
    {
      key: "licenses", title: "자격 및 면허", description: "전문의, 면허, 인증 등을 입력합니다.", summary: "title",
      fields: [field("title", "자격·면허명", true), field("period", "유효 기간")],
    },
    {
      key: "projects", title: "연구과제", description: "연구책임자·공동연구자 과제를 관리합니다. 연구비 금액은 공개하지 않으므로 PI 등 필요한 정보만 적으세요.", summary: "title",
      fields: [field("title", "과제명", true, true), field("sponsor", "지원기관"), field("period", "기간"), field("role", "역할"), field("detail", "비고(PI 등)", true)],
    },
    {
      key: "awards", title: "수상", description: "최근 수상부터 입력하세요. 상세 설명은 있으면 항상 함께 표시됩니다.", summary: "title",
      fields: [field("title", "수상명", true), field("organization", "수여기관", true), field("date", "수상 시기"), field("detail", "상세 설명(선택)", true, true)],
    },
    {
      key: "presentations", title: "학술 발표", description: "대표 발표를 최근 순서로 입력하세요. 웹사이트에는 학회·장소가 먼저 보이고, 제목은 펼쳤을 때 나타납니다.", summary: "title",
      fields: [field("title", "발표 제목", true, true), field("venue", "학회·장소", true), field("year", "연도"), field("type", "발표 유형")],
    },
  ];

  function field(key, label, wide = false, multiline = false) {
    return { key, label, wide, multiline };
  }

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}), "X-Editor-Token": token };
    const response = await fetch(path, { ...options, headers });
    let payload;
    try { payload = await response.json(); } catch { payload = { error: await response.text() }; }
    if (!response.ok) {
      const error = new Error(payload.error || `HTTP ${response.status}`);
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  function setDirty(value = true) {
    dirty = value;
    saveState.textContent = value ? "저장되지 않은 변경이 있습니다" : "모든 변경이 저장되었습니다";
    saveState.classList.toggle("is-dirty", value);
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function createField(config, value, onChange) {
    const wrap = element("div", `field${config.wide ? " field-wide" : ""}`);
    const label = element("label", "", config.label);
    if (config.help) label.append(element("span", "field-help", ` · ${config.help}`));
    const control = document.createElement(config.multiline ? "textarea" : "input");
    if (!config.multiline) control.type = "text";
    control.value = config.array ? (Array.isArray(value) ? value.join("\n") : "") : (value || "");
    control.addEventListener("input", () => {
      const next = config.array
        ? control.value.split("\n").map((item) => item.trim()).filter(Boolean)
        : control.value;
      onChange(next);
      setDirty();
      const details = control.closest("details");
      if (details && config.key === details.dataset.summaryKey) {
        details.querySelector(".repeat-summary-text").textContent = next || "새 항목";
      }
    });
    wrap.append(label, control);
    return wrap;
  }

  function section(title, description, actionLabel) {
    const card = element("section", "editor-section");
    const header = element("div", "section-header");
    const copy = element("div");
    copy.append(element("h2", "", title), element("p", "", description));
    header.append(copy);
    if (actionLabel) {
      const button = element("button", "add-button", actionLabel);
      button.type = "button";
      header.append(button);
      card.actionButton = button;
    }
    const body = element("div", "section-body");
    card.append(header, body);
    card.body = body;
    return card;
  }

  function renderProfile() {
    root.replaceChildren();
    const profile = content.profile;
    const identity = section("연구자·연락처", "사이트 전체에서 공통으로 사용하는 정보입니다.");
    const grid = element("div", "field-grid");
    const profileFields = [
      { label: "ORCID iD", get: () => profile.orcid_id, set: (v) => profile.orcid_id = v },
      { label: "이메일", get: () => profile.contact.emails, set: (v) => profile.contact.emails = v, array: true, multiline: true, wide: true, help: "한 줄에 하나씩 입력" },
      { label: "한글 주소", get: () => profile.contact.address_ko, set: (v) => profile.contact.address_ko = v, wide: true },
      { label: "영문 주소", get: () => profile.contact.address_en, set: (v) => profile.contact.address_en = v, wide: true },
      { label: "Google Scholar URL", get: () => profile.links.google_scholar, set: (v) => profile.links.google_scholar = v, wide: true },
    ];
    profileFields.forEach((config) => {
      grid.append(createField(config, config.get(), config.set));
    });
    identity.body.append(grid);

    const note = section("사진 변경", "프로필 사진은 assets/profile.jpg 파일입니다.");
    const text = element("p", "empty-state", "사진을 바꾸려면 새 JPG 사진의 파일명을 profile.jpg로 바꾼 뒤 assets 폴더의 기존 파일과 교체하세요.");
    note.body.append(text);
    root.append(identity, note);
  }

  function renderPublications() {
    root.replaceChildren();
    if (!content.publications) content.publications = {};
    const overrides = content.publications;
    const works = content.orcid_works || [];

    const card = section(
      "논문 저자 표시",
      "목록 맨 앞 저자로 등록된 논문은 자동으로 주저자로 표시됩니다(회색 '자동' 표시). 실제로는 공동 1저자(Co-first)나 공동 교신저자(Co-corresponding)인데 자동으로 표시되지 않은 논문은 체크하세요. 반대로 자동 표시가 잘못된 경우 체크를 해제하면 공저자로 옮길 수 있습니다."
    );
    const list = element("div", "pub-override-list");
    if (!works.length) {
      list.append(element("div", "empty-state", "ORCID 논문 목록을 불러오지 못했습니다. 먼저 저장을 한 번 실행해 ORCID를 동기화하세요."));
    }

    works.forEach((work) => {
      const putCode = String(work.put_code || "");
      if (!putCode) return;
      const auto = isAutoLead(work);
      const override = Object.prototype.hasOwnProperty.call(overrides[putCode] || {}, "lead")
        ? overrides[putCode].lead
        : null;
      const effective = override === null ? auto : override;

      const row = element("div", "pub-override-row");
      const meta = element("div", "pub-override-meta");
      const authorNames = (work.contributors || []).map((c) => c.name).filter(Boolean).join(", ");
      const venue = [work.journal, work.date && work.date.year].filter(Boolean).join(" · ");
      meta.append(element("strong", "", work.title || "(제목 없음)"));
      if (authorNames) meta.append(element("span", "", authorNames));
      if (venue) meta.append(element("span", "", venue));

      const controls = element("label", "pub-override-toggle");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = effective;
      checkbox.addEventListener("change", () => {
        const next = checkbox.checked;
        if (next === auto) {
          if (overrides[putCode]) delete overrides[putCode].lead;
          if (overrides[putCode] && Object.keys(overrides[putCode]).length === 0) delete overrides[putCode];
        } else {
          overrides[putCode] = overrides[putCode] || {};
          overrides[putCode].lead = next;
        }
        setDirty();
      });
      controls.append(
        checkbox,
        element("span", "", "주저자로 표시"),
        element("span", `pub-auto-badge${auto ? " is-auto" : ""}`, auto ? "자동: 주저자" : "자동: 공저자")
      );

      row.append(meta, controls);
      list.append(row);
    });

    card.body.append(list);
    root.append(card);
  }

  function renderLocale(localeKey) {
    root.replaceChildren();
    const cv = content[localeKey];
    const languageName = localeKey === "ko" ? "한글" : "English";
    const basics = section(`${languageName} 기본 정보`, "이름, 현재 소속, 소개 문구를 입력합니다.");
    const grid = element("div", "field-grid");
    basicFields.forEach((config) => {
      grid.append(createField(config, cv[config.key], (value) => cv[config.key] = value));
    });
    basics.body.append(grid);
    root.append(basics);
    sectionSchemas.forEach((schema) => root.append(renderRepeatSection(cv, schema)));
  }

  function renderRepeatSection(cv, schema) {
    if (!Array.isArray(cv[schema.key])) cv[schema.key] = [];
    const card = section(schema.title, schema.description, "+ 항목 추가");
    card.actionButton.addEventListener("click", () => {
      const item = Object.fromEntries(schema.fields.map((config) => [config.key, ""]));
      cv[schema.key].push(item);
      setDirty();
      render();
      const items = root.querySelectorAll(`[data-section="${schema.key}"]`);
      items[items.length - 1]?.setAttribute("open", "");
    });

    const list = element("div", "repeat-list");
    if (!cv[schema.key].length) {
      list.append(element("div", "empty-state", "아직 입력된 항목이 없습니다. ‘항목 추가’를 눌러 시작하세요."));
    }

    cv[schema.key].forEach((item, index) => {
      const details = element("details", "repeat-item");
      details.dataset.section = schema.key;
      details.dataset.summaryKey = schema.summary;
      if (index === 0) details.open = true;

      const summary = document.createElement("summary");
      const title = element("span", "repeat-title");
      title.append(element("span", "repeat-number", String(index + 1)), element("span", "repeat-summary-text", item[schema.summary] || "새 항목"));
      const actions = element("span", "item-actions");
      actions.append(
        itemButton("↑", "위로", () => moveItem(cv[schema.key], index, -1), index === 0),
        itemButton("↓", "아래로", () => moveItem(cv[schema.key], index, 1), index === cv[schema.key].length - 1),
        itemButton("복제", "항목 복제", () => cloneItem(cv[schema.key], index), false, "copy-button"),
        itemButton("삭제", "항목 삭제", () => deleteItem(cv[schema.key], index), false, "danger")
      );
      summary.append(title, actions);

      const fields = element("div", "repeat-fields field-grid");
      schema.fields.forEach((config) => {
        fields.append(createField(config, item[config.key], (value) => item[config.key] = value));
      });
      details.append(summary, fields);
      list.append(details);
    });
    card.body.append(list);
    return card;
  }

  function itemButton(text, title, callback, disabled = false, extraClass = "") {
    const button = element("button", `icon-button ${extraClass}`.trim(), text);
    button.type = "button";
    button.title = title;
    button.disabled = disabled;
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      callback();
    });
    return button;
  }

  function moveItem(items, index, offset) {
    const target = index + offset;
    if (target < 0 || target >= items.length) return;
    [items[index], items[target]] = [items[target], items[index]];
    setDirty();
    render();
  }

  function cloneItem(items, index) {
    items.splice(index + 1, 0, structuredClone(items[index]));
    setDirty();
    render();
  }

  function deleteItem(items, index) {
    const name = items[index].title || "이 항목";
    if (!window.confirm(`‘${name}’을(를) 삭제할까요?`)) return;
    items.splice(index, 1);
    setDirty();
    render();
  }

  function render() {
    document.querySelectorAll(".tab").forEach((button) => button.classList.toggle("is-active", button.dataset.tab === activeTab));
    if (!content) return;
    if (activeTab === "profile") renderProfile();
    else if (activeTab === "publications") renderPublications();
    else renderLocale(activeTab);
  }

  async function save() {
    progress.hidden = false;
    progressLog.textContent = "입력 내용을 저장하고 있습니다…";
    saveButton.disabled = true;
    try {
      const result = await api("/api/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(content),
      });
      progressLog.textContent = result.log || "완료";
      setDirty(false);
      showToast("저장, ORCID 동기화, 웹페이지와 PDF 생성이 완료되었습니다.");
      window.setTimeout(() => { progress.hidden = true; }, 900);
    } catch (error) {
      progress.hidden = true;
      const log = error.payload?.log ? `\n\n${error.payload.log}` : "";
      showToast(`저장 중 문제가 발생했습니다: ${error.message}${log}`, true);
    } finally {
      saveButton.disabled = false;
    }
  }

  function exportBackup() {
    const blob = new Blob([JSON.stringify(content, null, 2) + "\n"], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `richul-oh-cv-backup-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  function showToast(message, isError = false) {
    toast.textContent = message;
    toast.classList.toggle("is-error", isError);
    toast.hidden = false;
    window.setTimeout(() => { toast.hidden = true; }, isError ? 8000 : 4500);
  }

  document.querySelector("#tabs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-tab]");
    if (!button) return;
    activeTab = button.dataset.tab;
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  saveButton.addEventListener("click", save);
  exportButton.addEventListener("click", exportBackup);
  window.addEventListener("beforeunload", (event) => {
    if (!dirty) return;
    event.preventDefault();
    event.returnValue = "";
  });

  api("/api/content")
    .then((payload) => {
      content = payload;
      saveButton.disabled = false;
      exportButton.disabled = false;
      setDirty(false);
      render();
    })
    .catch((error) => {
      root.replaceChildren(element("div", "empty-state", `편집 데이터를 불러오지 못했습니다: ${error.message}`));
      saveState.textContent = "연결 오류";
      showToast("편집기 실행 파일로 다시 열어주세요.", true);
    });
})();
