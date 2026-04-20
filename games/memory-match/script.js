const symbols = ["◆", "◆", "●", "●", "▲", "▲", "■", "■", "✦", "✦", "☀", "☀"];

const boardNode = document.getElementById("board");
const movesNode = document.getElementById("moves");
const matchesNode = document.getElementById("matches");
const statusNode = document.getElementById("status");
const resetButton = document.getElementById("reset-button");

let deck = [];
let revealedIndexes = [];
let moves = 0;
let matches = 0;
let lockBoard = false;

function shuffle(values) {
  const copy = [...values];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[swapIndex]] = [copy[swapIndex], copy[index]];
  }
  return copy;
}

function updateStats() {
  movesNode.textContent = `Moves: ${moves}`;
  matchesNode.textContent = `Matches: ${matches} / 6`;
}

function updateStatus(message) {
  statusNode.textContent = message;
}

function renderBoard() {
  boardNode.innerHTML = "";
  deck.forEach((card, index) => {
    const button = document.createElement("button");
    button.className = "card";
    button.type = "button";
    button.textContent = card.matched || revealedIndexes.includes(index) ? card.symbol : "?";
    if (card.matched) {
      button.classList.add("matched");
      button.disabled = true;
    } else if (revealedIndexes.includes(index)) {
      button.classList.add("revealed");
    }
    button.addEventListener("click", () => revealCard(index));
    boardNode.appendChild(button);
  });
}

function resetGame() {
  deck = shuffle(symbols).map((symbol) => ({ symbol, matched: false }));
  revealedIndexes = [];
  moves = 0;
  matches = 0;
  lockBoard = false;
  updateStats();
  updateStatus("Turn over any two cards to begin.");
  renderBoard();
}

function revealCard(index) {
  if (lockBoard || revealedIndexes.includes(index) || deck[index].matched) {
    return;
  }

  revealedIndexes.push(index);
  renderBoard();

  if (revealedIndexes.length < 2) {
    updateStatus("Pick one more card.");
    return;
  }

  moves += 1;
  updateStats();
  lockBoard = true;

  const [firstIndex, secondIndex] = revealedIndexes;
  const isMatch = deck[firstIndex].symbol === deck[secondIndex].symbol;

  if (isMatch) {
    deck[firstIndex].matched = true;
    deck[secondIndex].matched = true;
    matches += 1;
    revealedIndexes = [];
    lockBoard = false;
    updateStats();
    renderBoard();
    updateStatus(matches === 6 ? "Board cleared. Shuffle for another round." : "Pair found. Keep going.");
    return;
  }

  updateStatus("No match. Watch closely.");
  window.setTimeout(() => {
    revealedIndexes = [];
    lockBoard = false;
    renderBoard();
    updateStatus("Try a new pair.");
  }, 700);
}

resetButton.addEventListener("click", resetGame);

resetGame();
