const winningLines = [
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8],
  [0, 3, 6],
  [1, 4, 7],
  [2, 5, 8],
  [0, 4, 8],
  [2, 4, 6],
];

const statusNode = document.getElementById("status");
const resetButton = document.getElementById("reset-button");
const cells = Array.from(document.querySelectorAll(".cell"));

let boardState = Array(9).fill("");
let currentPlayer = "X";
let gameFinished = false;

function setStatus(message) {
  statusNode.textContent = message;
}

function findWinner() {
  for (const [a, b, c] of winningLines) {
    const value = boardState[a];
    if (value && value === boardState[b] && value === boardState[c]) {
      return value;
    }
  }
  return "";
}

function syncBoard() {
  cells.forEach((cell, index) => {
    const value = boardState[index];
    cell.textContent = value;
    cell.disabled = gameFinished || Boolean(value);
    cell.classList.toggle("x", value === "X");
    cell.classList.toggle("o", value === "O");
  });
}

function resetGame() {
  boardState = Array(9).fill("");
  currentPlayer = "X";
  gameFinished = false;
  syncBoard();
  setStatus("Player X starts.");
}

function handleMove(index) {
  if (gameFinished || boardState[index]) {
    return;
  }

  boardState[index] = currentPlayer;
  const winner = findWinner();

  if (winner) {
    gameFinished = true;
    syncBoard();
    setStatus(`Player ${winner} wins the round.`);
    return;
  }

  if (boardState.every(Boolean)) {
    gameFinished = true;
    syncBoard();
    setStatus("Draw. Clear the board and try again.");
    return;
  }

  currentPlayer = currentPlayer === "X" ? "O" : "X";
  syncBoard();
  setStatus(`Player ${currentPlayer} to move.`);
}

cells.forEach((cell) => {
  cell.addEventListener("click", () => {
    handleMove(Number(cell.dataset.index));
  });
});

resetButton.addEventListener("click", resetGame);

resetGame();
