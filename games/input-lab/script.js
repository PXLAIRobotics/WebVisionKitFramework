const STEP_DEFS = [
  {
    slug: "pointer",
    menuLabel: "1. Pointer",
    title: "Pointer Pad",
    waitingSummary: "Move, press, and release in the pad.",
  },
  {
    slug: "clicks",
    menuLabel: "2. Clicks",
    title: "Click Targets",
    waitingSummary: "Do one single click and one double click.",
  },
  {
    slug: "drag",
    menuLabel: "3. Drag",
    title: "Drag Lane",
    waitingSummary: "Drag the token into the dock.",
  },
  {
    slug: "scroll-panel",
    menuLabel: "4. Scroll Panel",
    title: "Inner Scroll Panel",
    waitingSummary: "Scroll the inner panel through the milestone stack.",
  },
  {
    slug: "page-scroll",
    menuLabel: "5. Page Scroll",
    title: "Page Scroll Runway",
    waitingSummary: "Scroll the document runway downward.",
  },
  {
    slug: "text-entry",
    menuLabel: "6. Text Entry",
    title: "Text Entry",
    waitingSummary: "Fill both the input field and the textarea.",
  },
  {
    slug: "keyboard",
    menuLabel: "7. Keyboard",
    title: "Keyboard Stage",
    waitingSummary: "Focus the stage, hold a key, release it, and send a quick press.",
  },
];

const SCROLL_MILESTONES = [
  "Wheel input started.",
  "The panel is moving.",
  "You crossed the upper band.",
  "The card stack is clearly scrolling now.",
  "You reached the first quarter of the lane.",
  "You passed the fifth marker.",
  "You moved beyond the upper cluster.",
  "You crossed the midpoint.",
  "The lower half is now in view.",
  "You reached the deep scroll band.",
  "You are close to the floor line.",
  "Only a few cards remain below.",
  "You reached the final stretch.",
  "You hit the bottom of the stack.",
];

const REQUIRED_SCROLL_MILESTONES = 5;

const stepRail = document.getElementById("step-rail");
const stepStrip = document.getElementById("step-strip");
const scrollStack = document.getElementById("scroll-stack");

const pointerPad = document.getElementById("pointer-pad");
const pointerCrosshair = document.getElementById("pointer-crosshair");
const pointerPadReadout = document.getElementById("pointer-pad-readout");

const clickTarget = document.getElementById("click-target");
const clickFeedback = document.getElementById("click-feedback");
const clickCountNode = document.getElementById("click-count");
const clickStepStatus = document.getElementById("click-step-status");

const doubleClickTarget = document.getElementById("double-click-target");
const doubleClickFeedback = document.getElementById("double-click-feedback");
const doubleClickCountNode = document.getElementById("double-click-count");

const dragTrack = document.getElementById("drag-track");
const dragPiece = document.getElementById("drag-piece");
const dragDropZone = document.getElementById("drag-dropzone");
const dragDropCopy = document.getElementById("drag-drop-copy");
const dragStepStatus = document.getElementById("drag-step-status");

const scrollFrame = document.getElementById("scroll-frame");
const scrollPanelStatusNode = document.getElementById("scroll-panel-status");

const runwayStatus = document.getElementById("runway-status");
const runwayMarkerTop = document.getElementById("runway-marker-top");
const runwayMarkerMiddle = document.getElementById("runway-marker-middle");
const runwayMarkerBottom = document.getElementById("runway-marker-bottom");
const pageRunwayProof = document.getElementById("page-runway-proof");
const pageRunwayProofCopy = document.getElementById("page-runway-proof-copy");

const textInput = document.getElementById("text-input");
const textArea = document.getElementById("text-area");
const textInputPreview = document.getElementById("text-input-preview");
const textAreaPreview = document.getElementById("text-area-preview");
const inputField = textInput.closest(".field");
const textareaField = textArea.closest(".field");

const keyboardStage = document.getElementById("keyboard-stage");
const keyboardStageStatus = document.getElementById("keyboard-stage-status");
const heldKeysNode = document.getElementById("held-keys");
const lastKeyNode = document.getElementById("last-key");

const resetButton = document.getElementById("reset-button");
const previousButton = document.getElementById("previous-step");
const nextButton = document.getElementById("next-step");
const stepTitle = document.getElementById("step-title");
const stepProgress = document.getElementById("step-progress");
const stepNodes = Array.from(document.querySelectorAll(".wizard-step"));

const timeline = document.getElementById("timeline");
const timelineCount = document.getElementById("timeline-count");

const railRowNodes = new Map();
const railStatusNodes = new Map();
const railSummaryNodes = new Map();
const chipNodes = new Map();
const stepBadgeNodes = new Map(
  Array.from(document.querySelectorAll("[data-step-badge]")).map((node) => [node.dataset.stepBadge, node]),
);
const proofBeaconNodes = new Map(
  Array.from(document.querySelectorAll("[data-step-proof]")).map((node) => [node.dataset.stepProof, node]),
);
const proofCopyNodes = new Map(
  Array.from(document.querySelectorAll("[data-step-proof-copy]")).map((node) => [node.dataset.stepProofCopy, node]),
);

let milestoneNodes = [];

const timelineLimit = 20;
const labStartedAt = performance.now();
const pageInstanceId = `input-lab-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
let suppressTimeline = false;

const state = {
  currentStepIndex: 0,
  pointerPressed: false,
  pointerMoved: false,
  pointerPressedSeen: false,
  pointerReleasedSeen: false,
  lastPointerLogAt: 0,
  lastPointerXPct: 50,
  lastPointerYPct: 50,
  clickCount: 0,
  doubleClickCount: 0,
  drag: {
    active: false,
    success: false,
    offsetX: 0,
    offsetY: 0,
    x: 82,
    y: 110,
  },
  panelScroll: {
    maxMilestones: 0,
    complete: false,
    stage: "top",
    lastBucket: -1,
  },
  pageScroll: {
    maxProgress: 0,
    complete: false,
    stage: "top",
    latchedStage: "top",
    lastBucket: -1,
  },
  heldKeys: new Set(),
  lastQuickKey: "none",
  keyboardInteracted: false,
  keyboardEventCount: 0,
};

function buildWizardUi() {
  stepStrip.innerHTML = "";
  stepRail.innerHTML = "";
  railRowNodes.clear();
  railStatusNodes.clear();
  railSummaryNodes.clear();
  chipNodes.clear();

  STEP_DEFS.forEach((step) => {
    const chip = document.createElement("li");
    chip.className = "step-chip";
    chip.dataset.stepChip = step.slug;
    chip.textContent = step.menuLabel;
    stepStrip.append(chip);
    chipNodes.set(step.slug, chip);

    const row = document.createElement("li");
    row.className = "step-row";
    row.dataset.stepRow = step.slug;
    row.innerHTML = `
      <div class="step-row-top">
        <span class="step-row-label">${step.menuLabel}</span>
        <span class="status-pill waiting">Waiting</span>
      </div>
      <p class="step-row-summary">${step.waitingSummary}</p>
    `;
    stepRail.append(row);
    railRowNodes.set(step.slug, row);
    railStatusNodes.set(step.slug, row.querySelector(".status-pill"));
    railSummaryNodes.set(step.slug, row.querySelector(".step-row-summary"));
  });

  scrollStack.innerHTML = "";
  SCROLL_MILESTONES.forEach((copy, index) => {
    const section = document.createElement("section");
    section.className = "milestone";
    section.innerHTML = `<strong>Milestone ${index + 1}</strong><span>${copy}</span>`;
    scrollStack.append(section);
  });
  milestoneNodes = Array.from(scrollStack.querySelectorAll(".milestone"));
}

function formatElapsed() {
  const elapsedSeconds = (performance.now() - labStartedAt) / 1000;
  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
  const seconds = (elapsedSeconds % 60).toFixed(1).padStart(4, "0");
  return `${minutes}:${seconds}`;
}

function activeStep() {
  return STEP_DEFS[state.currentStepIndex];
}

function activeStepSlug() {
  return activeStep().slug;
}

function isPointerComplete() {
  return state.pointerMoved && state.pointerPressedSeen && state.pointerReleasedSeen;
}

function isClickStepComplete() {
  return state.clickCount > 0 && state.doubleClickCount > 0;
}

function isTextStepComplete() {
  return Boolean(textInput.value.trim()) && Boolean(textArea.value.trim());
}

function isKeyboardComplete() {
  return state.keyboardInteracted && state.keyboardEventCount >= 2 && state.lastQuickKey !== "none";
}

function getCompletionMap() {
  return {
    pointer: isPointerComplete(),
    clicks: isClickStepComplete(),
    drag: state.drag.success,
    "scroll-panel": state.panelScroll.complete,
    "page-scroll": state.pageScroll.complete,
    "text-entry": isTextStepComplete(),
    keyboard: isKeyboardComplete(),
  };
}

function getStepSummary(slug) {
  switch (slug) {
    case "pointer":
      if (isPointerComplete()) {
        return `Moved, pressed, and released at ${state.lastPointerXPct}% x ${state.lastPointerYPct}%.`;
      }
      if (state.pointerPressed) {
        return `Pointer is pressed at ${state.lastPointerXPct}% x ${state.lastPointerYPct}%.`;
      }
      if (state.pointerMoved) {
        return `Pointer is hovering at ${state.lastPointerXPct}% x ${state.lastPointerYPct}%.`;
      }
      return STEP_DEFS[0].waitingSummary;
    case "clicks":
      if (isClickStepComplete()) {
        return `Single click ${state.clickCount}x and double click ${state.doubleClickCount}x recorded.`;
      }
      if (state.clickCount > 0 && state.doubleClickCount === 0) {
        return "Single click complete. Double click is still waiting.";
      }
      if (state.doubleClickCount > 0 && state.clickCount === 0) {
        return "Double click complete. Single click is still waiting.";
      }
      return STEP_DEFS[1].waitingSummary;
    case "drag":
      if (state.drag.success) {
        return "The token is docked successfully.";
      }
      if (state.drag.active) {
        return "Drag is in progress toward the dock.";
      }
      return STEP_DEFS[2].waitingSummary;
    case "scroll-panel":
      if (state.panelScroll.complete) {
        return `Scrolled through ${state.panelScroll.maxMilestones} of ${milestoneNodes.length} milestones.`;
      }
      if (state.panelScroll.maxMilestones > 0) {
        return `Reached ${state.panelScroll.maxMilestones} of ${milestoneNodes.length} milestones.`;
      }
      return STEP_DEFS[3].waitingSummary;
    case "page-scroll":
      if (state.pageScroll.complete) {
        return `Scrolled to the ${state.pageScroll.latchedStage} band.`;
      }
      if (state.pageScroll.stage !== "top") {
        return `Document is currently in the ${state.pageScroll.stage} band.`;
      }
      return STEP_DEFS[4].waitingSummary;
    case "text-entry":
      if (isTextStepComplete()) {
        return "Input and textarea are both filled.";
      }
      if (textInput.value.trim() && !textArea.value.trim()) {
        return "Input is filled. Textarea is still waiting.";
      }
      if (!textInput.value.trim() && textArea.value.trim()) {
        return "Textarea is filled. Input is still waiting.";
      }
      return STEP_DEFS[5].waitingSummary;
    case "keyboard":
      if (isKeyboardComplete()) {
        return `Keyboard proof captured. Last quick key: ${state.lastQuickKey}.`;
      }
      if (state.heldKeys.size > 0) {
        return `Holding ${Array.from(state.heldKeys).join(", ")}.`;
      }
      if (state.keyboardInteracted) {
        return `Keyboard activity detected. Last quick key: ${state.lastQuickKey}.`;
      }
      return STEP_DEFS[6].waitingSummary;
    default:
      return "";
  }
}

function updateStepChips() {
  const completion = getCompletionMap();
  STEP_DEFS.forEach((step, index) => {
    const chip = chipNodes.get(step.slug);
    if (!chip) {
      return;
    }
    chip.classList.toggle("active", index === state.currentStepIndex);
    chip.classList.toggle("complete", Boolean(completion[step.slug]));
  });
}

function updateStepRail() {
  const completion = getCompletionMap();

  STEP_DEFS.forEach((step, index) => {
    const row = railRowNodes.get(step.slug);
    const statusNode = railStatusNodes.get(step.slug);
    const summaryNode = railSummaryNodes.get(step.slug);
    if (!row || !statusNode || !summaryNode) {
      return;
    }

    const isCurrent = index === state.currentStepIndex;
    const isComplete = Boolean(completion[step.slug]);
    const tone = isComplete ? "complete" : isCurrent ? "in-progress" : "waiting";
    const label = isComplete ? "Complete" : isCurrent ? "Active" : "Waiting";

    row.classList.toggle("active", tone === "in-progress");
    row.classList.toggle("complete", tone === "complete");
    statusNode.className = `status-pill ${tone}`;
    statusNode.textContent = label;
    summaryNode.textContent = getStepSummary(step.slug);
  });
}

function publishSnapshot() {
  const completion = getCompletionMap();
  window.__INPUT_LAB_STATE__ = {
    pageInstanceId,
    currentStepIndex: state.currentStepIndex,
    currentStepSlug: activeStepSlug(),
    totalStepCount: STEP_DEFS.length,
    stepMenuLabels: STEP_DEFS.map((step) => step.menuLabel),
    completedProofs: {
      pointer: completion.pointer,
      clicks: completion.clicks,
      drag: completion.drag,
      scrollPanel: completion["scroll-panel"],
      pageScroll: completion["page-scroll"],
      textEntry: completion["text-entry"],
      keyboard: completion.keyboard,
    },
    clickCount: state.clickCount,
    doubleClickCount: state.doubleClickCount,
    dragSuccess: state.drag.success,
    scrollMilestonesReached: state.panelScroll.maxMilestones,
    scrollStage: state.panelScroll.stage,
    pageScrollMaxProgress: Number(state.pageScroll.maxProgress.toFixed(4)),
    pageScrollStage: state.pageScroll.stage,
    pageScrollLatchedStage: state.pageScroll.latchedStage,
    inputValue: textInput.value,
    textareaValue: textArea.value,
    heldKeys: Array.from(state.heldKeys),
    lastQuickKey: state.lastQuickKey,
    keyboardInteracted: state.keyboardInteracted,
  };
}

function updateVisionSignals() {
  const completion = getCompletionMap();

  STEP_DEFS.forEach((step, index) => {
    const isCurrent = index === state.currentStepIndex;
    const isComplete = Boolean(completion[step.slug]);
    const badgeNode = stepBadgeNodes.get(step.slug);
    const proofNode = proofBeaconNodes.get(step.slug);
    const proofCopyNode = proofCopyNodes.get(step.slug);

    if (badgeNode) {
      badgeNode.classList.toggle("active", isCurrent);
      badgeNode.classList.toggle("complete", isComplete);
    }

    if (proofNode) {
      proofNode.classList.toggle("active", isCurrent);
      proofNode.classList.toggle("complete", isComplete);
      proofNode.classList.toggle("waiting", !isComplete);
    }

    if (proofCopyNode) {
      proofCopyNode.textContent = isComplete ? "Proof complete" : "Proof waiting";
    }
  });
}

function syncGlobalSummary() {
  updateVisionSignals();
  updateStepChips();
  updateStepRail();
  publishSnapshot();
}

function logEvent(message) {
  if (suppressTimeline) {
    return;
  }

  const entry = document.createElement("li");
  const time = document.createElement("time");
  time.dateTime = new Date().toISOString();
  time.textContent = formatElapsed();
  entry.append(time, message);
  timeline.prepend(entry);

  while (timeline.children.length > timelineLimit) {
    timeline.removeChild(timeline.lastElementChild);
  }

  const entryCount = timeline.children.length;
  timelineCount.textContent = `${entryCount} entr${entryCount === 1 ? "y" : "ies"}`;
}

function updateWizardChrome() {
  stepNodes.forEach((node, index) => {
    node.classList.toggle("is-active", index === state.currentStepIndex);
  });

  stepTitle.textContent = activeStep().title;
  stepProgress.textContent = `Step ${state.currentStepIndex + 1} of ${STEP_DEFS.length}`;
  previousButton.disabled = state.currentStepIndex === 0;
  nextButton.disabled = state.currentStepIndex === STEP_DEFS.length - 1;
  syncGlobalSummary();
}

function isEditableElement(node) {
  if (!(node instanceof Element)) {
    return false;
  }
  return Boolean(node.closest("input, textarea, [contenteditable=''], [contenteditable='true'], [contenteditable='plaintext-only']"));
}

function setStep(index, source) {
  const nextIndex = Math.max(0, Math.min(STEP_DEFS.length - 1, index));
  if (nextIndex === state.currentStepIndex) {
    return false;
  }

  state.currentStepIndex = nextIndex;
  updateWizardChrome();
  window.scrollTo(0, 0);

  if (activeStepSlug() === "drag") {
    if (state.drag.success) {
      positionDragPieceInDock();
    } else if (!state.drag.active) {
      positionDragPieceAtStart();
    }
  }

  updatePageScrollSummary();

  if (source) {
    logEvent(`Moved to ${STEP_DEFS[nextIndex].menuLabel} via ${source}.`);
  }
  return true;
}

function nextStep(source) {
  return setStep(state.currentStepIndex + 1, source);
}

function previousStep(source) {
  return setStep(state.currentStepIndex - 1, source);
}

function setPointerPosition(clientX, clientY) {
  const rect = pointerPad.getBoundingClientRect();
  const x = Math.max(0, Math.min(rect.width, clientX - rect.left));
  const y = Math.max(0, Math.min(rect.height, clientY - rect.top));
  const xPct = rect.width > 0 ? Math.round((x / rect.width) * 100) : 0;
  const yPct = rect.height > 0 ? Math.round((y / rect.height) * 100) : 0;

  state.lastPointerXPct = xPct;
  state.lastPointerYPct = yPct;
  pointerCrosshair.style.left = `${x}px`;
  pointerCrosshair.style.top = `${y}px`;
  pointerPadReadout.textContent = `Pad position ${xPct}% x ${yPct}%`;
  pointerPad.classList.toggle("pressed", state.pointerPressed);
  syncGlobalSummary();
}

function maybeLogPointerMove(event) {
  const now = performance.now();
  if (now - state.lastPointerLogAt < 280) {
    return;
  }
  state.lastPointerLogAt = now;
  logEvent(`Pointer moved inside the pad at ${Math.round(event.offsetX)} x ${Math.round(event.offsetY)}.`);
}

function updateClickEvidence() {
  const singleDone = state.clickCount > 0;
  const doubleDone = state.doubleClickCount > 0;

  clickCountNode.textContent = String(state.clickCount);
  doubleClickCountNode.textContent = String(state.doubleClickCount);

  clickTarget.classList.toggle("complete", singleDone);
  doubleClickTarget.classList.toggle("complete", doubleDone);

  clickFeedback.textContent = singleDone
    ? `Activated ${state.clickCount} time${state.clickCount === 1 ? "" : "s"}.`
    : "Waiting for the first click.";
  doubleClickFeedback.textContent = doubleDone
    ? `Activated ${state.doubleClickCount} time${state.doubleClickCount === 1 ? "" : "s"}.`
    : "Waiting for the first double click.";

  clickStepStatus.textContent =
    singleDone && doubleDone
      ? "Single click and double click are both complete."
      : "Complete both click targets on this step.";

  syncGlobalSummary();
}

function positionDragPiece(x, y) {
  const width = dragTrack.clientWidth || 620;
  const height = dragTrack.clientHeight || 340;
  const clampedX = Math.max(36, Math.min(width - 36, x));
  const clampedY = Math.max(58, Math.min(height - 36, y));
  state.drag.x = clampedX;
  state.drag.y = clampedY;
  dragPiece.style.left = `${clampedX}px`;
  dragPiece.style.top = `${clampedY}px`;
}

function positionDragPieceAtStart() {
  const height = dragTrack.clientHeight || 340;
  positionDragPiece(110, height / 2);
}

function positionDragPieceInDock() {
  const trackRect = dragTrack.getBoundingClientRect();
  const dropRect = dragDropZone.getBoundingClientRect();
  if (!trackRect.width || !dropRect.width) {
    return;
  }
  const dockCenterX = dropRect.left - trackRect.left + dropRect.width / 2;
  const dockCenterY = dropRect.top - trackRect.top + dropRect.height / 2;
  positionDragPiece(dockCenterX, dockCenterY);
}

function updateDragEvidence() {
  dragDropZone.classList.toggle("success", state.drag.success);

  if (state.drag.success) {
    dragDropCopy.textContent = "Token docked";
    dragStepStatus.textContent = "Drop successful. The token is docked.";
  } else if (state.drag.active) {
    dragDropCopy.textContent = "Release inside the dock";
    dragStepStatus.textContent = "Dragging token toward the dock.";
  } else {
    dragDropCopy.textContent = "Release the token here";
    dragStepStatus.textContent = "Press, move, and release inside the dock.";
  }

  syncGlobalSummary();
}

function resetDragPiece() {
  state.drag.active = false;
  state.drag.success = false;
  dragPiece.classList.remove("dragging");
  positionDragPieceAtStart();
  updateDragEvidence();
}

function getReachedMilestones(progress) {
  if (progress <= 0.02) {
    return 0;
  }
  return Math.max(1, Math.min(milestoneNodes.length, Math.ceil(progress * milestoneNodes.length)));
}

function stageFromProgress(progress) {
  if (progress > 0.88) {
    return "finish";
  }
  if (progress > 0.62) {
    return "deep";
  }
  if (progress > 0.28) {
    return "mid";
  }
  if (progress > 0.03) {
    return "started";
  }
  return "top";
}

function updateScrollEvidence() {
  const maxScroll = Math.max(1, scrollFrame.scrollHeight - scrollFrame.clientHeight);
  const progress = scrollFrame.scrollTop / maxScroll;
  const reachedCount = getReachedMilestones(progress);
  state.panelScroll.maxMilestones = Math.max(state.panelScroll.maxMilestones, reachedCount);
  state.panelScroll.stage = stageFromProgress(progress);

  if (state.panelScroll.maxMilestones >= Math.min(REQUIRED_SCROLL_MILESTONES, milestoneNodes.length)) {
    state.panelScroll.complete = true;
  }

  const visibleCount = state.panelScroll.maxMilestones;
  const activeIndex = visibleCount > 0 ? visibleCount - 1 : -1;

  milestoneNodes.forEach((node, index) => {
    node.classList.toggle("reached", index < visibleCount);
    node.classList.toggle("active", index === activeIndex && index < visibleCount);
  });

  scrollPanelStatusNode.textContent = state.panelScroll.complete
    ? `Inner panel proof is latched with ${visibleCount} of ${milestoneNodes.length} milestones.`
    : visibleCount > 0
    ? `Inner panel reached ${visibleCount} of ${milestoneNodes.length} milestones.`
    : "Wheel the panel to unlock the milestones.";

  const bucket = Math.round(progress * 10);
  if (bucket !== state.panelScroll.lastBucket) {
    state.panelScroll.lastBucket = bucket;
    logEvent(`Scroll panel moved to ${state.panelScroll.stage} (${Math.round(progress * 100)}%).`);
  }

  syncGlobalSummary();
}

function updateRunwayMarkers(progress) {
  runwayMarkerTop.classList.toggle("reached", progress > 0.02);
  runwayMarkerMiddle.classList.toggle("reached", progress > 0.34);
  runwayMarkerBottom.classList.toggle("reached", progress > 0.72);

  runwayMarkerTop.classList.toggle("active", progress <= 0.34);
  runwayMarkerMiddle.classList.toggle("active", progress > 0.34 && progress <= 0.72);
  runwayMarkerBottom.classList.toggle("active", progress > 0.72);
}

function updatePageScrollSummary() {
  const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
  const progress = window.scrollY / maxScroll;
  state.pageScroll.stage = stageFromProgress(progress);

  if (activeStepSlug() === "page-scroll") {
    state.pageScroll.maxProgress = Math.max(state.pageScroll.maxProgress, progress);
    state.pageScroll.latchedStage = stageFromProgress(state.pageScroll.maxProgress);
    if (state.pageScroll.maxProgress > 0.28) {
      state.pageScroll.complete = true;
    }
  }

  updateRunwayMarkers(state.pageScroll.maxProgress);
  pageRunwayProof.classList.toggle("complete", state.pageScroll.complete);
  pageRunwayProof.classList.toggle("waiting", !state.pageScroll.complete);
  pageRunwayProofCopy.textContent = state.pageScroll.complete ? "Proof complete" : "Proof waiting";

  runwayStatus.textContent = state.pageScroll.complete
    ? `Page scroll proof is latched at the ${state.pageScroll.latchedStage} band. Current position: ${state.pageScroll.stage}.`
    : progress > 0.72
    ? "Page scroll marker: bottom band."
    : progress > 0.34
    ? "Page scroll marker: middle band."
    : "Page scroll marker: top band.";

  if (activeStepSlug() === "page-scroll") {
    const bucket = Math.round(progress * 5);
    if (bucket !== state.pageScroll.lastBucket) {
      state.pageScroll.lastBucket = bucket;
      logEvent(`Page scrolled to ${state.pageScroll.stage} (${Math.round(progress * 100)}%).`);
    }
  }

  syncGlobalSummary();
}

function updateTextEvidence() {
  const inputValue = textInput.value.trim();
  const notesValue = textArea.value.trim();

  inputField.classList.toggle("complete", Boolean(inputValue));
  textareaField.classList.toggle("complete", Boolean(notesValue));

  textInputPreview.textContent = inputValue || "Waiting for text input.";
  textAreaPreview.textContent = notesValue || "Waiting for textarea input.";

  syncGlobalSummary();
}

function updateKeyboardEvidence() {
  const heldKeys = Array.from(state.heldKeys).join(", ") || "none";

  heldKeysNode.textContent = heldKeys;
  lastKeyNode.textContent = state.lastQuickKey;

  keyboardStage.classList.toggle("focused", document.activeElement === keyboardStage);
  keyboardStage.classList.toggle("complete", isKeyboardComplete());

  if (state.heldKeys.size > 0) {
    keyboardStageStatus.textContent = `Holding ${heldKeys}.`;
  } else if (state.lastQuickKey !== "none") {
    keyboardStageStatus.textContent = `Last quick key was ${state.lastQuickKey}.`;
  } else if (document.activeElement === keyboardStage) {
    keyboardStageStatus.textContent = "Focused and ready for keys.";
  } else {
    keyboardStageStatus.textContent = "Waiting for keyboard focus.";
  }

  syncGlobalSummary();
}

function startDrag(event) {
  event.preventDefault();
  const pieceRect = dragPiece.getBoundingClientRect();
  state.drag.active = true;
  state.drag.offsetX = event.clientX - pieceRect.left;
  state.drag.offsetY = event.clientY - pieceRect.top;
  dragPiece.classList.add("dragging");
  updateDragEvidence();
  logEvent("Drag started.");
}

function moveDrag(event) {
  if (!state.drag.active) {
    return;
  }

  const rect = dragTrack.getBoundingClientRect();
  positionDragPiece(
    event.clientX - rect.left - state.drag.offsetX + dragPiece.offsetWidth / 2,
    event.clientY - rect.top - state.drag.offsetY + dragPiece.offsetHeight / 2,
  );
}

function finishDrag() {
  if (!state.drag.active) {
    return;
  }

  state.drag.active = false;
  dragPiece.classList.remove("dragging");

  const pieceRect = dragPiece.getBoundingClientRect();
  const dropRect = dragDropZone.getBoundingClientRect();
  const pieceCenterX = pieceRect.left + pieceRect.width / 2;
  const pieceCenterY = pieceRect.top + pieceRect.height / 2;
  const droppedInside =
    pieceCenterX >= dropRect.left &&
    pieceCenterX <= dropRect.right &&
    pieceCenterY >= dropRect.top &&
    pieceCenterY <= dropRect.bottom;

  if (droppedInside) {
    state.drag.success = true;
    positionDragPieceInDock();
    updateDragEvidence();
    logEvent("Drag finished inside the dock.");
    return;
  }

  positionDragPieceAtStart();
  updateDragEvidence();
  dragStepStatus.textContent = "Missed the dock. The token returned to the rail.";
  dragDropCopy.textContent = "Release the token here";
  logEvent("Drag released outside the dock.");
}

function resetLab() {
  suppressTimeline = true;
  state.currentStepIndex = 0;
  state.pointerPressed = false;
  state.pointerMoved = false;
  state.pointerPressedSeen = false;
  state.pointerReleasedSeen = false;
  state.lastPointerLogAt = 0;
  state.lastPointerXPct = 50;
  state.lastPointerYPct = 50;
  state.clickCount = 0;
  state.doubleClickCount = 0;
  state.drag.active = false;
  state.drag.success = false;
  state.drag.offsetX = 0;
  state.drag.offsetY = 0;
  state.panelScroll.maxMilestones = 0;
  state.panelScroll.complete = false;
  state.panelScroll.stage = "top";
  state.panelScroll.lastBucket = -1;
  state.pageScroll.maxProgress = 0;
  state.pageScroll.complete = false;
  state.pageScroll.stage = "top";
  state.pageScroll.latchedStage = "top";
  state.pageScroll.lastBucket = -1;
  state.heldKeys.clear();
  state.lastQuickKey = "none";
  state.keyboardInteracted = false;
  state.keyboardEventCount = 0;

  pointerCrosshair.style.left = "50%";
  pointerCrosshair.style.top = "50%";
  pointerPadReadout.textContent = "Awaiting pointer input.";
  pointerPad.classList.remove("pressed");

  clickStepStatus.textContent = "Complete both click targets on this step.";
  clickTarget.classList.remove("complete");
  doubleClickTarget.classList.remove("complete");
  clickFeedback.textContent = "Waiting for the first click.";
  doubleClickFeedback.textContent = "Waiting for the first double click.";
  clickCountNode.textContent = "0";
  doubleClickCountNode.textContent = "0";

  textInput.value = "";
  textArea.value = "";

  if (document.activeElement instanceof HTMLElement) {
    document.activeElement.blur();
  }

  timeline.innerHTML = "";
  timelineCount.textContent = "0 entries";

  scrollFrame.scrollTop = 0;
  updateScrollEvidence();
  window.scrollTo(0, 0);
  updatePageScrollSummary();
  updateTextEvidence();
  updateKeyboardEvidence();
  resetDragPiece();
  updateWizardChrome();
  suppressTimeline = false;
  logEvent("Lab reset. Ready for the next interaction run.");
}

pointerPad.addEventListener("mousemove", (event) => {
  state.pointerMoved = true;
  setPointerPosition(event.clientX, event.clientY);
  maybeLogPointerMove(event);
});

pointerPad.addEventListener("mousedown", (event) => {
  state.pointerPressed = true;
  state.pointerMoved = true;
  state.pointerPressedSeen = true;
  pointerPad.classList.add("pressed");
  setPointerPosition(event.clientX, event.clientY);
  logEvent("Pointer pad received mouse down.");
});

window.addEventListener("mouseup", (event) => {
  if (state.pointerPressed) {
    state.pointerPressed = false;
    state.pointerReleasedSeen = true;
    pointerPad.classList.remove("pressed");
    if (event.target instanceof Node && pointerPad.contains(event.target)) {
      setPointerPosition(event.clientX, event.clientY);
    } else {
      syncGlobalSummary();
    }
    logEvent("Pointer pad received mouse up.");
  }
  finishDrag();
});

clickTarget.addEventListener("click", () => {
  state.clickCount += 1;
  updateClickEvidence();
  logEvent(`Single click target activated (${state.clickCount}).`);
});

doubleClickTarget.addEventListener("dblclick", () => {
  state.doubleClickCount += 1;
  updateClickEvidence();
  logEvent(`Double click target activated (${state.doubleClickCount}).`);
});

dragPiece.addEventListener("mousedown", startDrag);
window.addEventListener("mousemove", moveDrag);

scrollFrame.addEventListener("scroll", updateScrollEvidence);
window.addEventListener("scroll", updatePageScrollSummary, { passive: true });

textInput.addEventListener("input", () => {
  updateTextEvidence();
  logEvent(`Input field changed to "${textInput.value}".`);
});

textArea.addEventListener("input", () => {
  updateTextEvidence();
  logEvent(`Text area changed to "${textArea.value}".`);
});

keyboardStage.addEventListener("click", () => {
  keyboardStage.focus();
});

keyboardStage.addEventListener("focus", () => {
  state.keyboardInteracted = true;
  updateKeyboardEvidence();
  logEvent("Keyboard stage focused.");
});

keyboardStage.addEventListener("blur", () => {
  updateKeyboardEvidence();
  logEvent("Keyboard stage blurred.");
});

keyboardStage.addEventListener("keydown", (event) => {
  if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", " ", "Enter"].includes(event.key)) {
    event.preventDefault();
  }

  if (!event.repeat) {
    state.heldKeys.add(event.key);
    state.keyboardEventCount += 1;
  }
  state.keyboardInteracted = true;
  updateKeyboardEvidence();
  logEvent(`Key down: ${event.key}.`);
});

keyboardStage.addEventListener("keyup", (event) => {
  state.heldKeys.delete(event.key);
  state.lastQuickKey = event.key;
  state.keyboardInteracted = true;
  state.keyboardEventCount += 1;
  updateKeyboardEvidence();
  logEvent(`Key up: ${event.key}.`);
});

window.addEventListener(
  "keydown",
  (event) => {
    if (event.defaultPrevented) {
      return;
    }
    if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) {
      return;
    }
    if (isEditableElement(document.activeElement)) {
      return;
    }

    const key = String(event.key || "").toLowerCase();
    if (key === "n") {
      event.preventDefault();
      event.stopPropagation();
      nextStep("the n key");
    } else if (key === "p") {
      event.preventDefault();
      event.stopPropagation();
      previousStep("the p key");
    }
  },
  true,
);

previousButton.addEventListener("click", () => {
  previousStep("the Previous button");
});

nextButton.addEventListener("click", () => {
  nextStep("the Next button");
});

resetButton.addEventListener("click", resetLab);

window.addEventListener("resize", () => {
  if (state.drag.success) {
    positionDragPieceInDock();
  } else if (!state.drag.active) {
    positionDragPieceAtStart();
  }
  syncGlobalSummary();
});

buildWizardUi();
resetLab();
