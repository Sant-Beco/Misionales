// app/static/js/firma.js
(function () {
  const canvas = document.getElementById("firmaCanvas");
  const ctx = canvas.getContext("2d");

  // === FIX: configurar resolución solo UNA VEZ ===
  function setupCanvas() {
    const dpi = window.devicePixelRatio || 1;

    const width = canvas.clientWidth;
    const height = 200; // altura fija en px

    canvas.width = width * dpi;
    canvas.height = height * dpi;

    ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset transform antes de escalar
    ctx.scale(dpi, dpi);

    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#000";
  }

  setupCanvas();
  window.addEventListener("resize", setupCanvas);

  let drawing = false;
  let last = { x: 0, y: 0 };

  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;

    return {
      x: clientX - rect.left,
      y: clientY - rect.top,
    };
  }

  // Mouse
  canvas.addEventListener("mousedown", (e) => {
    drawing = true;
    last = getPos(e);
  });

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

  // Touch
  canvas.addEventListener("touchstart", (e) => {
    drawing = true;
    last = getPos(e);
    e.preventDefault();
  });

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

  // Limpiar
  document.getElementById("limpiarBtn").onclick = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  // Preview de firma
  document.getElementById("guardarBtn").onclick = () => {
    const data = canvas.toDataURL("image/png");
    const img = document.createElement("img");
    img.src = data;
    img.style.maxWidth = "300px";

    const preview = document.getElementById("firmaPreview");
    preview.innerHTML = "";
    preview.appendChild(img);
  };

  // Export para enviar en formulario
  window.firmaApp = {
    getDataURL: () => canvas.toDataURL("image/png"),
  };
})();


