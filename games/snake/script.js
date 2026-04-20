const canvas = document.getElementById("game-canvas");
const context = canvas.getContext("2d");
const scoreNode = document.getElementById("score");
const statusNode = document.getElementById("status");
const startButton = document.getElementById("start-button");
const resetButton = document.getElementById("reset-button");

const tileSize = 24;
const tileCount = canvas.width / tileSize;

let snake = [];
let direction = { x: 1, y: 0 };
let pendingDirection = { x: 1, y: 0 };
let food = { x: 10, y: 10 };
let score = 0;
let timerId = null;
let gameRunning = false;

function randomCell() {
  return Math.floor(Math.random() * tileCount);
}

function updateStatus(message) {
  statusNode.textContent = message;
}

function updateScore() {
  scoreNode.textContent = `Score: ${score}`;
}

function placeFood() {
  do {
    food = { x: randomCell(), y: randomCell() };
  } while (snake.some((segment) => segment.x === food.x && segment.y === food.y));
}

function resetGame() {
  snake = [
    { x: 8, y: 10 },
    { x: 7, y: 10 },
    { x: 6, y: 10 },
  ];
  direction = { x: 1, y: 0 };
  pendingDirection = { x: 1, y: 0 };
  score = 0;
  updateScore();
  placeFood();
  updateStatus("Press Start to begin.");
  gameRunning = false;
  if (timerId !== null) {
    clearInterval(timerId);
    timerId = null;
  }
  draw();
}

function drawRoundedRect(x, y, size, color) {
  context.fillStyle = color;
  context.beginPath();
  context.roundRect(x + 2, y + 2, size - 4, size - 4, 8);
  context.fill();
}

function draw() {
  context.clearRect(0, 0, canvas.width, canvas.height);
  drawRoundedRect(food.x * tileSize, food.y * tileSize, tileSize, "#f76c5e");

  snake.forEach((segment, index) => {
    const color = index === 0 ? "#1a6d3a" : "#2f9d5b";
    drawRoundedRect(segment.x * tileSize, segment.y * tileSize, tileSize, color);
  });
}

function step() {
  direction = pendingDirection;
  const head = {
    x: snake[0].x + direction.x,
    y: snake[0].y + direction.y,
  };

  const hitWall =
    head.x < 0 ||
    head.y < 0 ||
    head.x >= tileCount ||
    head.y >= tileCount;
  const hitSelf = snake.some((segment) => segment.x === head.x && segment.y === head.y);

  if (hitWall || hitSelf) {
    updateStatus("Crash. Hit Reset to play again.");
    gameRunning = false;
    clearInterval(timerId);
    timerId = null;
    return;
  }

  snake.unshift(head);
  if (head.x === food.x && head.y === food.y) {
    score += 1;
    updateScore();
    updateStatus("Snack collected. Keep moving.");
    placeFood();
  } else {
    snake.pop();
  }

  draw();
}

function startGame() {
  if (gameRunning) {
    return;
  }

  gameRunning = true;
  updateStatus("Use the arrow keys to steer.");
  timerId = window.setInterval(step, 120);
}

document.addEventListener("keydown", (event) => {
  const next = {
    ArrowUp: { x: 0, y: -1 },
    ArrowDown: { x: 0, y: 1 },
    ArrowLeft: { x: -1, y: 0 },
    ArrowRight: { x: 1, y: 0 },
  }[event.key];

  if (!next) {
    return;
  }

  event.preventDefault();
  if (next.x === -direction.x && next.y === -direction.y) {
    return;
  }
  pendingDirection = next;
});

startButton.addEventListener("click", startGame);
resetButton.addEventListener("click", resetGame);

resetGame();
