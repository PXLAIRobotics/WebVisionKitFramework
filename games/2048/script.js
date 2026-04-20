const boardNode = document.getElementById("board");
const scoreNode = document.getElementById("score");
const bestNode = document.getElementById("best");
const statusNode = document.getElementById("status");
const resetButton = document.getElementById("reset-button");

let grid = [];
let score = 0;

function createEmptyGrid() {
  return Array.from({ length: 4 }, () => Array(4).fill(0));
}

function cloneGrid(source) {
  return source.map((row) => [...row]);
}

function randomEmptyCell() {
  const emptyCells = [];
  for (let row = 0; row < 4; row += 1) {
    for (let column = 0; column < 4; column += 1) {
      if (grid[row][column] === 0) {
        emptyCells.push({ row, column });
      }
    }
  }

  if (emptyCells.length === 0) {
    return null;
  }

  return emptyCells[Math.floor(Math.random() * emptyCells.length)];
}

function addRandomTile() {
  const cell = randomEmptyCell();
  if (!cell) {
    return;
  }
  grid[cell.row][cell.column] = Math.random() < 0.9 ? 2 : 4;
}

function renderBoard() {
  boardNode.innerHTML = "";
  let bestTile = 0;

  for (let row = 0; row < 4; row += 1) {
    for (let column = 0; column < 4; column += 1) {
      const value = grid[row][column];
      bestTile = Math.max(bestTile, value);
      const tile = document.createElement("div");
      tile.className = "tile";
      tile.dataset.value = String(value);
      tile.textContent = value === 0 ? "" : String(value);
      boardNode.appendChild(tile);
    }
  }

  scoreNode.textContent = `Score: ${score}`;
  bestNode.textContent = `Best Tile: ${bestTile}`;
}

function compressLine(line) {
  const values = line.filter((value) => value !== 0);
  const result = [];
  let lineScore = 0;

  for (let index = 0; index < values.length; index += 1) {
    if (values[index] === values[index + 1]) {
      const merged = values[index] * 2;
      result.push(merged);
      lineScore += merged;
      index += 1;
    } else {
      result.push(values[index]);
    }
  }

  while (result.length < 4) {
    result.push(0);
  }

  return { line: result, lineScore };
}

function transpose(matrix) {
  return matrix[0].map((_, column) => matrix.map((row) => row[column]));
}

function reverseRows(matrix) {
  return matrix.map((row) => [...row].reverse());
}

function applyMove(direction) {
  let working = cloneGrid(grid);

  if (direction === "up" || direction === "down") {
    working = transpose(working);
  }
  if (direction === "right" || direction === "down") {
    working = reverseRows(working);
  }

  let moveScore = 0;
  working = working.map((row) => {
    const compressed = compressLine(row);
    moveScore += compressed.lineScore;
    return compressed.line;
  });

  if (direction === "right" || direction === "down") {
    working = reverseRows(working);
  }
  if (direction === "up" || direction === "down") {
    working = transpose(working);
  }

  return { nextGrid: working, moveScore };
}

function boardsEqual(left, right) {
  return left.every((row, rowIndex) =>
    row.every((value, columnIndex) => value === right[rowIndex][columnIndex])
  );
}

function hasAvailableMoves() {
  if (grid.some((row) => row.includes(0))) {
    return true;
  }

  for (let row = 0; row < 4; row += 1) {
    for (let column = 0; column < 4; column += 1) {
      const value = grid[row][column];
      if (grid[row + 1] && grid[row + 1][column] === value) {
        return true;
      }
      if (grid[row][column + 1] === value) {
        return true;
      }
    }
  }

  return false;
}

function setStatus(message) {
  statusNode.textContent = message;
}

function resetGame() {
  grid = createEmptyGrid();
  score = 0;
  addRandomTile();
  addRandomTile();
  renderBoard();
  setStatus("Press an arrow key to start.");
}

function handleMove(direction) {
  const { nextGrid, moveScore } = applyMove(direction);
  if (boardsEqual(grid, nextGrid)) {
    return;
  }

  grid = nextGrid;
  score += moveScore;
  addRandomTile();
  renderBoard();

  const bestTile = Math.max(...grid.flat());
  if (bestTile >= 2048) {
    setStatus("2048 reached. Keep climbing if you want.");
    return;
  }

  if (!hasAvailableMoves()) {
    setStatus("No moves left. Start a new board.");
    return;
  }

  setStatus("Board shifted. Find the next merge.");
}

document.addEventListener("keydown", (event) => {
  const direction = {
    ArrowLeft: "left",
    ArrowRight: "right",
    ArrowUp: "up",
    ArrowDown: "down",
  }[event.key];

  if (!direction) {
    return;
  }

  event.preventDefault();
  handleMove(direction);
});

resetButton.addEventListener("click", resetGame);

resetGame();
