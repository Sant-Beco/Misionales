// app/static/js/firma.js
document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("firmaCanvas");
  const ctx = canvas.getContext("2d");
  const formBox = document.getElementById("formBox");

  let drawing = false;
  let last = { x: 0, y: 0 };
  let hasRealStroke = false; // evitar firmas vacías

  const FIXED_HEIGHT = 160; // altura fija para estabilidad en PDF

  // ======================================================
  // CONFIGURACIÓN DE CANVAS (con preservación del dibujo)
  // ======================================================
  function setupCanvas() {
    if (!formBox || !formBox.offsetParent) return;

    const dpi = window.devicePixelRatio || 1;

    // Guardar la firma antes de redimensionar
    let previous = null;
    if (canvas.width > 0 && canvas.height > 0) {
      previous = new Image();
      previous.src = canvas.toDataURL("image/png");
    }

    const width = canvas.clientWidth;

    canvas.width = width * dpi;
    canvas.height = FIXED_HEIGHT * dpi;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpi, dpi);

    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.strokeStyle = "#000";

    // Si había firma, restaurarla
    if (previous) {
      previous.onload = () => ctx.drawImage(previous, 0, 0, canvas.width / dpi, FIXED_HEIGHT);
    }
  }

  setupCanvas();
  window.addEventListener("resize", setupCanvas);

  // ======================================================
  // COORDENADAS
  // ======================================================
  function getPos(e) {
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return { x: clientX - rect.left, y: clientY - rect.top };
  }

  // ======================================================
  // EVENTOS DE DIBUJO
  // ======================================================
  function startDraw(e) {
    drawing = true;
    last = getPos(e);
  }

  function moveDraw(e) {
    if (!drawing) return;

    const p = getPos(e);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();

    last = p;
    hasRealStroke = true; // La firma es real
  }

  function endDraw() {
    drawing = false;
  }

  // Mouse
  canvas.addEventListener("mousedown", startDraw);
  canvas.addEventListener("mousemove", moveDraw);
  document.addEventListener("mouseup", endDraw);

  // Touch
  canvas.addEventListener("touchstart", (e) => { startDraw(e); e.preventDefault(); });
  canvas.addEventListener("touchmove", (e) => { moveDraw(e); e.preventDefault(); });
  document.addEventListener("touchend", endDraw);

  // ======================================================
  // BOTONES
  // ======================================================
  document.getElementById("limpiarBtn").onclick = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    hasRealStroke = false;
    document.getElementById("firmaPreview").innerHTML = "";
  };

  document.getElementById("guardarBtn").onclick = () => {
    if (!hasRealStroke) {
      alert("Debes realizar una firma válida.");
      return;
    }

    const data = canvas.toDataURL("image/png");
    const img = document.createElement("img");
    img.src = data;
    img.style.maxWidth = "300px";

    const preview = document.getElementById("firmaPreview");
    preview.innerHTML = "";
    preview.appendChild(img);
  };

  // ======================================================
  // API PARA FORMULARIO
  // ======================================================
  window.firmaApp = {
    getDataURL: () => {
    if (!hasRealStroke) return "";
    return canvas.toDataURL("image/png");
  },

    refresh: setupCanvas,
    isEmpty: () => !hasRealStroke
  };
});

