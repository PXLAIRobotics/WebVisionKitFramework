const rows = 6;
const columns = 7;
const board = [];

const boardNode = document.getElementById("board");
const controlsNode = document.getElementById("column-controls");
const statusNode = document.getElementById("status");
const resetButton = document.getElementById("reset-button");

let currentPlayer = "red";
let gameFinished = false;

function createBoard() {
  board.length = 0;
  for (let row = 0; row < rows; row += 1) {
    board.push(Array(columns).fill(""));
  }
}

function setStatus(message) {
  statusNode.textContent = message;
}

function labelForPlayer(player) {
  return player === "red" ? "Red" : "Yellow";
}

function renderControls() {
  controlsNode.innerHTML = "";
  for (let column = 0; column < columns; column += 1) {
    const button = document.createElement("button");
    button.className = "drop-button";
    button.type = "button";
    button.textContent = String(column + 1);
    button.disabled = gameFinished || board[0][column] !== "";
    button.addEventListener("click", () => handleDrop(column));
    controlsNode.appendChild(button);
  }
}

function renderBoard() {
  boardNode.innerHTML = "";
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const slot = document.createElement("div");
      slot.className = "slot";
      if (board[row][column]) {
        slot.classList.add(board[row][column]);
      }
      boardNode.appendChild(slot);
    }
  }
}

function isWinningDirection(row, column, rowStep, columnStep) {
  const player = board[row][column];
  let streak = 1;

  let nextRow = row + rowStep;
  let nextColumn = column + columnStep;
  while (
    nextRow >= 0 &&
    nextRow < rows &&
    nextColumn >= 0 &&
    nextColumn < columns &&
    board[nextRow][nextColumn] === player
  ) {
    streak += 1;
    nextRow += rowStep;
    nextColumn += columnStep;
  }

  nextRow = row - rowStep;
  nextColumn = column - columnStep;
  while (
    nextRow >= 0 &&
    nextRow < rows &&
    nextColumn >= 0 &&
    nextColumn < columns &&
    board[nextRow][nextColumn] === player
  ) {
    streak += 1;
    nextRow -= rowStep;
    nextColumn -= columnStep;
  }

  return streak >= 4;
}

function hasWinner(row, column) {
  return (
    isWinningDirection(row, column, 0, 1) ||
    isWinningDirection(row, column, 1, 0) ||
    isWinningDirection(row, column, 1, 1) ||
    isWinningDirection(row, column, 1, -1)
  );
}

function handleDrop(column) {
  if (gameFinished || board[0][column] !== "") {
    return;
  }

  let placedRow = -1;
  for (let row = rows - 1; row >= 0; row -= 1) {
    if (board[row][column] === "") {
      board[row][column] = currentPlayer;
      placedRow = row;
      break;
    }
  }

  if (placedRow === -1) {
    return;
  }

  if (hasWinner(placedRow, column)) {
    gameFinished = true;
    renderBoard();
    renderControls();
    setStatus(`${labelForPlayer(currentPlayer)} connects four and wins.`);
    return;
  }

  if (board.every((row) => row.every(Boolean))) {
    gameFinished = true;
    renderBoard();
    renderControls();
    setStatus("Draw. The board is full.");
    return;
  }

  currentPlayer = currentPlayer === "red" ? "yellow" : "red";
  renderBoard();
  renderControls();
  setStatus(`${labelForPlayer(currentPlayer)} to drop.`);
}

function resetGame() {
  createBoard();
  currentPlayer = "red";
  gameFinished = false;
  renderBoard();
  renderControls();
  setStatus("Red opens the match.");
}

resetButton.addEventListener("click", resetGame);

resetGame();
