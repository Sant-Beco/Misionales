// app/static/js/firma.js
document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("firmaCanvas");
  const ctx = canvas.getContext("2d");
  const formBox = document.getElementById("formBox");

  // === CONFIGURAR CANVAS ===
  function setupCanvas() {
    // Solo inicializa si el formBox es visible
    if (!formBox || !formBox.offsetParent) return;

    const dpi = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = 150; // altura fija

    canvas.width = width * dpi;
    canvas.height = height * dpi;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpi, dpi);

    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#000";
  }

  // Inicializa solo si formBox está visible
  setupCanvas();

  // Re-inicializar en resize si formBox sigue visible
  window.addEventListener("resize", setupCanvas);

  // === DIBUJO ===
  let drawing = false;
  let last = { x: 0, y: 0 };

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return { x: clientX - rect.left, y: clientY - rect.top };
  }

  canvas.addEventListener("mousedown", (e) => { drawing = true; last = getPos(e); });
  canvas.addEventListener("mousemove", (e) => {
    if (!drawing) return;
    const p = getPos(e);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last = p;
  });
  document.addEventListener("mouseup", () => (drawing = false));

  canvas.addEventListener("touchstart", (e) => { drawing = true; last = getPos(e); e.preventDefault(); });
  canvas.addEventListener("touchmove", (e) => {
    if (!drawing) return;
    const p = getPos(e);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last = p;
    e.preventDefault();
  });
  document.addEventListener("touchend", () => (drawing = false));

  // === BOTONES ===
  document.getElementById("limpiarBtn").onclick = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  document.getElementById("guardarBtn").onclick = () => {
    const data = canvas.toDataURL("image/png");
    const img = document.createElement("img");
    img.src = data;
    img.style.maxWidth = "300px";
    const preview = document.getElementById("firmaPreview");
    preview.innerHTML = "";
    preview.appendChild(img);
  };

  // Export para formulario
  window.firmaApp = {
    getDataURL: () => canvas.toDataURL("image/png"),
    refresh: setupCanvas, // permite re-inicializar cuando se muestre el formBox dinámicamente
  };
});





