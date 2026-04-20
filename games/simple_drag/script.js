const stage = document.getElementById("stage");
const startZone = document.getElementById("start-zone");
const goalZone = document.getElementById("goal-zone");
const dragBlock = document.getElementById("drag-block");
const statusNode = document.getElementById("status");
const resetButton = document.getElementById("reset-button");

const state = {
  dragging: false,
  won: false,
  x: 0,
  y: 0,
  pointerOffsetX: 0,
  pointerOffsetY: 0,
};

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function setStatus(message) {
  statusNode.textContent = message;
}

function rectInStage(node) {
  const stageRect = stage.getBoundingClientRect();
  const rect = node.getBoundingClientRect();
  return {
    left: rect.left - stageRect.left,
    top: rect.top - stageRect.top,
    width: rect.width,
    height: rect.height,
  };
}

function setBlockPosition(x, y) {
  const maxX = stage.clientWidth - dragBlock.offsetWidth;
  const maxY = stage.clientHeight - dragBlock.offsetHeight;
  state.x = clamp(x, 0, Math.max(maxX, 0));
  state.y = clamp(y, 0, Math.max(maxY, 0));
  dragBlock.style.transform = `translate(${state.x}px, ${state.y}px)`;
}

function centerBlockInZone(zone) {
  const rect = rectInStage(zone);
  const x = rect.left + (rect.width - dragBlock.offsetWidth) / 2;
  const y = rect.top + (rect.height - dragBlock.offsetHeight) / 2;
  setBlockPosition(x, y);
}

function blockCenter() {
  return {
    x: state.x + dragBlock.offsetWidth / 2,
    y: state.y + dragBlock.offsetHeight / 2,
  };
}

function blockCenterInsideGoal() {
  const center = blockCenter();
  const goalRect = rectInStage(goalZone);
  return (
    center.x >= goalRect.left &&
    center.x <= goalRect.left + goalRect.width &&
    center.y >= goalRect.top &&
    center.y <= goalRect.top + goalRect.height
  );
}

function finishDrag(pointerId) {
  if (!state.dragging) {
    return;
  }

  state.dragging = false;
  dragBlock.classList.remove("dragging");
  dragBlock.releasePointerCapture(pointerId);

  if (blockCenterInsideGoal()) {
    state.won = true;
    stage.classList.add("won");
    centerBlockInZone(goalZone);
    setStatus("Goal reached.");
    return;
  }

  centerBlockInZone(startZone);
  setStatus("Missed the goal. Try again.");
}

function resetGame() {
  state.dragging = false;
  state.won = false;
  stage.classList.remove("won");
  dragBlock.classList.remove("dragging");
  centerBlockInZone(startZone);
  setStatus("Drag the block into the goal.");
}

dragBlock.addEventListener("pointerdown", (event) => {
  if (state.won) {
    return;
  }

  const stageRect = stage.getBoundingClientRect();
  state.dragging = true;
  state.pointerOffsetX = event.clientX - stageRect.left - state.x;
  state.pointerOffsetY = event.clientY - stageRect.top - state.y;
  dragBlock.classList.add("dragging");
  dragBlock.setPointerCapture(event.pointerId);
  setStatus("Dragging...");
  event.preventDefault();
});

dragBlock.addEventListener("pointermove", (event) => {
  if (!state.dragging) {
    return;
  }

  const stageRect = stage.getBoundingClientRect();
  const nextX = event.clientX - stageRect.left - state.pointerOffsetX;
  const nextY = event.clientY - stageRect.top - state.pointerOffsetY;
  setBlockPosition(nextX, nextY);
});

dragBlock.addEventListener("pointerup", (event) => {
  finishDrag(event.pointerId);
});

dragBlock.addEventListener("pointercancel", (event) => {
  finishDrag(event.pointerId);
});

resetButton.addEventListener("click", resetGame);

window.addEventListener("resize", () => {
  if (state.dragging) {
    return;
  }
  if (state.won) {
    centerBlockInZone(goalZone);
    return;
  }
  centerBlockInZone(startZone);
});

resetGame();
